<!-- Auto-generated from IDENTITY.md — edit IDENTITY.md, then re-run /icm-sync to sync -->

# IDENTITY.md

> **job-scraper** — GitHub Actions pipelines that scrape job boards on a schedule, commit results to `output/`, and serve a filterable triage dashboard (`triage.html`) on GitHub Pages. Designed to be forked; no server, no paid services required (AI triage is optional).

This workspace already has a hand-maintained `docs/DEV_GUIDE.md` and `README.md`. Those are canonical for *how to use* the project. IDENTITY.md is the **map** — where things live and what not to touch. Read it first, then route via `CONTEXT.md`.

## Workspace Map

```
job-scraper/
├── scrape_jobs.py            # Main scraper; dispatched by all watcher workflows (Layer 4 producer)
├── triage_agent.py           # Claude API fit-scoring agent; run by triage.yml (Layer 4 producer)
├── notify.py                 # Pushover/notification delivery
├── eval_triage.py            # Eval harness for the triage agent
├── triage.html               # The dashboard. Pure client-side JS; reads output/*.json at load (Layer 4 consumer)
├── config.json               # User search config (gitignored). Copy from config.example.json
├── config.example.json       # Documented template. DO NOT EDIT — kept for upstream sync
├── scoring_profile.json      # AI triage calibration (gitignored). Copy from scoring_profile.example.json
├── scoring_profile.example.json  # Template. DO NOT EDIT
├── requirements.txt          # Python deps (only needed for Indeed/Glassdoor/ZipRecruiter/Google)
├── output/                   # All scraped data (gitignored upstream). all_jobs.json = 30-day rolling master (Layer 4)
│   └── deltas/               # Per-run delta files (LinkedIn only, 30d retention). See docs/JOB_SCHEMA.md
├── .github/workflows/        # 18 watcher + utility workflows (Layer 4 orchestrators)
│   └── disabled/             # Source watchers turned off by default (calcareers, glassdoor, indeed, etc.)
├── scripts/                  # One-command setup, config-secret export, feasibility slice/merge helpers
├── docs/                     # Long-form docs + deep-dive change logs (Layer 3 reference)
│   ├── DEV_GUIDE.md          # Canonical dev guide — read this before editing scrapers/workflows
│   ├── AGENT_README.md       # Canonical triage-agent doc — read this before editing triage_agent.py
│   ├── JOB_SCHEMA.md         # Data contract for job records + delta files (read before writing a consumer)
│   └── deep-dive/            # Dated architecture/change notes
├── schema/                   # Machine-validatable JSON Schema (jobs.schema.json, delta.schema.json)
├── tests/                    # Pytest suite (fixtures/, local/ for WSL-only tests)
├── CLAUDE.md                 # This file — auto-generated from IDENTITY.md. Do not edit directly.
├── README.md                 # Canonical user-facing docs
└── _config/                  # ICM Layer 3 — conventions, glossary, voice (see CONTEXT.md)
```

## Raw Source Locations

The "raw sources" are external job boards and GitHub Actions inputs, not files in this repo.

| Source | Path / Location | Contents |
|--------|-----------------|----------|
| Job boards | External (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs, HiringCafe, USAJOBS, CalCareers, NEOGOV/CalOpps) | Live postings, scraped on cron |
| `CONFIG_JSON` secret | GitHub Actions **Secrets** | Minified single-line config; exported via `scripts/export-config-secret.sh` |
| `ENABLE_DATA_COMMITS` var | GitHub Actions **Variables** | Feature flag — must be `true` for scrapers to commit |
| `ANTHROPIC_API_KEY`, `CANDIDATE_PROFILE`, `CANDIDATE_RESUME` | GitHub Actions **Secrets** | Optional — required only for AI triage |
| `PUSHOVER_TOKEN`, `PUSHOVER_USER` | GitHub Actions **Secrets** | Optional — push notifications |

## Related repos

- **Upstream:** `scottcoffin/Job_Scraper` (inferred from dashboard URL in `docs/AGENT_README.md`). This is a fork. `sync_upstream.yml` rebases weekly — safer than GitHub's "Sync fork" button.

## Rules

1. **Outputs are written to `output/`.** Scrapers write `output/<source>_jobs.{json,md,html}` and merge into `output/all_jobs.json`. The triage agent writes `output/scores.json`. Do not write scraped data anywhere else.
2. **Do not edit `config.example.json` or `scoring_profile.example.json`.** They are kept identical to upstream for sync. Edit `config.json` / `scoring_profile.json` (gitignored) instead.
3. **Do not edit generated `output/` files by hand.** They are overwritten on the next scrape. Fix the scraper, not the data.
4. **`docs/DEV_GUIDE.md` and `README.md` are canonical** for usage and dev tasks. IDENTITY.md / CONTEXT.md route to them; they do not replace them. If a fact lives in DEV_GUIDE.md, link to it — don't duplicate.
5. **Secrets vs variables:** `ENABLE_DATA_COMMITS` is a **Variable** (plaintext, log-visible). API keys and credentials are **Secrets**. Confusing the two is the #1 fork-setup failure.
6. **Concurrency group `job-scraper-commit-push`** serializes all commit workflows. Any new workflow that commits must join this group or it will race and corrupt `output/`.
7. **`ACP_BACKEND=windsurf` breaks `devin -p` in subprocess mode.** `DevinCLIChecker` strips it; if calling `devin -p` manually from WSL, use `env -u ACP_BACKEND devin -p ...`.
