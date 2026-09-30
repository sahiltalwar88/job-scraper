#!/usr/bin/env bash
# Re-create your job-scraper fork from sahiltalwar88/job-scraper, keeping your
# own job data and settings.
#
#   bash refork-keeping-data.sh            # show what it would do (changes nothing)
#   bash refork-keeping-data.sh --apply    # do it
#
# Needs: git, python3, and the GitHub CLI logged in as you with permission to
# delete repos (run `gh auth refresh -s delete_repo` first). Run it from the
# folder that should hold the backup; put your config.json there too, or
# enter its path when asked.
#
# GitHub allows one fork of a repo per account, so your current fork has to
# be deleted before re-forking. Before that, this script:
#   - clones a complete backup of it (every branch, every commit) into
#     ./job-scraper-backup.git and checks it,
#   - saves your repository variables to ./job-scraper-backup-variables.json,
#   - lists your secrets (GitHub never reveals secret values; you'll re-enter
#     them), and
#   - asks you to type your repo's name to confirm.
# After re-forking it copies your output/ data into the new fork, restores
# your variables, sets CONFIG_JSON from your config.json, and turns on
# Actions and Pages. The backup stays on your computer.

set -euo pipefail

SOURCE="${SOURCE_REPO:-sahiltalwar88/job-scraper}"
GH_URL="${GH_URL:-https://github.com}"   # override for testing
APPLY=false
[ "${1:-}" = "--apply" ] && APPLY=true
say() { echo "== $*"; }

ME=$(gh api user -q .login)
REPO="$ME/job-scraper"
BACKUP="$PWD/job-scraper-backup.git"
VARS="$PWD/job-scraper-backup-variables.json"

gh repo view "$REPO" >/dev/null 2>&1 || { echo "Error: $REPO not found." >&2; exit 1; }
if ! $APPLY; then
  cat <<EOF
Dry run. With --apply this would:
  1. back up $REPO to $BACKUP and its variables to $VARS
  2. ask you to confirm, then delete $REPO on GitHub
  3. fork $SOURCE to $REPO (main only)
  4. copy your output/ data into the new fork and push it
  5. restore your variables, set CONFIG_JSON from your config.json,
     and turn on Actions, workflow permissions and Pages
Secrets you'll need to re-enter afterwards:
EOF
  gh secret list --repo "$REPO" --json name -q '.[].name' | sed 's/^/  - /'
  exit 0
fi

say "1. Back up $REPO"
[ -e "$BACKUP" ] && { echo "Error: $BACKUP already exists; move it aside first." >&2; exit 1; }
git clone -q --mirror "$GH_URL/$REPO.git" "$BACKUP"
git -C "$BACKUP" fsck --no-progress --no-dangling
branches=$(git -C "$BACKUP" for-each-ref --format='%(refname:short)' refs/heads | tr '\n' ' ')
echo "  backed up branches: $branches"
gh variable list --repo "$REPO" --json name,value > "$VARS"
echo "  saved $(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))))' "$VARS") variable(s) to $VARS"
SECRETS=$(gh secret list --repo "$REPO" --json name -q '.[].name' | tr '\n' ' ')
DATA_BRANCH=$(python3 -c '
import json, sys
print(next((v["value"] for v in json.load(open(sys.argv[1])) if v["name"] == "DATA_BRANCH"), "main"))' "$VARS")
git -C "$BACKUP" rev-parse -q --verify "refs/heads/$DATA_BRANCH" >/dev/null \
  || { echo "Error: your data branch '$DATA_BRANCH' isn't in the backup." >&2; exit 1; }
echo "  your job data is on: $DATA_BRANCH"

say "2. Delete $REPO on GitHub"
read -r -p "   Type $REPO to delete it (your backup is at $BACKUP): " answer
[ "$answer" = "$REPO" ] || { echo "Not confirmed; nothing deleted."; exit 1; }
gh repo delete "$REPO" --yes

say "3. Fork $SOURCE"
gh repo fork "$SOURCE" --default-branch-only --clone=false
for _ in $(seq 1 30); do gh repo view "$REPO" >/dev/null 2>&1 && break; sleep 2; done

say "4. Restore your job data"
work=$(mktemp -d)
git clone -q "$GH_URL/$REPO.git" "$work/fork"
rm -rf "$work/fork/output"
git -C "$BACKUP" archive "refs/heads/$DATA_BRANCH" output | tar -x -C "$work/fork"
git -C "$work/fork" add -A -f output
git -C "$work/fork" commit -q -m "chore: restore my job data after re-forking" || echo "  (no data to restore)"
git -C "$work/fork" push -q origin HEAD:main
echo "  output/ restored to main"

say "5. Restore settings"
python3 -c '
import json, sys
for v in json.load(open(sys.argv[1])):
    if v["name"] != "DATA_BRANCH":
        print(v["name"] + "\t" + v["value"])' "$VARS" | while IFS=$'\t' read -r name value; do
  gh variable set "$name" --repo "$REPO" --body "$value" && echo "  variable $name restored"
done
read -r -p "   Path to your config.json [config.json]: " cfg
cfg=${cfg:-config.json}
if [ -f "$cfg" ]; then
  bash "$work/fork/scripts/export-config-secret.sh" "$cfg" | gh secret set CONFIG_JSON --repo "$REPO" \
    && echo "  CONFIG_JSON set from $cfg"
else
  echo "  $cfg not found: set CONFIG_JSON yourself (scripts/export-config-secret.sh)."
fi
gh api -X PUT "repos/$REPO/actions/permissions" -F enabled=true -f allowed_actions=all >/dev/null \
  && echo "  Actions enabled"
gh api -X PUT "repos/$REPO/actions/permissions/workflow" -f default_workflow_permissions=write >/dev/null \
  && echo "  workflow permissions: read and write"
echo '{"source": {"branch": "main", "path": "/"}}' | gh api -X POST "repos/$REPO/pages" --input - >/dev/null 2>&1 \
  && echo "  Pages on main" || echo "  Pages: turn on by hand (Settings → Pages → main, / root)"

echo
echo "Done. Still to do by hand:"
for s in $SECRETS; do [ "$s" = CONFIG_JSON ] || echo "  - re-add secret $s (Settings → Secrets and variables → Actions)"; done
echo "  - re-clone your local copy (its history no longer matches): git clone $GH_URL/$REPO.git"
echo "Your backup: $BACKUP (delete it once everything works)."
