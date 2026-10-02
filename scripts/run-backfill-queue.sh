#!/usr/bin/env bash
# Run backfills one after another: each starts only once the previous one has
# finished.
#
#   bash scripts/run-backfill-queue.sh scrape_jobs.yml:backfill linkedin_backfill.yml
#
# Each argument is a workflow file; "name.yml:backfill" runs it with
# backfill=true. Used by the Backfill queue workflow (backfill_queue.yml),
# which setup.sh starts.
#
# Why not start them all at once: the watchers share the job-scraper-commit-push
# concurrency group, which holds one running and one waiting run, and GitHub
# cancels the waiting run when another arrives. A run that is cancelled anyway
# (an hourly run took its place) is started again, up to MAX_TRIES times.

set -euo pipefail

REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
POLL="${POLL_SECONDS:-30}"
TRIES="${MAX_TRIES:-3}"

# Wait for the run of $1 dispatched at or after $2, newer than run $3 (the
# attempt it replaces, which may have been cancelled seconds ago); print its id.
find_run() {
  local id=""
  until [ -n "$id" ]; do
    sleep "$POLL"
    id=$(gh run list --repo "$REPO" --workflow "$1" --event workflow_dispatch --limit 10 \
           --json databaseId,createdAt \
           -q "[.[] | select(.createdAt >= \"$2\" and .databaseId > $3)] | last | .databaseId // empty")
  done
  echo "$id"
}

failed=()
for spec in "$@"; do
  wf="${spec%%:*}"
  inputs=()
  [ "$spec" != "$wf" ] && inputs=(-f "${spec#*:}=true")
  conclusion=""
  id=0
  for try in $(seq 1 "$TRIES"); do
    since=$(date -u -d '-10 seconds' +%Y-%m-%dT%H:%M:%SZ)
    gh workflow run "$wf" --repo "$REPO" --ref main "${inputs[@]}"
    id=$(find_run "$wf" "$since" "$id")
    echo "▶ $spec: run $id (attempt $try)"
    until [ "$(gh run view "$id" --repo "$REPO" --json status -q .status)" = "completed" ]; do
      sleep "$POLL"
    done
    conclusion=$(gh run view "$id" --repo "$REPO" --json conclusion -q .conclusion)
    echo "  $spec: $conclusion"
    [ "$conclusion" = "cancelled" ] || break
  done
  [ "$conclusion" = "success" ] || failed+=("$spec ($conclusion)")
done

if [ ${#failed[@]} -gt 0 ]; then
  echo "Backfills that didn't succeed: ${failed[*]}" >&2
  exit 1
fi
echo "All backfills finished."
