#!/usr/bin/env bash
# One-time, for a repo that others fork: move its job data off main onto a
# data branch, so new forks start with an empty output/ while this repo keeps
# all its data and keeps collecting more.
#
#   bash scripts/move-data-to-branch.sh sahil-data            # show what it would do
#   bash scripts/move-data-to-branch.sh sahil-data --apply    # do it
#
# Run from a fresh clone of the repo (step 4 deletes the local output/ files;
# they're kept on the data branch), with main checked out, after the
# workflows that support DATA_BRANCH (scripts/use-data-branch.sh) are on main.
# Nothing is deleted: the data branch starts as an exact copy of main.
#
# Steps:
#   1. Set the DATA_BRANCH repository variable, so every run from now on
#      writes to the data branch.
#   2. Wait for runs that started before that (they still write to main).
#   3. Create the data branch from the latest main (all data included).
#   4. On main, replace output/ with empty placeholders, and push.
#   5. Point GitHub Pages at the data branch, so the dashboard keeps its data.

set -euo pipefail

BRANCH="${1:?usage: move-data-to-branch.sh <data-branch> [--apply]}"
APPLY=false
[ "${2:-}" = "--apply" ] && APPLY=true

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
run() { echo "+ $*"; if $APPLY; then "$@"; fi; }

cd "$(git rev-parse --show-toplevel)"
if [ "$(git symbolic-ref --short HEAD)" != "main" ] || ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Error: check out main with no uncommitted changes first." >&2
  exit 1
fi
if ! grep -q "use-data-branch.sh" .github/workflows/linkedin_watch.yml; then
  echo "Error: push the DATA_BRANCH-aware workflows to main first." >&2
  exit 1
fi
$APPLY || echo "Dry run for $REPO; re-run with --apply to make these changes."

echo "== 1. Send new data to $BRANCH"
run gh variable set DATA_BRANCH --repo "$REPO" --body "$BRANCH"

echo "== 2. Wait for runs that started before the switch"
if $APPLY; then
  while true; do
    ids=$(for status in in_progress queued; do
            gh run list --repo "$REPO" --status "$status" --json databaseId -q '.[].databaseId'
          done)
    [ -z "$ids" ] && break
    echo "  waiting for run(s): $(echo "$ids" | tr '\n' ' ')"
    sleep 30
  done
fi

echo "== 3. Create $BRANCH from the latest main (keeps every job)"
run git fetch -q origin main
if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  echo "  $BRANCH already exists on GitHub; leaving it as is."
else
  run git push origin "refs/remotes/origin/main:refs/heads/$BRANCH"
fi

echo "== 4. Empty output/ on main (placeholders only)"
run git merge -q --ff-only origin/main
run git rm -r -q --cached -- output
if $APPLY; then
  rm -rf output
  mkdir -p output/deltas
  echo '{"updated_at": null, "jobs": []}' > output/all_jobs.json
  : > output/deltas/index.jsonl
  : > output/.gitkeep
fi
run git add -f output/all_jobs.json output/deltas/index.jsonl output/.gitkeep
run git commit -q -m "chore: move job data to the $BRANCH branch; main ships an empty output/"
run git push origin main

echo "== 5. Serve the dashboard from $BRANCH"
if $APPLY; then
  echo '{"source": {"branch": "'"$BRANCH"'", "path": "/"}}' \
    | gh api -X PUT "repos/$REPO/pages" --input - >/dev/null \
    && echo "  Pages now builds from $BRANCH." \
    || echo "  Could not switch Pages; do it by hand: Settings → Pages → Branch: $BRANCH, / (root)."
else
  echo "+ gh api -X PUT repos/$REPO/pages  (source: $BRANCH, /)"
fi

echo
echo "Done. Point anything that reads your data (e.g. job-hunter's JOB_SCRAPER_DIR clone) at $BRANCH:"
echo "  git clone -b $BRANCH https://github.com/$REPO.git <folder>"
