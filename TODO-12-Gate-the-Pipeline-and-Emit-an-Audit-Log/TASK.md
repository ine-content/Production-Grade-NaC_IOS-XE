# TODO 12 — Gate the Pipeline and Emit an Audit Log

## Topics Covered

```
✓ A pipeline as ordered stages, where a failure stops everything after it
✓ An approval gate: nothing is pushed to a router unless a person asks for it
✓ Plan exit code 2 is a result, not a failure
✓ An audit log: who ran what, when, and what happened, including what was skipped
✓ Tying the whole course together: validate, plan, apply, verify
```

## Recap

TODO 11 is solved in this folder, and so is everything before it. You can validate the data (TODO 03 and 04), plan against the routers (TODO 05 to 10), push (TODO 06) and test the live state (TODO 11). Each of those you ran by hand, one at a time, and you decided when to move on. In this TODO a script makes that decision for you, and writes down every decision it made.

## Scenario

By hand, it is easy to skip a step. Someone is in a hurry, the schema complains, and they run `terraform apply` anyway. A pipeline makes the order fixed and the stopping automatic. The stages are:

1. validate: the data passes the schema and every rule.
2. plan: Terraform reads the routers and says whether anything would change.
3. apply: Terraform pushes the changes. This only happens when someone asked for it with `--apply`, and only when the plan found something to push.
4. verify: the nac-test tests from TODO 11 pass on the live routers.

If a stage fails, the stages after it do not run. Bad data never reaches a router. A router that can't be planned is never changed.

The plan stage needs one careful rule. `terraform plan -detailed-exitcode` exits `2` when there are changes to make. That is not a failure, because it is the answer you wanted. The pipeline records it as `CHANGES` and carries on. Only an exit code of `1`, or anything else unexpected, is a failure.

The second half is the audit log. Every stage, including the ones that were skipped, is written to `audit.log` as one line of JSON: when, who, which run, which stage, what command, what exit code, and what the result was. Writing the skipped stages down matters. Later, someone asking "why didn't the change go out?" can read the log and see that validation failed and nothing after it ran.

## Worked Example

A made-up pipeline with three steps, where the second one fails. It shows the gate and the log line, without any of your tools:

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
- A skipped step still prints a line. It is the same loop, so nothing is forgotten.
- `subprocess.run(command)` lets the command print to your terminal as usual, and `.returncode` gives you the exit code.
- One JSON object on one line is easy to add to a file, easy to search with `grep`, and easy for another program to read.

## Technical Requirements

`pipeline.py`, in this folder. It runs these four stages in this order:

| Stage | Command | Result |
|-------|---------|--------|
| `validate` | `nac-validate data -s .schema.yaml -r rules` | exit 0 is `PASS`, anything else is `FAIL` |
| `plan` | `terraform plan -detailed-exitcode -no-color` | 0 is `PASS`, 2 is `CHANGES`, anything else is `FAIL` |
| `apply` | `terraform apply -auto-approve -no-color` | runs only with `--apply` and only after `CHANGES`. 0 is `PASS`, anything else is `FAIL`. Otherwise `SKIPPED` |
| `verify` | `nac-test -d data -t tests -o test-results` | exit 0 is `PASS`, anything else is `FAIL` |

After any `FAIL`, every stage still to come is `SKIPPED`. The script exits `1` if any stage failed and `0` otherwise.

Every stage adds one line to `audit.log`, which is appended to and never overwritten. The line is a JSON object with exactly these keys:

```json
{"time": "2026-10-08T14:03:11+00:00", "run": "3fa9c1d2", "user": "expert", "stage": "plan", "command": "terraform plan -detailed-exitcode -no-color", "exit_code": 2, "result": "CHANGES"}
```

`time` is UTC. `run` is the same for all four lines of one run and different between runs. `exit_code` is `null` for a skipped stage. No password or other login detail may reach the log or the script. The tools read the login from the environment, as before.

## Notation Used Below

Skeletons in the Steps section use one kind of blank:

```
...   - replace this with your own value or expression.
```

Everything else in a skeleton is already filled in and must stay as it is.

## Working Folder

