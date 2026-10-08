#!/usr/bin/env bash
# Compare the routers with the data model. Changes nothing.

terraform plan -detailed-exitcode -no-color > drift-plan.txt 2>&1
code=$?

if [ "$code" -eq 0 ]; then
    echo "IN SYNC: the routers match the data model"
    exit 0
elif [ "$code" -eq 2 ]; then
    echo "DRIFT: the routers differ from the data model"
    grep '^Plan:' drift-plan.txt
    exit 2
else
    echo "ERROR: terraform plan failed, see drift-plan.txt"
    exit 1
fi
