#!/usr/bin/env python3

"""
Production-Grade Network as Code for IOS-XE - Coaching-Style Grader (Rich terminal UI)

This grader validates the course one TODO at a time, always starting from
TODO 01, and stops at the first incomplete one. Earlier TODOs are already
solved for you in each lab folder, but they are re-checked live on every run,
so you always see current proof that nothing earlier broke.

TODO 01-05 never touch a router: they run entirely on this machine, using
the nac-validate tool from the netascode project (01-04) and Terraform's
init and validate commands (05). TODO 06 reads from the routers, but only
with terraform plan, which never changes them. Every check that mutates
data (to prove your schema or rules really catch bad input) does so in a
disposable temporary copy - your real files in data/ are never modified.

Requires: Python 3.10+, and the packages in requirements.txt
(pip install -r requirements.txt).
"""

import copy
import json
import os
import re
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
ROUTING_FILE = DATA_DIR / "routing.nac.yaml"
# Data files that belong to later TODOs. An earlier TODO's check must not look at them,
# so a half-finished file for TODO 08 can never make TODO 07 look broken.
FILE_TODO = {"routing.nac.yaml": 7, "ospf.nac.yaml": 8, "bgp.nac.yaml": 9}
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
TOTAL_TODOS = 11

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
    5: "Terraform loads the nac-iosxe module, reads your data/ folder, and the configuration is valid.",
    6: "R10, R11 and R12 match the data model, and a second plan finds nothing left to change.",
    7: "Static routes and an ACL are modelled, validated by schema and rule, and match the live routers.",
    8: "OSPF is modelled, validated by schema and rules 101 to 104, and the routers run it as described.",
    9: "BGP is modelled, validated by schema and rules 101 to 105, and the three routers peer as described.",
    10: "Drift is detected by drift_check.sh, reconciled both ways, and the routers match the data model again.",
    11: "The tests are generated from the data model and the live routers pass every one of them.",
}

