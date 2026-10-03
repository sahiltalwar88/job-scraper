#!/usr/bin/env bash
# setup.sh — one-command first-time setup for a Job_Scraper fork
#
# What it does (idempotent — safe to re-run):
#   1. Checks prerequisites (gh CLI installed + authenticated)
#   2. Enables GitHub Actions with read+write workflow permissions
#   3. Enables GitHub Pages (main branch, / root)
#   4. Sets ENABLE_DATA_COMMITS=true (the variable that makes scrapers save results)
#      and the CONFIG_JSON secret from your config.json
#   5. Optionally sets Pushover notification secrets
#   6. Optionally sets Anthropic API key for AI fit-scoring
#   7. Optionally starts a first-time backfill of the enabled watchers, one
#      after another (the Backfill queue workflow)
#
# Requirements:
#   gh CLI (https://cli.github.com) installed and authenticated
#   Run from the root of your cloned fork:  bash scripts/setup.sh

set -euo pipefail

# ── Terminal helpers ───────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC}  $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
info() { echo -e "   $*"; }
err()  { echo -e "${RED}✗${NC}  $*"; }
step() { echo -e "\n${CYAN}──${NC} $*"; }
ask()  { local prompt="$1"; local REPLY; read -r -p "   ${prompt} " REPLY; echo "$REPLY"; }
# Lowercase without bash 4's ${var,,}: macOS ships bash 3.2.
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

echo ""
echo "╔═════════════════════════════════════════════════════╗"
echo "║       Job Scraper — First-Time Setup Script         ║"
echo "╚═════════════════════════════════════════════════════╝"
echo ""

# ── 1. Prerequisites ───────────────────────────────────────────────────────────
step "Checking prerequisites"

if ! command -v gh &>/dev/null; then
  err "GitHub CLI (gh) is not installed."
  info "Install from https://cli.github.com, then run:  gh auth login"
  exit 1
fi
ok "GitHub CLI: $(gh --version | head -1)"

if ! gh auth status &>/dev/null 2>&1; then
  err "Not authenticated. Run:  gh auth login"
  exit 1
fi
GH_USER=$(gh api user -q .login 2>/dev/null)
ok "Authenticated as: $GH_USER"

# ── 2. Detect repo ─────────────────────────────────────────────────────────────
step "Detecting repository"

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)
if [ -z "$REPO" ]; then
  err "Could not detect GitHub repo. Run this script from inside your cloned fork."
  exit 1
fi
ok "Target repo: $REPO"

OWNER=$(echo "$REPO" | cut -d/ -f1)
REPONAME=$(echo "$REPO" | cut -d/ -f2)

# Warn if running against the upstream template (not a fork)
PARENT=$(gh repo view --json parent -q '.parent.nameWithOwner // ""' 2>/dev/null || true)
if [ -z "$PARENT" ]; then
  warn "This repo has no parent — if you haven't forked yet, do so first."
fi

# ── 3. Config files ─────────────────────────────────────────────────────────────
step "Checking config files"

# config.json is gitignored: workflows get it from the CONFIG_JSON secret.
CONFIG_PATH=$(ask "Path to your config.json [config.json]:")
CONFIG_PATH=${CONFIG_PATH:-config.json}
if [ -f "$CONFIG_PATH" ]; then
  if bash "$(dirname "$0")/export-config-secret.sh" "$CONFIG_PATH" | gh secret set CONFIG_JSON --repo "$REPO" 2>/dev/null; then
    ok "CONFIG_JSON secret set from $CONFIG_PATH (single line, via scripts/export-config-secret.sh)."
  else
    err "Could not set CONFIG_JSON from $CONFIG_PATH (is it valid JSON?)."
    info "Set it manually: bash scripts/export-config-secret.sh $CONFIG_PATH, then paste into"
    info "Settings → Secrets and variables → Actions → New repository secret → CONFIG_JSON."
  fi
else
  warn "$CONFIG_PATH not found — the scrapers need it."
  info "Create it from docs/cv-to-config-prompt.md (an AI interviews you from your résumé),"
  info "or copy config.example.json and edit it, then re-run this script."
fi

if [ -f "scoring_profile.json" ]; then
  ok "scoring_profile.json found."
else
  info "scoring_profile.json not found (optional — only needed for AI triage)."
fi

# ── 4. Actions permissions ──────────────────────────────────────────────────────
step "Configuring Actions permissions"

