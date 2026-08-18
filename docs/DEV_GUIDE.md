# Job Scraper — Developer Guide

> **Canonical dev guide for job-scraper.** Moved here from `CLAUDE.md` during ICM restructure so that `CLAUDE.md` could become a thin auto-generated pointer to `IDENTITY.md` (per ICM convention: entry files route, they don't hold content). This is the file IDENTITY.md / CONTEXT.md route to for "how do I run/fix/extend this project" questions.

## What this project is

GitHub Actions pipelines that scrape job boards (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs, HiringCafe, USAJOBS, CalCareers, NEOGOV/CalOpps) on a schedule, commit results to the repo, and serve them through a filterable triage dashboard (`triage.html`) hosted on GitHub Pages.

Designed to be forked. No server. No paid services required (AI triage is optional).

## Key files

| File | Purpose |
|------|---------|
| `config.json` | User's search config — keywords, locations, employers. Gitignored upstream. Copy from `config.example.json`. |
| `config.example.json` | Documented template. **Do not edit** — kept for upstream sync. |
| `scoring_profile.json` | AI triage calibration — fit/poor-fit terms. Gitignored upstream. Copy from `scoring_profile.example.json`. |
| `scrape_jobs.py` | Main scraper. Dispatched by all watcher workflows. |
| `triage_agent.py` | Claude API fit-scoring agent. Run by `triage.yml`. |
| `triage.html` | The dashboard. Pure client-side JS; reads `output/*.json` at page-load time. |
| `output/` | All scraped data (gitignored upstream). `all_jobs.json` = 14-day rolling master. |

## Workflow architecture

All 18 workflows live in `.github/workflows/`. Pattern:
- **Watcher workflows** (`*_watch.yml`, `scrape_jobs.yml`) run on cron, call `scrape_jobs.py`, then commit to `output/` when `vars.ENABLE_DATA_COMMITS == 'true'`.
- **Concurrency group** `job-scraper-commit-push` serializes all commits (prevents push conflicts).
- **`triage.yml`** scores new roles via Claude API nightly. Disabled by default — requires `ANTHROPIC_API_KEY`, `CANDIDATE_PROFILE`, `CANDIDATE_RESUME` secrets.
- **`sync_upstream.yml`** rebases the fork weekly on upstream. Safer than GitHub's "Sync fork" button.

## Required GitHub configuration (for a fork to work)

| Item | Where to set | Required? |
|------|-------------|-----------|
| `ENABLE_DATA_COMMITS=true` | Settings → Secrets and variables → Actions → **Variables** tab | **Yes** |
| `CONFIG_JSON` secret | Settings → Secrets and variables → Actions → **Secrets** tab | **Yes** |
| Workflow permissions: Read+write | Settings → Actions → General → Workflow permissions | **Yes** |
| GitHub Pages: main branch, / root | Settings → Pages | Yes (for dashboard) |
| `PUSHOVER_TOKEN` + `PUSHOVER_USER` secrets | Settings → Secrets | Optional |
| `ANTHROPIC_API_KEY` secret | Settings → Secrets | Optional (AI triage only) |
| `CANDIDATE_PROFILE` + `CANDIDATE_RESUME` secrets | Settings → Secrets | Optional (AI triage only) |

### Exporting `CONFIG_JSON` to the secret

The config must be stored as a **single-line, ASCII-safe** JSON string. If stored
multi-line, GitHub Actions treats each line as a separate secret pattern and
redacts any step output containing those substrings — including the partition
matrix, which breaks the parallel backfill with `fromJson: empty input`.

```bash
# Print to stdout:
bash scripts/export-config-secret.sh

# Copy directly to Windows clipboard (WSL):
bash scripts/export-config-secret.sh --clip
```

The script minifies to one line and escapes non-ASCII chars as `\uXXXX` to
prevent corruption through `clip.exe`.

## Automated setup

```bash
# One-command setup (requires gh CLI: https://cli.github.com)
bash scripts/setup.sh
```

Verify everything is configured:
**Actions → Validate Setup → Run workflow**

## Common development tasks

### Run a scraper locally
```bash
pip install -r requirements.txt        # only for Indeed/Glassdoor/ZipRecruiter/Google
python scrape_jobs.py --linkedin-only
python scrape_jobs.py --indeed-only
python scrape_jobs.py --hiringcafe
python scrape_jobs.py --usajobs
```

### Serve the dashboard locally
```bash
python -m http.server 8000
# Open http://localhost:8000/triage.html
```

### Run the triage agent locally
```bash
pip install anthropic
ANTHROPIC_API_KEY=sk-... \
CANDIDATE_PROFILE="..." \
CANDIDATE_RESUME="..." \
python triage_agent.py --limit 50
```

### Run evals for the triage agent
```bash
python eval_triage.py
```

### Feasibility checking

The scraper can tag jobs with a tripartite feasibility verdict using the Devin CLI (`devin -p` / GLM-5.2 High). Each job gets two fields: `feasible` (bool) and `feasibility` (str: `"preferred"`, `"yes"`, or `"no"`).

```bash
# Tag all untagged jobs:
python scrape_jobs.py --feasibility-check

# Test on a small batch:
python scrape_jobs.py --feasibility-check --feasibility-limit 20
```

The prompt is configured in `config.json` under `feasibility_check.prompt`. Jobs that already have a `feasible` field are skipped (incremental).

**Parallel runs** (for large sets of untagged jobs):
```bash
python scripts/feasibility_slice.py --slice 0 --total-slices 3 &
python scripts/feasibility_slice.py --slice 1 --total-slices 3 &
python scripts/feasibility_slice.py --slice 2 --total-slices 3 &
wait
python scripts/merge_feasibility_slices.py
```

**Error handling:** Failed batches get `feasibility_error: true` (defaulting to `feasible: true`). Re-check by clearing feasibility fields and re-running.

**ACP_BACKEND:** The Devin Desktop WSL extension sets `ACP_BACKEND=windsurf`, which breaks `devin -p` in subprocess mode. `DevinCLIChecker` strips it from the subprocess env. If calling `devin -p` manually from WSL, use `env -u ACP_BACKEND devin -p ...`.

### Add a new job source

1. Create `.github/workflows/SOURCENAME_watch.yml` (copy an existing simple watcher as template).
2. Add a corresponding `--sourcename` flag to `scrape_jobs.py`.
3. The watcher should write to `output/SOURCENAME_jobs.json` (and `.md`/`.html`).
4. `triage.html` discovers output files at runtime — no changes needed to the dashboard unless adding new fields.

## Secrets vs variables

GitHub Actions uses two distinct namespaces:
- **Secrets** (`secrets.NAME`): encrypted, write-only. Use for API keys, credentials.
- **Variables** (`vars.NAME`): plaintext, readable in logs. Use for feature flags and tuning knobs.

`ENABLE_DATA_COMMITS` is a **Variable** (not a secret) — a common source of confusion for new users.

## Personal data handling

`config.json`, `scoring_profile.json`, and `output/` are in `.gitignore` in the upstream repo. The `.gitattributes` file marks them `merge=ours` so `sync_upstream.yml` never overwrites your customizations.

`CANDIDATE_PROFILE` and `CANDIDATE_RESUME` live only in GitHub Actions Secrets — never written to disk or committed.
