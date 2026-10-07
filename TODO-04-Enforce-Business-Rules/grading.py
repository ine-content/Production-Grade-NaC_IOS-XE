#!/usr/bin/env python3

"""
Production-Grade Network as Code for IOS-XE - Coaching-Style Grader (Rich terminal UI)

This grader validates the course one TODO at a time, always starting from
TODO 01, and stops at the first incomplete one. Earlier TODOs are already
solved for you in each lab folder, but they are re-checked live on every run,
so you always see current proof that nothing earlier broke.

TODO 01-04 never touch a router: they run entirely on this machine, using
the nac-validate tool from the netascode project. Every check that mutates
data (to prove your schema or rules really catch bad input) does so in a
disposable temporary copy - your real files in data/ are never modified.

Requires: Python 3.10+, and the packages in requirements.txt
(pip install -r requirements.txt).
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from rich.align import Align
from rich.bar import Bar
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DEVICES_FILE = DATA_DIR / "devices.nac.yaml"
COMMON_FILE = DATA_DIR / "common.nac.yaml"
SCHEMA_FILE = ROOT / ".schema.yaml"
RULES_DIR = ROOT / "rules"

console = Console(markup=False, highlight=False)

BOLD = "bold "
DIM = "dim"
RED = "red"
GREEN = "green"
YELLOW = "yellow"
CYAN = "cyan"

INTERACTIVE_MODE = os.environ.get("CAPSTONE_INTERACTIVE", "1") != "0"

COURSE_TOTAL_TODOS = 12
TOTAL_TODOS = 4

# -----------------------------------------------------------------------------
# Lab facts (the "business requirements" every check is derived from)
# -----------------------------------------------------------------------------

EXPECTED_DEVICES = {
    "R10": {"host": "10.10.10.10", "loopback0": "10.255.0.10"},
    "R11": {"host": "10.10.10.11", "loopback0": "10.255.0.11"},
    "R12": {"host": "10.10.10.12", "loopback0": "10.255.0.12"},
}

SHARED_SYSTEM = {
    "ip_routing": True,
    "ip_domain_name": "meridian.local",
    "ip_domain_lookup": False,
}

FORBIDDEN_KEYS = {"password", "secret", "username", "enable_secret", "token", "community"}

TODO_NAMES = {
    1: "Author the Network Data Model",
    2: "Layer Shared Settings Across Files",
    3: "Validate Structure with a Schema",
    4: "Enforce Business Rules",
    5: "Connect the Data Model to Terraform",
    6: "First Push to R10-R12",
    7: "Static Routes and ACLs",
    8: "OSPF Across the Branch Routers",
    9: "BGP Peering",
    10: "Detect and Reconcile Drift",
    11: "Verify Live State with nac-test",
    12: "Gate the Pipeline and Emit an Audit Log",
}

SUCCESS_MESSAGES = {
    1: "data/devices.nac.yaml describes R10, R11 and R12 exactly as the business requirements say.",
    2: "Shared settings live in data/common.nac.yaml and merge cleanly into every device.",
    3: "Your schema accepts the real data and rejects every kind of bad input we tried.",
    4: "Your semantic rules catch hostname mismatches and duplicate addresses.",
}

FAIL_MESSAGES = {
    1: "The pipeline cannot continue because the network data model has not been authored correctly yet.",
    2: "The pipeline cannot continue because the shared settings have not been layered into their own file correctly yet.",
    3: "The pipeline cannot continue because the schema does not yet accept good data and reject bad data.",
    4: "The pipeline cannot continue because the semantic rules do not yet catch the business-rule violations.",
}

PROBLEMS = {}
EXPECTED = {}
HINTS = {}
SOLUTIONS = {}

PROBLEMS[1] = (
    "data/devices.nac.yaml is missing, is not valid YAML, or does not match the required\n"
    "devices. Each of R10, R11 and R12 needs its name, management host, hostname, and a\n"
    "Loopback0 router-ID address. No credentials may appear anywhere in the file."
)
EXPECTED[1] = (
    "iosxe.devices - a list of exactly 3 devices:\n"
    "  R10  host 10.10.10.10  hostname R10  Loopback0 10.255.0.10/32  description ROUTER-ID\n"
    "  R11  host 10.10.10.11  hostname R11  Loopback0 10.255.0.11/32  description ROUTER-ID\n"
    "  R12  host 10.10.10.12  hostname R12  Loopback0 10.255.0.12/32  description ROUTER-ID\n"
    "A /32 loopback has address_mask 255.255.255.255."
)
HINTS[1] = (
    "Follow the shape in TASK.md: iosxe -> devices (a list) -> each device has name, host, and a\n"
    "configuration block holding system.hostname and interfaces.loopbacks (a list again). In YAML a\n"
    "list item starts with '- ' and nesting is done with 2 spaces - never tabs."
)
SOLUTIONS[1] = """iosxe:
  devices:
    - name: R10
      host: 10.10.10.10
      configuration:
        system:
          hostname: R10
        interfaces:
          loopbacks:
            - id: 0
              description: ROUTER-ID
              ipv4:
                address: 10.255.0.10
                address_mask: 255.255.255.255
    - name: R11
      host: 10.10.10.11
      configuration:
        system:
          hostname: R11
        interfaces:
          loopbacks:
            - id: 0
              description: ROUTER-ID
              ipv4:
                address: 10.255.0.11
                address_mask: 255.255.255.255
    - name: R12
      host: 10.10.10.12
      configuration:
        system:
          hostname: R12
        interfaces:
          loopbacks:
            - id: 0
              description: ROUTER-ID
              ipv4:
                address: 10.255.0.12
                address_mask: 255.255.255.255
