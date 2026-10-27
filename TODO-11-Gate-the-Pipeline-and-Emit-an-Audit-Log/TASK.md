# TODO 11 — Gate the Pipeline and Emit an Audit Log

## Topics Covered

```
✓ A pipeline as ordered stages, where a failure stops everything after it
✓ An approval gate: nothing is pushed to a router unless a person asks for it
✓ Plan exit code 2 is a result, not a failure
✓ An audit log: who ran what, when, and what happened, including what was skipped
✓ Tying the whole course together: validate, plan, apply, verify
```

## Recap

This folder already has TODO 10 solved, along with everything before it. So far you've validated the data (TODO 03 and 04), planned against the routers (TODO 05 to 09), pushed changes (TODO 06), and tested the live state (TODO 10). You ran each of those by hand, one at a time, and decided when to move on. In this TODO, a script makes that decision for you and writes down every choice it made. The script, `pipeline.py`, is already in this folder, and it's finished. Your job is to read it, test it, and run it for real, so it leaves a record in `audit.log`.

The grader looks for two real runs in `audit.log`: one that validation stopped (step 5), and one that applied a change (step 8). Without them, the grader fails, so don't skip those steps.

## Scenario

By hand, it's easy to skip a step. Someone's in a hurry, the schema complains, and they run `terraform apply` anyway. A pipeline fixes the order and stops automatically. The stages are:

1. validate: the data passes the schema and every rule.
2. plan: Terraform reads the routers and says whether anything would change.
3. apply: Terraform pushes the changes. This only happens when someone asked for it with `--apply`, and only when the plan found something to push.
4. verify: the nac-test tests from TODO 10 pass on the live routers.

If a stage fails, the stages after it don't run. Bad data never reaches a router. A router that can't be planned is never changed.

The plan stage needs one careful rule. `terraform plan -detailed-exitcode` exits `2` when there are changes to make. That isn't a failure, because it's the answer you wanted. The pipeline records it as `CHANGES` and carries on. Only an exit code of `1`, or anything else unexpected, counts as a failure.

The pipeline also keeps an audit log. Every stage, including the ones that were skipped, is written to `audit.log` as one line of JSON: when, who, which run, which stage, what command, what exit code, and what the result was. Writing the skipped stages down matters. Later, someone asking "why didn't the change go out?" can read the log and see that validation failed and nothing after it ran.

## Worked Example

Here's a made-up pipeline with three steps, where the second one fails. It shows the gate and the log line without any of your tools:

```python
import json
import subprocess

steps = [("lint", ["true"]), ("build", ["false"]), ("ship", ["true"])]
failed = False
for name, command in steps:
    if failed:
        print(json.dumps({"step": name, "result": "SKIPPED"}))
        continue
    code = subprocess.run(command).returncode
    if code != 0:
        failed = True
    print(json.dumps({"step": name, "result": "FAIL" if code else "PASS"}))
```

`true` and `false` are shell commands that do nothing and exit with 0 and 1. The output is:

```
{"step": "lint", "result": "PASS"}
{"step": "build", "result": "FAIL"}
{"step": "ship", "result": "SKIPPED"}
```

Things to notice:

- `failed` is set once and checked at the top of every pass of the loop. That one flag is the whole gate.
- A skipped step still prints a line. It's the same loop, so nothing is forgotten.
- `subprocess.run(command)` lets the command print to your terminal as usual, and `.returncode` gives you the exit code.
- One JSON object on one line is easy to add to a file, easy to search with `grep`, and easy for another program to read.

## Technical Requirements

`pipeline.py` is already in this folder, and it's finished. You don't edit it. It runs these four stages, in this order:

| Stage | Command | Runs when | Result |
|-------|---------|-----------|--------|
| `validate` | `nac-validate data -s .schema.yaml -r rules` | no earlier stage failed | exit 0 is `PASS`, anything else is `FAIL` |
| `plan` | `terraform plan -detailed-exitcode -no-color` | no earlier stage failed | 0 is `PASS`, 2 is `CHANGES`, anything else is `FAIL` |
| `apply` | `terraform apply -auto-approve -no-color` | you used `--apply`, the plan said `CHANGES`, and no earlier stage failed | 0 is `PASS`, anything else is `FAIL` |
| `verify` | `nac-test -d data -t tests -o test-results` | no earlier stage failed | exit 0 is `PASS`, anything else is `FAIL` |

A stage that doesn't run is `SKIPPED`. After any `FAIL`, every stage still to come is `SKIPPED`. The script exits `1` if any stage failed and `0` otherwise.

