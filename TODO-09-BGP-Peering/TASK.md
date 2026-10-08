# TODO 09 — BGP Peering

## Topics Covered

```
✓ Describing BGP in the data model: process, neighbors, address family, advertised networks
✓ Peering between loopbacks, and why the session needs an update source
✓ A rule that checks neighbors against other devices in the model (address and AS)
✓ Why OSPF still wins the routing table when BGP carries the same prefix
✓ Reading a BGP session and the BGP table
```

## Recap

TODO 08 is solved in this folder: the static routes, the ACL, OSPF, the Loopback10 branch LANs, the extended schema and rules 101 to 104 are all in place. They stay. In this TODO you add BGP in a new file and take it through the same path: data, schema, rule, plan, apply.

## Scenario

OSPF is how the three routers find each other inside the site. BGP is how Meridian will later exchange routes with the rest of the world. Before that happens, the routers need to speak it with each other.

All three routers go into one autonomous system, AS 65010, so every session is iBGP. Each router peers with the other two, which makes a full mesh of three sessions. The sessions run between the loopbacks, not between the management addresses. A loopback never goes down because a cable did, and it is the usual choice for iBGP. Two things make that work. Each neighbor entry says the session must be sourced from Loopback0 (`update_source`), otherwise the router would source it from the management interface and the other side would refuse it. And each router must know how to reach the other loopbacks. The static routes from TODO 07 already do that. The ACL from TODO 07 also lets these sessions through, because it permits sources in 10.255.0.0/24 on Loopback0.

Each router advertises its own Loopback10, the branch LAN. Those prefixes are already in OSPF, so BGP is carrying a second copy. That is on purpose, and it teaches something you will see on the router: the routing table keeps the OSPF route (distance 110) and ignores the iBGP one (distance 200). The prefixes show up in the BGP table, not as `B` routes in `show ip route`.

You also write rule 105. The schema can see that a neighbor is an IP address and that `remote_as` is a number, but it can't see that this address belongs to another router in your model, or that the AS number matches the one that router really runs. Rule 105 checks both.

## Worked Example

A made-up router, `EDGE1`, in AS 64512 with one peer. The addresses come from the ranges reserved for documentation:

```yaml
iosxe:
  devices:
    - name: EDGE1
      configuration:
        routing:
          bgp:
            as_number: 64512
            router_id: 192.0.2.1
            default_ipv4_unicast: false
            log_neighbor_changes: true
            neighbors:
              - ip: 192.0.2.2
                remote_as: 64512
                description: EDGE2
                update_source_interface_type: Loopback
                update_source_interface_id: 0
            address_family:
              ipv4_unicast:
                networks:
                  - network: 198.51.100.1
                    mask: 255.255.255.255
                neighbors:
                  - ip: 192.0.2.2
                    activate: true
```

Things to notice:

- `neighbors` and `address_family` are both under `bgp`. The first defines the session. The second decides what is exchanged over it.
- The neighbor appears twice on purpose: once to define the session, once under `address_family` -> `ipv4_unicast` to activate it. With `default_ipv4_unicast: false`, a neighbor that is not activated exchanges nothing.
- `remote_as` equal to the router's own `as_number` means iBGP. A different number means eBGP.
- A `networks` entry needs the network and its mask. BGP only advertises a prefix that is already in the routing table, and a Loopback10 /32 is there because it is a connected interface.
- `update_source_interface_type` and `update_source_interface_id` name the interface the session starts from, the same way `passive_interfaces` named interfaces in TODO 08.

## Technical Requirements

BGP on every router: AS 65010, `default_ipv4_unicast: false`, `log_neighbor_changes: true`, and the router ID is that router's own Loopback0 address.

