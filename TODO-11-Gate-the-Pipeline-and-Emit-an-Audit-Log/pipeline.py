#!/usr/bin/env python3
# Run the NaC pipeline: validate, plan, apply (only when approved), verify.
# This file is finished. You don't edit it. Read the comments to see how it works.
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone

# The log file. Every stage adds one line to it.
LOG = "audit.log"

# A short random id. All four stages of one run share it, so you can tell runs apart in the log.
RUN = uuid.uuid4().hex[:8]

# True only when you run "python pipeline.py --apply". Without --apply, nothing is pushed to a router.
APPROVED = "--apply" in sys.argv[1:]

# The four stages, in order. Each one is a name and a command, with the command split into words.
STAGES = [
    ("validate", ["nac-validate", "data", "-s", ".schema.yaml", "-r", "rules"]),
    ("plan", ["terraform", "plan", "-detailed-exitcode", "-no-color"]),
    ("apply", ["terraform", "apply", "-auto-approve", "-no-color"]),
    ("verify", ["nac-test", "-d", "data", "-t", "tests", "-o", "test-results"]),
]


def record(stage, command, exit_code, result):
    # Write one line of JSON to audit.log, then print the stage and its result on the screen.
    # This runs for every stage, including the ones that were skipped.
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
    # failed: true once a stage has failed.
    # changes_waiting: true when the plan found changes to push.
    failed = False
    changes_waiting = False
    for stage, command in STAGES:
        # SKIP CHECK
        # Skip this stage if an earlier stage failed. Also skip it if this is the apply stage
        # and it isn't allowed to run: you didn't use --apply, or the plan found nothing to push.
        if failed or (stage == "apply" and not (APPROVED and changes_waiting)):
            record(stage, command, None, "SKIPPED")
            continue
        # Run the command and keep its exit code. Exit code 0 means it worked.
        code = subprocess.run(command).returncode
        # CHANGES CHECK
        # For the plan stage, exit code 2 means "there are changes to make". That isn't a failure.
        if stage == "plan" and code == 2:
            changes_waiting = True
            result = "CHANGES"
        # PASS CHECK
        # Exit code 0 means the stage passed.
        elif code == 0:
            result = "PASS"
        # FAIL
        # Any other exit code is a failure. Remember it, so every later stage is skipped.
        else:
            result = "FAIL"
            failed = True
        record(stage, command, code, result)
    # EXIT CODE
    # Exit with 1 if any stage failed, otherwise 0.
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
