"""The Tests workflow runs for every code change, but not for data commits.

Data commits (output/ only) land every hour; code anywhere else (scripts,
workflows, the dashboard, schemas) is covered by the tests and must trigger them.
"""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent


def _glob_to_regex(glob):
    out = ""
    i = 0
    while i < len(glob):
        if glob.startswith("**", i):
            out += ".*"
            i += 2
        elif glob[i] == "*":
            out += "[^/]*"
            i += 1
        else:
            out += re.escape(glob[i])
            i += 1
    return re.compile(out + "$")


def triggers_tests(event, changed_files):
    """GitHub's paths / paths-ignore rules for one event of tests.yml."""
    on = yaml.safe_load((REPO_ROOT / ".github/workflows/tests.yml").read_text())[True]
    rules = on[event] or {}
    if "paths" in rules:
        return any(_glob_to_regex(g).match(f) for g in rules["paths"] for f in changed_files)
    ignored = [_glob_to_regex(g) for g in rules.get("paths-ignore", [])]
    return any(not any(r.match(f) for r in ignored) for f in changed_files)


CODE_CHANGES = ["scrape_jobs.py", "scripts/use-data-branch.sh", "scripts/setup.sh",
                ".github/workflows/linkedin_watch.yml", "triage.html",
                "schema/jobs.schema.json", "notify.py", "tests/test_ci_triggers.py"]


def test_any_code_change_runs_the_tests():
    for event in ("push", "pull_request"):
        for path in CODE_CHANGES:
            assert triggers_tests(event, [path]), f"{event} of {path} should run the tests"


def test_data_commits_do_not_run_the_tests():
    data_commit = ["output/all_jobs.json", "output/linkedin_jobs.json",
                   "output/deltas/2026-10-02T02-27-40Z_linkedin.json", "output/deltas/index.jsonl"]
    assert not triggers_tests("push", data_commit)
