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

# STAGE COMMANDS
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
        # SKIP CHECK
        if ...:
            record(stage, command, None, "SKIPPED")
            continue
        code = subprocess.run(command).returncode
        # CHANGES CHECK
        if stage == "plan" and code == ...:
            changes_waiting = True
            result = "..."
        # PASS CHECK
        elif code == ...:
            result = "..."
        # FAIL
        else:
            result = "..."
            failed = True
        record(stage, command, code, result)
    # EXIT CODE
    sys.exit(...)


if __name__ == "__main__":
    main()