FAIL_MESSAGES = {
    1: "The pipeline cannot continue because the network data model has not been authored correctly yet.",
    2: "The pipeline cannot continue because the shared settings have not been layered into their own file correctly yet.",
    3: "The pipeline cannot continue because the schema does not yet accept good data and reject bad data.",
    4: "The pipeline cannot continue because the semantic rules do not yet catch the business-rule violations.",
    5: "The pipeline cannot continue because Terraform is not yet connected to the data model.",
    6: "The pipeline cannot continue because the routers do not yet match the data model.",
    7: "The pipeline cannot continue because the routes and ACL are not modelled, validated and applied yet.",
    8: "The pipeline cannot continue because OSPF is not modelled, validated and applied yet.",
    9: "The pipeline cannot continue because BGP is not modelled, validated and applied yet.",
    10: "The pipeline cannot continue because drift cannot be detected and reconciled yet.",
    11: "The pipeline cannot continue because the live state is not yet verified by tests generated from the data model.",
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

PROBLEMS[5] = (
    "main.tf is missing or incomplete, or Terraform could not load it. It needs a terraform\n"
    "block with a required_version of 1.9 or newer, and a module block that points at the\n"
    "nac-iosxe module and reads the data/ folder. No username, password or provider block\n"
    "may appear in any .tf file. Then terraform init and terraform validate must both succeed."
)
EXPECTED[5] = (
    "terraform { required_version = \">= 1.9.0\" }\n"
    "module \"iosxe\" { source = <the nac-iosxe module>, yaml_directories = [\"data\"] }\n"
    "terraform init  -> succeeds (providers come from the local mirror)\n"
    "terraform validate -> \"Success! The configuration is valid.\""
)
HINTS[5] = (
    "The module is already on this machine: ../offline-bundle/modules/nac-iosxe. If init fails,\n"
    "open a new terminal and run  . ../prep/env.sh  first, so Terraform uses the local mirror.\n"
    "The module sets up the iosxe provider itself, so do not add a provider block, a host or\n"
    "any credentials."
)
SOLUTIONS[5] = """# main.tf
terraform {
  required_version = ">= 1.9.0"
}

module "iosxe" {
  source           = "../offline-bundle/modules/nac-iosxe"
  yaml_directories = ["data"]
}
"""

PROBLEMS[6] = (
    "Terraform does not report the routers as in sync with the data model. Possible causes:\n"
    "managed_devices in main.tf still lists only some of the routers; IOSXE_USERNAME or\n"
    "IOSXE_PASSWORD is not set in this terminal; a router cannot be reached on NETCONF port 830;\n"
    "or you have not run terraform apply for all three routers yet."
)
EXPECTED[6] = (
    "main.tf: managed_devices is either absent or lists R10, R11 and R12.\n"
    "IOSXE_USERNAME and IOSXE_PASSWORD are set in this terminal.\n"
    "terraform plan -detailed-exitcode exits 0, which means 'No changes' on all three routers."
)
HINTS[6] = (
    "Run terraform plan yourself and read it. If it still lists changes, run terraform apply.\n"
    "If it shows an error, check that the port answers (bash: echo > /dev/tcp/10.10.10.12/830) and\n"
    "that the username and password are exported in this same terminal. The grader needs both."
)
SOLUTIONS[6] = """# main.tf  (the module block at the end of TODO 06)
terraform {
  required_version = ">= 1.9.0"
}

module "iosxe" {
  source           = "../offline-bundle/modules/nac-iosxe"
  yaml_directories = ["data"]
  managed_devices  = ["R10", "R11", "R12"]
}
"""

EXPECTED_ROUTES = {
    "R10": {("10.255.0.11", "255.255.255.255"): "10.10.10.11", ("10.255.0.12", "255.255.255.255"): "10.10.10.12"},
    "R11": {("10.255.0.10", "255.255.255.255"): "10.10.10.10", ("10.255.0.12", "255.255.255.255"): "10.10.10.12"},
    "R12": {("10.255.0.10", "255.255.255.255"): "10.10.10.10", ("10.255.0.11", "255.255.255.255"): "10.10.10.11"},
}
ACL_NAME = "LOOPBACK-NET"

PROBLEMS[7] = (
    "One of these is not right yet. data/routing.nac.yaml must give each router its two static\n"
    "routes (to the other routers' loopbacks) and a standard ACL named LOOPBACK-NET that is\n"
    "applied inbound on Loopback0. .schema.yaml must accept all of it and reject mistakes in it.\n"
    "rules/103_acl_references_exist.py must flag an interface that uses an ACL the device does\n"
    "not define. Finally terraform plan must show no changes, which means it is applied."
)
EXPECTED[7] = (
    "R10  10.255.0.11/32 via 10.10.10.11   10.255.0.12/32 via 10.10.10.12\n"
    "R11  10.255.0.10/32 via 10.10.10.10   10.255.0.12/32 via 10.10.10.12\n"
    "R12  10.255.0.10/32 via 10.10.10.10   10.255.0.11/32 via 10.10.10.11\n"
    "Every router: standard ACL LOOPBACK-NET  10 permit 10.255.0.0 0.0.0.255, 20 deny any,\n"
    "applied inbound on Loopback0 (ipv4.access_group_in).\n"
    "Schema: bad masks, bad IPs, a wrong action and a misspelled key are all rejected (exit 2).\n"
    "Rule 103: an interface using an undefined ACL is flagged (exit 1, rule 103 only).\n"
    "terraform plan -detailed-exitcode exits 0."
)
HINTS[7] = (
    "Each router entry in routing.nac.yaml has three parts under configuration: routing ->\n"
    "static_routes, access_lists -> standard, and interfaces -> loopbacks (id 0) -> ipv4 ->\n"
    "access_group_in. Devices and loopbacks merge by name and id, so the loopback entry only\n"
    "needs id and the new key. If plan still shows changes, run terraform apply. If plan wants\n"
    "to create the loopbacks again, copy the state file from the previous TODO folder."
)
SOLUTIONS[7] = """# data/routing.nac.yaml  (R10 shown; R11 and R12 follow the table in TASK.md)
iosxe:
  devices:
    - name: R10
      configuration:
        interfaces:
          loopbacks:
            - id: 0
              ipv4:
                access_group_in: LOOPBACK-NET
        routing:
          static_routes:
            - prefix: 10.255.0.11
              mask: 255.255.255.255
              next_hops:
                - ip: 10.10.10.11
            - prefix: 10.255.0.12
              mask: 255.255.255.255
              next_hops:
                - ip: 10.10.10.12
        access_lists:
          standard:
            - name: LOOPBACK-NET
              entries:
                - sequence: 10
                  action: permit
                  prefix: 10.255.0.0
                  prefix_mask: 0.0.0.255
                - sequence: 20
                  action: deny
                  any: true

# additions to .schema.yaml
configuration:
  routing: include('routing', required=False)
  access_lists: include('access_lists', required=False)
routing:
  static_routes: list(include('static_route'), required=False)
static_route:
  prefix: ip(version=4)
  mask: ip(version=4)
  next_hops: list(include('next_hop'))
next_hop:
  ip: ip(version=4)
access_lists:
  standard: list(include('standard_acl'), required=False)
standard_acl:
  name: str()
  entries: list(include('standard_entry'))
standard_entry:
  sequence: int(min=1, max=2147483647)
  action: enum('permit', 'deny')
  prefix: ip(version=4, required=False)
  prefix_mask: ip(version=4, required=False)
  any: bool(required=False)
ipv4:
  access_group_in: str(required=False)

# rules/103_acl_references_exist.py
from nac_validate import RuleBase


class Rule(RuleBase):
    id = "103"
    description = "An interface may only use an ACL that the same device defines"
    severity = "HIGH"

    @classmethod
    def match(cls, data):
        results = []
        for device in data.get("iosxe", {}).get("devices", []):
            config = device.get("configuration", {})
            lists = config.get("access_lists", {})
            defined = {acl["name"] for kind in ("standard", "extended") for acl in lists.get(kind, [])}
            for loopback in config.get("interfaces", {}).get("loopbacks", []):
                name = loopback.get("ipv4", {}).get("access_group_in")
                if name and name not in defined:
                    results.append(
                        f"{device['name']} Loopback{loopback.get('id')} uses ACL '{name}', "
                        f"which the device does not define"
                    )
        return results
"""


def _data_dir_upto(workdir, todo, name="data"):
    """A copy of data/ with only the files that belong to TODO <todo> or earlier."""
    target = Path(workdir) / name
    target.mkdir(parents=True, exist_ok=True)
    for source in sorted(DATA_DIR.glob("*.yaml")) + sorted(DATA_DIR.glob("*.yml")):
        if FILE_TODO.get(source.name, 1) <= todo:
            shutil.copy(source, target / source.name)
    return target


def _mutated_full_dir(workdir, mutator, filename="routing.nac.yaml", todo=7):
    """Copy the data files up to TODO <todo>, apply mutator to <filename>, return the path."""
    target = _data_dir_upto(workdir, todo)
    model = copy.deepcopy(_load_yaml(DATA_DIR / filename))
    mutator(model)
    (target / filename).write_text(yaml.safe_dump(model, sort_keys=False), encoding="utf-8")
    return target


def _routing_schema_mutations():
    """(label, mutator) - each must make the extended schema reject the data (exit 2)."""

    def bad_mask(routing):
        _device(routing, "R10")["configuration"]["routing"]["static_routes"][0]["mask"] = "banana"

    def bad_next_hop(routing):
        _device(routing, "R11")["configuration"]["routing"]["static_routes"][0]["next_hops"][0]["ip"] = "10.10.10.999"

    def bad_action(routing):
        acl = _device(routing, "R12")["configuration"]["access_lists"]["standard"][0]
        acl["entries"][0]["action"] = "allow"

    def zero_sequence(routing):
        acl = _device(routing, "R10")["configuration"]["access_lists"]["standard"][0]
        acl["entries"][1]["sequence"] = 0

    def missing_action(routing):
        acl = _device(routing, "R11")["configuration"]["access_lists"]["standard"][0]
        del acl["entries"][0]["action"]

    def typo_key(routing):
        route = _device(routing, "R12")["configuration"]["routing"]["static_routes"][0]
        route["next_hop"] = route.pop("next_hops")

    return [
        ("static route mask not an IP", bad_mask),
        ("next hop not a valid IP", bad_next_hop),
        ("ACL action 'allow'", bad_action),
        ("ACL sequence 0", zero_sequence),
        ("ACL entry without an action", missing_action),
        ("misspelled next_hops key", typo_key),
    ]


def _routing_rule_mutations():
    """(label, mutator) - each must make rule 103 (and only 103) fire (exit 1)."""

    def unknown_acl(routing):
        lo = _device(routing, "R10")["configuration"]["interfaces"]["loopbacks"][0]
        lo["ipv4"]["access_group_in"] = "NO-SUCH-ACL"

    def renamed_acl(routing):
        _device(routing, "R11")["configuration"]["access_lists"]["standard"][0]["name"] = "OTHER-NAME"

    return [
        ("interface uses an undefined ACL", unknown_acl),
        ("ACL renamed, interface still points at the old name", renamed_acl),
    ]


EXPECTED_BRANCH_LAN = {"R10": "172.16.10.1", "R11": "172.16.11.1", "R12": "172.16.12.1"}
EXPECTED_OSPF_NETWORKS = {
    ("10.10.10.0", "0.0.0.255", 0),
    ("10.255.0.0", "0.0.0.255", 0),
    ("172.16.0.0", "0.0.255.255", 0),
}
EXPECTED_OSPF_PASSIVE = {("Loopback", 0), ("Loopback", 10)}

PROBLEMS[8] = (
    "One of these is not right yet. data/ospf.nac.yaml must give every router a Loopback10 (the\n"
    "branch LAN) and OSPF process 1 with the router ID, three networks in area 0, and both loopbacks\n"
    "passive. .schema.yaml must accept all of it and reject mistakes in it. rules/104 must flag an\n"
    "OSPF router ID that is not the Loopback0 address. Finally terraform plan must show no changes."
)
EXPECTED[8] = (
    "Loopback10, description BRANCH-LAN: R10 172.16.10.1, R11 172.16.11.1, R12 172.16.12.1 (all /32).\n"
    "OSPF process 1 on every router, router_id = that router's Loopback0 address.\n"
    "networks (all area 0): 10.10.10.0 0.0.0.255, 10.255.0.0 0.0.0.255, 172.16.0.0 0.0.255.255.\n"
    "passive interfaces: Loopback0 and Loopback10.\n"
    "Schema rejects bad router IDs, wildcards, areas, process ids, misspelled keys (exit 2).\n"
    "Rule 104 flags a router ID that is not the Loopback0 address; rule 102 still flags a duplicate\n"
    "Loopback10 address. terraform plan -detailed-exitcode exits 0."
)
HINTS[8] = (
    "ospf.nac.yaml has two parts per router: interfaces -> loopbacks (a new entry, id 10) and\n"
    "routing -> ospf_processes (a list, process id 1). Each network needs ip, wildcard and area.\n"
    "Wildcards are the inverse of masks. If plan still shows changes, run terraform apply. If plan\n"
    "wants to recreate things from earlier TODOs, copy the state file from the previous TODO folder."
)
SOLUTIONS[8] = """# data/ospf.nac.yaml  (R10 shown; R11 and R12 follow the table in TASK.md)
iosxe:
  devices:
    - name: R10
      configuration:
        interfaces:
          loopbacks:
            - id: 10
              description: BRANCH-LAN
              ipv4:
                address: 172.16.10.1
                address_mask: 255.255.255.255
        routing:
          ospf_processes:
            - id: 1
              router_id: 10.255.0.10
              networks:
                - ip: 10.10.10.0
                  wildcard: 0.0.0.255
                  area: 0
                - ip: 10.255.0.0
                  wildcard: 0.0.0.255
                  area: 0
                - ip: 172.16.0.0
                  wildcard: 0.0.255.255
                  area: 0
              passive_interfaces:
                - interface_type: Loopback
                  interface_id: 0
                - interface_type: Loopback
                  interface_id: 10

# additions to .schema.yaml
routing:
  ospf_processes: list(include('ospf_process'), required=False)
ospf_process:
  id: int(min=1, max=65535)
  router_id: ip(version=4, required=False)
  networks: list(include('ospf_network'), required=False)
  passive_interfaces: list(include('interface_ref'), required=False)
ospf_network:
  ip: ip(version=4)
  wildcard: ip(version=4)
  area: int(min=0)
interface_ref:
  interface_type: str()
  interface_id: int(min=0)

# rules/104_ospf_router_id_is_loopback0.py
from nac_validate import RuleBase


class Rule(RuleBase):
    id = "104"
    description = "An OSPF router ID must be the device's Loopback0 address"
    severity = "HIGH"

    @classmethod
    def match(cls, data):
        results = []
        for device in data.get("iosxe", {}).get("devices", []):
            config = device.get("configuration", {})
            loopbacks = config.get("interfaces", {}).get("loopbacks", [])
            loopback0 = next((lb for lb in loopbacks if lb.get("id") == 0), {})
            address = loopback0.get("ipv4", {}).get("address")
            for process in config.get("routing", {}).get("ospf_processes", []):
                router_id = process.get("router_id")
                if router_id != address:
                    results.append(
                        f"{device['name']} OSPF {process.get('id')} router_id {router_id} "
                        f"is not the Loopback0 address {address}"
                    )
        return results
"""


def _ospf_schema_mutations():
    """(label, mutator) - each must make the extended schema reject the data (exit 2)."""

    def bad_router_id(ospf):
        _device(ospf, "R10")["configuration"]["routing"]["ospf_processes"][0]["router_id"] = "10.255.0"

    def bad_wildcard(ospf):
        _device(ospf, "R11")["configuration"]["routing"]["ospf_processes"][0]["networks"][0]["wildcard"] = "banana"

    def text_area(ospf):
        _device(ospf, "R12")["configuration"]["routing"]["ospf_processes"][0]["networks"][1]["area"] = "backbone"

    def text_process_id(ospf):
        _device(ospf, "R10")["configuration"]["routing"]["ospf_processes"][0]["id"] = "one"

    def typo_key(ospf):
        process = _device(ospf, "R11")["configuration"]["routing"]["ospf_processes"][0]
        process["network"] = process.pop("networks")

    def missing_interface_id(ospf):
        process = _device(ospf, "R12")["configuration"]["routing"]["ospf_processes"][0]
        del process["passive_interfaces"][0]["interface_id"]

    return [
        ("router ID not an IP", bad_router_id),
        ("network wildcard not an IP", bad_wildcard),
        ("area written as text", text_area),
        ("process id written as text", text_process_id),
        ("misspelled networks key", typo_key),
        ("passive interface without an id", missing_interface_id),
    ]


def _ospf_rule_mutations():
    """(label, mutator, rule id) - each must make exactly that rule fire (exit 1)."""

    def wrong_router_id(ospf):
        _device(ospf, "R11")["configuration"]["routing"]["ospf_processes"][0]["router_id"] = "1.1.1.1"

    def no_router_id(ospf):
        del _device(ospf, "R12")["configuration"]["routing"]["ospf_processes"][0]["router_id"]

    def duplicate_branch_lan(ospf):
        lan = _device(ospf, "R11")["configuration"]["interfaces"]["loopbacks"][0]
        lan["ipv4"]["address"] = EXPECTED_BRANCH_LAN["R10"]

    return [
        ("router ID is not the Loopback0 address", wrong_router_id, "104"),
        ("OSPF process without a router ID", no_router_id, "104"),
        ("two routers share the branch LAN address", duplicate_branch_lan, "102"),
    ]



# -----------------------------------------------------------------------------
# Terraform helpers (TODO 05)
# -----------------------------------------------------------------------------

MAIN_TF = ROOT / "main.tf"
CREDENTIAL_PATTERN = re.compile(r"^\s*(username|password|secret|enable_secret|token)\s*=", re.M | re.I)


def _terraform_exe():
    exe = shutil.which("terraform")
    if exe:
        return exe
    bundled = ROOT.parent / "offline-bundle" / "bin" / "terraform"
    return str(bundled) if bundled.exists() else None


def _terraform_env():
    env = dict(os.environ)
    env["TF_IN_AUTOMATION"] = "1"
    env["TF_INPUT"] = "0"
    # This course's own mirror always wins over a value left in the shell by
    # another course (a stale TF_CLI_CONFIG_FILE would break terraform init).
    rc = ROOT.parent / "offline-bundle" / "terraform.rc"
    if rc.exists():
        env["TF_CLI_CONFIG_FILE"] = str(rc)
    return env


def run_terraform(args, timeout=600):
    exe = _terraform_exe()
    if exe is None:
        return 127, "", "terraform not found"
    try:
        proc = subprocess.run(
            [exe] + list(args), cwd=ROOT, env=_terraform_env(),
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, "", "terraform timed out"
    return proc.returncode, proc.stdout, proc.stderr


def _read_tf_without_comments():
    parts = []
    for path in sorted(ROOT.glob("*.tf")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            parts.append(line.split(" #")[0])
    return "\n".join(parts)


def _version_at_least(constraint, minimum=(1, 9)):
    match = re.search(r"(\d+)\.(\d+)", constraint)
    if not match or constraint.strip().startswith("<"):
        return False
    return (int(match.group(1)), int(match.group(2))) >= minimum


def _module_body(text):
    match = re.search(r'^module\s+"[^"]+"\s*\{(.*?)^\}', text, re.M | re.S)
    return match.group(1) if match else None


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


def _core_data_dir(workdir):
    """Only the TODO 01-02 files, so later TODOs' data never affects earlier checks."""
    return _data_dir_upto(workdir, 2, "core-data")


def check_todo_3():
    if not SCHEMA_FILE.exists() or _nac_validate_cmd() is None:
        return False

    with tempfile.TemporaryDirectory() as core_tmp:
        code, _, _ = run_nac_validate(_core_data_dir(core_tmp), schema=SCHEMA_FILE)
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

    with tempfile.TemporaryDirectory() as core_tmp:
        core = _core_data_dir(core_tmp)
        code, out, _ = run_nac_validate(core, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["--list-rules"])
        if code != 0 or "101" not in out or "102" not in out:
            return False
        code, out, _ = run_nac_validate(core, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["-f", "json"])
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


def check_todo_5():
    if not MAIN_TF.exists():
        return False
    text = _read_tf_without_comments()

    if CREDENTIAL_PATTERN.search(text) or re.search(r'provider\s+"iosxe"', text):
        return False

    version = re.search(r'required_version\s*=\s*"([^"]+)"', text)
    if not version or not _version_at_least(version.group(1)):
        return False

    body = _module_body(text)
    if body is None:
        return False
    source = re.search(r'source\s*=\s*"([^"]+)"', body)
    if not source or "nac-iosxe" not in source.group(1):
        return False
    dirs = re.search(r"yaml_directories\s*=\s*\[([^\]]*)\]", body)
    if not dirs or not re.search(r'"(\./)?data/?"', dirs.group(1)):
        return False

    if _terraform_exe() is None:
        return False
    code, _, _ = run_terraform(["init", "-no-color"])
    if code != 0:
        return False
    code, out, _ = run_terraform(["validate", "-json", "-no-color"])
    if code != 0:
        return False
    try:
        return bool(json.loads(out).get("valid"))
    except (json.JSONDecodeError, AttributeError):
        return False


def check_todo_6():
    if not MAIN_TF.exists() or _terraform_exe() is None:
        return False
    text = _read_tf_without_comments()
    if CREDENTIAL_PATTERN.search(text) or re.search(r'provider\s+"iosxe"', text):
        return False

    body = _module_body(text)
    if body is None:
        return False
    managed = re.search(r"managed_devices\s*=\s*\[([^\]]*)\]", body)
    if managed:
        names = set(re.findall(r'"([^"]+)"', managed.group(1)))
        if names != set(EXPECTED_DEVICES):
            return False

    if not os.environ.get("IOSXE_USERNAME") or not os.environ.get("IOSXE_PASSWORD"):
        return False

    # init is cheap and makes sure this folder is initialised
    code, _, _ = run_terraform(["init", "-no-color"])
    if code != 0:
        return False
    # plan only reads from the routers. Exit code 0 = nothing to change.
    # In later labs the data model already holds the next TODO's work, so a
    # plan that lists pending changes (exit 2) is fine here; an error (1) is not.
    code, _, _ = run_terraform(["plan", "-detailed-exitcode", "-no-color"], timeout=900)
    return code == 0 if TOTAL_TODOS == 6 else code in (0, 2)


def _routing_in_merged_model_ok(data_dir):
    """The merged model must carry the routes, the ACL and the ACL binding on every router."""
    with tempfile.TemporaryDirectory() as tmp:
        merged = Path(tmp) / "merged.yaml"
        code, _, _ = run_nac_validate(data_dir, extra=["-o", str(merged)])
        if code != 0 or not merged.exists():
            return False
        model = _load_yaml(merged)

    for name, routes in EXPECTED_ROUTES.items():
        try:
            config = _device(model, name)["configuration"]
        except (KeyError, TypeError):
            return False

        found = {}
        for route in config.get("routing", {}).get("static_routes", []) or []:
            hops = [str(h.get("ip")) for h in route.get("next_hops", []) or []]
            if len(hops) != 1:
                return False
            found[(str(route.get("prefix")), str(route.get("mask")))] = hops[0]
        if found != routes:
            return False

        acls = [a for a in (config.get("access_lists", {}).get("standard", []) or []) if a.get("name") == ACL_NAME]
        if len(acls) != 1:
            return False
        entries = sorted(acls[0].get("entries", []) or [], key=lambda e: e.get("sequence", 0))
        if len(entries) != 2:
            return False
        first, second = entries
        if (first.get("sequence"), first.get("action"), str(first.get("prefix")), str(first.get("prefix_mask"))) != (
            10, "permit", "10.255.0.0", "0.0.0.255",
        ):
            return False
        if (second.get("sequence"), second.get("action"), second.get("any")) != (20, "deny", True):
            return False

        loopbacks = config.get("interfaces", {}).get("loopbacks", []) or []
        lo0 = [lo for lo in loopbacks if lo.get("id") == 0]
        if len(lo0) != 1 or lo0[0].get("ipv4", {}).get("access_group_in") != ACL_NAME:
            return False
    return True


def check_todo_7():
    if not ROUTING_FILE.exists() or not SCHEMA_FILE.exists() or not RULES_DIR.is_dir():
        return False
    routing = _load_yaml(ROUTING_FILE)
    if _devices_of(routing) is None or _contains_forbidden_key(routing):
        return False

    with tempfile.TemporaryDirectory() as upto:
        data7 = _data_dir_upto(upto, 7)

        # 1. the data (up to this TODO) passes the schema and every rule
        code, out, _ = run_nac_validate(data7, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["-f", "json"])
        if code != 0:
            return False
        code, out, _ = run_nac_validate(data7, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["--list-rules"])
        if code != 0 or "103" not in out:
            return False

        # 2. the merged model holds exactly what the requirements ask for
        if not _routing_in_merged_model_ok(data7):
            return False

    # 3. the schema rejects mistakes in the new data
    for _label, mutator in _routing_schema_mutations():
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = _mutated_full_dir(tmp, mutator, "routing.nac.yaml", 7)
            code, _, _ = run_nac_validate(data_dir, schema=SCHEMA_FILE)
            if code != 2:
                return False

    # 4. rule 103 catches a dangling ACL reference, and nothing else fires
    for _label, mutator in _routing_rule_mutations():
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = _mutated_full_dir(tmp, mutator, "routing.nac.yaml", 7)
            code, out, _ = run_nac_validate(data_dir, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["-f", "json"])
            if code != 1 or _rule_ids_from_json(out) != {"103"}:
                return False

    # 5. the routers match: terraform plan reads from them and must find nothing to change.
    # In later labs the model already holds the next TODO's work, so pending changes (2) are fine there.
    if _terraform_exe() is None or not os.environ.get("IOSXE_USERNAME") or not os.environ.get("IOSXE_PASSWORD"):
        return False
    code, _, _ = run_terraform(["init", "-no-color"])
    if code != 0:
        return False
    code, _, _ = run_terraform(["plan", "-detailed-exitcode", "-no-color"], timeout=900)
    return code == 0 if TOTAL_TODOS == 7 else code in (0, 2)


def _ospf_in_merged_model_ok(data_dir):
    """The merged model must carry the branch LAN loopback and the OSPF process on every router."""
    with tempfile.TemporaryDirectory() as tmp:
        merged = Path(tmp) / "merged.yaml"
        code, _, _ = run_nac_validate(data_dir, extra=["-o", str(merged)])
        if code != 0 or not merged.exists():
            return False
        model = _load_yaml(merged)

    for name, expected in EXPECTED_DEVICES.items():
        try:
            config = _device(model, name)["configuration"]
        except (KeyError, TypeError):
            return False

        loopbacks = {lo.get("id"): lo for lo in config.get("interfaces", {}).get("loopbacks", []) or []}
        lan = loopbacks.get(10)
        if not lan or lan.get("description") != "BRANCH-LAN":
            return False
        if str(lan.get("ipv4", {}).get("address")) != EXPECTED_BRANCH_LAN[name]:
            return False
        if str(lan.get("ipv4", {}).get("address_mask")) != "255.255.255.255":
            return False

        processes = config.get("routing", {}).get("ospf_processes", []) or []
        if len(processes) != 1 or processes[0].get("id") != 1:
            return False
        process = processes[0]
        if str(process.get("router_id")) != expected["loopback0"]:
            return False
        networks = {
            (str(n.get("ip")), str(n.get("wildcard")), n.get("area")) for n in process.get("networks", []) or []
        }
        if networks != EXPECTED_OSPF_NETWORKS:
            return False
        passive = {
            (str(p.get("interface_type")), p.get("interface_id")) for p in process.get("passive_interfaces", []) or []
        }
        if passive != EXPECTED_OSPF_PASSIVE:
            return False
    return True


def check_todo_8():
    ospf_file = DATA_DIR / "ospf.nac.yaml"
    if not ospf_file.exists() or not SCHEMA_FILE.exists() or not RULES_DIR.is_dir():
        return False
    ospf = _load_yaml(ospf_file)
    if _devices_of(ospf) is None or _contains_forbidden_key(ospf):
        return False

    with tempfile.TemporaryDirectory() as upto:
        data8 = _data_dir_upto(upto, 8)

        code, out, _ = run_nac_validate(data8, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["-f", "json"])
        if code != 0:
            return False
        code, out, _ = run_nac_validate(data8, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["--list-rules"])
        if code != 0 or "104" not in out:
            return False

        if not _ospf_in_merged_model_ok(data8):
            return False

    for _label, mutator in _ospf_schema_mutations():
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = _mutated_full_dir(tmp, mutator, "ospf.nac.yaml", 8)
            code, _, _ = run_nac_validate(data_dir, schema=SCHEMA_FILE)
            if code != 2:
                return False

    for _label, mutator, expected_id in _ospf_rule_mutations():
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = _mutated_full_dir(tmp, mutator, "ospf.nac.yaml", 8)
            code, out, _ = run_nac_validate(data_dir, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["-f", "json"])
            if code != 1 or _rule_ids_from_json(out) != {expected_id}:
                return False

    if _terraform_exe() is None or not os.environ.get("IOSXE_USERNAME") or not os.environ.get("IOSXE_PASSWORD"):
        return False
    code, _, _ = run_terraform(["init", "-no-color"])
    if code != 0:
        return False
    code, _, _ = run_terraform(["plan", "-detailed-exitcode", "-no-color"], timeout=900)
    return code == 0 if TOTAL_TODOS == 8 else code in (0, 2)


EXPECTED_BGP_AS = 65010
EXPECTED_BGP_PEERS = {
    "R10": {"10.255.0.11", "10.255.0.12"},
    "R11": {"10.255.0.10", "10.255.0.12"},
    "R12": {"10.255.0.10", "10.255.0.11"},
}

PROBLEMS[9] = (
    "One of these is not right yet. data/bgp.nac.yaml must give every router BGP in AS 65010 with its\n"
    "Loopback0 as router ID, two neighbors (the other routers' Loopback0 addresses, sourced from\n"
    "Loopback0), its own Loopback10 advertised, and both neighbors activated. .schema.yaml must accept\n"
    "all of it and reject mistakes in it. rules/105 must flag a neighbor that is not another router's\n"
    "Loopback0 or whose remote_as is not that router's AS. Finally terraform plan must show no changes."
)
EXPECTED[9] = (
    "BGP AS 65010 on R10, R11, R12; router_id = that router's Loopback0 address.\n"
    "Neighbors (remote_as 65010, update source Loopback0): R10 -> 10.255.0.11 and 10.255.0.12,\n"
    "R11 -> 10.255.0.10 and 10.255.0.12, R12 -> 10.255.0.10 and 10.255.0.11.\n"
    "address-family ipv4 unicast: network = own Loopback10 /32; both neighbors activate: true.\n"
    "Schema rejects bad AS numbers, IPs, masks and misspelled keys (exit 2).\n"
    "Rule 105 flags an unknown neighbor, a neighbor that is the device itself, and a wrong remote_as.\n"
    "terraform plan -detailed-exitcode exits 0."
)
HINTS[9] = (
    "bgp.nac.yaml only needs the device name and routing -> bgp. as_number, router_id, neighbors and\n"
    "address_family -> ipv4_unicast (networks and neighbors) are siblings under bgp. A network entry\n"
    "has network and mask. update_source_interface_type is Loopback and the id is 0. If plan still\n"
    "shows changes, run terraform apply. If plan wants to recreate things from earlier TODOs, copy the\n"
    "state file from the previous TODO folder."
)
SOLUTIONS[9] = """# data/bgp.nac.yaml  (R10 shown; R11 and R12 follow the table in TASK.md)
iosxe:
  devices:
    - name: R10
      configuration:
        routing:
          bgp:
            as_number: 65010
            router_id: 10.255.0.10
            default_ipv4_unicast: false
            log_neighbor_changes: true
            neighbors:
              - ip: 10.255.0.11
                remote_as: 65010
                description: R11
                update_source_interface_type: Loopback
                update_source_interface_id: 0
              - ip: 10.255.0.12
                remote_as: 65010
                description: R12
                update_source_interface_type: Loopback
                update_source_interface_id: 0
            address_family:
              ipv4_unicast:
                networks:
                  - network: 172.16.10.1
                    mask: 255.255.255.255
                neighbors:
                  - ip: 10.255.0.11
                    activate: true
                  - ip: 10.255.0.12
                    activate: true

# additions to .schema.yaml
routing:
  bgp: include('bgp', required=False)
bgp:
  as_number: int(min=1, max=4294967295)
  router_id: ip(version=4, required=False)
  default_ipv4_unicast: bool(required=False)
  log_neighbor_changes: bool(required=False)
  neighbors: list(include('bgp_neighbor'), required=False)
  address_family: include('bgp_address_family', required=False)
bgp_neighbor:
  ip: ip(version=4)
  remote_as: int(min=1, max=4294967295)
  description: str(required=False)
  update_source_interface_type: str(required=False)
  update_source_interface_id: int(min=0, required=False)
bgp_address_family:
  ipv4_unicast: include('bgp_ipv4_unicast', required=False)
bgp_ipv4_unicast:
  networks: list(include('bgp_network'), required=False)
  neighbors: list(include('bgp_af_neighbor'), required=False)
bgp_network:
  network: ip(version=4)
  mask: ip(version=4)
bgp_af_neighbor:
  ip: ip(version=4)
  activate: bool(required=False)

# rules/105_bgp_neighbor_matches_peer.py
from nac_validate import RuleBase


class Rule(RuleBase):
    id = "105"
    description = "A BGP neighbor must be another device's Loopback0 and carry that device's AS"
    severity = "HIGH"

    @classmethod
    def match(cls, data):
        devices = data.get("iosxe", {}).get("devices", [])
        owners = {}
        for device in devices:
            config = device.get("configuration", {})
            loopbacks = config.get("interfaces", {}).get("loopbacks", [])
            loopback0 = next((lb for lb in loopbacks if lb.get("id") == 0), {})
            address = loopback0.get("ipv4", {}).get("address")
            asn = config.get("routing", {}).get("bgp", {}).get("as_number")
            if address:
                owners[address] = (device["name"], asn)
        results = []
        for device in devices:
            bgp = device.get("configuration", {}).get("routing", {}).get("bgp", {})
            for neighbor in bgp.get("neighbors", []):
                ip = neighbor.get("ip")
                owner = owners.get(ip)
                if owner is None:
                    results.append(f"{device['name']} neighbor {ip} is not the Loopback0 address of any device")
                elif owner[0] == device["name"]:
                    results.append(f"{device['name']} neighbor {ip} is its own Loopback0 address")
                elif owner[1] != neighbor.get("remote_as"):
                    results.append(
                        f"{device['name']} neighbor {ip} has remote_as {neighbor.get('remote_as')} "
                        f"but {owner[0]} is in AS {owner[1]}"
                    )
        return results
"""


def _bgp_of(model, name):
    return _device(model, name)["configuration"]["routing"]["bgp"]


def _bgp_schema_mutations():
    """(label, mutator) - each must make the extended schema reject the data (exit 2)."""

    def text_as(bgp):
        _bgp_of(bgp, "R10")["as_number"] = "meridian"

    def bad_router_id(bgp):
        _bgp_of(bgp, "R11")["router_id"] = "10.255.0"

    def bad_neighbor_ip(bgp):
        _bgp_of(bgp, "R12")["neighbors"][0]["ip"] = "10.255.0.999"

    def text_remote_as(bgp):
        _bgp_of(bgp, "R10")["neighbors"][1]["remote_as"] = "same"

    def bad_mask(bgp):
        _bgp_of(bgp, "R11")["address_family"]["ipv4_unicast"]["networks"][0]["mask"] = "banana"

    def typo_key(bgp):
        af = _bgp_of(bgp, "R12")["address_family"]["ipv4_unicast"]
        af["neighbours"] = af.pop("neighbors")

    return [
        ("AS number written as text", text_as),
        ("router ID not an IP", bad_router_id),
        ("neighbor address not a valid IP", bad_neighbor_ip),
        ("remote_as written as text", text_remote_as),
        ("advertised network mask not an IP", bad_mask),
        ("misspelled neighbors key in the address family", typo_key),
    ]


def _bgp_rule_mutations():
    """(label, mutator, rule_id) - each must make exactly that rule fire (exit 1)."""

    def unknown_peer(bgp):
        _bgp_of(bgp, "R10")["neighbors"][0]["ip"] = "10.255.0.99"

    def own_address(bgp):
        _bgp_of(bgp, "R11")["neighbors"][0]["ip"] = "10.255.0.11"

    def wrong_as(bgp):
        _bgp_of(bgp, "R12")["neighbors"][1]["remote_as"] = 65011

    return [
        ("neighbor is not any router's Loopback0", unknown_peer, "105"),
        ("neighbor is the router's own Loopback0", own_address, "105"),
        ("remote_as differs from the peer's AS", wrong_as, "105"),
    ]


def _bgp_in_merged_model_ok(data_dir):
    """The merged model must carry the BGP process, neighbors, advertised network and activation."""
    with tempfile.TemporaryDirectory() as tmp:
        merged = Path(tmp) / "merged.yaml"
        code, _, _ = run_nac_validate(data_dir, extra=["-o", str(merged)])
        if code != 0 or not merged.exists():
            return False
        model = _load_yaml(merged)

    for name, expected in EXPECTED_DEVICES.items():
        try:
            bgp = _bgp_of(model, name)
        except (KeyError, TypeError):
            return False
        if bgp.get("as_number") != EXPECTED_BGP_AS or str(bgp.get("router_id")) != expected["loopback0"]:
            return False

        neighbors = bgp.get("neighbors", []) or []
        if {str(n.get("ip")) for n in neighbors} != EXPECTED_BGP_PEERS[name] or len(neighbors) != 2:
            return False
        for n in neighbors:
            if n.get("remote_as") != EXPECTED_BGP_AS:
                return False
            if (str(n.get("update_source_interface_type")), n.get("update_source_interface_id")) != ("Loopback", 0):
                return False

        ipv4 = bgp.get("address_family", {}).get("ipv4_unicast", {}) or {}
        networks = {(str(n.get("network")), str(n.get("mask"))) for n in ipv4.get("networks", []) or []}
        if networks != {(EXPECTED_BRANCH_LAN[name], "255.255.255.255")}:
            return False
        active = {str(n.get("ip")) for n in ipv4.get("neighbors", []) or [] if n.get("activate") is True}
        if active != EXPECTED_BGP_PEERS[name]:
            return False
    return True


def check_todo_9():
    bgp_file = DATA_DIR / "bgp.nac.yaml"
    if not bgp_file.exists() or not SCHEMA_FILE.exists() or not RULES_DIR.is_dir():
        return False
    bgp = _load_yaml(bgp_file)
    if _devices_of(bgp) is None or _contains_forbidden_key(bgp):
        return False

    with tempfile.TemporaryDirectory() as upto:
        data9 = _data_dir_upto(upto, 9)

        code, out, _ = run_nac_validate(data9, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["-f", "json"])
        if code != 0:
            return False
        code, out, _ = run_nac_validate(data9, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["--list-rules"])
        if code != 0 or "105" not in out:
            return False

        if not _bgp_in_merged_model_ok(data9):
            return False

    for _label, mutator in _bgp_schema_mutations():
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = _mutated_full_dir(tmp, mutator, "bgp.nac.yaml", 9)
            code, _, _ = run_nac_validate(data_dir, schema=SCHEMA_FILE)
            if code != 2:
                return False

    for _label, mutator, expected_id in _bgp_rule_mutations():
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = _mutated_full_dir(tmp, mutator, "bgp.nac.yaml", 9)
            code, out, _ = run_nac_validate(data_dir, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["-f", "json"])
            if code != 1 or _rule_ids_from_json(out) != {expected_id}:
                return False

    if _terraform_exe() is None or not os.environ.get("IOSXE_USERNAME") or not os.environ.get("IOSXE_PASSWORD"):
        return False
    code, _, _ = run_terraform(["init", "-no-color"])
    if code != 0:
        return False
    code, _, _ = run_terraform(["plan", "-detailed-exitcode", "-no-color"], timeout=900)
    return code == 0 if TOTAL_TODOS == 9 else code in (0, 2)


DRIFT_SCRIPT = ROOT / "drift_check.sh"
NEIGHBOR_NAMES = {"10.255.0.10": "R10", "10.255.0.11": "R11", "10.255.0.12": "R12"}

PROBLEMS[10] = (
    "One of these is not right yet. drift_check.sh must run terraform plan -detailed-exitcode and\n"
    "turn its exit code into a message and the same exit code: 0 prints a line starting IN SYNC, 2\n"
    "prints a line starting DRIFT plus the plan's 'Plan:' summary line, anything else prints a line\n"
    "starting ERROR and exits 1. It may only plan, never apply. The BGP neighbor descriptions in\n"
    "data/bgp.nac.yaml must be back to the router names, and terraform plan must show no changes."
)
EXPECTED[10] = (
    "bash drift_check.sh -> plan exit 0: 'IN SYNC ...' and exit 0.\n"
    "plan exit 2: 'DRIFT ...', the 'Plan: X to add, Y to change, Z to destroy.' line, and exit 2.\n"
    "plan exit 1 (or any other): 'ERROR ...' and exit 1.\n"
    "The plan output is saved in drift-plan.txt. The script never runs apply or destroy.\n"
    "Every BGP neighbor description is the name of the peer (R10, R11, R12).\n"
    "terraform plan -detailed-exitcode exits 0."
)
HINTS[10] = (
    "Save the plan output with > drift-plan.txt 2>&1, then read the exit code straight away with\n"
    "code=$?, because the next command overwrites $?. Compare it with [ \"$code\" -eq 0 ]. Put an\n"
    "exit in every branch. If plan still shows changes, run terraform apply, and make sure the\n"
    "description in data/bgp.nac.yaml is back to the name of the peer."
)
SOLUTIONS[10] = """# drift_check.sh
#!/usr/bin/env bash
# Compare the routers with the data model. Changes nothing.

terraform plan -detailed-exitcode -no-color > drift-plan.txt 2>&1
code=$?

if [ "$code" -eq 0 ]; then
    echo "IN SYNC: the routers match the data model"
    exit 0
elif [ "$code" -eq 2 ]; then
    echo "DRIFT: the routers differ from the data model"
    grep '^Plan:' drift-plan.txt
    exit 2
else
    echo "ERROR: terraform plan failed, see drift-plan.txt"
    exit 1
fi
"""


def _drift_script_runs(rc, workdir):
    """Run drift_check.sh against a stub terraform that exits <rc>. Returns (exit code, stdout, calls)."""
    stub_dir = Path(workdir) / "bin"
    stub_dir.mkdir()
    calls = Path(workdir) / "calls.log"
    stub = stub_dir / "terraform"
    lines = ["#!/bin/sh", f'echo "$@" >> "{calls}"']
    if rc == 2:
        lines.append('echo "Plan: 0 to add, 2 to change, 0 to destroy."')
    elif rc == 0:
        lines.append('echo "No changes. Your infrastructure matches the configuration."')
    else:
        lines.append('echo "Error: stub failure"')
    lines.append(f"exit {rc}")
    stub.write_text("\n".join(lines) + "\n", encoding="utf-8")
    stub.chmod(0o755)

    run_dir = Path(workdir) / "run"
    run_dir.mkdir()
    shutil.copy(DRIFT_SCRIPT, run_dir / "drift_check.sh")
    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
    try:
        proc = subprocess.run(
            ["bash", "drift_check.sh"], cwd=run_dir, env=env, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "", ""
    log = calls.read_text(encoding="utf-8") if calls.exists() else ""
    saved = (run_dir / "drift-plan.txt").exists()
    return proc.returncode, proc.stdout, log, saved


def _drift_script_ok():
    if not DRIFT_SCRIPT.exists():
        return False
    text = DRIFT_SCRIPT.read_text(encoding="utf-8")
    code_lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    body = "\n".join(code_lines)
    if re.search(r"\b(apply|destroy|auto-approve)\b", body):
        return False
    if re.search(r"(?i)password|secret|IOSXE_USERNAME|token", body):
        return False

    expectations = {0: ("IN SYNC", 0), 2: ("DRIFT", 2), 1: ("ERROR", 1), 3: ("ERROR", 1)}
    for rc, (word, want_exit) in expectations.items():
        with tempfile.TemporaryDirectory() as tmp:
            result = _drift_script_runs(rc, tmp)
            if result[0] is None:
                return False
            exit_code, out, log, saved = result
            lines = out.splitlines()
            if exit_code != want_exit:
                return False
            if not any(ln.startswith(word) for ln in lines):
                return False
            for other in ("IN SYNC", "DRIFT", "ERROR"):
                if other != word and any(ln.startswith(other) for ln in lines):
                    return False
            if rc == 2 and "Plan: 0 to add, 2 to change, 0 to destroy." not in out:
                return False
            if not saved:
                return False
            calls = [ln.split() for ln in log.splitlines() if ln.strip()]
            if not calls or any(c[0] != "plan" for c in calls) or not any("-detailed-exitcode" in c for c in calls):
                return False
    return True


def _neighbor_descriptions_restored(data_dir):
    with tempfile.TemporaryDirectory() as tmp:
        merged = Path(tmp) / "merged.yaml"
        code, _, _ = run_nac_validate(data_dir, extra=["-o", str(merged)])
        if code != 0 or not merged.exists():
            return False
        model = _load_yaml(merged)
    for name in EXPECTED_DEVICES:
        try:
            neighbors = _bgp_of(model, name)["neighbors"]
        except (KeyError, TypeError):
            return False
        for n in neighbors:
            if n.get("description") != NEIGHBOR_NAMES.get(str(n.get("ip"))):
                return False
    return True


def check_todo_10():
    if not SCHEMA_FILE.exists() or not RULES_DIR.is_dir():
        return False
    if not _drift_script_ok():
        return False

    with tempfile.TemporaryDirectory() as upto:
        data10 = _data_dir_upto(upto, 10)
        code, _, _ = run_nac_validate(data10, schema=SCHEMA_FILE, rules=RULES_DIR, extra=["-f", "json"])
        if code != 0:
            return False
        if not _neighbor_descriptions_restored(data10):
            return False

    if _terraform_exe() is None or not os.environ.get("IOSXE_USERNAME") or not os.environ.get("IOSXE_PASSWORD"):
        return False
    code, _, _ = run_terraform(["init", "-no-color"])
    if code != 0:
        return False
    code, _, _ = run_terraform(["plan", "-detailed-exitcode", "-no-color"], timeout=900)
    return code == 0 if TOTAL_TODOS == 10 else code in (0, 2)


TESTS_DIR = ROOT / "tests"
TEST_FILE = TESTS_DIR / "verify_routers.robot"

PROBLEMS[11] = (
    "One of these is not right yet. tests/verify_routers.robot must be a nac-test template that\n"
    "turns the data model into Robot tests: per router a hostname test, per loopback a test, and per\n"
    "BGP neighbor a test that the session is established with the right AS. The names, hosts and\n"
    "values must come from the data, not be typed in. Login details come from the environment. And\n"
    "the tests must pass against the live routers."
)
EXPECTED[11] = (
    "15 tests: '<router> hostname' (3), '<router> Loopback<id>' (6), '<router> BGP neighbor <ip>' (6).\n"
    "hostname -> GET Cisco-IOS-XE-native:native/hostname, equals the hostname in the data.\n"
    "Loopback -> GET .../interface/Loopback=<id>, contains the loopback address from the data.\n"
    "BGP neighbor -> GET Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors, state fsm-established,\n"
    "AS equal to remote_as. Add a loopback or remove a neighbor in the data and the tests follow.\n"
    "Login from %{IOSXE_USERNAME} and %{IOSXE_PASSWORD}. nac-test exits 0 against the routers."
)
HINTS[11] = (
    "Three nested Jinja loops: devices, then device.configuration.interfaces.loopbacks, then\n"
    "device.configuration.routing.bgp.neighbors. Inside them {{ device.name }}, {{ device.host }},\n"
    "{{ loopback.id }}, {{ loopback.ipv4.address }}, {{ neighbor.ip }} and {{ neighbor.remote_as }}\n"
    "fill the blanks. Robot needs at least two spaces between a keyword and its arguments. If a live\n"
    "test fails, run curl against that router first (step 4) to see what it really returns."
)
SOLUTIONS[11] = """# tests/verify_routers.robot
*** Settings ***
Documentation     The live routers match the data model
Library           RequestsLibrary

*** Keywords ***
Router Get
    [Documentation]    GET one RESTCONF path from a router and return the data under its top-level key.
    [Arguments]    ${host}    ${path}
    ${auth}=    Create List    %{IOSXE_USERNAME}    %{IOSXE_PASSWORD}
    Create Session    ${host}    https://${host}    auth=${auth}    verify=${FALSE}
    ${headers}=    Create Dictionary    Accept=application/yang-data+json
    ${response}=    GET On Session    ${host}    /restconf/data/${path}    headers=${headers}    expected_status=200
    ${data}=    Evaluate    next(iter($response.json().values()))
    RETURN    ${data}

*** Test Cases ***
{% for device in iosxe.devices | default([]) %}
{{ device.name }} hostname
    [Tags]    iosxe    system
    ${hostname}=    Router Get    {{ device.host }}    Cisco-IOS-XE-native:native/hostname
    Should Be Equal    ${hostname}    {{ device.configuration.system.hostname }}

{% for loopback in device.configuration.interfaces.loopbacks | default([]) %}
{{ device.name }} Loopback{{ loopback.id }}
    [Tags]    iosxe    interfaces
    ${entries}=    Router Get    {{ device.host }}    Cisco-IOS-XE-native:native/interface/Loopback={{ loopback.id }}
    ${text}=    Convert To String    ${entries}[0]
    Should Contain    ${text}    {{ loopback.ipv4.address }}

{% endfor %}
{% for neighbor in device.configuration.routing.bgp.neighbors | default([]) %}
{{ device.name }} BGP neighbor {{ neighbor.ip }}
    [Tags]    iosxe    bgp
    ${neighbors}=    Router Get    {{ device.host }}    Cisco-IOS-XE-bgp-oper:bgp-state-data/neighbors
    ${found}=    Evaluate    [n for n in $neighbors['neighbor'] if n['neighbor-id'] == '{{ neighbor.ip }}']
    Should Not Be Empty    ${found}    no BGP session to {{ neighbor.ip }} on {{ device.name }}
    Should Be Equal    ${found}[0][session-state]    fsm-established
    Should Be Equal As Integers    ${found}[0][as]    {{ neighbor.remote_as }}

{% endfor %}
{% endfor %}
"""


def _nac_test_exe():
    return shutil.which("nac-test")


def _expected_tests(hosts=None, loopbacks_extra=None, drop_neighbor=None):
    """name -> list of substrings the rendered test body must contain."""
    hosts = hosts or {}
    tests = {}
    for name, info in EXPECTED_DEVICES.items():
        host = hosts.get(name, info["host"])
        tests[f"{name} hostname"] = [host, "Cisco-IOS-XE-native:native/hostname", name]
        lo = {0: info["loopback0"], 10: EXPECTED_BRANCH_LAN[name]}
        lo.update((loopbacks_extra or {}).get(name, {}))
        for lid, address in lo.items():
            tests[f"{name} Loopback{lid}"] = [host, f"interface/Loopback={lid}", address]
        for ip in sorted(EXPECTED_BGP_PEERS[name]):
            if drop_neighbor == (name, ip):
                continue
            tests[f"{name} BGP neighbor {ip}"] = [
                host, "bgp-state-data/neighbors", ip, "fsm-established", str(EXPECTED_BGP_AS),
            ]
    return tests


def _render_robot(data_dir, workdir):
    """Render the template with nac-test and return {test name: body text}, or None on failure."""
    exe = _nac_test_exe()
    if exe is None or not TEST_FILE.exists():
        return None
    out = Path(workdir) / "rendered"
    env = dict(os.environ)
    env.setdefault("IOSXE_USERNAME", "render-only")
    env.setdefault("IOSXE_PASSWORD", "render-only")
    try:
        proc = subprocess.run(
            [exe, "-d", str(data_dir), "-t", str(TESTS_DIR), "-o", str(out), "--render-only"],
            capture_output=True, text=True, timeout=300, env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    files = sorted(out.rglob("verify_routers.robot")) if out.exists() else []
    if proc.returncode != 0 or not files:
        return None

    tests, section, current = {}, None, None
    for line in files[0].read_text(encoding="utf-8").splitlines():
        if line.startswith("***"):
            section = line.strip("* ").lower()
            current = None
            continue
        if section not in ("test cases", "test case"):
            continue
        if line.strip() and not line[0].isspace() and not line.startswith("#"):
            current = line.strip()
            tests[current] = ""
        elif current is not None:
            tests[current] += line + "\n"
    return tests


def _tests_match(rendered, expected):
    if rendered is None or set(rendered) != set(expected):
        return False
    return all(all(piece in rendered[name] for piece in pieces) for name, pieces in expected.items())


def _robot_mutations():
    """(label, mutate(data_dir), expected tests) - the rendered tests must follow the data."""

    def new_loopback(d):
        path = d / "ospf.nac.yaml"
        model = _load_yaml(path)
        _device(model, "R11")["configuration"]["interfaces"]["loopbacks"].append(
            {"id": 20, "description": "GUEST", "ipv4": {"address": "172.16.20.1", "address_mask": "255.255.255.255"}}
        )
        path.write_text(yaml.safe_dump(model, sort_keys=False), encoding="utf-8")

    def lost_neighbor(d):
        path = d / "bgp.nac.yaml"
        model = _load_yaml(path)
        _bgp_of(model, "R12")["neighbors"].pop(0)
        path.write_text(yaml.safe_dump(model, sort_keys=False), encoding="utf-8")

    def moved_router(d):
        path = d / "devices.nac.yaml"
        model = _load_yaml(path)
        _device(model, "R12")["host"] = "10.10.10.99"
        path.write_text(yaml.safe_dump(model, sort_keys=False), encoding="utf-8")

    return [
        ("a loopback added to R11 -> a new test appeared", new_loopback,
         _expected_tests(loopbacks_extra={"R11": {20: "172.16.20.1"}})),
        ("a BGP neighbor removed from R12 -> its test disappeared", lost_neighbor,
         _expected_tests(drop_neighbor=("R12", "10.255.0.10"))),
        ("R12 given another management address -> its tests followed", moved_router,
         _expected_tests(hosts={"R12": "10.10.10.99"})),
    ]


def _robot_file_ok():
    if not TEST_FILE.exists():
        return False
    text = TEST_FILE.read_text(encoding="utf-8")
    if "%{IOSXE_USERNAME}" not in text or "%{IOSXE_PASSWORD}" not in text:
        return False
    stripped = text.replace("%{IOSXE_USERNAME}", "").replace("%{IOSXE_PASSWORD}", "")
    return not re.search(r"(?i)password|secret|token", stripped)


def check_todo_11():
    if not _robot_file_ok() or _nac_test_exe() is None:
        return False

    with tempfile.TemporaryDirectory() as tmp:
        data = _data_dir_upto(tmp, 11)
        if not _tests_match(_render_robot(data, tmp), _expected_tests()):
            return False

    for _label, mutate, expected in _robot_mutations():
        with tempfile.TemporaryDirectory() as tmp:
            data = _data_dir_upto(tmp, 11)
            mutate(data)
            if not _tests_match(_render_robot(data, tmp), expected):
                return False

    # syntax: Robot's dry run checks every keyword without contacting a router
    with tempfile.TemporaryDirectory() as tmp:
        data = _data_dir_upto(tmp, 11)
        env = dict(os.environ)
        env.setdefault("IOSXE_USERNAME", "dry-run")
        env.setdefault("IOSXE_PASSWORD", "dry-run")
        try:
            proc = subprocess.run(
                [_nac_test_exe(), "-d", str(data), "-t", str(TESTS_DIR), "-o", str(Path(tmp) / "dry"), "--dry-run"],
                capture_output=True, text=True, timeout=300, env=env,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if proc.returncode != 0:
            return False

    # the live run: the routers must pass every test
    if not os.environ.get("IOSXE_USERNAME") or not os.environ.get("IOSXE_PASSWORD"):
        return False
    with tempfile.TemporaryDirectory() as tmp:
        data = _data_dir_upto(tmp, 11)
        try:
            proc = subprocess.run(
                [_nac_test_exe(), "-d", str(data), "-t", str(TESTS_DIR), "-o", str(Path(tmp) / "live")],
                capture_output=True, text=True, timeout=900,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return proc.returncode == 0


CHECKS = {
    1: check_todo_1, 2: check_todo_2, 3: check_todo_3, 4: check_todo_4,
    5: check_todo_5, 6: check_todo_6, 7: check_todo_7, 8: check_todo_8,
    9: check_todo_9, 10: check_todo_10,
    11: check_todo_11,
}


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
        5: "[5] Connecting the data model to Terraform...",
        6: "[6] First push to R10, R11 and R12...",
        7: "[7] Static routes and an ACL...",
        8: "[8] OSPF across the branch routers...",
        9: "[9] BGP peering...",
        10: "[10] Detecting and reconciling drift...",
        11: "[11] Verifying live state with nac-test...",
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
    elif number == 5:
        console.print("  main.tf -> module nac-iosxe reads data/")
        console.print("  no credentials and no provider block in any .tf file")
        console.print("  terraform init -> ok")
        console.print("  terraform validate -> ok")
    elif number == 6:
        console.print("  main.tf -> all three routers are managed")
        console.print("  IOSXE_USERNAME and IOSXE_PASSWORD are set in this terminal")
        console.print("  terraform plan -> no changes (R10, R11 and R12 match the data model)")
    elif number == 7:
        for name, routes in EXPECTED_ROUTES.items():
            hops = ", ".join(f"{prefix}/32 via {hop}" for (prefix, _mask), hop in routes.items())
            console.print(f"  {name} -> {hops}")
        console.print(f"  every router -> ACL {ACL_NAME} applied inbound on Loopback0")
        console.print("  real data -> passes schema and rules 101, 102, 103 (exit 0)")
        for label, _ in _routing_schema_mutations():
            console.print(f"  injected: {label} -> rejected (exit 2)")
        for label, _ in _routing_rule_mutations():
            console.print(f"  injected: {label} -> rule 103 fired (exit 1)")
        console.print("  terraform plan -> no changes")
    elif number == 8:
        for name, lan in EXPECTED_BRANCH_LAN.items():
            console.print(f"  {name} -> Loopback10 {lan}/32, OSPF 1, router ID {EXPECTED_DEVICES[name]['loopback0']}")
        console.print("  every router -> three networks in area 0, both loopbacks passive")
        console.print("  real data -> passes schema and rules 101 to 104 (exit 0)")
        for label, _ in _ospf_schema_mutations():
            console.print(f"  injected: {label} -> rejected (exit 2)")
        for label, _, rule_id in _ospf_rule_mutations():
            console.print(f"  injected: {label} -> rule {rule_id} fired (exit 1)")
        console.print("  terraform plan -> no changes")
    elif number == 9:
        for name, lan in EXPECTED_BRANCH_LAN.items():
            peers = " ".join(sorted(EXPECTED_BGP_PEERS[name]))
            console.print(f"  {name} -> AS {EXPECTED_BGP_AS}, peers {peers}, advertises {lan}/32")
        console.print("  every neighbor -> sourced from Loopback0 and activated in ipv4 unicast")
        console.print("  real data -> passes schema and rules 101 to 105 (exit 0)")
        for label, _ in _bgp_schema_mutations():
            console.print(f"  injected: {label} -> rejected (exit 2)")
        for label, _, rule_id in _bgp_rule_mutations():
            console.print(f"  injected: {label} -> rule {rule_id} fired (exit 1)")
        console.print("  terraform plan -> no changes")
    elif number == 10:
        console.print("  drift_check.sh -> plan exit 0 prints IN SYNC and exits 0")
        console.print("  drift_check.sh -> plan exit 2 prints DRIFT and the Plan line, exits 2")
        console.print("  drift_check.sh -> any other plan exit prints ERROR, exits 1")
        console.print("  drift_check.sh -> only ever runs plan (no apply, no destroy)")
        console.print("  BGP neighbor descriptions -> back to R10, R11, R12")
        console.print("  terraform plan -> no changes")
    elif number == 11:
        console.print("  tests/verify_routers.robot -> rendered by nac-test from the data model")
        console.print("  15 tests: 3 hostname, 6 loopback, 6 BGP neighbor, all built from the data")
        console.print("  login -> read from IOSXE_USERNAME and IOSXE_PASSWORD, none in the file")
        for label, _, _ in _robot_mutations():
            console.print(f"  injected: {label}")
        console.print("  robot dry run -> every keyword resolves")
        console.print("  live run -> every test passes on R10, R11 and R12")


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
        lexer = {4: "python", 5: "terraform", 6: "terraform", 7: "text", 8: "text", 9: "text", 10: "bash", 11: "text"}.get(failed, "yaml")
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
