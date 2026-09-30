#!/usr/bin/env bash
# Check out the branch that holds this repo's job data, up to date.
#
# Workflows run this right after actions/checkout, which captures the commit
# at trigger time; another workflow may have committed since.
#
# DATA_BRANCH (repository variable; default "main") names the branch:
#   - main: just move to the latest origin/main (data lives on main, as in
#     any fork that hasn't set DATA_BRANCH).
#   - anything else (e.g. sahil-data): code comes from main, data (output/)
#     from the data branch. If main has new commits, record a commit on the
#     data branch whose tree is main's code plus the data branch's output/,
#     with both tips as parents, and push it when ENABLE_DATA_COMMITS=true.
#     The data branch only ever moves forward, so clones of it can always
#     `git pull --ff-only`, and main (what new forks copy) keeps no data.
#     A missing data branch is started from main.
#
# Works on GitHub's shallow checkouts: only the two tips are needed.

set -euo pipefail

BRANCH="${DATA_BRANCH:-main}"

# The update commit below is made before workflows configure a git identity.
if [ -z "$(git config user.name || true)" ]; then
  export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-github-actions[bot]}"
  export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"
  export GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-$GIT_AUTHOR_NAME}"
  export GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-$GIT_AUTHOR_EMAIL}"
fi

# Explicit refspecs: shallow clones may only track main by default.
fetch() { git fetch -q origin "+refs/heads/$1:refs/remotes/origin/$1"; }

if [ "$BRANCH" = "main" ]; then
  fetch main
  git checkout -q -B main origin/main
  exit 0
fi

for attempt in 1 2 3; do
  fetch main
  if ! fetch "$BRANCH" 2>/dev/null; then
    echo "Data branch '$BRANCH' doesn't exist yet; starting it from main."
    git checkout -q -B "$BRANCH" origin/main
    # Create it on the remote now, so later `git pull origin $BRANCH` steps work.
    if [ "${ENABLE_DATA_COMMITS:-}" = "true" ]; then
      git push -q origin "HEAD:refs/heads/$BRANCH"
    fi
    exit 0
  fi
  data="origin/$BRANCH"

  index=$(mktemp) && rm -f "$index"  # git needs a missing (not empty) index file
  GIT_INDEX_FILE="$index" git read-tree origin/main
  GIT_INDEX_FILE="$index" git rm -r -q --cached --ignore-unmatch -- output
  if git cat-file -e "$data:output" 2>/dev/null; then
    GIT_INDEX_FILE="$index" git read-tree --prefix=output/ "$data:output"
  fi
  tree=$(GIT_INDEX_FILE="$index" git write-tree)
  rm -f "$index"

  if [ "$tree" = "$(git rev-parse "$data^{tree}")" ]; then
    git checkout -q -B "$BRANCH" "$data"
    exit 0
  fi

  commit=$(git commit-tree "$tree" -p "$data" -p origin/main \
    -m "chore: bring $BRANCH up to date with main")
  git checkout -q -B "$BRANCH" "$commit"
  if [ "${ENABLE_DATA_COMMITS:-}" != "true" ]; then
    exit 0
  fi
  if git push -q origin "HEAD:$BRANCH"; then
    echo "Brought $BRANCH up to date with main."
    exit 0
  fi
  echo "Push of $BRANCH raced another update (attempt $attempt); retrying."
done

echo "Error: could not bring $BRANCH up to date with main." >&2
exit 1
