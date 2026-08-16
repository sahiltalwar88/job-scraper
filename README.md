# Engineering Leadership Job Scraper

A fork of [Scott Coffin's Job Scraper](https://github.com/ScottCoffin/Job_Scraper), reconfigured for **software engineering leadership roles** (Director of Engineering, VP of Engineering, Head of Engineering, Senior Engineering Manager, etc.) across the United States.

GitHub Actions pipelines scrape **LinkedIn** on a schedule, commit results to the repo, and surface them in a filterable [`triage.html`](triage.html) dashboard hosted on GitHub Pages. **No server, no paid services, no API keys required.**

Everything you search for lives in one file: [`config.json`](config.json) — point it at your field and locations and you have your own tracker.

---

## What's different from the upstream repo

This fork has been substantially modified from the original environmental/toxicology scraper. The upstream repo is a general-purpose multi-board scraper; this fork is focused on LinkedIn-only engineering leadership discovery with a two-phase parallel backfill architecture. Key changes:

### Scope: LinkedIn-only

All non-LinkedIn watchers (Indeed, Glassdoor, ZipRecruiter, Google Jobs, HiringCafe, USAJOBS, CalCareers, CSU Careers, NEOGOV/CalOpps) have been **disabled** — their workflow files moved to `.github/workflows/disabled/`. The scraper code for them still exists in `scrape_jobs.py` and can be re-enabled, but only LinkedIn is actively scraped. The priority-employer digest (`scrape_jobs.yml`) also runs against LinkedIn.

### Two-phase parallel backfill

The upstream repo had a single LinkedIn backfill that hit LinkedIn's ~1000-result-per-query cap on high-volume locations. This fork implements a two-phase architecture (`linkedin_backfill.yml`):

- **Phase 1 (low-volume):** 43 low-volume locations × 4 term-batches = 172 parallel workers, each with a 7-day lookback. These locations have fewer than ~1000 results per week, so a single query captures everything.
- **Phase 2 (high-volume):** 9 high-volume locations (California, Texas, New York, Washington, Virginia, Massachusetts, Illinois, US-wide, Remote) × 4 term-batches × 7 day-slices = 252 parallel workers. Each worker queries with a cumulative lookback and filters by `date_posted` to keep only the target day's jobs, staying well under the cap.

Both phases are under GitHub Actions' 256-matrix-item limit. See `linkedin_backfill.yml` for the full workflow.

### Fuzzy title pre-filter

`role_is_relevant()` — a broad fuzzy pre-filter that catches title variants the exact-phrase keyword filter misses (e.g. "Director, Engineering", "Senior Engineering Manager", "Head of Dropbox"). Configurable via `keywords.fuzzy_seniority`, `keywords.fuzzy_domain`, and `keywords.fuzzy_exclude` in `config.json`. Leave all three empty to disable fuzzy filtering and fall back to keyword-only matching. The LLM feasibility check (`--feasibility-check`) makes the final cut.

### LLM feasibility checking

`--feasibility-check` mode and `DevinCLIChecker` class uses `devin -p` (GLM-5.2 High) to batch-check whether scraped jobs are plausibly relevant to the configured search. The filter prompt is config-driven via `feasibility_check.prompt` in `config.json`. Tags each job in `all_jobs.json` with `feasible: true/false`. Incremental — only checks jobs without an existing `feasible` field.

### State-level partition fan-out

All 50 US states are queried independently via `locations.linkedin_partitions.states` in `config.json`, bypassing the 1000-result cap by splitting one large query into many small ones. High-volume states are further split into day-slices (Phase 2).

### Location filter bug fix

Fixed a bug where `is_target_location()` rejected "Indiana" (contains "india") and "New Mexico" (contains "mexico") due to country-name substring matching. Now checks US state names before country rejection, and uses word-boundary matching for single-word country names.

### Wider scraping window

The LinkedIn watcher runs hourly from **5am to 8pm PT** (12:00–03:00 UTC) — 5am PT covers 8am ET so East Coast morning postings are captured. The upstream repo ran 8am–8pm PT.

### Acceptance test suite

Added a pytest acceptance test suite (`tests/`) with 154 CI-safe tests (222 total including config-dependent local tests). Tests use fixture data (real LinkedIn HTML captured once) rather than live scraping. See [Testing](#testing) below.

### CONFIG_JSON secret export script

Added `scripts/export-config-secret.sh` — exports `config.json` as a single-line, ASCII-safe JSON string for the `CONFIG_JSON` GitHub Actions secret. This avoids a GitHub Actions issue where multi-line secrets cause step output redaction (each line becomes a separate masking pattern). See [Setup](#setup) below.

### Other changes

- Removed enrichment cap; filter before enrich; retry failed JD fetches
- Fixed rate-limit handling that was killing pagination mid-backfill
- Fixed LinkedIn pagination to use step=10
- Added country exclusion to location filter
- Dashboard branding updated for engineering leadership
- Cleared upstream toxicology data from the repo

---

## Setup

### Prerequisites

You need a free [GitHub account](https://github.com/signup). Everything runs on GitHub's servers (Actions + Pages) — you don't need to install anything or keep a computer on.

### Step 1 — Fork and clone

Click **Fork** at the top of this page, then optionally clone locally:

```bash
git clone https://github.com/YOUR-USERNAME/job-scraper.git
cd job-scraper
```

### Step 2 — Configure your search (`config.json`)

Create `config.json` in the repo root. Copy from [`config.example.json`](config.example.json) and edit, or generate it from your CV using [`docs/cv-to-config-prompt.md`](docs/cv-to-config-prompt.md).

The key sections to customize:
- `keywords.include` — exact title-match phrases (e.g. "director of engineering")
- `keywords.fuzzy_seniority` / `fuzzy_domain` / `fuzzy_exclude` — broad fuzzy pre-filter
- `search_terms.linkedin` — queries sent to LinkedIn's search box
- `locations.linkedin` — LinkedIn geo entries (geoId can be left `""`)
- `locations.linkedin_partitions.states` — all 50 US states for partitioned backfill
- `locations.linkedin_partitions.high_volume.locations` — locations that need day-slicing
- `location_filter.terms` — substrings for post-filtering
- `employers.priority` — companies worth a daily digest even on a quiet day

### Step 3 — Host the dashboard (GitHub Pages)

1. **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: **`main`**, folder: **`/ (root)`** → **Save**
4. Your dashboard is live at `https://YOUR-USERNAME.github.io/job-scraper/triage.html`

### Step 4 — Configure GitHub Actions

1. **Actions tab** → click "I understand my workflows, enable them."
2. **Settings → Actions → General → Workflow permissions** → **Read and write permissions** → Save
3. **Settings → Secrets and variables → Actions → Variables tab** → add:

   | Variable | Value |
   |----------|-------|
   | `ENABLE_DATA_COMMITS` | `true` |

   This tells CI to commit scraped results back to your repo. Without it, scrapers run but nothing is saved.

4. **Settings → Secrets and variables → Actions → New repository secret** → add:

   | Secret | Value |
   |--------|-------|
   | `CONFIG_JSON` | The full contents of your `config.json` (see below) |

   The scraper workflows reconstruct `config.json` on the runner from this secret at the start of each job (your real `config.json` is gitignored and not in the repo).

   **Important — store it as a single line, not pretty-printed:**
   GitHub Actions treats each line of a multi-line secret as a separate secret pattern for masking. If your config is stored multi-line, each line (e.g. `"Director of Engineering",`) becomes its own secret, and any step output containing that text gets redacted — including the partition matrix that drives the parallel backfill, which will fail with `fromJson: empty input`.

   **Export command (run from the repo root):**

   ```bash
   # Print single-line, ASCII-safe JSON to stdout:
   bash scripts/export-config-secret.sh

   # Copy directly to Windows clipboard (WSL only):
   bash scripts/export-config-secret.sh --clip
   ```

   The script minifies the JSON to one line and escapes non-ASCII characters (em-dashes, emoji) as `\uXXXX` to prevent corruption through `clip.exe`. Paste the result into the `CONFIG_JSON` secret value field.

   > **Why a secret and not a variable?** The config is stored as a secret to keep your search parameters private. Variables are visible in plain text in the Actions tab. The trade-off is the single-line requirement above — if you don't need privacy, a variable works too and avoids the redaction issue entirely.

### Step 5 — Run it the first time

In the **Actions** tab, open each active workflow and click **Run workflow**:

| Workflow | Schedule | Description |
|----------|----------|-------------|
| **LinkedIn Watcher** | Hourly :17 PT, 5am–8pm | Last 1h of LinkedIn postings |
| **Priority Employer Digest** | Daily 8 PM PT | Last 24h from priority employers |
| **LinkedIn Backfill (Parallel)** | Manual only | Two-phase historical backfill (7 days) |
| **Workflow Watchdog** | Hourly :33 PT, 5am–8pm | Re-dispatches missed LinkedIn runs |
| **Validate Setup** | Manual only | Checks required config/secrets |

The first manual run seeds your dataset. The backfill workflow is the most important for a new setup — it pulls 7 days of history across all 50 states in parallel.

### Step 6 — Phone notifications (optional)

Get a push when a relevant new role appears, via [Pushover](https://pushover.net):

1. Sign in at pushover.net, create an Application/API Token, copy the token and your user key.
2. Add `PUSHOVER_TOKEN` and `PUSHOVER_USER` as repository secrets.
3. Test: **Actions → Test Pushover Notification → Run workflow**.

Without these secrets, notifications are off and everything else works.

### Step 7 — AI fit-scoring (optional, advanced)

`triage_agent.py` can score each role against your resume with the Claude API. Needs `ANTHROPIC_API_KEY`, `CANDIDATE_PROFILE`, and `CANDIDATE_RESUME` secrets. The `triage.yml` workflow is disabled by default — enable it only if you use this feature.

---

## What's scraped

### Active sources

| Source | Workflow | Schedule | Lookback | Notes |
|--------|----------|----------|----------|-------|
| **LinkedIn** (general) | `linkedin_watch.yml` | Hourly :17 PT, 5am–8pm | 1 hour | All configured search terms across configured locations |
| **LinkedIn** (priority employers) | `scrape_jobs.yml` | Daily 8 PM PT | 24 hours | Filtered to `employers.priority` allowlist |
| **LinkedIn** (historical backfill) | `linkedin_backfill.yml` | Manual | 7 days | Two-phase parallel: 172 + 252 workers |

All three use LinkedIn's **unauthenticated public guest endpoint** — no login, no cookies, no credentials.

### Disabled sources

The following sources were in the upstream repo but are **disabled** in this fork (workflow files moved to `.github/workflows/disabled/`). The scraper code still exists in `scrape_jobs.py` and can be re-enabled by moving the workflow files back:

| Source | Reason for disabling |
|--------|---------------------|
| Indeed | Not needed — LinkedIn covers the target roles |
| Glassdoor | Not needed |
| ZipRecruiter | Not needed |
| Google Jobs | Not needed |
| HiringCafe | Not needed |
| USAJOBS | Not relevant for private-sector engineering leadership |
| CalCareers | California state jobs — not relevant |
| CSU Careers | California State University — not relevant |
| NEOGOV / CalOpps | State/local government — not relevant |
| Weekly Digest | Optional Pushover feature — disabled |
| Triage agent | Optional Claude API scoring — disabled |

To re-enable a source: move its `.yml` from `.github/workflows/disabled/` back to `.github/workflows/`.

---

## Running locally

Optional — only if you want to test scrapes on your own machine. Needs [Python 3.11+](https://www.python.org/downloads/):

```bash
python scrape_jobs.py --linkedin-only              # standard library only
python scrape_jobs.py --priority-only             # priority-employer digest
python scrape_jobs.py --linkedin-backfill          # 7-day backfill
python scrape_jobs.py --linkedin-emit-matrix       # preview partition matrix
python scrape_jobs.py --linkedin-emit-matrix --phase high   # Phase 2 matrix
python scrape_jobs.py --feasibility-check          # LLM feasibility tagging
python -m http.server 8000                         # then open http://localhost:8000/triage.html
```

The dashboard must be served over HTTP — opening `triage.html` from `file://` won't load the data.

---

## Testing

This repo has a pytest acceptance test suite in `tests/`. Tests use fixture data (real LinkedIn HTML captured once) rather than live scraping.

### Test structure

```
tests/
├── conftest.py                          # Shared fixtures
├── requirements-dev.txt                 # pytest
├── fixtures/
│   ├── linkedin_search_results_california_5pages.html   # Real LinkedIn search HTML
│   ├── linkedin_job_posting_detail_page.html            # Real LinkedIn JD page
│   ├── sample_all_jobs_with_feasibility_tags.json       # Synthetic job data
│   └── sample_linkedin_partitions/                      # Synthetic partition files
│       ├── california_director_vp.json
│       ├── texas_director_vp.json
│       └── new_york_head_senior_manager_cap_hit.json
├── test_feasibility_check_cli_mode.py
├── test_feasibility_checker_adapter.py
├── test_job_deduplication.py
├── test_linkedin_jd_extraction.py
├── test_linkedin_partition_merge.py
├── test_linkedin_partition_merge_mixed.py
├── test_linkedin_partition_skips_jd_enrichment.py
├── test_linkedin_partition_worker_spec.py
├── test_linkedin_search_result_parsing.py
├── test_location_filter_us_states.py
├── test_master_jobs_file_merge.py
├── test_partition_key_slugify.py
├── test_work_arrangement_classification.py
└── local/                               # Config-dependent tests (excluded from CI)
    ├── test_linkedin_day_slice_filter.py
    ├── test_linkedin_partition_matrix_generation.py
    ├── test_location_filter_config_dependent.py
    └── test_title_filter_software_eng_leadership.py
```

### Running tests

```bash
# CI-scoped tests (config-independent, run against config.example.json):
pytest tests/ --ignore=tests/local

# All tests (requires your real config.json):
pytest tests/

# Install dev dependencies:
pip install -r tests/requirements-dev.txt
```

### Why `tests/local/` exists

Some tests depend on the user's specific `config.json` (engineering leadership titles, partition matrix sizes, day-slice filtering). In CI, only `config.example.json` is available (the toxicology template), so those tests would fail. Config-dependent tests live in `tests/local/` and are excluded from CI via `--ignore=tests/local`. They still run locally and are committed to the repo so the test logic is version-controlled.

**CI:** 154 tests pass with `config.example.json`.
**Local:** 222 tests pass with the real `config.json`.

---

## Output files

| File | Source | Description |
|------|--------|-------------|
| `linkedin_jobs.json` / `.md` / `.html` | LinkedIn watcher | Roles in configured locations, last 1h, deduped |
| `jobs.json` / `.md` / `.html` | Priority-employer digest | Allowlisted employer roles, last 24h, deduped |
| `all_jobs.json` | Accumulator | Cumulative 14-day master (feeds dashboard + triage) |
| `notified.json` | Pushover | Notification dedup log |
| `workflow_runs.jsonl` | All workflows | CI run audit log |
| `linkedin_matrix.json` | Backfill emit step | Partition work matrix (debugging) |
| `linkedin_partition_*.json` | Backfill workers | Per-partition results (ephemeral) |

All output files are gitignored upstream and populated by CI when `ENABLE_DATA_COMMITS=true`.

---

## Repo structure

```
├── config.json                     # YOUR settings (gitignored; stored as CONFIG_JSON secret)
├── config.example.json             # Template config (toxicology example — do not edit)
├── scoring_profile.json            # AI triage calibration (gitignored; optional)
├── triage.html                     # Interactive dashboard (served by GitHub Pages)
├── scrape_jobs.py                  # All scraping logic (reads config.json)
├── notify.py                       # Pushover notifications (optional)
├── triage_agent.py                 # Optional Claude API fit-scoring agent
├── eval_triage.py                  # Golden-case evals for triage agent
├── requirements.txt                # python-jobspy (for re-enabling Indeed/Glassdoor/etc.)
├── scripts/
│   ├── setup.sh                    # One-command GitHub setup (requires gh CLI)
│   └── export-config-secret.sh     # Export config.json as single-line secret
├── tests/                          # Pytest acceptance test suite
│   ├── conftest.py
│   ├── fixtures/                   # Real LinkedIn HTML + synthetic JSON fixtures
│   └── local/                      # Config-dependent tests (excluded from CI)
├── docs/
│   ├── cv-to-config-prompt.md      # LLM prompt to generate config.json from a CV
│   └── triage.gif                  # Dashboard demo
├── output/                         # Scraped data (gitignored; populated by CI)
└── .github/workflows/
    ├── linkedin_watch.yml          # Hourly :17 PT — LinkedIn (last 1h)
    ├── linkedin_watch_backup.yml   # Watchdog :33 PT — re-dispatches missed runs
    ├── linkedin_backfill.yml       # Manual — two-phase parallel backfill (7 days)
    ├── scrape_jobs.yml             # Daily — priority-employer digest
    ├── notify_test.yml             # Manual — test Pushover notification
    ├── validate_setup.yml          # Manual — check required config/secrets
    ├── tests.yml                   # On push — run pytest (excludes tests/local/)
    ├── clear_data.yml              # Manual — reset all output files
    ├── sync_upstream.yml           # Weekly — rebase code updates from upstream
    └── disabled/                   # Disabled workflow files (non-LinkedIn sources)
        ├── indeed_watch.yml
        ├── glassdoor_watch.yml
        ├── ziprecruiter_watch.yml
        ├── google_jobs_watch.yml
        ├── hiringcafe_watch.yml
        ├── usajobs_watch.yml
        ├── calcareers_watch.yml
        ├── csucareers_watch.yml
        ├── localgov_watch.yml
        ├── triage.yml
        ├── evals.yml
        └── weekly_digest.yml
```

---

## Secrets vs variables

GitHub Actions uses two distinct namespaces:
- **Secrets** (`secrets.NAME`): encrypted, masked in logs. Use for anything you want to keep private.
- **Variables** (`vars.NAME`): plaintext, visible in logs. Use for feature flags and tuning knobs.

| Item | Type | Purpose |
|------|------|---------|
| `CONFIG_JSON` | Secret | Full `config.json` contents (single-line, ASCII-safe) |
| `ENABLE_DATA_COMMITS` | Variable | `true` = commit scraped data to repo |
| `PUSHOVER_TOKEN` / `PUSHOVER_USER` | Secret | Phone notifications (optional) |
| `ANTHROPIC_API_KEY` | Secret | AI triage scoring (optional) |
| `CANDIDATE_PROFILE` / `CANDIDATE_RESUME` | Secret | Resume for AI triage (optional) |

`ENABLE_DATA_COMMITS` is a **Variable** (not a secret) — a common source of confusion.

---

## Tuning the search

Everything you'd adjust lives in [`config.json`](config.json) (no code edits):

- `keywords.include` — exact title-match phrases
- `keywords.exclude` — titles to drop (junior, intern, recruiter, etc.)
- `keywords.fuzzy_seniority` / `fuzzy_domain` / `fuzzy_exclude` — broad fuzzy pre-filter for the leadership title filter
- `search_terms.linkedin` — queries sent to LinkedIn's search box
- `locations.linkedin` — LinkedIn geo entries
- `locations.linkedin_partitions.states` — US states for partitioned backfill
- `locations.linkedin_partitions.high_volume.locations` — locations that need day-slicing in Phase 2
- `location_filter.terms` — substrings for post-filtering
- `employers.priority` — companies worth a daily digest
- `employers.exclude` — companies to drop (empty list = no company exclusion)
- `keywords.fuzzy_seniority` / `fuzzy_domain` / `fuzzy_exclude` — optional fuzzy pre-filter (empty = disabled, falls back to keyword-only matching)
- `priority_topics` — gold-star highlights on the dashboard and push notifications
- `role_categories` — dashboard Role-filter buckets
- `sector_classification` — dashboard Sector-filter buckets (empty = no sector classification)
- `feasibility_check.prompt` — LLM feasibility filter prompt (empty = `--feasibility-check` disabled)
- `triage.role_families` — pipe-delimited category labels for the AI triage agent
- `profile` — dashboard title/subtitle/emoji

Generate the whole file from your CV with [`docs/cv-to-config-prompt.md`](docs/cv-to-config-prompt.md), or edit it by hand (every key is commented in `config.example.json`).

---

## Staying up to date with upstream

Enable the **`sync_upstream.yml`** workflow (**Actions → Sync from upstream → Enable workflow**) and it rebases new code improvements from the upstream repo every Monday.

> **Use the workflow, not the GitHub "Sync fork" button.** Because your fork has commits upstream doesn't (your `config.json`, your scraped data), GitHub's built-in button shows "Discard N commits" — which would delete your config. The `sync_upstream.yml` workflow handles this correctly by rebasing your commits on top of upstream.

---

## Attribution

This repo is a fork of [Scott Coffin's Job Scraper](https://github.com/ScottCoffin/Job_Scraper), which began as [Ernesto Diaz](https://github.com/ernestod1998)'s Bay Area ML-engineer scraper. The upstream repo is a general-purpose multi-board job scraper; this fork focuses on LinkedIn-only engineering leadership discovery.
