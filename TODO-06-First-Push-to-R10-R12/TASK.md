# TODO 06 — First Push to R10-R12

## Topics Covered

```
✓ Reading a plan before you apply it
✓ A staged rollout: staging router first, then production
✓ Keeping the router login in environment variables
✓ Checking the result on the router itself
✓ Idempotence: a second plan finds nothing left to do
✓ Putting a router back the way it was
```

## Recap

TODO 05 is solved in this folder, so `main.tf` already calls the nac-iosxe module. Until now nothing has touched a router. This is the first TODO that does.

## Scenario

Meridian wants the three routers to carry the same basic settings: a domain name, domain lookup turned off, and a Loopback0 that acts as the router ID. All of it already sits in your YAML. Terraform will compare that YAML with what each router has now and change only what differs.

You won't push to all three at once. R12 in Seattle is the staging router, so it goes first. If something is wrong, you find out on the router that matters least. Only then do R10 and R11, the production routers, get the same change. The module has an input for exactly this, `managed_devices`. It takes a list of device names, and the module leaves every other router alone.

## What this TODO changes

On each router, and nothing else:

| Setting | Value |
|---------|-------|
| `ip routing` | on (it is on by default, so you may see no change) |
| `ip domain name` | meridian.local |
| `ip domain lookup` | off |
| `hostname` | R10, R11 or R12 (they already have these names) |
| `interface Loopback0` | description ROUTER-ID, address 10.255.0.10, .11 or .12, mask 255.255.255.255 |

The management interface is never touched. Its address stays as it is and no ACL goes on it. That interface is how you reach the routers.

## Worked Example

A made-up module takes a list called `only_sites`. Leave it out and the module works on every site. Give it names and the module works on those and skips the rest:

```hcl
module "lab_vpn" {
  source      = "./modules/vpn"
  config_dirs = ["settings"]
  only_sites  = ["lab-b"]
}
```

A first rollout would list one site, check it, then list all of them or remove the line.

## Notation Used Below

Skeletons in the Steps section use one kind of blank:

```
...   - replace this with your own value or expression.
```

Everything else in a skeleton is already filled in and must stay as it is.

## Steps

```
1. Check that each router answers on the NETCONF port:

     for ip in 10.10.10.10 10.10.10.11 10.10.10.12; do
       timeout 3 bash -c "echo > /dev/tcp/$ip/830" && echo "$ip open" || echo "$ip CLOSED"
     done

   All three must say open. If one says CLOSED, NETCONF is not turned on
   there yet. The Router setup section of the course README shows how.

2. Save R12's current state, so you can compare later. On R12 run:

     show running-config | include hostname|domain
     show running-config interface Loopback0
     show ip interface brief

   Copy the output somewhere. You'll need it in step 7.

3. Give Terraform the router login. Do this in the terminal where you'll
   run everything from here on, because the grader needs the same variables:

     export IOSXE_USERNAME=<your username>
     read -s IOSXE_PASSWORD; export IOSXE_PASSWORD

   After the second command, type the password and press Enter. Nothing is
   shown on screen, and it stays out of your shell history and your files.

4. Limit the module to the staging router. In the module block of main.tf,
   add one line:

     managed_devices = [...]

   Put R12 in the list, and only R12.

5. Run:  terraform init
          terraform plan

   Read the plan. Only R12 should show anything. Expect a Loopback0 to be
   added and a domain name set. If R10 or R11 appear, stop and check the
   line from step 4.

6. Run:  terraform apply

   Look through the plan once more and type yes.

7. On R12, run the three commands from step 2 again and compare with what
   you saved. Loopback0 and the domain settings should be new. The
   management address on your interface list must be unchanged.

8. Widen the rollout. Change managed_devices so that it lists all three
   routers, then run terraform plan. Only R10 and R11 should show changes
   now, because R12 already matches. Run terraform apply.

9. Run terraform plan once more. It must say there is nothing to change.

10. Run: python grading.py
```

## Test It Yourself (without the grader)

The grader only asks Terraform one question: does anything still differ from the data model? You can ask it yourself:

```
terraform plan -detailed-exitcode
echo $?
```

`0` means no changes. `2` means changes are waiting, so read the plan and apply. `1` means an error, such as a router that can't be reached or a wrong password.

On each router after the apply, you should see these. Here is R12:

```
R12# show running-config | include hostname|domain
hostname R12
no ip domain lookup
ip domain name meridian.local

R12# show running-config interface Loopback0
interface Loopback0
 description ROUTER-ID
 ip address 10.255.0.12 255.255.255.255
end

R12# show ip interface brief | include Loopback0
Loopback0              10.255.0.12     YES manual up                    up
```

The lines can come in a different order, and the extra header lines `show` prints are left out above. R10 and R11 look the same, with their own addresses (10.255.0.10 and 10.255.0.11).

Terraform keeps a record of what it manages in `terraform.tfstate` in this folder. List it if you're curious:

```
terraform state list
```

## Put a router back

If you want to start over, undo the change on the router. For R12:

```
configure terminal
 no interface Loopback0
 no ip domain name meridian.local
 ip domain lookup
end
```

Do the same on R10 or R11 if you pushed there. Then delete Terraform's record, so it doesn't think it still manages those settings:

```
rm -f terraform.tfstate terraform.tfstate.backup
```

Don't touch the management interface in the reset either. It was never changed.

## Grading Check

```
python grading.py
```

Run it in the terminal where you exported `IOSXE_USERNAME` and `IOSXE_PASSWORD`. The grader re-checks TODO 01 to TODO 05 first. Then it checks that `managed_devices` in `main.tf` is either gone or lists R10, R11 and R12, that the two login variables are set, and that no password or provider block is in your `.tf` files. Last, it runs `terraform plan -detailed-exitcode`. That reads from the routers but never changes them, and it has to exit 0.

Before you complete this TODO:

```
TODO 06 - First Push to R10-R12
────────────────────────────────────────────────────────────────────────────────

[6] First push to R10, R11 and R12...

✗ TODO 06 Not Complete

The pipeline cannot continue because the routers do not yet match the data model.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 06 - First Push to R10-R12
────────────────────────────────────────────────────────────────────────────────

[6] First push to R10, R11 and R12...
  main.tf -> all three routers are managed
  IOSXE_USERNAME and IOSXE_PASSWORD are set in this terminal
  terraform plan -> no changes (R10, R11 and R12 match the data model)

✓ TODO 06 Complete
R10, R11 and R12 match the data model, and a second plan finds nothing left to change.
```

---