Every stage adds one line to `audit.log`. The file is only ever appended to, never overwritten. Each line is a JSON object with exactly these keys:

```json
{"time": "2026-10-08T14:03:11+00:00", "run": "3fa9c1d2", "user": "expert", "stage": "plan", "command": "terraform plan -detailed-exitcode -no-color", "exit_code": 2, "result": "CHANGES"}
```

`time` is UTC. `run` is the same for all four lines of one run and different between runs. `exit_code` is `null` for a skipped stage. Passwords and other login details must never reach the log or the script. The tools read the login from the environment, as before.

## The Provided pipeline.py

The script is already in this folder, and it's finished. You don't write or edit any of it. Open it and read the comments. Here's a map of the parts:

| Part of the file | What it does |
|------------------|--------------|
| `STAGES` | The four stages, in order. Each one is a name and a command, with the command split into words. |
| `APPROVED` | True only when you run the script with `--apply`. This is the approval gate. |
| `record(...)` | Writes one line of JSON to `audit.log` and prints the stage and its result. It runs for every stage, even skipped ones. |
| `# SKIP CHECK` | Skips a stage if an earlier stage failed. Also skips `apply` unless you used `--apply` and the plan found changes. |
| `# CHANGES CHECK` | For the plan stage, exit code 2 means "changes waiting". It's recorded as `CHANGES` and isn't a failure. |
| `# PASS CHECK` and `# FAIL` | Exit code 0 is `PASS`. Any other exit code is `FAIL`, and every later stage is skipped. |
| `# EXIT CODE` | The script exits `1` if any stage failed, and `0` otherwise. |

Leave the file as it is. The grader runs it, and an edited copy may no longer do these things.

## Working Folder

Do everything for this TODO from its own folder. Open a terminal and run:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-11-Gate-the-Pipeline-and-Emit-an-Audit-Log
```

Change the path if you put the course folder somewhere else.

## Before You Start

You can do each TODO on its own, so this one assumes the routers already have the work from TODO 06 to 08, plus RESTCONF, which you turned on by hand in TODO 10.

**Fresh routers need a one-time setup first.** Terraform talks to the routers over NETCONF, and the tests talk to them over RESTCONF. Neither works until you turn them on, and you need a login with privilege 15. Enter this on each of R10, R11, and R12, with your own username and password:

     configure terminal
      username <name> privilege 15 secret <password>
      netconf-yang
      ip http secure-server
      ip http authentication local
      restconf
     end
     write memory

You'll use that same username and password in a moment as `IOSXE_USERNAME` and `IOSXE_PASSWORD`. If you already did TODO 06 and TODO 10 on these routers, skip this block, because it's already there. Everything else (hostname, loopbacks, static routes, ACL, and OSPF) comes from the baseline apply below. You don't type any of it by hand.

Here is how to check R10:

     show running-config | include ip http|restconf
     show ip ospf neighbor

You should see ip http secure-server, ip http authentication local, and restconf, plus two OSPF neighbors in state FULL.

Even if the routers already look like that, start with a baseline apply. This folder already has the solved data and main.tf for everything before this TODO. The apply does two jobs. It gives Terraform a record of the earlier work, so later plans only show this TODO's changes. And it catches up any router that's behind, like a new router, a reset one, or a restored snapshot. If a router already has the work, the apply just matches it. On CWS, in this folder, set the router login:

     export IOSXE_USERNAME=<your username>
     read -s IOSXE_PASSWORD; export IOSXE_PASSWORD

Then run:

     terraform init
     terraform plan
     terraform apply

The plan lists what the earlier TODOs configured. Read it and type yes. Then run write memory on R10, R11, and R12 so they keep the config after a reload.

When it finishes, run the check commands again and make sure the output looks right.

## Steps

Each step starts by saying where to run it. "On CWS" means a normal terminal on the lab machine (CWS), in this folder. "On R10" (or R11, R12) means that router's own command line (SSH or console). These labels are only directions. You don't type them anywhere. Steps 5 and 8 are the important ones for grading, because they write the two real runs to `audit.log`.

```
1. On CWS: Open pipeline.py in your editor and read it. It's already in
   this folder, and it's finished, so you don't change anything. The
   comments explain each part, and The Provided pipeline.py section
   above gives you a map. Find the SKIP CHECK, the CHANGES CHECK, and
   the EXIT CODE.

2. On R10, R11, and R12: Take a snapshot on each router, then check it:

     copy running-config flash:before-todo11.cfg
     dir flash:before-todo11.cfg

   Press Enter to accept the file name. Use bootflash: if flash: isn't
   accepted. The listing must show a size above zero.