# Enable Actions
if gh api "repos/$REPO/actions/permissions" \
    --method PUT \
    --field enabled=true \
    --field allowed_actions=all \
    --silent 2>/dev/null; then
  ok "GitHub Actions enabled."
else
  warn "Could not enable Actions via API (may already be enabled)."
fi

# Set workflow permissions to read+write
if gh api "repos/$REPO/actions/permissions/workflow" \
    --method PUT \
    --field default_workflow_permissions=write \
    --field can_approve_pull_request_reviews=false \
    --silent 2>/dev/null; then
  ok "Workflow permissions set to read+write."
else
  warn "Could not set workflow permissions — set manually: Settings → Actions → General → Workflow permissions → Read and write."
fi

# ── 5. Required variable ────────────────────────────────────────────────────────
step "Setting required variables"

CURRENT_VAL=$(gh api "repos/$REPO/actions/variables/ENABLE_DATA_COMMITS" -q .value 2>/dev/null || true)
if [ "$CURRENT_VAL" = "true" ]; then
  ok "ENABLE_DATA_COMMITS=true already set."
else
  gh variable set ENABLE_DATA_COMMITS --body "true" 2>/dev/null \
    && ok "ENABLE_DATA_COMMITS=true set." \
    || { err "Failed to set ENABLE_DATA_COMMITS."; info "Set manually: Settings → Secrets and variables → Actions → Variables tab → Add ENABLE_DATA_COMMITS = true"; }
fi

# ── 6. GitHub Pages ─────────────────────────────────────────────────────────────
step "Enabling GitHub Pages"

# Test the exit status: on a 404, gh prints the error body to stdout.
if gh api "repos/$REPO/pages" --silent 2>/dev/null; then
  PAGES_URL=$(gh api "repos/$REPO/pages" -q .html_url 2>/dev/null || true)
  ok "GitHub Pages already active: $PAGES_URL"
else
  if gh api "repos/$REPO/pages" \
      --method POST \
      --field source[branch]=main \
      --field source[path]=/ \
      --silent 2>/dev/null; then
    ok "GitHub Pages enabled (main branch, / root)."
    info "Dashboard will be live in ~1 minute at: https://${OWNER}.github.io/${REPONAME}/triage.html"
  else
    warn "Could not enable Pages automatically."
    info "Set manually: Settings → Pages → Deploy from branch → main / (root)"
  fi
fi

# ── 7. Pushover notifications (optional) ────────────────────────────────────────
step "Pushover phone notifications (optional)"

EXISTING_SECRETS=$(gh secret list --json name -q '.[].name' 2>/dev/null || true)
HAVE_PUSHOVER_TOKEN=false
echo "$EXISTING_SECRETS" | grep -q "^PUSHOVER_TOKEN$" && HAVE_PUSHOVER_TOKEN=true

if echo "$EXISTING_SECRETS" | grep -q "^PUSHOVER_TOKEN$"; then
  ok "PUSHOVER_TOKEN already set."
else
  info "Pushover sends a push notification the moment a high-fit role appears."
  info "One-time ~\$5 app (iOS/Android); API is free. See README Step 6."
  TOKEN=$(ask "Pushover API Token (press Enter to skip):")
  [ -n "$TOKEN" ] && HAVE_PUSHOVER_TOKEN=true
  if [ -n "$TOKEN" ]; then
    printf '%s' "$TOKEN" | gh secret set PUSHOVER_TOKEN \
      && ok "PUSHOVER_TOKEN set." \
      || warn "Failed to set PUSHOVER_TOKEN."
  else
    info "Skipped. Add later: Settings → Secrets and variables → Actions → New secret."
  fi
fi

if echo "$EXISTING_SECRETS" | grep -q "^PUSHOVER_USER$"; then
  ok "PUSHOVER_USER already set."
else
  # The user key is only useful with a token; don't ask after a skipped token.
  if $HAVE_PUSHOVER_TOKEN; then
    USER_KEY=$(ask "Pushover User Key (press Enter to skip):")
    if [ -n "$USER_KEY" ]; then
      printf '%s' "$USER_KEY" | gh secret set PUSHOVER_USER \
        && ok "PUSHOVER_USER set." \
        || warn "Failed to set PUSHOVER_USER."
    fi
  fi
fi

# ── 8. AI fit-scoring via Claude API (optional) ──────────────────────────────────
step "AI fit-scoring via Claude API (optional)"

if echo "$EXISTING_SECRETS" | grep -q "^ANTHROPIC_API_KEY$"; then
  ok "ANTHROPIC_API_KEY already set."
