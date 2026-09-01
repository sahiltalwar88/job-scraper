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
| `output/` | All scraped data (gitignored upstream). `all_jobs.json` = rolling master (last 50d). `output/deltas/` = per-run delta files for incremental consumers (LinkedIn only). See `docs/JOB_SCHEMA.md` for the data contract. |

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
5. To enable delta production for the new source, pass `source="sourcename"` to `save_jobs_output()` and add `output/deltas/` to the workflow's `git add -f` line. Deltas are optional — sources without them still merge into `all_jobs.json` normally.

### Delta files (incremental consumption)

LinkedIn runs produce per-run delta files in `output/deltas/` so downstream consumers (job-hunter, custom pipelines) can fetch only what changed instead of re-parsing the full `all_jobs.json`.

- **Delta file**: `output/deltas/<timestamp>_linkedin.json` — contains `added` and `updated` arrays of full job records.
- **Manifest**: `output/deltas/index.jsonl` — append-only, one line per delta file with run_at, filename, source, and counts.
- **Pruning**: Delta files and manifest lines older than 30 days are removed on each run.
- **Only LinkedIn** produces deltas in this fork. Other sources merge into `all_jobs.json` as before. The mechanism is source-agnostic — any source can opt in by passing `source=` to `save_jobs_output()`.
- **Transport**: Consumers can read `output/deltas/` from the filesystem (co-located repos) or fetch via HTTP from GitHub Pages / `raw.githubusercontent.com` (portable across machines).

#### Delta envelope format

Each delta file is a JSON object:

```json
{
  "run_at": "2026-08-31T14:00:00Z",
  "source": "linkedin",
  "added": [ {job object}, ... ],
  "updated": [ {job object}, ... ]
}
```

- `run_at` — ISO-8601 UTC timestamp of the scraper run. Matches the filename.
- `source` — Source label (same values as the `ats` field on job records).
- `added` — Jobs newly added to `all_jobs.json` this run (got a new `first_seen`).
- `updated` — Existing jobs that were enriched this run (gained `description` or `salary` via duplicate merge). Contains the full updated job record.

If a run produces no new and no enriched jobs, no delta file is written and no manifest line is appended.

#### Manifest line format

`output/deltas/index.jsonl` — one JSON object per line:

```json
{"run_at": "2026-08-31T14:00:00Z", "file": "2026-08-31T14-00-00Z_linkedin.json", "source": "linkedin", "added": 5, "updated": 2}
```

#### Consumption pattern

1. Fetch `output/deltas/index.jsonl` (filesystem or HTTP).
2. Parse each line. Track the set of `run_at` values already processed.
3. For each unprocessed line, fetch `output/deltas/<file>`.
4. Upsert all jobs in `added` and `updated` into your store — both arrays contain full job records, upsert by `url`.
5. Record `run_at` as processed.
6. On cold start (no processed state), fall back to a full sync from `output/all_jobs.json`, then switch to delta mode.

### Job record fields

Job records appear in `all_jobs.json`, per-source files, and delta files. The machine-validatable schema is at `schema/jobs.schema.json`.

**Required fields** (always present):

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Canonical posting URL (http/https). Primary key. |
| `title` | string | Job title. |
| `company` | string | Employer name. |
| `ats` | string | Source label: `LinkedIn`, `Indeed`, `Glassdoor`, `ZipRecruiter`, `GoogleJobs`, `HiringCafe`, `CalCareers`, `CSUCareers`, `USAJOBS`, `NEOGOV`, `CalOpps`, `Greenhouse`, `Workday`, `Priority`. |
| `first_seen` | string | ISO-8601 UTC timestamp added by the merge step. Present on master + deltas, not on per-source files. |

**Optional fields** (may be absent depending on source):

| Field | Type | Description | Sources that populate it |
|-------|------|-------------|------------------------|
| `location` | string | Location string. May be empty. | All sources |
| `date_posted` | string | ISO date or relative string. Format varies. | All sources, may be empty |
| `salary` | string | Raw salary string. May be empty. | Most sources |
| `description` | string | Job description (LinkedIn: ≤12k chars; JobSpy: ≤6k). **Absent for government boards.** | LinkedIn (detail-page fetch), Indeed/Glassdoor/ZipRecruiter (inline), Google Jobs (inline), HiringCafe (inline), CSU Careers (short summary) |
| `direct_url` | string | Direct apply URL when different from `url`. | Some sources; backfilled during merge |
| `job_type` | string | Employment type (full-time, contract, etc.). | Some sources; backfilled during merge |
| `is_remote` | boolean | Remote signal. | Some sources (JobSpy boards) |
| `telework` | string | Board-specific telework label. | CalCareers, NEOGOV |
| `work_arrangement` | string | Normalized: `On-site`, `Remote`, `Hybrid`. | Sources where inferable |
| `salary_source` | string | Where salary was extracted from. | Some sources |
| `salary_currency` | string | Currency code (e.g. USD). | Some sources |
| `emails` | string | Contact emails, comma-separated. | JobSpy sources |
| `company_url` | string | Employer homepage URL. | Some sources |
| `duplicate_urls` | array[string] | Alternate URLs for the same job. | Added by merge step |

**Triage agent fields** (written by `triage_agent.py`, appear in `all_jobs.json` only — not in delta files):

| Field | Type | Description |
|-------|------|-------------|
| `feasible` | boolean | Whether the job passed feasibility check. |
| `feasibility` | string | Verdict: `preferred`, `yes`, or `no`. |
| `feasibility_error` | boolean | True if the feasibility batch failed. |

## Secrets vs variables

GitHub Actions uses two distinct namespaces:
- **Secrets** (`secrets.NAME`): encrypted, write-only. Use for API keys, credentials.
- **Variables** (`vars.NAME`): plaintext, readable in logs. Use for feature flags and tuning knobs.

`ENABLE_DATA_COMMITS` is a **Variable** (not a secret) — a common source of confusion for new users.

## Personal data handling

`config.json`, `scoring_profile.json`, and `output/` are in `.gitignore` in the upstream repo. The `.gitattributes` file marks them `merge=ours` so `sync_upstream.yml` never overwrites your customizations.

`CANDIDATE_PROFILE` and `CANDIDATE_RESUME` live only in GitHub Actions Secrets — never written to disk or committed.