Do everything for this TODO from its own folder. Open a terminal and run:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-12-Gate-the-Pipeline-and-Emit-an-Audit-Log
```

Change the path if you put the course folder somewhere else.

## Steps

Each step starts by saying where to run it. "On CWS" means a normal terminal on the lab machine (CWS), in this folder. "On R10" (or R11, R12) means that router's own command line (SSH or console). These labels are only directions. You don't type them anywhere.

```
1. On CWS: Create pipeline.py. The record function is complete and you
   copy it as it is. Fill in each ... :

     #!/usr/bin/env python3
     # Run the NaC pipeline: validate, plan, apply (only when approved), verify.
     import json
     import os
     import subprocess
     import sys
     import uuid
     from datetime import datetime, timezone

     LOG = "audit.log"
     RUN = uuid.uuid4().hex[:8]
     APPROVED = "--apply" in sys.argv[1:]

     STAGES = [
         ("validate", [...]),
         ("plan", [...]),
         ("apply", [...]),
         ("verify", [...]),
     ]


     def record(stage, command, exit_code, result):
         entry = {
             "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "run": RUN,
             "user": os.environ.get("USER", "unknown"),
             "stage": stage,
             "command": " ".join(command),
             "exit_code": exit_code,
             "result": result,
         }
         with open(LOG, "a", encoding="utf-8") as log:
             log.write(json.dumps(entry) + "\n")
         print(f"{stage:<9} {result}")


     def main():
         failed = False
         changes_waiting = False
         for stage, command in STAGES:
             if ...:
                 record(stage, command, None, "SKIPPED")
                 continue
             code = subprocess.run(command).returncode
             if stage == "plan" and code == ...:
                 changes_waiting = True
                 result = "..."
             elif code == ...:
                 result = "..."
             else:
                 result = "..."
                 failed = True
             record(stage, command, code, result)
         sys.exit(...)


     if __name__ == "__main__":
         main()

   - Each command in STAGES is a list of words, as in the Worked
     Example. Use the commands from the Technical Requirements table.
   - The condition at the top of the loop is true when the pipeline has
     already failed, or when this is the apply stage and it is not
     approved or there are no changes waiting. Both cases skip the stage.
   - The exit code of the script is 1 after a failure and 0 otherwise.

2. On R10, R11, R12: Take a snapshot on each router, then check it:

     copy running-config flash:before-todo12.cfg
     dir flash:before-todo12.cfg

   Press Enter to accept the file name. Use bootflash: if flash: isn't
   accepted. The listing must show a size above zero.

3. On CWS: Bring Terraform's record forward from the last TODO:

     cp ../TODO-11-Verify-Live-State-with-nac-test/terraform.tfstate .
     terraform init

   Make sure the router login is still exported in this terminal
   (IOSXE_USERNAME and IOSXE_PASSWORD, as in TODO 06).

4. On CWS: A normal run, with nothing to change:

     python pipeline.py
     echo $?

   Expected output is in Test It Yourself below. Every stage but apply
   should be PASS, and apply SKIPPED. If plan says CHANGES here,
   something on a router differs from your data. Run terraform plan to
   see what, fix that first, and run again.

5. On CWS: The gate. Break the data so validation fails, ask for the
   most, and see what stops:

     sed -i.bak 's/remote_as: 65010/remote_as: same/' data/bgp.nac.yaml
     python pipeline.py --apply
     echo $?
     mv data/bgp.nac.yaml.bak data/bgp.nac.yaml

   validate must say FAIL, the three stages after it must say SKIPPED,
   and the exit code must be 1. Nothing was sent to a router, even with
   --apply.

6. On R11: Make a change the pipeline has to push. Change the
   description of Loopback10 by hand, as in TODO 10:

     configure terminal
      interface Loopback10
       description MANUAL-CHANGE
     end

7. On CWS: Run the pipeline without approval:

     python pipeline.py

   plan must say CHANGES, apply must say SKIPPED, and verify must say
   PASS. The router is still different from the data, because you did
   not approve anything.

8. On CWS: Now approve it:

     python pipeline.py --apply

   validate PASS, plan CHANGES, apply PASS, verify PASS. Check the
   router:

     On R11: show running-config interface Loopback10 | include description

   It must say BRANCH-LAN again.

9. On CWS: Look at what the log says about those runs:

     tail -n 12 audit.log

   You should see the lines of the last three runs, each with its own
   run id.

