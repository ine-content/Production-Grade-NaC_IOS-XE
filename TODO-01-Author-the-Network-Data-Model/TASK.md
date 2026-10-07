---
# TODO 01 — Author the Network Data Model
---

<details>
<summary><strong>Overview</strong></summary>

This course is about Network as Code (NaC) for Cisco IOS-XE, the approach published at netascode.cisco.com. You don't type commands on a router. You describe the network in plain YAML, check that description, and let Terraform push it. Over twelve labs you will:

```
✓ Describe a network in a YAML data model
✓ Split shared settings out into their own file
✓ Check the structure with a schema, and the business rules with Python
✓ Push the model to real routers with Terraform and the nac-iosxe module
✓ Re-apply safely and catch drift
✓ Test the live network afterwards
✓ Put a CI/CD gate and an audit trail around all of it
```

You won't write a lot of YAML. The point is a pipeline that is safe to run against real routers, again and again, without someone watching it.

</details>

---

<details>
<summary><strong>Business Scenario</strong></summary>

```
- Meridian Retail has three branch sites, each with one IOS-XE router. Every
  change used to be typed by hand, router by router. During one routine change
  somebody gave two routers the same loopback address, and routing was quietly
  broken for a day before anyone noticed.

- Leadership wants this fixed for good:

  • No hand-typed router changes. Every change goes through code.
  • The network is described once, in a data model, kept in version control.
  • Bad data is rejected before it gets anywhere near a router.
  • Business rules (no duplicate addresses, names must match) are checked
    automatically.
  • Every push is checked against the live routers afterwards.
  • A change made outside the pipeline has to be spotted and corrected.

- The three routers are real IOS-XE devices in the lab:

    R10  (Raleigh  - rdu01, prod)      10.10.10.10
    R11  (Austin   - aus02, prod)      10.10.10.11
    R12  (Seattle  - sea03, staging)   10.10.10.12

  Your lab machine (10.10.10.250) is on the same 10.10.10.0/24 segment. That
  segment is also how you reach the routers, so this course never changes its
  IP address and never puts an ACL on it.
```

</details>

---

<details>
<summary><strong>Final Pipeline</strong></summary>

```
Author the Network Data Model
        ↓
Layer Shared Settings Across Files
        ↓
Validate Structure with a Schema
        ↓
Enforce Business Rules
        ↓
Connect the Data Model to Terraform
        ↓
First Push to R10-R12
        ↓
Static Routes and ACLs
        ↓
OSPF Across the Branch Routers
        ↓
BGP Peering
        ↓
Detect and Reconcile Drift
        ↓
Verify Live State with nac-test
        ↓
Gate the Pipeline and Emit an Audit Log
```

Each stage is one lab, TODO 01 to TODO 12. TODO 01 to TODO 04 run entirely on your own machine. No router is touched until TODO 06.

</details>

---

<details>
<summary><strong>Lab Files</strong></summary>

Run every command from this lab's own folder.

```
TODO-01-Author-the-Network-Data-Model/
├── data/
│   └── (empty - you create devices.nac.yaml here)
├── grading.py
├── requirements.txt
└── TASK.md
```

You create:

```
data/devices.nac.yaml
```

Don't edit `grading.py`.

</details>

---

<details>
<summary><strong>Before You Start</strong></summary>

```
pip install -r requirements.txt
nac-validate --version
```

If your lab is offline, follow OFFLINE-SETUP.md in the course root first.

</details>

---

<details>
<summary><strong>Run the grader</strong></summary>

```
python grading.py
```

TODO 01 only reads the YAML file you create, so nothing else needs to be running.

</details>

---

# TODO 01 — Author the Network Data Model

## Topics Covered

```
✓ Declarative data models
✓ YAML basics: mappings, lists, nesting
✓ The netascode IOS-XE data model (iosxe -> devices -> configuration)
✓ Keeping credentials out of the data model
```

## Business Requirements

