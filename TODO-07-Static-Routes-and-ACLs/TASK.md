# TODO 07 — Static Routes and ACLs

## Topics Covered

```
✓ Adding a new feature to the data model in its own file
✓ Teaching the schema about the new keys
✓ A rule that checks references: an ACL a device uses must exist
✓ Static routes and standard ACLs in the nac-iosxe model
✓ Carrying Terraform's record from one TODO folder to the next
✓ Verifying routes and an ACL on the router
```

## Recap

TODO 06 is solved in this folder. The routers have their domain settings and Loopback0, and `main.tf` manages all three. In this TODO you add routing and an ACL, and you take the whole change through the same path as before: data, schema, rule, plan, apply.

## Scenario

Right now each router knows only its own Loopback0. R10 has no idea that 10.255.0.11 exists, so it can't reach R11's loopback. The three routers sit on one shared segment, 10.10.10.0/24, and that segment is also how you manage them. So each router gets a static route to the other two loopbacks, with the other router's management address as the next hop.

The same TODO adds a standard ACL named `LOOPBACK-NET` on every router and applies it inbound on Loopback0. The ACL goes on the loopback and nowhere else. The management interface never gets an ACL. To be straight about it: an ACL on a loopback filters very little, because traffic for a loopback address arrives on another interface. It's here so you can practise modelling an ACL and its binding without risking your connection to the routers.

Everything new lives in a new file, `data/routing.nac.yaml`. You saw in TODO 02 that files merge by device name. The loopback merges by its `id`, so the new file only needs `id: 0` and the one new key.

Two things will fail until you deal with them. The schema is strict, so it rejects the new keys until you add them. And a typo in an ACL name would pass the schema and break on the router, so you'll write rule 103 to catch it.

## Worked Example

A made-up router, `EDGE1`, with one static route and one ACL applied to a loopback. The addresses come from the ranges reserved for documentation:

```yaml
iosxe:
  devices:
    - name: EDGE1
      configuration:
        routing:
          static_routes:
            - prefix: 198.51.100.0
              mask: 255.255.255.0
              next_hops:
                - ip: 192.0.2.254
        access_lists:
          standard:
            - name: GUEST-NET
              entries:
                - sequence: 10
                  action: deny
                  prefix: 203.0.113.0
                  prefix_mask: 0.0.0.255
                - sequence: 20
                  action: permit
                  any: true
        interfaces:
          loopbacks:
            - id: 99
              ipv4:
                access_group_in: GUEST-NET
```

Things to notice:

- `static_routes` is a list. Each route has a `prefix`, a `mask` and a list of `next_hops`, each with an `ip`.
- An ACL entry needs a `sequence` and an `action`. The `prefix_mask` in an ACL is wildcard bits, so `0.0.0.255` means the first three numbers must match. It's the opposite of a subnet mask.
- `any: true` matches everything.
- The loopback only mentions what is new. Its address is in the other file.

## Technical Requirements

Static routes, all with mask 255.255.255.255:

| Router | Prefix | Next hop |
|--------|--------|----------|
| R10 | 10.255.0.11 | 10.10.10.11 |
| R10 | 10.255.0.12 | 10.10.10.12 |
| R11 | 10.255.0.10 | 10.10.10.10 |
| R11 | 10.255.0.12 | 10.10.10.12 |
| R12 | 10.255.0.10 | 10.10.10.10 |
| R12 | 10.255.0.11 | 10.10.10.11 |

On every router, a standard ACL named `LOOPBACK-NET`:

| Sequence | Action | Match |
|----------|--------|-------|
| 10 | permit | 10.255.0.0, wildcard 0.0.0.255 |
| 20 | deny | any |

On every router, `LOOPBACK-NET` is applied inbound on Loopback0 (`access_group_in`).

Don't put routes, ACLs or an `access_group_in` anywhere else. In particular, nothing goes on the management interface.

## Notation Used Below

Skeletons in the Steps section use one kind of blank:

```
...   - replace this with your own value or expression.
```

Everything else in a skeleton is already filled in and must stay as it is.

## Working Folder

Do everything for this TODO from its own folder. Open a terminal and run:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-07-Static-Routes-and-ACLs
```

Change the path if you put the course folder somewhere else.

## Steps

Each step says where to run its commands. LAB MACHINE means a normal terminal on the lab machine, in this folder. ROUTER means the router's own command line (SSH or console).

```
1. [LAB MACHINE] Create data/routing.nac.yaml. For each of R10, R11 and
   R12, add an entry with its name and, under configuration, the static
   routes, the ACL, and the loopback binding from the Technical
   Requirements. Follow the shape of the Worked Example.

