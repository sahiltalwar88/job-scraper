# CONTEXT.md

> Layer 1 routing for `job-scraper`. "Where do I go?" — pick a task, follow the row. Read `IDENTITY.md` first for the workspace map.

## Routing Table

| Task | Destination | Load first |
|------|-------------|------------|
| Understand what this project is | `README.md`, then `docs/DEV_GUIDE.md` | `IDENTITY.md` (this repo) |
| Add a new job source | New `.github/workflows/<source>_watch.yml` + new `--<source>` flag in `scrape_jobs.py` | An existing simple watcher (e.g. `hiringcafe_watch.yml` in `disabled/`); `docs/DEV_GUIDE.md` → "Add a new job source" |
| Fix / extend the scraper | `scrape_jobs.py` | `docs/DEV_GUIDE.md` → "Run a scraper locally"; relevant test in `tests/` |
| Fix / extend the triage agent | `triage_agent.py` | `docs/AGENT_README.md` (canonical), then `docs/DEV_GUIDE.md` → "Run the triage agent locally" |
| Run feasibility checks (Devin CLI) | `scrape_jobs.py --feasibility-check` | `docs/DEV_GUIDE.md` → "Feasibility checking"; `scripts/feasibility_slice.py` for parallel |
| Edit my search config | `config.json` (never `config.example.json`) | `config.example.json` for documented fields |
| Calibrate AI triage | `scoring_profile.json` (never `scoring_profile.example.json`) | `scoring_profile.example.json` |
| Serve the dashboard locally | `python -m http.server 8000` → `http://localhost:8000/triage.html` | `triage.html` |
| Add / fix a test | `tests/` (pytest); WSL-only tests go in `tests/local/` | `tests/conftest.py`, a neighboring `test_*.py` |
| Set up a fresh fork | `scripts/setup.sh` (requires `gh` CLI) | `docs/DEV_GUIDE.md` → "Required GitHub configuration"; then run **Actions → Validate Setup** |
| Export `CONFIG_JSON` to the secret | `scripts/export-config-secret.sh` | `docs/DEV_GUIDE.md` → "Exporting `CONFIG_JSON` to the secret" |
| Sync with upstream | `.github/workflows/sync_upstream.yml` (weekly, manual run ok) | `docs/DEV_GUIDE.md` → "Workflow architecture" |
| Understand a workflow | `.github/workflows/<name>.yml` | `docs/DEV_GUIDE.md` → "Workflow architecture" for the shared pattern |
| Read deep-dive architecture notes | `docs/deep-dive/` (dated files) | Newest file by date |

## Session Start Protocol

1. Read `IDENTITY.md` for the workspace map and the 7 rules.
2. Check `git status` — `config.json`, `scoring_profile.json`, and `output/` are gitignored locally; do not expect them in diffs.
3. If the task touches scraping or workflows → load `docs/DEV_GUIDE.md` → "Workflow architecture" and "Common development tasks".
4. If the task touches AI triage → load `docs/AGENT_README.md` (canonical for the agent).
5. If the task touches the dashboard → load `triage.html` and note it is pure client-side JS reading `output/*.json` at page-load.
6. Run the relevant test subset before making changes: `pytest tests/ -k <topic>`.

## Pipeline (Virtual Stages)

The project is an automation pipeline, not a knowledge-compilation pipeline. Stages are virtual — they live inside existing files and workflows, not in `stages/` folders.

### Stage 1 — Scrape
- **Purpose:** Pull postings from job boards on a schedule.
- **Inputs:** `config.json` (keywords, locations, employers); external job boards.
- **Process:** Watcher workflows (`.github/workflows/*_watch.yml`, `scrape_jobs.yml`) run on cron → call `scrape_jobs.py --<source>` → produce per-source `new_jobs`.
- **Outputs:** `output/<source>_jobs.{json,md,html}`; new jobs merged into `output/all_jobs.json` (14-day rolling master).

### Stage 2 — Commit
- **Purpose:** Persist scraped data to the repo so the dashboard can read it.
- **Inputs:** `output/<source>_jobs.*` from Stage 1; `vars.ENABLE_DATA_COMMITS == 'true'`.
- **Process:** Watcher workflow commits under concurrency group `job-scraper-commit-push` (serializes all commits).
- **Outputs:** Updated `output/` on `main`.
- **Routing:** If `ENABLE_DATA_COMMITS` is unset/false, scrapers run but commit nothing — data stays ephemeral.

### Stage 3 — Triage (optional)
- **Purpose:** Score every unscored role 0–100 against the candidate's profile + resume.
- **Inputs:** `output/all_jobs.json`; `ANTHROPIC_API_KEY`, `CANDIDATE_PROFILE`, `CANDIDATE_RESUME` secrets; `scoring_profile.json`.
- **Process:** `triage.yml` runs nightly (09:00 UTC) → `triage_agent.py` loops over unscored roles, fetches JDs where ATS allows, calls the model → commits verdicts.
- **Outputs:** `output/scores.json` (consumed by `triage.html` ★ Rank tab).
- **Routing:** Disabled by default. Without the three secrets, this stage is skipped entirely.

### Stage 4 — Feasibility check (optional)
- **Purpose:** Tag each job with a tripartite verdict (`feasible` bool + `feasibility` ∈ `preferred|yes|no`) using the Devin CLI.
- **Inputs:** `output/all_jobs.json` (jobs lacking a `feasible` field); `config.json` → `feasibility_check.prompt`.
- **Process:** `scrape_jobs.py --feasibility-check` (or `scripts/feasibility_slice.py` for parallel) calls `devin -p` per batch. Already-tagged jobs are skipped (incremental). Failed batches get `feasibility_error: true` and default `feasible: true`.
- **Outputs:** Mutates `feasible` / `feasibility` / `feasibility_error` fields on jobs in `output/all_jobs.json`.
- **Routing:** On `ACP_BACKEND=windsurf` (Devin Desktop WSL extension), `devin -p` breaks in subprocess mode — `DevinCLIChecker` strips it. Manual calls: `env -u ACP_BACKEND devin -p ...`.

### Stage 5 — Publish
- **Purpose:** Serve the dashboard.
- **Inputs:** `output/all_jobs.json`, `output/scores.json`, per-source `output/<source>_jobs.json`.
- **Process:** GitHub Pages serves `triage.html` from `main` root. The page fetches `output/*.json` at load and renders client-side.
- **Outputs:** Public dashboard URL.
- **Routing:** Pages must be configured for `main` branch, `/` root. No server, no build step.

## Shared Config References (`_config/`)

| File | Purpose |
|------|---------|
| `_config/conventions.md` | Naming, file-layout, and workflow conventions. Re-exports `docs/DEV_GUIDE.md`. |
| `_config/glossary.md` | Domain terms: watcher, partition, all_jobs.json, feasibility, triage, ACP_BACKEND, etc. |
| `_config/voice.md` | Tone, audience, evidence standards for any docs/commits written here. |