| Device | Management host | Hostname | Loopback0 (router ID) |
|--------|-----------------|----------|------------------------|
| R10    | 10.10.10.10     | R10      | 10.255.0.10/32         |
| R11    | 10.10.10.11     | R11      | 10.255.0.11/32         |
| R12    | 10.10.10.12     | R12      | 10.255.0.12/32         |

Give every loopback the description `ROUTER-ID`. A /32 has the mask `255.255.255.255`.

Don't put usernames, passwords or secrets in this file. The routers' credentials come from environment variables later in the course. The grader fails this TODO if it finds a key that looks like a credential.

## Worked Example

A data model is a nested structure. The top key is the platform (`iosxe`), under it is a list of `devices`, and each device has a `name`, a management `host` and a `configuration` block. Here is a made-up device, `EDGE1`, with a hostname and one loopback:

```yaml
iosxe:
  devices:
    - name: EDGE1
      host: 192.0.2.1
      configuration:
        system:
          hostname: EDGE1
        interfaces:
          loopbacks:
            - id: 99
              description: EXAMPLE
              ipv4:
                address: 192.0.2.99
                address_mask: 255.255.255.255
```

`devices` is a list, so each device starts with `- `. `loopbacks` is a list too, because a router can have several. Indent with 2 spaces. Tabs break YAML, and one wrong indent changes what the file means.

## Steps

```
1. Create the file data/devices.nac.yaml.

2. Describe all three routers (R10, R11 and R12) using the shape in the
   Worked Example and the values in the Business Requirements table. Each
   device needs a name, a host, system.hostname, and one loopback with
   id 0, the description ROUTER-ID, an address and a mask.

3. Leave out any credentials.

4. Save, then run: python grading.py
```

## Test It Yourself (without the grader)

Run these from inside this folder.

```
# 1. Is the file valid YAML? (prints YAML OK, or an error with a line number)
python -c "import yaml; yaml.safe_load(open('data/devices.nac.yaml')); print('YAML OK')"

# 2. Read back what you wrote, one labeled line per router
python -c "import yaml; d=yaml.safe_load(open('data/devices.nac.yaml')); [print('name=%-4s host=%-12s hostname=%-4s loopback0=%s' % (x['name'], x['host'], x['configuration']['system']['hostname'], x['configuration']['interfaces']['loopbacks'][0]['ipv4']['address'])) for x in d['iosxe']['devices']]"

# 3. Make sure no credentials slipped in (no output means none found)
grep -inE 'password|secret|username|token|community' data/*.yaml
```

Command 2 should print exactly this:

```
name=R10  host=10.10.10.10  hostname=R10  loopback0=10.255.0.10
name=R11  host=10.10.10.11  hostname=R11  loopback0=10.255.0.11
name=R12  host=10.10.10.12  hostname=R12  loopback0=10.255.0.12
```

`name` is the device's name in the data model, which is how the tools find and merge it. `host` is the management IP the tools connect to. `hostname` is the name the router will be given. `loopback0` is the address of its Loopback0 interface.

If a line is missing, has a wrong value, or the command crashes with a `KeyError`, compare your file with the Worked Example. A crash usually means a key is misspelled or sits at the wrong indent.

## Grading Check

```
python grading.py
```

The grader loads your YAML and compares every device, host, hostname, loopback address and mask with the table above. It also fails if a credential-style key shows up anywhere.

Before you complete this TODO:

```
TODO 01 - Author the Network Data Model
────────────────────────────────────────────────────────────────────────────────

[1] Authoring the network data model...

✗ TODO 01 Not Complete

The pipeline cannot continue because the network data model has not been authored
correctly yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 01 - Author the Network Data Model
────────────────────────────────────────────────────────────────────────────────

[1] Authoring the network data model...
  R10 -> host 10.10.10.10, Loopback0 10.255.0.10/32
  R11 -> host 10.10.10.11, Loopback0 10.255.0.11/32
  R12 -> host 10.10.10.12, Loopback0 10.255.0.12/32

✓ TODO 01 Complete
data/devices.nac.yaml describes R10, R11 and R12 exactly as the business requirements say.
```

---