"""

PROBLEMS[2] = (
    "Shared settings are not correctly layered. Either data/common.nac.yaml is missing or has\n"
    "the wrong content, the shared settings were written into data/devices.nac.yaml instead,\n"
    "or the two files do not merge into the expected combined model."
)
EXPECTED[2] = (
    "data/common.nac.yaml lists R10, R11 and R12 (by name only) and gives each one:\n"
    "  system.ip_routing: true\n"
    "  system.ip_domain_name: meridian.local\n"
    "  system.ip_domain_lookup: false\n"
    "It must NOT repeat host, hostname or loopbacks, and data/devices.nac.yaml must NOT\n"
    "contain any of the three shared settings."
)
HINTS[2] = (
    "nac-validate (like the Terraform module later) merges every YAML file in data/ into one\n"
    "model. Devices with the same name are merged together, key by key. So common.nac.yaml only\n"
    "needs the device name (the merge key) plus the settings that are shared."
)
SOLUTIONS[2] = """iosxe:
  devices:
    - name: R10
      configuration:
        system:
          ip_routing: true
          ip_domain_name: meridian.local
          ip_domain_lookup: false
    - name: R11
      configuration:
        system:
          ip_routing: true
          ip_domain_name: meridian.local
          ip_domain_lookup: false
    - name: R12
      configuration:
        system:
          ip_routing: true
          ip_domain_name: meridian.local
          ip_domain_lookup: false
"""

PROBLEMS[3] = (
    ".schema.yaml is missing, malformed, or too loose or too strict. A correct schema must\n"
    "accept the real data and make nac-validate exit with code 2 (syntax error) for each bad\n"
    "input we inject into a temporary copy."
)
EXPECTED[3] = (
    "nac-validate data -s .schema.yaml  ->  exit 0 on the real data, and exit 2 for each of:\n"
    "  a device host that is not a valid IPv4 address\n"
    "  a device with no name\n"
    "  a loopback id that is not a number\n"
    "  a loopback address that is not a valid IPv4 address\n"
    "  a loopback mask that is not a valid IPv4 address\n"
    "  ip_routing set to text instead of true/false\n"
    "  a misspelled key (strict mode must reject unknown keys)"
)
HINTS[3] = (
    "Replace each ... with a yamale validator: str() for text, int(min=0) for whole numbers,\n"
    "bool() for true/false, ip(version=4) for IPv4 addresses. Add required=False to anything\n"
    "that is allowed to be missing. Remember: nac-validate checks EACH FILE separately against\n"
    "the schema, and common.nac.yaml has no host - so host must not be required."
)
SOLUTIONS[3] = """iosxe: include('iosxe', required=False)
---
iosxe:
  devices: list(include('device'), required=False)
