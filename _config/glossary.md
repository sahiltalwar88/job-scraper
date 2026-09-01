# glossary.md

Domain terms for `job-scraper`. Read when a workflow, scraper field, or triage output is unclear.

| Term | Definition |
|------|------------|
| **watcher workflow** | A GitHub Actions cron workflow in `.github/workflows/*_watch.yml` that scrapes one source and commits results. The shared pattern is documented in `docs/DEV_GUIDE.md` → "Workflow architecture". |
| **partition** | A slice of a large scrape (notably LinkedIn) run in parallel matrix jobs. Partition keys are slugified; the matrix is built in the workflow and consumed via `fromJson`. Broken partitions are usually a `CONFIG_JSON`-secret formatting issue. |
| **all_jobs.json** | The 50-day rolling master of every scraped role, with `first_seen` timestamps. Exists because per-source files are short rolling windows (e.g. `linkedin_jobs.json` holds only ~the last hour). Every scraper run merges its `new_jobs` into this master. |
| **delta file** | Per-run snapshot of new + enriched jobs, written to `output/deltas/<timestamp>_<source>.json`. LinkedIn only in this fork. Lets downstream consumers process incrementally instead of re-parsing `all_jobs.json`. See `docs/JOB_SCHEMA.md`. |
| **delta manifest** | `output/deltas/index.jsonl` — append-only, one line per delta file with run_at, filename, source, and counts. Pruned at 30 days. Consumers fetch this first, then download only unprocessed delta files. |
| **scores.json** | Output of the triage agent. One verdict per role: `{score, verdict, role_family, seniority_fit, why, flags, outreach_opener}`. Consumed by `triage.html` ★ Rank tab. |
| **triage** | The AI fit-scoring stage (`triage_agent.py`, `triage.yml`). Scores roles 0–100 against the candidate profile + resume. Optional — requires `ANTHROPIC_API_KEY`, `CANDIDATE_PROFILE`, `CANDIDATE_RESUME` secrets. |
| **feasibility check** | Optional Devin-CLI-based tagging of each job with `feasible` (bool) + `feasibility` (`"preferred"` / `"yes"` / `"no"`). Prompt in `config.json` → `feasibility_check.prompt`. Incremental — jobs with a `feasible` field are skipped. |
| **feasibility_error** | Field set on jobs whose feasibility batch failed. Defaults the job to `feasible: true`. Clear the field and re-run to retry. |
| **first_seen** | Timestamp added when a job first appears in `all_jobs.json`. Used by `--since N` and the 50-day rolling window. |
| **JD fetch** | The triage agent's attempt to read the full job description from the ATS. Works on Greenhouse-style pages; Workday is a JS shell (usually empty); LinkedIn/Indeed block scraping and are skipped. Verdicts are tagged `jd: read` or `jd: metadata-only`. |
| **ACP_BACKEND** | Env var set by the Devin Desktop WSL extension (`=windsurf`) that breaks `devin -p` in subprocess mode. `DevinCLIChecker` strips it; for manual calls use `env -u ACP_BACKEND devin -p ...`. |
| **ENABLE_DATA_COMMITS** | GitHub Actions **Variable** (not a secret). Must be `"true"` for scrapers to commit. Common fork-setup failure. |
| **CONFIG_JSON** | GitHub Actions **Secret** holding the user's `config.json` as a single-line, ASCII-safe minified JSON. Multi-line storage breaks GitHub's redaction and the partition matrix. Export via `scripts/export-config-secret.sh`. |
| **concurrency group `job-scraper-commit-push`** | Serializes all commit workflows to prevent push conflicts on `output/`. Any new committing workflow must join it. |
| **sync_upstream** | Weekly workflow that rebases this fork onto upstream. Safer than GitHub's "Sync fork" button because it preserves `merge=ours` user files. |
| **triage.html** | The dashboard. Pure client-side JS; no build step. Reads `output/*.json` at page-load. Hosted on GitHub Pages (main branch, `/` root). |