2. [LAB MACHINE] Teach the schema the new keys. Open .schema.yaml and add
   the blocks below. Fill in each ... with the right validator:

     configuration:
       system: include('system', required=False)
       interfaces: include('interfaces', required=False)
       routing: include('routing', required=False)
       access_lists: include('access_lists', required=False)
     routing:
       static_routes: list(include('static_route'), required=False)
     static_route:
       prefix: ...
       mask: ...
       next_hops: list(include('next_hop'))
     next_hop:
       ip: ...
     access_lists:
       standard: list(include('standard_acl'), required=False)
     standard_acl:
       name: ...
       entries: list(include('standard_entry'))
     standard_entry:
       sequence: ...
       action: ...
       prefix: ...
       prefix_mask: ...
       any: ...

   The first two lines of the configuration block are already in your
   schema, so only add the last two. Also add one key to the ipv4 block:

     access_group_in: ...

   - prefix, mask, ip, prefix and prefix_mask are IPv4 addresses.
   - sequence is a whole number from 1 to 2147483647.
   - action is exactly permit or deny. The validator enum('a', 'b')
     accepts only the words you list.
   - prefix, prefix_mask and any are optional, because an ACL entry uses
     either an address or any.
   - access_group_in is optional text.

   One more change is needed. Each file is checked on its own, and the
   loopback in routing.nac.yaml has only access_group_in, no address. So
   address and address_mask in the ipv4 block can no longer be required.
   Add required=False to both.

3. [LAB MACHINE] Create rules/103_acl_references_exist.py. It reports a
   loopback that uses an ACL its own device doesn't define:

     from nac_validate import RuleBase


     class Rule(RuleBase):
         id = "..."
         description = "..."
         severity = "HIGH"

         @classmethod
         def match(cls, data):
             results = []
             for device in data.get("iosxe", {}).get("devices", []):
                 config = device.get("configuration", {})
                 lists = config.get("access_lists", {})
                 # the names of every standard ACL this device defines
                 defined = ...
                 for loopback in config.get("interfaces", {}).get("loopbacks", []):
                     name = ...
                     if ...:
                         results.append(...)
             return results

   ACLs live at access_lists -> standard, which is a list, and each has a
   name. The binding is at ipv4 -> access_group_in on the loopback. A
   loopback may have no binding at all, so use .get() with a default, and
   only report when there is a name that is not in defined.

4. [ROUTER R10, R11, R12] Take a snapshot on each router, then check it:

     copy running-config flash:before-todo07.cfg
     dir flash:before-todo07.cfg

   Press Enter to accept the file name. Use bootflash: if flash: isn't
   accepted. The listing must show a size above zero.

5. [LAB MACHINE] Bring Terraform's record forward. Each TODO folder is
   separate, so this one starts with an empty record. Without the old one,
   Terraform would plan to create the loopbacks and domain settings again:

     cp ../TODO-06-First-Push-to-R10-R12/terraform.tfstate .
     terraform init

   Make sure the router login is still exported in this terminal
   (IOSXE_USERNAME and IOSXE_PASSWORD, as in TODO 06). Then run:

     terraform plan

   Read it. Only new things should appear: six static routes, three ACLs
   and a change to each Loopback0 for the access group. Nothing about
   domain names, hostnames or the Loopback0 address.

6. [LAB MACHINE] Run:  terraform apply

   Look through the plan once more and type yes.

7. [ROUTER R10, R11, R12] Check each router. Here is R10:

     show ip route static
     show access-lists LOOPBACK-NET
     show running-config interface Loopback0
     ping 10.255.0.11 source Loopback0

   The expected output is in Test It Yourself below. Do the same on R11
   and R12 with their own neighbours.

8. [LAB MACHINE] Run terraform plan once more. It must say there is
   nothing to change.

9. [LAB MACHINE] Run: python grading.py
```

## Test It Yourself (without the grader)

First, your real data must pass the schema and every rule:

```
nac-validate data -s .schema.yaml -r rules
echo $?
nac-validate data -s .schema.yaml -r rules --list-rules
```

You want `PASSED`, exit code `0`, and rules 101, 102 and 103 in the list.

Now break your data on purpose. As in TODO 03 and 04, `sed -i.bak` keeps the original next to the file, and `mv` puts it back. Restore each file before the next break.

A schema break, which must exit `2` and name the key:

```
sed -i.bak 's/mask: 255.255.255.255/mask: banana/' data/routing.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
mv data/routing.nac.yaml.bak data/routing.nac.yaml

sed -i.bak 's/action: permit/action: allow/' data/routing.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
mv data/routing.nac.yaml.bak data/routing.nac.yaml
```

A rule break, which passes the schema (the name is just text) but must exit `1` with rule 103:

```
sed -i.bak 's/access_group_in: LOOPBACK-NET/access_group_in: NO-SUCH-ACL/' data/routing.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
mv data/routing.nac.yaml.bak data/routing.nac.yaml
```

Expect a block like this, with one line for each of the three routers:

```
[RULE 103] An interface may only use an ACL that the same device defines
  • R10 Loopback0 uses ACL 'NO-SUCH-ACL', which the device does not define