| Router | Router ID | Neighbors (all remote_as 65010) | Advertises |
|--------|-----------|---------------------------------|------------|
| R10 | 10.255.0.10 | 10.255.0.11 (R11), 10.255.0.12 (R12) | 172.16.10.1 mask 255.255.255.255 |
| R11 | 10.255.0.11 | 10.255.0.10 (R10), 10.255.0.12 (R12) | 172.16.11.1 mask 255.255.255.255 |
| R12 | 10.255.0.12 | 10.255.0.10 (R10), 10.255.0.11 (R11) | 172.16.12.1 mask 255.255.255.255 |

Every neighbor is sourced from Loopback0, has the other router's name as its description, and is activated under `address_family` -> `ipv4_unicast`.

## Notation Used Below

Skeletons in the Steps section use one kind of blank:

```
...   - replace this with your own value or expression.
```

Everything else in a skeleton is already filled in and must stay as it is.

## Working Folder

Do everything for this TODO from its own folder. Open a terminal and run:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-09-BGP-Peering
```

Change the path if you put the course folder somewhere else.

## Steps

Each step starts by saying where to run it. "On CWS" means a normal terminal on the lab machine (CWS), in this folder. "On R10" (or R11, R12) means that router's own command line (SSH or console). These labels are only directions. You don't type them anywhere.

```
1. On CWS: Create data/bgp.nac.yaml. For each of R10, R11 and R12,
   add an entry with its name and, under configuration -> routing, the
   bgp block from the Technical Requirements. Follow the shape of the
   Worked Example. There is no interfaces section in this file, because
   the loopbacks already exist.

2. On CWS: Add BGP to the schema. In .schema.yaml, add this
   line to the routing block, next to ospf_processes:

     bgp: include('bgp', required=False)

   and add these blocks. Fill in each ... with the right validator:

     bgp:
       as_number: ...
       router_id: ...
       default_ipv4_unicast: ...
       log_neighbor_changes: ...
       neighbors: list(include('bgp_neighbor'), required=False)
       address_family: include('bgp_address_family', required=False)
     bgp_neighbor:
       ip: ...
       remote_as: ...
       description: ...
       update_source_interface_type: ...
       update_source_interface_id: ...
     bgp_address_family:
       ipv4_unicast: include('bgp_ipv4_unicast', required=False)
     bgp_ipv4_unicast:
       networks: list(include('bgp_network'), required=False)
       neighbors: list(include('bgp_af_neighbor'), required=False)
     bgp_network:
       network: ...
       mask: ...
     bgp_af_neighbor:
       ip: ...
       activate: ...

   - as_number and remote_as are whole numbers from 1 to 4294967295.
   - router_id, ip, network and mask are IPv4 addresses. router_id is
     optional.
   - default_ipv4_unicast, log_neighbor_changes and activate are true
     or false, and optional.
   - description and update_source_interface_type are text, and
     optional.
   - update_source_interface_id is a whole number, 0 or more, and
     optional.

3. On CWS: Create rules/105_bgp_neighbor_matches_peer.py. It reports a
   BGP neighbor that is not another device's Loopback0 address, or whose
   remote_as is not the AS that device runs:

     from nac_validate import RuleBase


     class Rule(RuleBase):
         id = "..."
         description = "..."
         severity = "HIGH"

         @classmethod
         def match(cls, data):
             devices = data.get("iosxe", {}).get("devices", [])
             # first pass: map each Loopback0 address to (device name, its AS)
             owners = {}
             for device in devices:
                 ...
             # second pass: check every neighbor against that map
             results = []
             for device in devices:
                 bgp = ...
                 for neighbor in bgp.get("neighbors", []):
                     owner = owners.get(neighbor.get("ip"))
                     if owner is None:
                         results.append(...)
                     elif ...:
                         results.append(...)
                     elif ...:
                         results.append(...)
             return results

   Loopback0 is the entry in loopbacks whose id is 0, as in rule 104.
   The three problems to report, in this order: the address is nobody's
   Loopback0, the address is the device's own, and remote_as differs
   from the owner's as_number. Not every device has a bgp block, so use
   .get() with a default.