else
  info "The triage agent scores each job against your résumé using Claude."
  info "Costs ~pennies/run. Requires Anthropic API key (anthropic.com/api)."
  info "Leave blank to skip — the triage.yml workflow is disabled by default."
  API_KEY=$(ask "Anthropic API Key (press Enter to skip):")
  if [ -n "$API_KEY" ]; then
    printf '%s' "$API_KEY" | gh secret set ANTHROPIC_API_KEY \
      && ok "ANTHROPIC_API_KEY set." \
      || warn "Failed to set ANTHROPIC_API_KEY."
    info "Also set CANDIDATE_PROFILE and CANDIDATE_RESUME secrets:"
    info "  gh secret set CANDIDATE_PROFILE   # paste your short profile, Ctrl+D when done"
    info "  gh secret set CANDIDATE_RESUME    # paste your résumé text, Ctrl+D when done"
    info "Then enable the triage.yml workflow: Actions → Nightly Job Triage → Enable workflow"
  else
    info "Skipped. triage.yml stays disabled — no AI scoring, no cost."
  fi
fi

# ── 9. First-time backfill (optional) ───────────────────────────────────────────
step "First-time backfill (optional)"

info "A backfill fetches recent listings once, so your dashboard has jobs before the"
info "regular runs catch up. Each board's backfill runs after the previous one finishes"
info "(the Backfill queue workflow, on GitHub), so you can close this window. How long it"
info "takes depends on your search: minutes for a small one, hours for a big one."
TRIGGER=$(ask "Run backfill now? [y/N]:")

if [[ "$(lower "$TRIGGER")" =~ ^y ]]; then
  info "LinkedIn has two ways to backfill the last 7 days:"
  info "  p) parallel: splits the search into many small jobs (one per search term and"
  info "     location) that run at once. Fastest for a big search. Check its size first:"
  info "     python scrape_jobs.py --linkedin-emit-matrix"
  info "  s) single run: the whole search in one job. Fine for a small search."
  LINKEDIN_MODE=$(ask "LinkedIn backfill: [P]arallel, [s]ingle run, or [n]one:")

  ACTIVE=$(gh workflow list --repo "$REPO" --json path,state \
             -q '.[] | select(.state == "active") | .path' 2>/dev/null || true)
  is_active() { echo "$ACTIVE" | grep -q "/$1\$"; }

  # The other boards first, LinkedIn last. ":backfill" runs a watcher with
  # backfill=true; calcareers and usajobs have no toggle (a normal run is a
  # full snapshot). Boards not enabled in this fork are skipped.
  BACKFILLS=()
  for wf in indeed_watch.yml ziprecruiter_watch.yml hiringcafe_watch.yml localgov_watch.yml scrape_jobs.yml; do
    if is_active "$wf"; then BACKFILLS+=("$wf:backfill"); fi
  done
  for wf in calcareers_watch.yml usajobs_watch.yml; do
    if is_active "$wf"; then BACKFILLS+=("$wf"); fi
  done
  case "$(lower "$LINKEDIN_MODE")" in
    n*) ;;
    s*) if is_active linkedin_watch.yml; then BACKFILLS+=("linkedin_watch.yml:backfill"); fi ;;
    *)  if is_active linkedin_backfill.yml; then BACKFILLS+=("linkedin_backfill.yml"); fi ;;
  esac

  if [ ${#BACKFILLS[@]} -eq 0 ]; then
    info "Nothing to backfill: none of those workflows are enabled in this fork."
  elif gh workflow run backfill_queue.yml --repo "$REPO" --ref main \
         -f backfills="${BACKFILLS[*]}" 2>/dev/null; then
    ok "Backfill queue started, in this order: ${BACKFILLS[*]}"
    info "Follow it in the Actions tab (Backfill queue)."
  else
    warn "Could not start the Backfill queue workflow. Run it by hand: Actions → Backfill queue →"
    info "Run workflow, with: ${BACKFILLS[*]}"
  fi
else
  info "Skipped. Later: Actions → Backfill queue → Run workflow (e.g. 'linkedin_backfill.yml')."
fi

# ── Summary ─────────────────────────────────────────────────────────────────────
echo ""
echo "╔═════════════════════════════════════════════════════╗"
echo "║               Setup complete!                       ║"
echo "╚═════════════════════════════════════════════════════╝"
echo ""
info "Dashboard: https://${OWNER}.github.io/${REPONAME}/triage.html"
info ""
info "Confirm everything is configured:"
info "  Actions → Validate Setup → Run workflow"
echo ""
