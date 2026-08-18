# voice.md

Tone, audience, and evidence standards for anything written in this workspace — docs, commit messages, PR bodies, code comments.

## Audience

Mixed: **LLM agents** (routing through IDENTITY/CONTEXT) and **engineers** (humans forking the repo). Write for both: terse and scannable, but complete enough that a human new to the fork can follow without asking.

## Tone

- Technical and direct. Match the existing `docs/DEV_GUIDE.md` / `README.md` voice — pragmatic, list-driven, no marketing language.
- No emojis unless the surrounding file already uses them (the README does, sparingly, in headers — follow suit there only).
- Prefer tables for structured mappings (config fields, workflow flags, routing). Prefer numbered steps for procedures.
- Short paragraphs. Lead with the action or the fact, not the motivation.

## Vocabulary

- Use the terms defined in `_config/glossary.md` precisely: "watcher workflow", "partition", `all_jobs.json`, "feasibility check", "triage", "JD fetch", `ACP_BACKEND`, `ENABLE_DATA_COMMITS`.
- Distinguish **Secret** (`secrets.*`) from **Variable** (`vars.*`) explicitly whenever a GitHub Actions setting is involved — this is the most common fork-setup error.
- Distinguish **user file** (`config.json`) from **upstream template** (`config.example.json`) when discussing config.

## Evidence standards

- Cite the canonical source file for any fact that lives there: `docs/DEV_GUIDE.md`, `README.md`, `docs/AGENT_README.md`. Don't duplicate — link.
- When documenting a workflow behavior, reference the workflow file path (e.g. `.github/workflows/triage.yml`).
- When documenting scraper output, reference the actual field names in `output/all_jobs.json` / `output/scores.json`.
- Dated architecture notes go in `docs/deep-dive/<topic>-<YYYY-MM-DD>.md`. Don't retrofit old notes; write new ones.

## Commit / PR style

- Commit messages: focus on *why*. Include the Devin co-author trailer when Devin authored the change (see `docs/DEV_GUIDE.md` / global rules).
- PR bodies: bullet summary + a test-plan checklist. Don't editorialize.