device:
  name: str()
  host: ip(version=4, required=False)
  configuration: include('configuration', required=False)
configuration:
  system: include('system', required=False)
  interfaces: include('interfaces', required=False)
system:
  hostname: str(required=False)
  ip_routing: bool(required=False)
  ip_domain_name: str(required=False)
  ip_domain_lookup: bool(required=False)
interfaces:
  loopbacks: list(include('loopback'), required=False)
loopback:
  id: int(min=0)
  description: str(required=False)
  ipv4: include('ipv4', required=False)
ipv4:
  address: ip(version=4)
  address_mask: ip(version=4)
"""

PROBLEMS[4] = (
    "rules/ does not yet contain two working semantic rules (ids 101 and 102), or they do not\n"
    "flag the violations we inject. A correct rule exits nac-validate with code 1 and names\n"
    "its own rule id in the JSON output - and stays silent on good data."
)
EXPECTED[4] = (
    "Rule 101 - a device's hostname must equal its device name.\n"
    "Rule 102 - no IPv4 address (device host or any loopback) may be used by more than one place.\n"
    "Both rules: no violations on the real data; a violation of exactly the matching rule\n"
    "when we inject a hostname mismatch or a duplicated address."
)
HINTS[4] = (
    "Each rule is its own .py file in rules/ with one class named Rule(RuleBase). match() gets\n"
    "the fully merged data and returns a list of strings - an empty list means no violation.\n"
    "For 102, collect every address into a dict {address: [owners]}, then report any address\n"
    "that has more than one owner."
)
SOLUTIONS[4] = """# rules/101_hostname_matches_name.py
from nac_validate import RuleBase


class Rule(RuleBase):
    id = "101"
    description = "Device hostname must equal its device name"
    severity = "HIGH"

    @classmethod
    def match(cls, data):
        results = []
        for device in data.get("iosxe", {}).get("devices", []):
            hostname = device.get("configuration", {}).get("system", {}).get("hostname")
            if hostname != device["name"]:
                results.append(
                    f"iosxe.devices[name={device['name']}].configuration.system.hostname - "
                    f"'{hostname}' does not match the device name"
                )
        return results


# rules/102_unique_addresses.py
from nac_validate import RuleBase


class Rule(RuleBase):
    id = "102"
    description = "No IPv4 address may be used more than once"
    severity = "HIGH"

    @classmethod
    def match(cls, data):
        users = {}
        for device in data.get("iosxe", {}).get("devices", []):
            pairs = []
            if device.get("host"):
                pairs.append(("host", device["host"]))
            loopbacks = device.get("configuration", {}).get("interfaces", {}).get("loopbacks", [])
            for loopback in loopbacks:
                address = loopback.get("ipv4", {}).get("address")
                if address:
                    pairs.append((f"loopback{loopback.get('id')}", address))
            for where, address in pairs:
                users.setdefault(address, []).append(f"{device['name']}.{where}")
        return [
            f"address {address} is used by {', '.join(owners)}"
            for address, owners in users.items()
            if len(owners) > 1
        ]
