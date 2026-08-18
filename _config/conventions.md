# conventions.md

> **Canonical source:** `docs/DEV_GUIDE.md` and `README.md`. This file is a quick reference only — edit the canonical sources, not this file.

## Quick Reference

### File layout
- Per-source scraper output: `output/<source>_jobs.{json,md,html}` (three formats, same data).
- Rolling master: `output/all_jobs.json` — 14-day window, cumulative, the source of truth for what's been seen.
- Triage scores: `output/scores.json`.
- Workflows: `.github/workflows/<source>_watch.yml` for scrapers; utility workflows (`scrape_jobs.yml`, `sync_upstream.yml`, `validate_setup.yml`, `tests.yml`, `triage.yml`) at the top level.
- Disabled watchers live in `.github/workflows/disabled/`.

### Config files (do not confuse)
- `config.json` / `scoring_profile.json` — yours, gitignored, edit freely.
- `config.example.json` / `scoring_profile.example.json` — upstream templates, **never edit**, kept for sync.
- `.gitattributes` marks the gitignored user files `merge=ours` so `sync_upstream.yml` never overwrites them.

### Workflow conventions
- Every committing workflow joins concurrency group `job-scraper-commit-push`.
- Commits are gated on `vars.ENABLE_DATA_COMMITS == 'true'`.
- Secrets (`secrets.*`) for keys/credentials; Variables (`vars.*`) for flags/knobs. `ENABLE_DATA_COMMITS` is a **Variable** — the #1 fork-setup gotcha.
- `CONFIG_JSON` secret must be **single-line, ASCII-safe** (use `scripts/export-config-secret.sh`). Multi-line secrets get redacted by GitHub Actions and break partition matrix `fromJson` calls.

### CLI flags
- `scrape_jobs.py --<source>-only` / `--<source>` for per-source runs.
- `triage_agent.py --limit N --no-jd --since N --dry-run --model ID --from-files`.
- Feasibility: `scrape_jobs.py --feasibility-check [--feasibility-limit N]`.

### Tests
- Pytest. WSL-only tests go in `tests/local/`. Fixtures in `tests/fixtures/`.
- Dev deps: `tests/requirements-dev.txt`.

See `docs/DEV_GUIDE.md` → "Common development tasks" and "Workflow architecture" for full detail.