4. On R10, R11 and R12: Take a snapshot on each router, then check it:

     copy running-config flash:before-todo09.cfg
     dir flash:before-todo09.cfg

   Press Enter to accept the file name. Use bootflash: if flash: isn't
   accepted. The listing must show a size above zero.

5. On CWS: Bring Terraform's record forward from the last TODO and
   read the plan:

     cp ../TODO-08-OSPF-Across-the-Branch-Routers/terraform.tfstate .
     terraform init

   Make sure the router login is still exported in this terminal
   (IOSXE_USERNAME and IOSXE_PASSWORD, as in TODO 06). Then run:

     terraform plan

   Only new things should appear: on each router one BGP process, two
   neighbors, one address family and two activated neighbors. That is 18
   to add in total, 0 to change, 0 to destroy. Nothing about OSPF,
   routes, ACLs or loopbacks.

6. On CWS: Run:  terraform apply

   Look through the plan once more and type yes.

7. On R10, R11 and R12: Wait about a minute for the sessions to come
   up, then check each router. Here is R10:

     show ip bgp summary
     show ip bgp
     show ip route 172.16.11.1

   The expected output is in Test It Yourself below. Do the same on R11
   and R12 with their own neighbours.

8. On CWS: Run terraform plan once more. It must say there is
   nothing to change.

9. On CWS: Run: python grading.py
```

## Test It Yourself (without the grader)

First, your real data must pass the schema and every rule:

```
nac-validate data -s .schema.yaml -r rules
echo $?
nac-validate data -s .schema.yaml -r rules --list-rules
```

You want `PASSED`, exit code `0`, and rules 101, 102, 103, 104 and 105 in the list.

Now break your data on purpose. As before, `sed -i.bak` keeps the original next to the file and `mv` puts it back. Restore each file before the next break.

A schema break, which must exit `2` and name the key. Every `remote_as` becomes text:

```
sed -i.bak 's/remote_as: 65010/remote_as: same/' data/bgp.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
mv data/bgp.nac.yaml.bak data/bgp.nac.yaml
```

A rule break. Every neighbor that pointed at R10 now points at 10.255.0.99, a valid IP that belongs to nobody, so it passes the schema and must exit `1` with rule 105:

```
sed -i.bak 's/ip: 10.255.0.10$/ip: 10.255.0.99/' data/bgp.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
```

Expect exit code `1` and a block like this:

```
[RULE 105] A BGP neighbor must be another device's Loopback0 and carry that device's AS
  • R11 neighbor 10.255.0.99 is not the Loopback0 address of any device
  • R12 neighbor 10.255.0.99 is not the Loopback0 address of any device
```

Then put the file back:

```
mv data/bgp.nac.yaml.bak data/bgp.nac.yaml
```

A second rule break, the typo that really happens: R10 is moved to AS 65011 and its two peers still expect 65010. The first `as_number` line in the file is R10's, so this changes only that one:

```
sed -i.bak '0,/as_number: 65010/s//as_number: 65011/' data/bgp.nac.yaml
nac-validate data -s .schema.yaml -r rules
echo $?
```

Expect exit code `1` and:

```
[RULE 105] A BGP neighbor must be another device's Loopback0 and carry that device's AS
  • R11 neighbor 10.255.0.10 has remote_as 65010 but R10 is in AS 65011
  • R12 neighbor 10.255.0.10 has remote_as 65010 but R10 is in AS 65011
```

Then put the file back:

```
mv data/bgp.nac.yaml.bak data/bgp.nac.yaml
```

Finally run `nac-validate data -s .schema.yaml -r rules` once more. It should pass again, which proves the files are back as they were.

On R10 after the apply, you should see something like this. The times, counters and table version vary. What matters is that both neighbors show a number (the prefixes received) in the last column, not a word like `Idle` or `Active`:

```
R10# show ip bgp summary
BGP router identifier 10.255.0.10, local AS number 65010
...
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.255.0.11     4        65010       9       9        4    0    0 00:03:41        1
10.255.0.12     4        65010       9       9        4    0    0 00:03:38        1