"""


# -----------------------------------------------------------------------------
# nac-validate helpers
# -----------------------------------------------------------------------------

def _nac_validate_cmd():
    exe = shutil.which("nac-validate")
    if exe:
        return [exe]
    return None


def run_nac_validate(data_dir, schema=None, rules=None, extra=None):
    """Run nac-validate and return (exit_code, stdout, stderr)."""
    cmd = _nac_validate_cmd()
    if cmd is None:
        return 127, "", "nac-validate not found on PATH"
    args = cmd + [str(data_dir), "--no-color"]
    if schema is not None:
        args += ["-s", str(schema)]
    if rules is not None:
        args += ["-r", str(rules)]
    if extra:
        args += list(extra)
    proc = subprocess.run(args, capture_output=True, text=True, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


def parse_json_result(stdout):
    start = stdout.find("{")
    if start == -1:
        return None
    try:
        return json.loads(stdout[start:])
    except json.JSONDecodeError:
        return None


def _load_yaml(path):
    try:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return None


def _devices_of(model):
    if not isinstance(model, dict):
        return None
    iosxe = model.get("iosxe")
    if not isinstance(iosxe, dict):
        return None
    devices = iosxe.get("devices")
    if not isinstance(devices, list):
        return None
    return devices


def _contains_forbidden_key(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                return True
            if _contains_forbidden_key(value):
                return True
    elif isinstance(node, list):
        return any(_contains_forbidden_key(item) for item in node)
    return False


def _mutated_data_dir(workdir, mutator):
    """Copy the real data files into workdir/data, apply mutator, return the path."""
    target = Path(workdir) / "data"
    target.mkdir(parents=True, exist_ok=True)
    devices = copy.deepcopy(_load_yaml(DEVICES_FILE))
    common = copy.deepcopy(_load_yaml(COMMON_FILE))
    mutator(devices, common)
    (target / "devices.nac.yaml").write_text(yaml.safe_dump(devices, sort_keys=False), encoding="utf-8")
    (target / "common.nac.yaml").write_text(yaml.safe_dump(common, sort_keys=False), encoding="utf-8")
    return target


def _device(model, name):
    for device in model["iosxe"]["devices"]:
        if device.get("name") == name:
            return device
    raise KeyError(name)


# -----------------------------------------------------------------------------
# Display helpers
# -----------------------------------------------------------------------------

def c(text, style):
    return Text(str(text), style=style.strip())


def todo_label(number):
    return f"TODO {number:02d}"


def banner(title, color=CYAN):
    console.print()
    console.print(
        Panel(
            Align.center(Text(str(title), style=f"bold {color}")),
            border_style=color,
            padding=(0, 2),
        )
    )
    console.print()


def divider():
    console.print()
    console.print(Rule(style="grey50"))
    console.print()


def pause(message):
    if INTERACTIVE_MODE:
        try:
            input(f"\n{message}")
        except EOFError:
            pass


def section(title, value, color):
    body = Text()
    lines = str(value).splitlines()
    for i, line in enumerate(lines):
        body.append(line)
        if i < len(lines) - 1:
            body.append("\n")
    console.print(Panel(body, title=title, title_align="left", border_style=color, padding=(0, 1)))
    console.print()


def render_bar(completed, total):
    total = max(total, 1)
    return Bar(size=total, begin=0, end=completed, color="green3", bgcolor="grey27", width=40)


# -----------------------------------------------------------------------------
# TODO checks
# -----------------------------------------------------------------------------

def check_todo_1():
    if not DEVICES_FILE.exists():
        return False
    model = _load_yaml(DEVICES_FILE)
    devices = _devices_of(model)
    if devices is None or len(devices) != 3:
        return False
    if _contains_forbidden_key(model):
        return False

    seen = set()
    for device in devices:
        if not isinstance(device, dict):
            return False
        name = device.get("name")
        expected = EXPECTED_DEVICES.get(name)
        if expected is None or name in seen:
            return False
        seen.add(name)
        if str(device.get("host")) != expected["host"]:
            return False
        configuration = device.get("configuration")
        if not isinstance(configuration, dict):
            return False
        system = configuration.get("system")
        if not isinstance(system, dict) or system.get("hostname") != name:
            return False
        interfaces = configuration.get("interfaces")
        loopbacks = interfaces.get("loopbacks") if isinstance(interfaces, dict) else None
        if not isinstance(loopbacks, list) or len(loopbacks) != 1:
            return False
        lo = loopbacks[0]
        if not isinstance(lo, dict) or lo.get("id") != 0 or lo.get("description") != "ROUTER-ID":
            return False
        ipv4 = lo.get("ipv4")
        if not isinstance(ipv4, dict):
            return False
        if str(ipv4.get("address")) != expected["loopback0"]:
            return False
        if str(ipv4.get("address_mask")) != "255.255.255.255":
            return False
    return seen == set(EXPECTED_DEVICES)


def check_todo_2():
    if not COMMON_FILE.exists() or not DEVICES_FILE.exists():
        return False

    devices_model = _load_yaml(DEVICES_FILE)
    common_model = _load_yaml(COMMON_FILE)
    devices = _devices_of(devices_model)
    common_devices = _devices_of(common_model)
    if devices is None or common_devices is None:
        return False

    # devices.nac.yaml must not carry any shared setting
    for device in devices:
        system = (device.get("configuration") or {}).get("system") or {}
        if any(key in system for key in SHARED_SYSTEM):
            return False

    # common.nac.yaml: exactly the 3 names, shared settings only
    if sorted(d.get("name") for d in common_devices) != sorted(EXPECTED_DEVICES):
        return False
    if _contains_forbidden_key(common_model):
        return False
    for device in common_devices:
        if set(device.keys()) != {"name", "configuration"}:
            return False
        configuration = device["configuration"]
        if not isinstance(configuration, dict) or set(configuration.keys()) != {"system"}:
            return False
        if configuration["system"] != SHARED_SYSTEM:
            return False

    # The two files must merge into the complete model
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        permissive = tmp_path / "permissive.schema.yaml"
        permissive.write_text("iosxe: any(required=False)\n", encoding="utf-8")
        merged = tmp_path / "merged.yaml"
        code, _, _ = run_nac_validate(DATA_DIR, schema=permissive, extra=["-o", str(merged)])
        if code != 0 or not merged.exists():
            return False
        merged_model = _load_yaml(merged)

    merged_devices = _devices_of(merged_model)
    if merged_devices is None or len(merged_devices) != 3:
        return False
    for name, expected in EXPECTED_DEVICES.items():
        try:
            device = _device(merged_model, name)
        except KeyError:
            return False
        system = device["configuration"]["system"]
        if str(device.get("host")) != expected["host"] or system.get("hostname") != name:
            return False
        for key, value in SHARED_SYSTEM.items():
            if system.get(key) != value:
                return False
        loopbacks = device["configuration"]["interfaces"]["loopbacks"]
        if str(loopbacks[0]["ipv4"]["address"]) != expected["loopback0"]:
            return False
    return True


def _schema_mutations():
    """(label, mutator) pairs - each must make a correct schema reject the data."""

    def bad_host(devices, common):
        _device(devices, "R11")["host"] = "10.10.10.999"

    def no_name(devices, common):
        del _device(devices, "R12")["name"]

    def string_id(devices, common):
        _device(devices, "R10")["configuration"]["interfaces"]["loopbacks"][0]["id"] = "zero"

    def bad_address(devices, common):
        _device(devices, "R10")["configuration"]["interfaces"]["loopbacks"][0]["ipv4"]["address"] = "not-an-ip"

    def bad_mask(devices, common):
        _device(devices, "R11")["configuration"]["interfaces"]["loopbacks"][0]["ipv4"]["address_mask"] = "256.0.0.0"

    def text_bool(devices, common):
        _device(common, "R10")["configuration"]["system"]["ip_routing"] = "maybe"

    def typo_key(devices, common):
        system = _device(devices, "R12")["configuration"]["system"]
        system["hostnaem"] = system.pop("hostname")

    return [
        ("bad host IP", bad_host),
        ("missing name", no_name),
        ("loopback id as text", string_id),
        ("loopback address not an IP", bad_address),
        ("loopback mask not an IP", bad_mask),
        ("ip_routing as text", text_bool),
        ("misspelled key", typo_key),
    ]


def check_todo_3():
    if not SCHEMA_FILE.exists() or _nac_validate_cmd() is None:
        return False

    code, _, _ = run_nac_validate(DATA_DIR, schema=SCHEMA_FILE)
    if code != 0:
        return False

    for _label, mutator in _schema_mutations():
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = _mutated_data_dir(tmp, mutator)
            code, _, _ = run_nac_validate(data_dir, schema=SCHEMA_FILE)
            if code != 2:
                return False
    return True


def _rule_ids_from_json(stdout):
    result = parse_json_result(stdout)
    if result is None:
        return None
    return {str(item.get("rule_id")) for item in result.get("semantic_errors", [])}


def _semantic_mutations():
    """(label, mutator, expected_rule_id)"""

    def wrong_hostname(devices, common):
        _device(devices, "R11")["configuration"]["system"]["hostname"] = "ROUTER-11"

    def duplicate_loopback(devices, common):
        lo = _device(devices, "R11")["configuration"]["interfaces"]["loopbacks"][0]
        lo["ipv4"]["address"] = EXPECTED_DEVICES["R10"]["loopback0"]

    def duplicate_host(devices, common):
        _device(devices, "R12")["host"] = EXPECTED_DEVICES["R11"]["host"]

    def loopback_reuses_host(devices, common):
        lo = _device(devices, "R12")["configuration"]["interfaces"]["loopbacks"][0]
        lo["ipv4"]["address"] = EXPECTED_DEVICES["R10"]["host"]

    return [
        ("hostname does not match name", wrong_hostname, "101"),
        ("two loopbacks share an address", duplicate_loopback, "102"),
        ("two devices share a host IP", duplicate_host, "102"),
        ("a loopback reuses a management IP", loopback_reuses_host, "102"),
    ]


def check_todo_4():
    if not SCHEMA_FILE.exists() or not RULES_DIR.is_dir() or _nac_validate_cmd() is None:
        return False
    if not list(RULES_DIR.glob("*.py")):
        return False

    code, out, _ = run_nac_validate(DATA_DIR, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["--list-rules"])
    if code != 0 or "101" not in out or "102" not in out:
        return False

    code, out, _ = run_nac_validate(DATA_DIR, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["-f", "json"])
    if code != 0:
        return False

    for _label, mutator, expected_id in _semantic_mutations():
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = _mutated_data_dir(tmp, mutator)
            code, out, _ = run_nac_validate(data_dir, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["-f", "json"])
            if code != 1:
                return False
            if _rule_ids_from_json(out) != {expected_id}:
                return False
    return True


CHECKS = {1: check_todo_1, 2: check_todo_2, 3: check_todo_3, 4: check_todo_4}


def compute_statuses():
    statuses = {}
    previous_ok = True
    for number in range(1, TOTAL_TODOS + 1):
        statuses[number] = CHECKS[number]() if previous_ok else False
        previous_ok = previous_ok and statuses[number]
    return statuses


def first_failed_todo(statuses):
    for number in range(1, TOTAL_TODOS + 1):
        if not statuses[number]:
            return number
    return None


# -----------------------------------------------------------------------------
# TODO progress / feedback / summary
# -----------------------------------------------------------------------------

def print_todo_details(number, statuses):
    titles = {
        1: "[1] Authoring the network data model...",
        2: "[2] Layering shared settings across files...",
        3: "[3] Validating structure with a schema...",
        4: "[4] Enforcing business rules...",
    }
    console.print(titles[number])
    if not statuses[number]:
        return
    if number == 1:
        for name, expected in EXPECTED_DEVICES.items():
            console.print(f"  {name} -> host {expected['host']}, Loopback0 {expected['loopback0']}/32")
    elif number == 2:
        console.print("  devices.nac.yaml + common.nac.yaml -> merged into one model")
        console.print("  every device carries ip_routing, ip_domain_name and ip_domain_lookup")
    elif number == 3:
        console.print("  real data -> accepted (exit 0)")
        for label, _ in _schema_mutations():
            console.print(f"  injected: {label} -> rejected (exit 2)")
    elif number == 4:
        console.print("  real data -> no violations (exit 0)")
        for label, _, rule_id in _semantic_mutations():
            console.print(f"  injected: {label} -> rule {rule_id} fired (exit 1)")


def print_todo_progress(statuses):
    banner("TODO PROGRESS")

    for number in range(1, TOTAL_TODOS + 1):
        console.print(c(f"{todo_label(number)} - {TODO_NAMES[number]}", f"{BOLD}{CYAN}"))
        console.print(Rule(style=CYAN))
        console.print()

        print_todo_details(number, statuses)
        console.print()

        if statuses[number]:
            console.print(c(f"✓ {todo_label(number)} Complete", f"{BOLD}{GREEN}"))
            console.print(c(SUCCESS_MESSAGES[number], GREEN))
            if number < TOTAL_TODOS:
                console.print()
                console.print(c(f"Moving to {todo_label(number + 1)}...", DIM))
            divider()
            continue

        console.print(c(f"✗ {todo_label(number)} Not Complete", f"{BOLD}{YELLOW}"))
        console.print()
        console.print(c(FAIL_MESSAGES[number], YELLOW))
        console.print()
        console.print(c("Proceeding to detailed feedback...", DIM))
        divider()
        break


def feedback(failed):
    banner("FEEDBACK")

    if failed is None:
        for number in range(1, TOTAL_TODOS + 1):
            console.print(Text.assemble(("[PASS] ", "bold green"), (f"{todo_label(number)} - {TODO_NAMES[number]}", "bold")))
        return

    for number in range(1, failed):
        console.print(Text.assemble(("[PASS] ", "bold green"), (f"{todo_label(number)} - {TODO_NAMES[number]}", "bold")))

    console.print()
    console.print(Text.assemble(("[FAIL] ", "bold red"), (f"{todo_label(failed)} - {TODO_NAMES[failed]}", "bold")))
    console.print()

    section("Problem", PROBLEMS[failed], YELLOW)
    section("Expected", EXPECTED[failed], CYAN)
    section("Hint", HINTS[failed], GREEN)

    console.print("Type S and press Enter to reveal the solution, or press Enter to skip: ", end="")
    try:
        answer = input().strip().lower()
    except EOFError:
        answer = ""

    if answer == "s":
        console.print()
        lexer = "python" if failed == 4 else "yaml"
        syntax = Syntax(SOLUTIONS[failed], lexer, theme="ansi_dark", line_numbers=False, word_wrap=True)
        console.print(Panel(syntax, title="Solution", title_align="left", border_style=GREEN, padding=(0, 1)))
        console.print()


def lab_summary(statuses):
    completed = sum(1 for number in range(1, TOTAL_TODOS + 1) if statuses[number])
    failed = first_failed_todo(statuses)
    percent = int((completed / TOTAL_TODOS) * 100)

    if failed is None:
        banner(f"{todo_label(TOTAL_TODOS)} COMPLETE - LAB {TOTAL_TODOS} OF {COURSE_TOTAL_TODOS} DONE", GREEN)
        console.print(c("Progress", f"{BOLD}{CYAN}"))
        console.print(Rule(style=CYAN))
        console.print(render_bar(completed, TOTAL_TODOS))
        console.print(f"  {percent}% Complete ({completed} of {TOTAL_TODOS} TODOs in this lab)")
        console.print()
        console.print(f"  {todo_label(TOTAL_TODOS)} - {TODO_NAMES[TOTAL_TODOS]} - is complete.")
        console.print("  Move on to the next lab; everything done here will")
        console.print("  already be done for you there.")
        console.print()
        return

    banner("LAB NOT COMPLETE", YELLOW)
    console.print(c("Progress", f"{BOLD}{CYAN}"))
    console.print(Rule(style=CYAN))
    console.print(render_bar(completed, TOTAL_TODOS))
    console.print(f"  {percent}% Complete ({completed} of {TOTAL_TODOS} TODOs)")
    console.print()

    console.print(c("Completed", f"{BOLD}{GREEN}"))
    console.print(Rule(style=GREEN))
    if completed == 0:
        console.print("  No TODOs completed yet.")
    else:
        for number in range(1, failed):
            console.print(f"  ✓ {todo_label(number)} - {TODO_NAMES[number]}")
    console.print()

    console.print(c("Remaining", f"{BOLD}{YELLOW}"))
    console.print(Rule(style=YELLOW))
    for number in range(failed, TOTAL_TODOS + 1):
        console.print(f"  ✗ {todo_label(number)} - {TODO_NAMES[number]}")
    console.print()

    console.print(c("Next Step", f"{BOLD}{CYAN}"))
    console.print(Rule(style=CYAN))
    console.print(f"  Complete {todo_label(failed)} and run:")
    console.print()
    console.print("  python grading.py")
    console.print()


def main():
    banner("Production-Grade Network as Code for IOS-XE")

    if _nac_validate_cmd() is None:
        console.print(c("nac-validate not found on PATH.", f"{BOLD}{RED}"))
        console.print(c("Run: pip install -r requirements.txt   (see OFFLINE-SETUP.md for an offline lab)", YELLOW))
        console.print()
        sys.exit(127)

    statuses = compute_statuses()

    print_todo_progress(statuses)
    pause("Press ENTER to view detailed feedback...")

    failed = first_failed_todo(statuses)
    feedback(failed)
    pause("Press ENTER to view lab progress...")

    divider()
    lab_summary(statuses)
    pause("Press ENTER to exit...")

    sys.exit(0 if failed is None else 1)


if __name__ == "__main__":
    main()
