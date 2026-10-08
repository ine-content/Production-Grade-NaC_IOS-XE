# TODO 08 — OSPF Across the Branch Routers

## Topics Covered

```
✓ Describing OSPF in the data model: process, router ID, networks, passive interfaces
✓ Wildcard masks and the network statement
✓ A rule that ties two parts of the model together (router ID and Loopback0)
✓ A rule written earlier keeps working on new data
✓ Checking an OSPF adjacency and the routes it teaches
```

## Recap

TODO 07 is solved in this folder: the static routes, the ACL, the extended schema and rule 103 are all in place. The static routes stay. In this TODO you add OSPF next to them, in a new file, and take it through the same path: data, schema, rule, plan, apply.

## Scenario

Static routes don't scale. Add a fourth router and you edit the other three. OSPF lets the routers tell each other what they have, so a new router only needs its own configuration.

Each router gets two things. A new Loopback10 stands in for the branch LAN, one per site, so there is something to advertise. And OSPF process 1 in area 0 advertises three things: the shared segment 10.10.10.0/24, so the routers can find each other, Loopback0, and Loopback10. Both loopbacks are passive, which means the router advertises them but doesn't send OSPF hellos out of them.

One thing to understand before you apply. The network statement `10.10.10.0 0.0.0.255` turns OSPF on for whichever interface holds an address in that range. On your routers that is the management interface, because the shared segment is the only link between them. This is intended. OSPF doesn't change that interface's address and nothing blocks it. It only starts sending hellos. Never mark that interface passive and never shut it down, or the routers stop seeing each other.

The static routes from TODO 07 still win for the Loopback0 addresses, because a static route (distance 1) beats an OSPF route (distance 110). The Loopback10 addresses exist only in OSPF. So those are the routes you check on the router.

You also write rule 104: an OSPF router ID has to be the router's own Loopback0 address. The schema can't check that. It would only see an IP address, and any IP address is valid.

## Worked Example

A made-up router, `EDGE1`, with its own LAN loopback and an OSPF process. The addresses come from the ranges reserved for documentation:

```yaml
iosxe:
  devices:
    - name: EDGE1
      configuration:
        interfaces:
          loopbacks:
            - id: 20
              description: GUEST-LAN
              ipv4:
                address: 198.51.100.1
                address_mask: 255.255.255.255
        routing:
          ospf_processes:
            - id: 7
              router_id: 192.0.2.1
              networks:
                - ip: 192.0.2.0
                  wildcard: 0.0.0.255
                  area: 0
                - ip: 198.51.100.0
                  wildcard: 0.0.0.255
                  area: 0
              passive_interfaces:
                - interface_type: Loopback
                  interface_id: 20
```

Things to notice:

- The process `id` only has meaning on this router. It doesn't have to match the neighbours.
- A `networks` entry turns OSPF on for every interface whose address falls inside it, and puts that network in the area.
- `wildcard` is the inverse of a subnet mask: `0.0.0.255` means the first three numbers must match, the same idea as in the ACL in TODO 07.
- `passive_interfaces` is a list. Each entry names an interface by its type and its number.
- The new loopback is a new entry in the `loopbacks` list. It doesn't touch Loopback0.

## Technical Requirements

Branch LAN, a new interface on every router, mask 255.255.255.255:

| Router | Interface | Description | Address |
|--------|-----------|-------------|---------|
| R10 | Loopback10 | BRANCH-LAN | 172.16.10.1 |
| R11 | Loopback10 | BRANCH-LAN | 172.16.11.1 |
| R12 | Loopback10 | BRANCH-LAN | 172.16.12.1 |

OSPF on every router: process id 1, and the router ID is that router's own Loopback0 address (10.255.0.10, .11 or .12). The networks, all in area 0:

| Network | Wildcard | What it covers |
|---------|----------|----------------|
| 10.10.10.0 | 0.0.0.255 | the shared segment (the link between routers) |
| 10.255.0.0 | 0.0.0.255 | Loopback0 |
| 172.16.0.0 | 0.0.255.255 | Loopback10 |

Passive interfaces: Loopback0 and Loopback10. The management interface is not listed anywhere.

## Notation Used Below

Skeletons in the Steps section use one kind of blank:

```
...   - replace this with your own value or expression.
```

Everything else in a skeleton is already filled in and must stay as it is.

## Working Folder