```

Then run `nac-validate data -s .schema.yaml -r rules` once more. It should pass again, which proves the files are back as they were.

On R10 after the apply, you should see this (the lines above the routes vary):

```
R10# show ip route static
S        10.255.0.11/32 [1/0] via 10.10.10.11
S        10.255.0.12/32 [1/0] via 10.10.10.12

R10# show access-lists LOOPBACK-NET
Standard IP access list LOOPBACK-NET
    10 permit 10.255.0.0, wildcard bits 0.0.0.255
    20 deny   any

R10# show running-config interface Loopback0
interface Loopback0
 description ROUTER-ID
 ip address 10.255.0.10 255.255.255.255
 ip access-group LOOPBACK-NET in
end

R10# ping 10.255.0.11 source Loopback0
!!!!!
Success rate is 100 percent (5/5)
```

R11 and R12 look the same with their own routes. The ping works because R11 has a route back to 10.255.0.10, which is its own static route from this TODO.

Ask Terraform the one question the grader asks:

```
terraform plan -detailed-exitcode
echo $?
```

`0` means no changes, `2` means changes are waiting, `1` means an error.

## Put a router back

To start over, undo the change on each router. For R10:

```
configure terminal
 interface Loopback0
  no ip access-group LOOPBACK-NET in
 exit
 no ip access-list standard LOOPBACK-NET
 no ip route 10.255.0.11 255.255.255.255 10.10.10.11
 no ip route 10.255.0.12 255.255.255.255 10.10.10.12
end
```

On R11 the routes go to 10.255.0.10 via 10.10.10.10 and 10.255.0.12 via 10.10.10.12. On R12 they go to 10.255.0.10 via 10.10.10.10 and 10.255.0.11 via 10.10.10.11. Leave Loopback0 itself and the domain settings alone, because TODO 06 put those there.

The snapshot you took in step 4 can also put a router back in one command with `configure replace flash:before-todo07.cfg`. It replaces the whole running configuration, so use it only if nothing else changed on that router since the snapshot.

After a reset, Terraform's record no longer matches the router. Run `terraform plan` and it will show the routes and ACLs as missing, which is what you want if you're going to apply them again.

## Grading Check

```
python grading.py
```

Run it in the terminal where you exported `IOSXE_USERNAME` and `IOSXE_PASSWORD`. The grader re-checks TODO 01 to TODO 06 first. The checks for TODO 03 and 04 use only your TODO 01 and 02 data, so a half-finished routing file doesn't fail them. Then it checks that your real data passes the schema and all three rules, and that the merged model holds the routes, the ACL and the binding exactly as the Technical Requirements say. In a temporary copy it breaks the routing file in six ways and every one must exit `2`. It also breaks it two more ways, an undefined ACL and a renamed ACL, and each must exit `1` with rule 103 only. Last, `terraform plan -detailed-exitcode` has to exit `0`. Your real files are never touched, and nothing is sent to a router.

Before you complete this TODO:

```
TODO 07 - Static Routes and ACLs
────────────────────────────────────────────────────────────────────────────────

[7] Static routes and an ACL...

✗ TODO 07 Not Complete

The pipeline cannot continue because the routes and ACL are not modelled, validated and
applied yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 07 - Static Routes and ACLs
────────────────────────────────────────────────────────────────────────────────

[7] Static routes and an ACL...
  R10 -> 10.255.0.11/32 via 10.10.10.11, 10.255.0.12/32 via 10.10.10.12
  R11 -> 10.255.0.10/32 via 10.10.10.10, 10.255.0.12/32 via 10.10.10.12
  R12 -> 10.255.0.10/32 via 10.10.10.10, 10.255.0.11/32 via 10.10.10.11
  every router -> ACL LOOPBACK-NET applied inbound on Loopback0
  real data -> passes schema and rules 101, 102, 103 (exit 0)
  injected: static route mask not an IP -> rejected (exit 2)
  injected: next hop not a valid IP -> rejected (exit 2)
  injected: ACL action 'allow' -> rejected (exit 2)
  injected: ACL sequence 0 -> rejected (exit 2)
  injected: ACL entry without an action -> rejected (exit 2)
  injected: misspelled next_hops key -> rejected (exit 2)
  injected: interface uses an undefined ACL -> rule 103 fired (exit 1)
  injected: ACL renamed, interface still points at the old name -> rule 103 fired (exit 1)
  terraform plan -> no changes

✓ TODO 07 Complete
Static routes and an ACL are modelled, validated by schema and rule, and match the live routers.
```

---
