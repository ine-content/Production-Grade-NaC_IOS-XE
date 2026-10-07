# TODO 03 — Validate Structure with a Schema

## Topics Covered

```
✓ Syntactic validation: is the data the right shape?
✓ A yamale schema: str(), int(), bool(), ip(), include(), list()
✓ Optional fields with required=False
✓ Strict mode: unknown or misspelled keys are errors
✓ nac-validate exit codes
```

## Recap

TODO 01 and TODO 02 are solved in this folder, so `data/devices.nac.yaml` and `data/common.nac.yaml` are already there. Your job now is the schema that checks them.

## Scenario

Valid YAML isn't the same as a valid network. `host: 10.10.10.999` is fine as YAML, but that address doesn't exist. A typo like `hostnaem:` is fine as YAML too, and it would quietly configure nothing. A schema catches both before a router is involved.

`nac-validate` checks every file against a schema and exits with a code you can use in a pipeline:

| Exit code | Meaning |
|-----------|---------|
| 0 | Everything passed |
| 1 | A business rule failed (that's TODO 04) |
| 2 | Syntax or schema error (this TODO) |
| 3 | Configuration problem, for example a missing schema |

Two things to remember for this lab. First, each file is checked on its own. `common.nac.yaml` has no `host`, so `host` can't be required, and anything that's allowed to be missing needs `required=False`. Second, strict mode is on, so any key the schema doesn't mention is an error. That's how typos get caught.

## Worked Example

A schema starts with the top-level keys, then a `---` line, then named blocks that the data points at with `include('name')`. This one is for a made-up `vlans` list:

```yaml
vlans: list(include('vlan'), required=False)
---
vlan:
  id: int(min=1, max=4094)
  name: str(required=False)
  shutdown: bool(required=False)
```

| Validator | Accepts |
|-----------|---------|
| `str()` | text |
| `int(min=0)` | a whole number, 0 or higher |
| `bool()` | true or false |
| `ip(version=4)` | a valid IPv4 address |
| `list(include('x'))` | a list where each item matches block `x` |
| `include('x', required=False)` | a mapping that matches block `x`, and may be missing |

Add `required=False` to any validator to make that key optional.

## Notation Used Below

The skeletons in the Steps section use one kind of blank:

```
...   - replace this with your own value or expression.
```

Everything else in a skeleton is already filled in. Leave it alone.

## Working Folder

Do everything for this TODO from its own folder. Open a terminal and run:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-03-Validate-Structure-with-a-Schema
```

Change the path if you put the course folder somewhere else.

## Steps

```
1. Create .schema.yaml in this folder (the dot at the start matters).

2. Replace each ... below with the right validator for that field. The
   fields are in data/devices.nac.yaml and data/common.nac.yaml.

     - A device must have a name. host is an IPv4 address but can be
       missing. configuration can be missing too.
     - In system: hostname is text, ip_routing is true/false,
       ip_domain_name is text, ip_domain_lookup is true/false. All four
       are optional.
     - A loopback needs a whole-number id (0 or higher). description is
       optional text. ipv4 is optional.
     - ipv4 needs both an address and a mask, each an IPv4 address.

   Complete the skeleton below:

     iosxe: include('iosxe', required=False)
     ---
     iosxe:
       devices: list(include('device'), required=False)
     device:
       name: ...
       host: ...
       configuration: include('configuration', required=False)
     configuration:
       system: include('system', required=False)
       interfaces: include('interfaces', required=False)
     system:
       hostname: ...
       ip_routing: ...
       ip_domain_name: ...
       ip_domain_lookup: ...
     interfaces:
       loopbacks: list(include('loopback'), required=False)
     loopback:
       id: ...
       description: ...
       ipv4: include('ipv4', required=False)
     ipv4:
       address: ...
       address_mask: ...

3. Save, then run: python grading.py
```

## Test It Yourself (without the grader)

First, your real data must pass:

```
nac-validate data -s .schema.yaml
echo $?
```

You want `Syntax validation: PASSED` and exit code `0`.

Then make sure the schema rejects bad data. You do this by breaking your real data on purpose, running the validator, and putting the file back. The `sed -i.bak` command edits the file and saves the original next to it as `devices.nac.yaml.bak`, so restoring is one `mv`:

First, break the data and run the validator. Don't restore the file yet:

```
sed -i.bak 's/address: 10.255.0.10/address: banana/' data/devices.nac.yaml
nac-validate data -s .schema.yaml
echo $?
```

This time you want `FAILED`, exit code `2`, and a message that names the exact key, like this:

```
iosxe.devices.[name=R10].configuration.interfaces.loopbacks.[id=0].ipv4.address: 'banana' is not a ip.
```

Once you've seen that, put the original back. Don't skip this:

```
mv data/devices.nac.yaml.bak data/devices.nac.yaml
```

Repeat with a different break each time. Each one should print `2`. Restore each file before the next break:

```
# ip_routing is neither true nor false
sed -i.bak 's/ip_routing: true/ip_routing: maybe/' data/common.nac.yaml
nac-validate data -s .schema.yaml; echo $?
mv data/common.nac.yaml.bak data/common.nac.yaml

# not a valid IP address
sed -i.bak 's/host: 10.10.10.11/host: 10.10.10.999/' data/devices.nac.yaml
nac-validate data -s .schema.yaml; echo $?
mv data/devices.nac.yaml.bak data/devices.nac.yaml

# misspelled key
sed -i.bak 's/address_mask:/adress_mask:/' data/devices.nac.yaml
nac-validate data -s .schema.yaml; echo $?
mv data/devices.nac.yaml.bak data/devices.nac.yaml
```

Every one of them should exit `2`. If one of them exits `0`, your schema is too loose for that field. When you're done, run `nac-validate data -s .schema.yaml` once more. It should pass again, which proves everything was restored.

## Grading Check

```
python grading.py
```

The grader re-checks TODO 01 and TODO 02 first. Then it runs `nac-validate` on your real data, which has to exit 0. After that, in a temporary copy, it breaks the data seven different ways, one at a time: a bad host IP, a missing name, a loopback id written as text, a bad address, a bad mask, `ip_routing: maybe`, and a misspelled key. Each one has to make `nac-validate` exit with code 2. Your real files are never touched.

Before you complete this TODO:

```
TODO 03 - Validate Structure with a Schema
────────────────────────────────────────────────────────────────────────────────

[3] Validating structure with a schema...

✗ TODO 03 Not Complete

The pipeline cannot continue because the schema does not yet accept good data and
reject bad data.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 03 - Validate Structure with a Schema
────────────────────────────────────────────────────────────────────────────────

[3] Validating structure with a schema...
  real data -> accepted (exit 0)
  injected: bad host IP -> rejected (exit 2)
  injected: missing name -> rejected (exit 2)
  injected: loopback id as text -> rejected (exit 2)
  injected: loopback address not an IP -> rejected (exit 2)
  injected: loopback mask not an IP -> rejected (exit 2)
  injected: ip_routing as text -> rejected (exit 2)
  injected: misspelled key -> rejected (exit 2)

✓ TODO 03 Complete
Your schema accepts the real data and rejects every kind of bad input we tried.
```

---
