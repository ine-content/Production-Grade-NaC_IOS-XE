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

A schema can't tell that two routers got the same loopback address, or that a router-ID loopback was given a /24 instead of a /32. Each value is a perfectly valid IPv4 address or mask, so the schema passes it, and the network is still broken. Checks like this are business logic, and `nac-validate` lets you write them as small Python classes.

Rules see the merged model (all the files combined), so they can compare one device with another. A rule returns a list of problems. An empty list means the rule is happy. If any rule returns a problem, `nac-validate` exits with code 1.

You'll write two rules:

| Rule id | What it enforces |
|---------|------------------|
| 101 | A device's `hostname` must equal its device `name` |
| 102 | Every loopback address must be unique across all devices, and every loopback mask must be `255.255.255.255` (a /32) |

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

   What goes in each blank:

     id = "..."           the rule number as text, in quotes: "101"
     description = "..."  one sentence that says what the rule demands,
                          for example: Device hostname must equal its device name
     hostname = ...       the hostname of this device. It is at
                          configuration -> system -> hostname. Follow the
                          same .get() pattern as the Worked Example, and
                          leave out the default on the last step so a
                          missing hostname gives None
     if ...:              the test for a problem: the hostname is NOT equal
                          to the device's name. In Python, "not equal" is !=
     results.append(...)  one message for the problem, as text. Say which
                          device is wrong and what its hostname is, for
                          example: R11 has hostname R10. The device name is
                          device["name"]

   The grader does not read your message, only the rule id and that the rule
   fires. A clear message is still worth writing, because it is what an
   engineer reads when the rule fails.

3. Rule 102. Every loopback must follow two rules:

     a) the mask must be /32 (255.255.255.255)
     b) the Loopback 0 address must be unique to each device. The rule goes
        through every loopback, so any other loopback you add later
        (Loopback10 in TODO 08) must be unique too

   Check every loopback on every device. Add one message to results for each
   rule it breaks. The dictionary "seen" remembers each address and which
   loopback used it first, so you can spot an address that comes up twice.

   Fill in the blanks:

     from nac_validate import RuleBase


     class Rule(RuleBase):
         id = "..."
         description = "..."
         severity = "HIGH"

         @classmethod
         def match(cls, data):
             results = []
             seen = {}   # address -> the loopback that used it first
             for device in data.get("iosxe", {}).get("devices", []):
                 loopbacks = ...
                 for loopback in loopbacks:
                     label = ...      # for example "R10 Loopback0"
                     address = ...
                     mask = ...
                     if address:
                         if ...:      # MASK CHECK: the mask is not 255.255.255.255
                             results.append(...)    # message about the mask
                         if ...:      # DUPLICATE CHECK: the address is already in seen
                             results.append(...)    # message about the duplicate
                         seen[address] = label
             return results

   What goes in each blank:

     id = "..."           the rule number as text, in quotes: "102"
     description = "..."  one sentence that says what the rule demands
     loopbacks = ...      the list of loopbacks of this device. It is at
                          configuration -> interfaces -> loopbacks. Use
                          .get() with a default of [] on the last step, so a
                          device with no loopbacks gives an empty list
     label = ...          text that names this loopback, for example
                          "R10 Loopback0". Build it from device["name"] and
                          loopback["id"]. Use str(...) around the id, because
                          it is a number
     address = ...        the loopback's IP address, at ipv4 -> address
     mask = ...           the loopback's mask, at ipv4 -> address_mask
                          (use .get() on both, so a loopback with no ipv4
                          gives None and is skipped by "if address:")
     if ...:              (MASK CHECK) the mask is NOT 255.255.255.255. The
                          mask is text, so compare it with a string
     results.append(...)  (MASK CHECK) a message that names the loopback and
                          its wrong mask, for example:
                          R12 Loopback0 mask is 255.255.255.0
     if ...:              (DUPLICATE CHECK) the address is already in seen.
                          The test for "already in the dictionary" is:
                          address in seen
     results.append(...)  (DUPLICATE CHECK) a message that names the address
                          and both loopbacks, for example:
                          10.255.0.10 is used by R10 Loopback0 and R11 Loopback0
                          The first loopback is seen[address]

   Why seen[address] = label comes last: it saves this loopback for the
   later ones to compare with. If it came first, every loopback would
   appear to be a duplicate of itself.

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
[RULE 102] Every loopback address must be unique and use a /32 mask
  • 10.255.0.10 is used by R10 Loopback0 and R11 Loopback0
```

Then put the file back:

```
mv data/devices.nac.yaml.bak data/devices.nac.yaml
```

One more to try, with the same pattern. Give R12's loopback a /24 mask instead of a /32. The `sed` range only changes lines from the `name: R12` line to the end of the file, so it only touches R12:

```
sed -i.bak '/name: R12/,$s/address_mask: 255.255.255.255/address_mask: 255.255.255.0/' data/devices.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
```

Expect exit code `1` and a message like `R12 Loopback0 mask is 255.255.255.0, it must be 255.255.255.255`, with rule 102 and nothing else. Then put the file back:

```
mv data/devices.nac.yaml.bak data/devices.nac.yaml
```

When you're done, run `nac-validate data -s .schema.yaml -r rules` once more. It should pass again, which proves everything was restored.

## Grading Check

```
python grading.py
```

The grader re-checks TODO 01 to TODO 03 first. Then it confirms rules 101 and 102 are listed, and that your real data has no violations (exit 0). After that, in a temporary copy, it injects three problems: a hostname mismatch, two loopbacks sharing an address, and a loopback with a /24 mask instead of a /32. Each one has to make `nac-validate` exit 1 with the right rule id, and only that id, in the JSON output. Your real files are never touched.

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
  injected: a loopback is not a /32 -> rule 102 fired (exit 1)

✓ TODO 04 Complete
Your semantic rules catch hostname mismatches, duplicate loopback addresses and loopbacks that are not a /32.
```

---
