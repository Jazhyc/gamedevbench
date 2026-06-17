#!/bin/bash
# Unzips all individual task zips from tasks/ and tasks_gt/ into their respective directories.

set -e

# -o overwrites without prompting; a bare `unzip` would block on a stdin
# "replace?" prompt when a file already exists (e.g. a re-run), which hangs
# non-interactive/background invocations.
for zip in tasks/task_*.zip; do
    unzip -o -q "$zip" -d .
done
echo "Unzipped $(ls tasks/task_*.zip | wc -l | tr -d ' ') tasks to tasks/"

for zip in tasks_gt/task_*.zip; do
    unzip -o -q "$zip" -d .
done
echo "Unzipped $(ls tasks_gt/task_*.zip | wc -l | tr -d ' ') tasks to tasks_gt/"