3. On CWS: Test the script with pretend tools. Do Part 1 of Test It
   Yourself, below. It takes about five minutes and doesn't touch a
   router. All five cases must print exactly what Part 1 shows.

4. On CWS: A normal run, with nothing to change:

     python pipeline.py
     echo $?

   Expected output is in Part 2 of Test It Yourself below. Every stage
   but apply should be PASS, and apply SKIPPED. If plan says CHANGES
   here, something on a router differs from your data. Run terraform
   plan to see what, fix that first, and run again.

5. On CWS: The gate. Break the data so validation fails, ask for an apply
   anyway, and see what stops:

     sed -i.bak 's/area: 0/area: zero/' data/ospf.nac.yaml
     python pipeline.py --apply
     echo $?
     mv data/ospf.nac.yaml.bak data/ospf.nac.yaml

   validate must say FAIL, the three stages after it must say SKIPPED,
   and the exit code must be 1. Nothing was sent to a router, even with
   --apply. This run is the first of the two real runs the grader looks
   for in audit.log. Make sure the mv line ran, so your data is back to
   normal.

6. On R11: Make a change the pipeline has to push. Change the
   description of Loopback10 by hand, as in TODO 09:

     configure terminal
      interface Loopback10
       description MANUAL-CHANGE
     end

7. On CWS: Run the pipeline without approval:

     python pipeline.py

   plan must say CHANGES, apply must say SKIPPED, and verify must say
   PASS. The router is still different from the data, because you didn't
   approve anything.

8. On CWS: Now approve it:

     python pipeline.py --apply

   validate PASS, plan CHANGES, apply PASS, verify PASS. This run is the
   second of the two real runs the grader looks for in audit.log. Check
   the router:

     On R11: show running-config interface Loopback10 | include description

   It must say BRANCH-LAN again.

   Terraform only changes the running configuration, so a reload would
   undo it. On R11: Save it to the startup configuration:

     write memory

9. On CWS: Look at what the log says about those runs:

     tail -n 12 audit.log

   You should see the lines of the last three runs, each with its own
   run id.

10. On CWS: Run: python grading.py
```

## Test It Yourself (without the grader)

### Part 1: Try it with pretend tools

This part tests the provided script's logic without touching a router. You make pretend versions of `nac-validate`, `terraform`, and `nac-test`. Each pretend tool just exits with a code you choose.

Set them up once. Everything happens in a scratch folder, so your real `audit.log` isn't touched:

```
mkdir -p /tmp/fakebin /tmp/pipe-test
cat > /tmp/fakebin/stub <<'EOF'
#!/bin/sh
case "$(basename "$0")" in
  nac-validate) exit ${V:-0};;
  terraform) case "$1" in plan) exit ${P:-0};; apply) exit ${A:-0};; esac;;
  nac-test) exit ${T:-0};;
esac
EOF
chmod +x /tmp/fakebin/stub
for t in nac-validate terraform nac-test; do ln -sf stub /tmp/fakebin/$t; done
cp pipeline.py /tmp/pipe-test
cd /tmp/pipe-test
```

The letters in front of a command are knobs. `V=1` makes the pretend `nac-validate` fail. `P=2` makes the pretend plan say "changes waiting". `A=1` makes the pretend apply fail. A knob you don't set means exit code 0, which is a pass.

Now run five cases, one at a time. Each one shows the command and what you should see.

Here's how to read each command. `PATH=/tmp/fakebin:$PATH` makes the shell find the pretend tools first, for this one command only. The provided `pipeline.py` runs, but no router is touched. `python pipeline.py` runs the script. `echo "exit $?"` prints the script's exit code, so you can check it. The knobs you add in front (`V=1`, `P=2`, `A=1`) change what the pretend tools do.

**Case 1: everything passes, no `--apply`.**

```
PATH=/tmp/fakebin:$PATH python pipeline.py; echo "exit $?"
```

```
validate  PASS
plan      PASS
apply     SKIPPED
verify    PASS
exit 0
```

Apply is skipped because there was nothing to push, and you didn't ask for it.

**Case 2: the plan finds changes, no `--apply`.**

```
PATH=/tmp/fakebin:$PATH P=2 python pipeline.py; echo "exit $?"
```

```
validate  PASS
plan      CHANGES
apply     SKIPPED
verify    PASS
exit 0
```

`CHANGES` isn't a failure. Apply is still skipped, because you didn't approve it.

**Case 3: the plan finds changes, with `--apply`.**

```
PATH=/tmp/fakebin:$PATH P=2 python pipeline.py --apply; echo "exit $?"
```

```
validate  PASS
plan      CHANGES
apply     PASS
verify    PASS
exit 0
```

This is the only case where apply runs.

**Case 4: validation fails, even with `--apply`.**

```
PATH=/tmp/fakebin:$PATH V=1 python pipeline.py --apply; echo "exit $?"
```

```
validate  FAIL
plan      SKIPPED
apply     SKIPPED
verify    SKIPPED
exit 1
```

This is the gate. One failure stops everything after it.

**Case 5: apply fails.**

```
PATH=/tmp/fakebin:$PATH P=2 A=1 python pipeline.py --apply; echo "exit $?"
```

```
validate  PASS
plan      CHANGES
apply     FAIL
verify    SKIPPED
exit 1
```

Now check the log from those five runs. Each run writes four lines, so there should be 20:

```
wc -l audit.log
tail -n 4 audit.log
```

`wc -l` must say `20`. The last four lines are the failed apply run, and the skipped verify line must show `"exit_code": null`. Then go back to your folder and clean up:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-11-Gate-the-Pipeline-and-Emit-an-Audit-Log
rm -r /tmp/fakebin /tmp/pipe-test
```

