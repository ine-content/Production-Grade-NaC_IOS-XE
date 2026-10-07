# Production-Grade Network as Code for IOS-XE

A hands-on course in the Network as Code approach from netascode.cisco.com. You work with three real Cisco IOS-XE routers, Terraform, and the netascode tools `nac-validate` and `nac-test`.

## The lab

| Router | Site | Environment | Management IP |
|--------|------|-------------|---------------|
| R10 | rdu01 (Raleigh) | prod | 10.10.10.10 |
| R11 | aus02 (Austin) | prod | 10.10.10.11 |
| R12 | sea03 (Seattle) | staging | 10.10.10.12 |

The lab machine is 10.10.10.250. All four are on the same 10.10.10.0/24 segment.

## Safety rules

These apply to every TODO that touches a router.

- Never change the management addresses above, and never put an ACL on the interface that carries them. That's how you reach the routers.
- Routing labs advertise loopbacks, not the management interface.
- Credentials never go in YAML or Terraform files. They come from environment variables.
- Every router-touching TODO has a reset step, so a failed run can't leave a router broken.

## Router setup (needed from TODO 06)

The Terraform `iosxe` provider talks to the routers over NETCONF on SSH port 830. Before TODO 06, each router needs NETCONF turned on and a login with privilege 15. The username and password are your choice. They go into the environment variables `IOSXE_USERNAME` and `IOSXE_PASSWORD`, never into a file.

```
configure terminal
 username <name> privilege 15 secret <password>
 netconf-yang
end
```

Port 830 has to be reachable from the lab machine (10.10.10.250). If the routers use AAA, make sure that login is allowed to run NETCONF. TODO 06 starts with a check that tells you whether this is set up correctly.

## Course map

| TODO | Topic | Needs routers? | Status |
|------|-------|----------------|--------|
| 01 | Author the Network Data Model | No | Built and tested |
| 02 | Layer Shared Settings Across Files | No | Built and tested |
| 03 | Validate Structure with a Schema | No | Built and tested |
| 04 | Enforce Business Rules | No | Built and tested |
| 05 | Connect the Data Model to Terraform | No | Built; Terraform steps not yet run on real hardware |
| 06 | First Push to R10-R12 | Yes | Planned |
| 07 | Static Routes and ACLs | Yes | Planned |
| 08 | OSPF Across the Branch Routers | Yes | Planned |
| 09 | BGP Peering | Yes | Planned |
| 10 | Detect and Reconcile Drift | Yes | Planned |
| 11 | Verify Live State with nac-test | Yes | Planned |
| 12 | Gate the Pipeline and Emit an Audit Log | Yes | Planned |

## How to use it

Each `TODO-NN-...` folder is a lab on its own, with the earlier TODOs already solved inside it. Open its `TASK.md`, do the work, and run `python grading.py` from inside that folder. Start with `TODO-01-Author-the-Network-Data-Model`.

```
pip install -r requirements.txt
cd TODO-01-Author-the-Network-Data-Model
python grading.py
```

If your lab is offline, read `OFFLINE-SETUP.md` first.

From TODO 05 on, the commands need Terraform and the local provider mirror. Both come from `. prep/env.sh`. If your lab doesn't load it for you, run it once in every new terminal, from the course folder.