10. On CWS: Run: python grading.py
```

## Test It Yourself (without the grader)

First test every path without a router, with pretend tools. They exit with whatever code you choose and do nothing else. Work in a scratch folder, so the real `audit.log` isn't touched:

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

Now try the cases. Each runs the pipeline with different pretend results:

```
PATH=/tmp/fakebin:$PATH python pipeline.py; echo "exit $?"
PATH=/tmp/fakebin:$PATH P=2 python pipeline.py; echo "exit $?"
PATH=/tmp/fakebin:$PATH P=2 python pipeline.py --apply; echo "exit $?"
PATH=/tmp/fakebin:$PATH V=1 python pipeline.py --apply; echo "exit $?"
PATH=/tmp/fakebin:$PATH P=2 A=1 python pipeline.py --apply; echo "exit $?"
```

Expect, in this order:

```
validate  PASS
plan      PASS
apply     SKIPPED
verify    PASS
exit 0

validate  PASS
plan      CHANGES
apply     SKIPPED
verify    PASS
exit 0

validate  PASS
plan      CHANGES
apply     PASS
verify    PASS
exit 0

validate  FAIL
plan      SKIPPED
apply     SKIPPED
verify    SKIPPED
exit 1

validate  PASS
plan      CHANGES
apply     FAIL
verify    SKIPPED
exit 1
```

If you print extra message lines of your own, such as a note that the pipeline stopped, they can appear too. The stage lines and the exit codes are what matter. Then look at the log of those five runs:

```
wc -l audit.log
tail -n 4 audit.log
```

`wc -l` must say `20`. The last four lines are the failed apply run, and the skipped verify line must show `"exit_code": null`. Then go back to your folder and clean up:

```
cd ~/Production-Grade-NaC_IOS-XE/TODO-12-Gate-the-Pipeline-and-Emit-an-Audit-Log
rm -r /tmp/fakebin /tmp/pipe-test
```

On the real routers, steps 4 to 8 should look like this. The run ids and times vary:

```
$ python pipeline.py
validate  PASS
plan      PASS
apply     SKIPPED
verify    PASS
$ echo $?
0
```

and for the gate:

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

Ask Terraform the one question the grader asks:

```
terraform plan -detailed-exitcode
echo $?
```

`0` means no changes, `2` means changes are waiting, `1` means an error.

## Put a router back

If step 8 did not finish and R11 still shows `MANUAL-CHANGE`, put it back by hand:

```
configure terminal
 interface Loopback10
  description BRANCH-LAN
end
```

Then run `python pipeline.py` and every stage but apply should say PASS. The snapshot from step 2 can also put a router back in one command with `configure replace flash:before-todo12.cfg`. It replaces the whole running configuration, so use it only if nothing else changed on that router since the snapshot.

Don't delete `audit.log` unless you mean to. The grader reads it to see that you really ran the gate and the apply, and if it is gone you have to repeat steps 5 to 8.

## Grading Check

```
python grading.py
```

Run it in the terminal where you exported `IOSXE_USERNAME` and `IOSXE_PASSWORD`. The grader re-checks TODO 01 to TODO 11 first, each against only the data files that belong to it. Then it runs your `pipeline.py` against pretend tools in a temporary folder: a clean run, a run with changes waiting and no approval, an approved run, an approved run with nothing to apply, a run where each of validate, plan, apply and verify fails in turn, and two runs in a row to check that the log is appended to. For each it checks the stage results, the exit code, which tools were called and in what order, and the fields in every log line. It makes sure a pretend password never reaches the log. Then it reads your real `audit.log` and looks for a run that validation stopped and a run that applied a change. Last, `terraform plan -detailed-exitcode` has to exit `0`. Nothing is changed on a router by the grader.

Before you complete this TODO:

```
TODO 12 - Gate the Pipeline and Emit an Audit Log
────────────────────────────────────────────────────────────────────────────────

[12] Gating the pipeline and writing the audit log...

✗ TODO 12 Not Complete

The pipeline cannot continue because changes are not yet gated and recorded in an audit log.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 12 - Gate the Pipeline and Emit an Audit Log
────────────────────────────────────────────────────────────────────────────────

[12] Gating the pipeline and writing the audit log...
  pipeline.py -> validate, plan, apply, verify, in that order
  gate -> a failed stage stops the rest, which are logged SKIPPED
  apply -> only with --apply and only when the plan found changes
  audit.log -> one JSON line per stage, no credentials in it
  audit.log -> shows a run stopped by validation and a run that applied a change
  terraform plan -> no changes

✓ TODO 12 Complete
The pipeline gates every change, applies only with approval, and records each stage in the audit log.
```

---
