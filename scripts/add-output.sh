#!/usr/bin/env bash
# Stage the given output files for a data commit, skipping any this run didn't
# produce (e.g. notified.json before the first notification). git add fails on
# a missing path, which would fail the whole commit step and lose the run.
#
#   bash scripts/add-output.sh output/linkedin_jobs.json output/notified.json ...
#
# -f because output/ is gitignored.

set -euo pipefail

for path in "$@"; do
  if [ -e "$path" ]; then
    git add -f -- "$path"
  fi
done