Do everything for this TODO from its own folder. Open a terminal and run:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-08-OSPF-Across-the-Branch-Routers
```

Change the path if you put the course folder somewhere else.

## Steps

Each step says where to run its commands. LAB MACHINE means a normal terminal on the lab machine, in this folder. ROUTER means the router's own command line (SSH or console).

```
1. [LAB MACHINE] Create data/ospf.nac.yaml. For each of R10, R11 and R12,
   add an entry with its name and, under configuration, the Loopback10
   and the OSPF process from the Technical Requirements. Follow the shape
   of the Worked Example.

2. [LAB MACHINE] Add OSPF to the schema. In .schema.yaml, add this
   line to the routing block, next to static_routes:

     ospf_processes: list(include('ospf_process'), required=False)

   and add these blocks. Fill in each ... with the right validator:

     ospf_process:
       id: ...
       router_id: ...
       networks: list(include('ospf_network'), required=False)
       passive_interfaces: list(include('interface_ref'), required=False)
     ospf_network:
       ip: ...
       wildcard: ...
       area: ...
     interface_ref:
       interface_type: ...
       interface_id: ...

   - id is a whole number from 1 to 65535.
   - router_id is an IPv4 address and optional, so that rule 104 has
     something to catch when it is missing.
   - ip and wildcard are IPv4 addresses.
   - area is a whole number, 0 or more.
   - interface_type is text, interface_id a whole number, 0 or more.

3. [LAB MACHINE] Create rules/104_ospf_router_id_is_loopback0.py. It reports
   an OSPF process whose router ID is not the device's Loopback0 address:

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
                 loopbacks = config.get("interfaces", {}).get("loopbacks", [])
                 # the address of the loopback whose id is 0
                 address = ...
                 for process in config.get("routing", {}).get("ospf_processes", []):
                     router_id = ...
                     if ...:
                         results.append(...)
             return results

   Loopback0 is the entry in loopbacks whose id is 0. It may not exist on
   a device, so use .get() with a default. A process with no router ID
   should be reported too.

4. [ROUTER R10, R11, R12] Take a snapshot on each router, then check it:

     copy running-config flash:before-todo08.cfg
     dir flash:before-todo08.cfg

   Press Enter to accept the file name. Use bootflash: if flash: isn't
   accepted. The listing must show a size above zero.

5. [LAB MACHINE] Bring Terraform's record forward from the last TODO and
   read the plan:

     cp ../TODO-07-Static-Routes-and-ACLs/terraform.tfstate .
     terraform init

   Make sure the router login is still exported in this terminal
   (IOSXE_USERNAME and IOSXE_PASSWORD, as in TODO 06). Then run:

     terraform plan

   Only new things should appear: three Loopback10 interfaces and three
   OSPF processes. Nothing about routes, ACLs, domain names or Loopback0.

6. [LAB MACHINE] Run:  terraform apply

   Look through the plan once more and type yes.

7. [ROUTER R10, R11, R12] Wait about 40 seconds for the adjacencies, then
   check each router. Here is R10:

     show ip ospf neighbor
     show ip route ospf
     ping 172.16.11.1 source Loopback10

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

You want `PASSED`, exit code `0`, and rules 101, 102, 103 and 104 in the list.

Now break your data on purpose. As before, `sed -i.bak` keeps the original next to the file and `mv` puts it back. Restore each file before the next break.

A schema break, which must exit `2` and name the key:

```
sed -i.bak 's/router_id: 10.255.0.10/router_id: banana/' data/ospf.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
mv data/ospf.nac.yaml.bak data/ospf.nac.yaml
```

A rule break. R11 gets a router ID that is a valid IP but not its Loopback0 address, so it passes the schema and must exit `1` with rule 104:

```
sed -i.bak 's/router_id: 10.255.0.11/router_id: 1.1.1.1/' data/ospf.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
```

Expect exit code `1` and a block like this:

```
[RULE 104] An OSPF router ID must be the device's Loopback0 address
  • R11 OSPF 1 router_id 1.1.1.1 is not the Loopback0 address 10.255.0.11
```

Then put the file back:

```
mv data/ospf.nac.yaml.bak data/ospf.nac.yaml
```

A break that an older rule catches. R11 reuses R10's branch LAN address, and rule 102 from TODO 04 notices without being changed:

```
sed -i.bak 's/address: 172.16.11.1/address: 172.16.10.1/' data/ospf.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
```

Expect exit code `1` and:

