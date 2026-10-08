# TODO 10 — Detect and Reconcile Drift

## Topics Covered

```
✓ What drift is: a router that no longer matches the data model
✓ Detecting drift with terraform plan and its exit code
✓ Wrapping that check in a script a pipeline can call
✓ Reconciling in both directions: fix the router, or update the data
✓ What a plan can't see: settings Terraform doesn't manage
```

## Recap

TODO 09 is solved in this folder: static routes, the ACL, OSPF and BGP are in the data model, in the schema, under rules 101 to 105, and on the routers. They stay as they are. This TODO adds no new router configuration. You build a drift check, then make some drift on purpose and clear it.

## Scenario

The data model says what the routers should look like. Someone logs in at 2 a.m. to fix something, types a command, and goes home. The router now differs from the data model, and nobody wrote it down. That gap is drift.

Terraform can find it. `terraform plan` reads the live router, compares it with the data model, and lists what it would change. The exit code of `terraform plan -detailed-exitcode` is a clean signal: `0` nothing to change, `2` there are differences, `1` an error. You will wrap that in a small script, `drift_check.sh`, which prints one clear line and passes the same exit code on. In TODO 12 a pipeline will call it.

When the check says DRIFT, someone has to decide which side is right. There are two answers:

- The router is wrong. Someone made a mistake, so push the data model back with `terraform apply`.
- The change is right. The data model is behind, so edit the YAML to match, and the plan goes quiet without touching the router.

Either way, the data model is where the decision gets recorded.

One limit to know about. A plan only compares what Terraform manages. If someone adds something Terraform has never heard of, such as a route that isn't in your data, the plan says nothing. You will see that happen too.

## Worked Example

A made-up script that checks a made-up thing: whether a file matches what it should. It shows the pattern you need, which is run, capture the exit code at once, branch on it, and exit with something the caller can read:

```bash
#!/usr/bin/env bash
# Is the notes file the same as the saved copy?

diff -q notes.txt notes.saved > /dev/null 2>&1
code=$?

if [ "$code" -eq 0 ]; then
    echo "SAME: notes.txt matches the saved copy"
    exit 0
elif [ "$code" -eq 1 ]; then
    echo "CHANGED: notes.txt differs from the saved copy"
    exit 1
else
    echo "ERROR: diff could not compare the files"
    exit 2
fi
```

Things to notice:

- `code=$?` comes straight after the command. Any command in between replaces `$?`.
- `[ "$code" -eq 0 ]` compares numbers. The quotes keep the test from breaking if the variable is empty.
- Every branch ends with an `exit`, so the script's own exit code is a decision, not an accident.
- The messages start with one fixed word. That makes them easy to search for and easy for a program to read.

## Technical Requirements

`drift_check.sh`, in this folder, does this:

| `terraform plan -detailed-exitcode` exits | Script prints a line starting | Script also | Script exits |
|-------------------------------------------|-------------------------------|-------------|--------------|
| 0 | `IN SYNC` | nothing more | 0 |
| 2 | `DRIFT` | the plan's `Plan:` summary line | 2 |
| anything else | `ERROR` | nothing more | 1 |

The full plan output goes into `drift-plan.txt` in this folder every time. The text after the first word is up to you. The script may only plan. It must never run `apply` or `destroy`, and it must not contain any login details. They come from the environment, as in TODO 06.

After you finish, the BGP neighbor descriptions in `data/bgp.nac.yaml` must be back to the name of the peer (R10, R11, R12), and `terraform plan` must show no changes.

## Notation Used Below

Skeletons in the Steps section use one kind of blank:

```
...   - replace this with your own value or expression.
```

Everything else in a skeleton is already filled in and must stay as it is.

## Working Folder