R10# show ip bgp
     Network          Next Hop            Metric LocPrf Weight Path
 *>   172.16.10.1/32   0.0.0.0                  0         32768 i
 *>i  172.16.11.1/32   10.255.0.11              0    100      0 i
 *>i  172.16.12.1/32   10.255.0.12              0    100      0 i

R10# show ip route 172.16.11.1
Routing entry for 172.16.11.1/32
  Known via "ospf 1", distance 110, metric 2, type intra area
```

The `i` in the BGP table means the route came from an iBGP neighbor. In the routing table the same prefix is `ospf 1`, distance 110, and not `bgp`. That is the point from the Scenario: both protocols know the prefix, and the lower distance wins. The BGP route is held in reserve.

If a neighbor stays in `Active` or `Idle`, test the path first with `ping 10.255.0.11 source Loopback0` on R10. If that fails, the static route from TODO 07 is the first thing to look at.

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
 no router bgp 65010
end
```

Leave Loopback0, Loopback10, OSPF, the static routes and the ACL alone, because earlier TODOs put those there. The snapshot from step 4 can also put a router back in one command with `configure replace flash:before-todo09.cfg`. It replaces the whole running configuration, so use it only if nothing else changed on that router since the snapshot.

After a reset, Terraform's record no longer matches the router. Run `terraform plan` and it will show the BGP resources as missing, which is what you want if you're going to apply them again.

## Grading Check

```
python grading.py
```

Run it in the terminal where you exported `IOSXE_USERNAME` and `IOSXE_PASSWORD`. The grader re-checks TODO 01 to TODO 08 first, each against only the data files that belong to it, so a half-finished `bgp.nac.yaml` doesn't make an earlier TODO look broken. Then it checks that your data passes the schema and rules 101 to 105, and that the merged model holds the AS, the router ID, both neighbors, the advertised network and the activation exactly as the Technical Requirements say. In a temporary copy it breaks the BGP file in six ways and every one must exit `2`. It breaks it three more ways, and each must exit `1` with only rule 105. Last, `terraform plan -detailed-exitcode` has to exit `0`. Your real files are never touched, and nothing is sent to a router.

Before you complete this TODO:

```
TODO 09 - BGP Peering
────────────────────────────────────────────────────────────────────────────────

[9] BGP peering...

✗ TODO 09 Not Complete

The pipeline cannot continue because BGP is not modelled, validated and applied yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 09 - BGP Peering
────────────────────────────────────────────────────────────────────────────────

[9] BGP peering...
  R10 -> AS 65010, peers 10.255.0.11 10.255.0.12, advertises 172.16.10.1/32
  R11 -> AS 65010, peers 10.255.0.10 10.255.0.12, advertises 172.16.11.1/32
  R12 -> AS 65010, peers 10.255.0.10 10.255.0.11, advertises 172.16.12.1/32
  every neighbor -> sourced from Loopback0 and activated in ipv4 unicast
  real data -> passes schema and rules 101 to 105 (exit 0)
  injected: AS number written as text -> rejected (exit 2)
  injected: router ID not an IP -> rejected (exit 2)
  injected: neighbor address not a valid IP -> rejected (exit 2)
  injected: remote_as written as text -> rejected (exit 2)
  injected: advertised network mask not an IP -> rejected (exit 2)
  injected: misspelled neighbors key in the address family -> rejected (exit 2)
  injected: neighbor is not any router's Loopback0 -> rule 105 fired (exit 1)
  injected: neighbor is the router's own Loopback0 -> rule 105 fired (exit 1)
  injected: remote_as differs from the peer's AS -> rule 105 fired (exit 1)
  terraform plan -> no changes

✓ TODO 09 Complete
BGP is modelled, validated by schema and rules 101 to 105, and the three routers peer as described.
```

---