```
[RULE 102] No IPv4 address may be used more than once
  • address 172.16.10.1 is used by R10.loopback10, R11.loopback10
```

Then put the file back:

```
mv data/ospf.nac.yaml.bak data/ospf.nac.yaml
```

Finally run `nac-validate data -s .schema.yaml -r rules` once more. It should pass again, which proves the files are back as they were.

On R10 after the apply, you should see something like this. The times, the interface name and the DR and BDR roles vary. What matters is that there are two neighbours and both are FULL:

```
R10# show ip ospf neighbor

Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.0.12       1   FULL/DR         00:00:33    10.10.10.12     GigabitEthernet1
10.255.0.11       1   FULL/BDR        00:00:38    10.10.10.11     GigabitEthernet1

R10# show ip route ospf
      172.16.0.0/32 is subnetted, 2 subnets
O        172.16.11.1 [110/2] via 10.10.10.11, 00:01:05, GigabitEthernet1
O        172.16.12.1 [110/2] via 10.10.10.12, 00:01:05, GigabitEthernet1

R10# ping 172.16.11.1 source Loopback10
!!!!!
Success rate is 100 percent (5/5)
```

You see only the 172.16 routes in `show ip route ospf`. The 10.255.0.x routes are in OSPF too, but the static routes from TODO 07 win for those, so they appear as `S` in `show ip route`.

Ask Terraform the one question the grader asks:

```
terraform plan -detailed-exitcode
echo $?
```

`0` means no changes, `2` means changes are waiting, `1` means an error.

## Put a router back

To start over, undo the change on each router:

```
configure terminal
 no router ospf 1
 no interface Loopback10
end
```

Leave Loopback0, the static routes and the ACL alone, because earlier TODOs put those there. The snapshot from step 4 can also put a router back in one command with `configure replace flash:before-todo08.cfg`. It replaces the whole running configuration, so use it only if nothing else changed on that router since the snapshot.

After a reset, Terraform's record no longer matches the router. Run `terraform plan` and it will show the OSPF process and Loopback10 as missing, which is what you want if you're going to apply them again.

## Grading Check

```
python grading.py
```

Run it in the terminal where you exported `IOSXE_USERNAME` and `IOSXE_PASSWORD`. The grader re-checks TODO 01 to TODO 07 first, each against only the data files that belong to it, so a half-finished `ospf.nac.yaml` doesn't make an earlier TODO look broken. Then it checks that your data passes the schema and rules 101 to 104, and that the merged model holds the branch LANs, the OSPF process, the networks and the passive interfaces exactly as the Technical Requirements say. In a temporary copy it breaks the OSPF file in six ways and every one must exit `2`. It breaks it three more ways, and each must exit `1` with exactly one rule: rule 104 twice and rule 102 once. Last, `terraform plan -detailed-exitcode` has to exit `0`. Your real files are never touched, and nothing is sent to a router.

Before you complete this TODO:

```
TODO 08 - OSPF Across the Branch Routers
────────────────────────────────────────────────────────────────────────────────

[8] OSPF across the branch routers...

✗ TODO 08 Not Complete

The pipeline cannot continue because OSPF is not modelled, validated and applied yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 08 - OSPF Across the Branch Routers
────────────────────────────────────────────────────────────────────────────────

[8] OSPF across the branch routers...
  R10 -> Loopback10 172.16.10.1/32, OSPF 1, router ID 10.255.0.10
  R11 -> Loopback10 172.16.11.1/32, OSPF 1, router ID 10.255.0.11
  R12 -> Loopback10 172.16.12.1/32, OSPF 1, router ID 10.255.0.12
  every router -> three networks in area 0, both loopbacks passive
  real data -> passes schema and rules 101 to 104 (exit 0)
  injected: router ID not an IP -> rejected (exit 2)
  injected: network wildcard not an IP -> rejected (exit 2)
  injected: area written as text -> rejected (exit 2)
  injected: process id written as text -> rejected (exit 2)
  injected: misspelled networks key -> rejected (exit 2)
  injected: passive interface without an id -> rejected (exit 2)
  injected: router ID is not the Loopback0 address -> rule 104 fired (exit 1)
  injected: OSPF process without a router ID -> rule 104 fired (exit 1)
  injected: two routers share the branch LAN address -> rule 102 fired (exit 1)
  terraform plan -> no changes

✓ TODO 08 Complete
OSPF is modelled, validated by schema and rules 101 to 104, and the routers run it as described.
```

---