Do everything for this TODO from its own folder. Open a terminal and run:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-10-Detect-and-Reconcile-Drift
```

Change the path if you put the course folder somewhere else.

## Steps

Each step starts by saying where to run it. "On CWS" means a normal terminal on the lab machine (CWS), in this folder. "On R10" (or R11, R12) means that router's own command line (SSH or console). These labels are only directions. You don't type them anywhere.

```
1. On CWS: Create drift_check.sh. Fill in each ...:

     #!/usr/bin/env bash
     # Compare the routers with the data model. Changes nothing.

     terraform plan -detailed-exitcode -no-color > drift-plan.txt 2>&1
     code=...

     if [ "$code" -eq ... ]; then
         echo "..."
         exit ...
     elif [ "$code" -eq ... ]; then
         echo "..."
         grep '^Plan:' drift-plan.txt
         exit ...
     else
         echo "..."
         exit ...
     fi

   Each message must start with the word from the Technical Requirements
   table. The grep line prints the plan's summary, for example
   "Plan: 0 to add, 1 to change, 0 to destroy."

2. On R10, R11 and R12: Take a snapshot on each router, then check it:

     copy running-config flash:before-todo10.cfg
     dir flash:before-todo10.cfg

   Press Enter to accept the file name. Use bootflash: if flash: isn't
   accepted. The listing must show a size above zero.

3. On CWS: Bring Terraform's record forward from the last TODO:

     cp ../TODO-09-BGP-Peering/terraform.tfstate .
     terraform init

   Make sure the router login is still exported in this terminal
   (IOSXE_USERNAME and IOSXE_PASSWORD, as in TODO 06). Then run your
   script on routers that haven't been touched:

     bash drift_check.sh
     echo $?

   It must print an IN SYNC line and the exit code must be 0. If it
   doesn't, fix that first, because the rest of this TODO depends on it.

4. On R11: Make drift. Change the description of the branch LAN
   loopback by hand:

     configure terminal
      interface Loopback10
       description MANUAL-CHANGE
     end

   On R10: Add a route that is not in the data model. 192.0.2.0/24 is
   a documentation range, so it is harmless:

     configure terminal
      ip route 192.0.2.0 255.255.255.0 10.10.10.11
     end

5. On CWS: Detect it:

     bash drift_check.sh
     echo $?

   Expected output is in Test It Yourself below. Then read what changed:

     grep -n 'description' drift-plan.txt

   Terraform found the loopback on R11. It did not find the route on R10.
   Remember that for later.

6. On CWS: The router is wrong here, so push the data model back:

     terraform apply

   Look through the plan. It must change one thing, the description on
   Loopback10 of R11. Type yes. Then run bash drift_check.sh again and
   the result must be IN SYNC.

7. On R10: Remove the route that Terraform never saw:

     configure terminal
      no ip route 192.0.2.0 255.255.255.0 10.10.10.11
     end

8. On CWS: Save a copy of the file you are about to edit:

     cp data/bgp.nac.yaml /tmp/bgp.before-todo10.yaml

   On R12: Now somebody renames a neighbor on the router, and this
   time the change is correct:

     configure terminal
      router bgp 65010
       neighbor 10.255.0.10 description R10-PRIMARY
     end

   On CWS: Run bash drift_check.sh. It must say DRIFT. This time the
   router is right and the data is behind. Edit data/bgp.nac.yaml, and in
   R12's entry change the description of the neighbor 10.255.0.10 from
   R10 to R10-PRIMARY. Only that one line. Run the check again. It must
   say IN SYNC, and the router wasn't touched.

9. On CWS: Put the data back and the router with it:

     cp /tmp/bgp.before-todo10.yaml data/bgp.nac.yaml
     terraform apply

   The plan must change one thing, the neighbor description on R12.
   Type yes. Then:

     bash drift_check.sh

   It must print IN SYNC.

10. On CWS: Run: python grading.py
```

## Test It Yourself (without the grader)

First test the script without touching a router. Make a pretend `terraform` that only prints a result and exits with the code you choose, and put it first on the path for one command at a time:

```
mkdir -p /tmp/fakebin
for rc in 0 1 2; do
  printf '#!/bin/sh\necho "Plan: 0 to add, 2 to change, 0 to destroy."\nexit %s\n' $rc > /tmp/fakebin/terraform
  chmod +x /tmp/fakebin/terraform
  PATH=/tmp/fakebin:$PATH bash drift_check.sh
  echo "plan exit $rc -> script exit $?"
