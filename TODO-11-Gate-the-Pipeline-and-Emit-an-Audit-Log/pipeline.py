#!/usr/bin/env python3
# Run the NaC pipeline: validate, plan, apply (only when approved), verify.
# Every line marked FILL IN needs your answer. Replace each ... and leave the rest as it is.
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone

LOG = "audit.log"
RUN = uuid.uuid4().hex[:8]
APPROVED = "--apply" in sys.argv[1:]

# STAGE COMMANDS
STAGES = [
    ("validate", [...]),  # FILL IN: the nac-validate command, as a list of words
    ("plan", [...]),  # FILL IN: the terraform plan command
    ("apply", [...]),  # FILL IN: the terraform apply command
    ("verify", [...]),  # FILL IN: the nac-test command
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
        # SKIP CHECK
        if ...:  # FILL IN: true when this stage must be skipped
            record(stage, command, None, "SKIPPED")
            continue
        code = subprocess.run(command).returncode
        # CHANGES CHECK
        if stage == "plan" and code == ...:  # FILL IN: the plan's exit code for changes
            changes_waiting = True
            result = "..."  # FILL IN: the result text for changes
        # PASS CHECK
        elif code == ...:  # FILL IN: the exit code for a pass
            result = "..."  # FILL IN: the result text for a pass
        # FAIL
        else:
            result = "..."  # FILL IN: the result text for a failure
            failed = True
        record(stage, command, code, result)
    # EXIT CODE
    sys.exit(...)  # FILL IN: 1 if a stage failed, otherwise 0


if __name__ == "__main__":
    main()