### Part 2: What you should see on the real routers

In steps 4 to 8, the run ids and times vary. A normal run, with nothing to change, looks like this:

```
$ python pipeline.py
validate  PASS
plan      PASS
apply     SKIPPED
verify    PASS
$ echo $?
0
```

The gate run in step 5, where the data is broken on purpose, looks like this:

```
$ python pipeline.py --apply
validate  FAIL
plan      SKIPPED
apply     SKIPPED
verify    SKIPPED
$ echo $?
1
```

In the log, one skipped line looks like this:

```
{"time": "2026-10-08T14:07:40+00:00", "run": "b21e07aa", "user": "expert", "stage": "plan", "command": "terraform plan -detailed-exitcode -no-color", "exit_code": null, "result": "SKIPPED"}
```

Last, ask Terraform the one question the grader asks:

```
terraform plan -detailed-exitcode
echo $?
```

`0` means no changes, `2` means changes are waiting, and `1` means an error.

## Put a router back

If step 8 didn't finish and R11 still shows `MANUAL-CHANGE`, put it back by hand:

```
configure terminal
 interface Loopback10
  description BRANCH-LAN
end
```

Then run `python pipeline.py` and every stage but apply should say PASS. The snapshot from step 2 can also put a router back in one command with `configure replace flash:before-todo11.cfg`. It replaces the whole running configuration, so use it only if nothing else changed on that router since the snapshot.

Don't delete `audit.log` unless you mean to. The grader reads it to see that you really ran the gate and the apply, and if it's gone you have to repeat steps 5 to 8.

**Save the reset too.** The reset commands change only the running configuration. Run `write memory` on every router you reset. Without it, a reload brings this TODO's settings back from the startup configuration.

## Grading Check

```
python grading.py
```

Run it in the terminal where you exported `IOSXE_USERNAME` and `IOSXE_PASSWORD`. First the grader re-checks TODO 01 to TODO 10, each against only its own data files. Then it runs the `pipeline.py` in this folder against pretend tools in a temporary folder: a clean run, a run with changes waiting and no approval, an approved run, an approved run with nothing to apply, a run where each of validate, plan, apply and verify fails in turn, and two runs in a row to check that the log is appended to. For each it checks the stage results, the exit code, which tools were called and in what order, and the fields in every log line. It makes sure a pretend password never reaches the log. Then it reads your real `audit.log` and looks for a run that validation stopped and a run that applied a change. That's why steps 5 and 8 matter. Last, `terraform plan -detailed-exitcode` has to exit `0`. Nothing is changed on a router by the grader.

Before you complete this TODO:

```
TODO 11 - Gate the Pipeline and Emit an Audit Log
────────────────────────────────────────────────────────────────────────────────

[11] Gating the pipeline and writing the audit log...

✗ TODO 11 Not Complete

The pipeline cannot continue because changes are not yet gated and recorded in an audit log.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 11 - Gate the Pipeline and Emit an Audit Log
────────────────────────────────────────────────────────────────────────────────

[11] Gating the pipeline and writing the audit log...
  pipeline.py -> validate, plan, apply, verify, in that order
  gate -> a failed stage stops the rest, which are logged SKIPPED
  apply -> only with --apply and only when the plan found changes
  audit.log -> one JSON line per stage, no credentials in it
  audit.log -> shows a run stopped by validation and a run that applied a change
  terraform plan -> no changes

✓ TODO 11 Complete
The pipeline gates every change, applies only with approval, and records each stage in the audit log.
```

---