done
```

Expect one result per code. The words after the colon are yours:

```
IN SYNC: the routers match the data model
plan exit 0 -> script exit 0
ERROR: terraform plan failed, see drift-plan.txt
plan exit 1 -> script exit 1
DRIFT: the routers differ from the data model
Plan: 0 to add, 2 to change, 0 to destroy.
plan exit 2 -> script exit 2
```

Then remove the pretend one so nothing is left behind: `rm -r /tmp/fakebin`.

Now the real thing. On CWS, after step 4, the check should look like this. The number of changes and the wording of the message vary:

```
$ bash drift_check.sh
DRIFT: the routers differ from the data model
Plan: 0 to add, 1 to change, 0 to destroy.
$ echo $?
2
```

and in the file:

```
$ grep -n 'description' drift-plan.txt
...  ~ description = "BRANCH-LAN" -> "MANUAL-CHANGE"
...  ~ description = "MANUAL-CHANGE" -> "BRANCH-LAN"
```

You may see the line twice. The first shows what changed on the router behind Terraform's back. The second shows what Terraform would do about it. The route you added on R10 appears nowhere, because Terraform has no resource that owns it. A plan finds drift in what it manages and says nothing about the rest. Anything you need to catch outside that list needs a different check, which is what TODO 11 is for.

After step 6 and after step 9 the check must end with:

```
$ bash drift_check.sh
IN SYNC: the routers match the data model
```

Ask Terraform the one question the grader asks:

```
terraform plan -detailed-exitcode
echo $?
```

`0` means no changes, `2` means changes are waiting, `1` means an error.

## Put a router back

If a step went wrong and you want to clear the manual changes by hand, undo them on the routers. On R10:

```
configure terminal
 no ip route 192.0.2.0 255.255.255.0 10.10.10.11
end
```

On R11:

```
configure terminal
 interface Loopback10
  description BRANCH-LAN
end
```

On R12:

```
configure terminal
 router bgp 65010
  neighbor 10.255.0.10 description R10
end
```

Then restore the data file if you changed it (`cp /tmp/bgp.before-todo10.yaml data/bgp.nac.yaml`) and run `bash drift_check.sh`. The snapshot from step 2 can also put a router back in one command with `configure replace flash:before-todo10.cfg`. It replaces the whole running configuration, so use it only if nothing else changed on that router since the snapshot.

## Grading Check

```
python grading.py
```

Run it in the terminal where you exported `IOSXE_USERNAME` and `IOSXE_PASSWORD`. The grader re-checks TODO 01 to TODO 09 first, each against only the data files that belong to it. Then it runs your `drift_check.sh` four times in a temporary folder, against a pretend `terraform` that exits 0, 2, 1 and 3. It checks the first word of the message, the extra `Plan:` line on drift, the exit code, that `drift-plan.txt` was written, and that the only thing the script ever ran was `plan -detailed-exitcode`. It also reads the script itself and rejects `apply`, `destroy` and login details. Then it checks that every BGP neighbor description in the merged data is the peer's name again, and last, `terraform plan -detailed-exitcode` has to exit `0`. Your real files are never touched, and nothing is sent to a router.

Before you complete this TODO:

```
TODO 10 - Detect and Reconcile Drift
────────────────────────────────────────────────────────────────────────────────

[10] Detecting and reconciling drift...

✗ TODO 10 Not Complete

The pipeline cannot continue because drift cannot be detected and reconciled yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 10 - Detect and Reconcile Drift
────────────────────────────────────────────────────────────────────────────────

[10] Detecting and reconciling drift...
  drift_check.sh -> plan exit 0 prints IN SYNC and exits 0
  drift_check.sh -> plan exit 2 prints DRIFT and the Plan line, exits 2
  drift_check.sh -> any other plan exit prints ERROR, exits 1
  drift_check.sh -> only ever runs plan (no apply, no destroy)
  BGP neighbor descriptions -> back to R10, R11, R12
  terraform plan -> no changes

✓ TODO 10 Complete
Drift is detected by drift_check.sh, reconciled both ways, and the routers match the data model again.
```

---
