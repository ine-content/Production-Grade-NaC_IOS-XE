# TODO 04 — Enforce Business Rules

## Topics Covered

```
✓ Semantic validation: does the data make sense, not just look right?
✓ Writing nac-validate rules in Python
✓ Why rules run on the merged model
✓ Machine-readable results with --format json
```

## Recap

TODO 01 to TODO 03 are solved in this folder, including `.schema.yaml`. The data is well-formed. Now you check that it makes sense.

## Scenario

A schema can't tell that two routers got the same loopback address. Each address is a perfectly valid IPv4 address, so the schema passes it, and the network is still broken. Checks like this are business logic, and `nac-validate` lets you write them as small Python classes.

Rules see the merged model (all the files combined), so they can compare one device with another. A rule returns a list of problems. An empty list means the rule is happy. If any rule returns a problem, `nac-validate` exits with code 1.

You'll write two rules:

| Rule id | What it enforces |
|---------|------------------|
| 101 | A device's `hostname` must equal its device `name` |
| 102 | No IPv4 address (a device `host` or any loopback address) may appear in more than one place |

## Worked Example

A rule is one `.py` file in `rules/`. It holds one class called `Rule` that extends `RuleBase`. Here is a made-up rule that flags any VLAN named `TEST`:

```python
from nac_validate import RuleBase


class Rule(RuleBase):
    id = "900"
    description = "No VLAN may be named TEST"
    severity = "MEDIUM"

    @classmethod
    def match(cls, data):
        results = []
        for device in data.get("iosxe", {}).get("devices", []):
            vlans = device.get("configuration", {}).get("vlan", {}).get("vlans", [])
            for vlan in vlans:
                if vlan.get("name") == "TEST":
                    results.append(f"{device['name']} has a VLAN named TEST")
        return results
```

`id` and `description` are required. `severity` is optional. `match` is a `classmethod`, and it gets the merged data as `data`. The `.get(..., {})` and `.get(..., [])` calls stop the rule from crashing when a device doesn't have that section at all.

## Notation Used Below

The skeletons in the Steps section use one kind of blank:

```
...   - replace this with your own value or expression.
```

Everything else in a skeleton is already filled in. Leave it alone.

## Working Folder

Do everything for this TODO from its own folder. Open a terminal and run:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-04-Enforce-Business-Rules
```

Change the path if you put the course folder somewhere else.

## Steps

```
1. Create two files in the rules/ folder:

     rules/101_hostname_matches_name.py
     rules/102_unique_addresses.py

2. Rule 101. Fill in the blanks so it reports any device whose hostname
   is different from its name:

     from nac_validate import RuleBase


     class Rule(RuleBase):
         id = "..."
         description = "..."
         severity = "HIGH"

         @classmethod
         def match(cls, data):
             results = []
             for device in data.get("iosxe", {}).get("devices", []):
                 hostname = ...
                 if ...:
                     results.append(...)
             return results

   The hostname is at configuration -> system -> hostname.

3. Rule 102. Collect every address along with its owner, then report any
   address that has more than one owner:

     from nac_validate import RuleBase


     class Rule(RuleBase):
         id = "..."
         description = "..."
         severity = "HIGH"

         @classmethod
         def match(cls, data):
             users = {}
             for device in data.get("iosxe", {}).get("devices", []):
                 # gather the device host and every loopback address
                 # as (where, address) pairs
                 pairs = ...
                 for where, address in pairs:
                     users.setdefault(address, []).append(f"{device['name']}.{where}")
             return [... for address, owners in users.items() if ...]

   Loopback addresses are at configuration -> interfaces -> loopbacks ->
   ipv4 -> address. A device might have no loopbacks or no host, so use
   .get() with a default.

4. Save, then run: python grading.py
```

## Test It Yourself (without the grader)

See that both rules are loaded:

```
nac-validate data -s .schema.yaml -r rules --list-rules
```

You should see `[101]` and `[102]` listed. Then your real data must pass:

```
nac-validate data -s .schema.yaml -r rules
echo $?
```

You want `Semantic validation: PASSED` and exit code `0`.

Now make each rule fire. You break your real data on purpose, run the validator, and put the file back. `sed -i.bak` saves the original as `devices.nac.yaml.bak`, so restoring is one `mv`. Restore before the next break.

Rule 101, R11 gets the wrong hostname:

```
sed -i.bak 's/hostname: R11/hostname: ROUTER-11/' data/devices.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
```

Expect exit code `1` and a block like this:

```
[RULE 101] Device hostname must equal its device name
  • iosxe.devices[name=R11].configuration.system.hostname - 'ROUTER-11' does not match the device name
```

Then put the file back:

```
mv data/devices.nac.yaml.bak data/devices.nac.yaml
```

Rule 102, R11 reuses R10's loopback address:

```
sed -i.bak 's/address: 10.255.0.11/address: 10.255.0.10/' data/devices.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
```

Expect exit code `1` and:

```
[RULE 102] No IPv4 address may be used more than once
  • address 10.255.0.10 is used by R10.loopback0, R11.loopback0
```

Then put the file back:

```
mv data/devices.nac.yaml.bak data/devices.nac.yaml
```

Two more to try, with the same pattern. Make R12's `host` equal to R10's, and give R11's loopback the management address `10.10.10.11`:

```
sed -i.bak 's/host: 10.10.10.12/host: 10.10.10.10/' data/devices.nac.yaml
nac-validate data -s .schema.yaml -r rules; echo $?
mv data/devices.nac.yaml.bak data/devices.nac.yaml

sed -i.bak 's/address: 10.255.0.11/address: 10.10.10.11/' data/devices.nac.yaml
nac-validate data -s .schema.yaml -r rules; echo $?
mv data/devices.nac.yaml.bak data/devices.nac.yaml
```

Both should trigger rule 102 and nothing else. When you're done, run `nac-validate data -s .schema.yaml -r rules` once more. It should pass again, which proves everything was restored.

## Grading Check

```
python grading.py
```

The grader re-checks TODO 01 to TODO 03 first. Then it confirms rules 101 and 102 are listed, and that your real data has no violations (exit 0). After that, in a temporary copy, it injects four problems: a hostname mismatch, two loopbacks sharing an address, two devices sharing a host IP, and a loopback reusing a management IP. Each one has to make `nac-validate` exit 1 with the right rule id, and only that id, in the JSON output. Your real files are never touched.

Before you complete this TODO:

```
TODO 04 - Enforce Business Rules
────────────────────────────────────────────────────────────────────────────────

[4] Enforcing business rules...

✗ TODO 04 Not Complete

The pipeline cannot continue because the semantic rules do not yet catch the
business-rule violations.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 04 - Enforce Business Rules
────────────────────────────────────────────────────────────────────────────────

[4] Enforcing business rules...
  real data -> no violations (exit 0)
  injected: hostname does not match name -> rule 101 fired (exit 1)
  injected: two loopbacks share an address -> rule 102 fired (exit 1)
  injected: two devices share a host IP -> rule 102 fired (exit 1)
  injected: a loopback reuses a management IP -> rule 102 fired (exit 1)

✓ TODO 04 Complete
Your semantic rules catch hostname mismatches and duplicate addresses.
```

---
