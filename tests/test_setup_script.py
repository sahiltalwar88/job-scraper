"""scripts/setup.sh configures a fork: secrets, Pages, and an optional backfill.

Runs the whole script against a fake `gh` that records every call (and every
secret it's asked to set), answering the script's prompts from stdin.
"""
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

FAKE_GH = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    log = os.environ["FAKE_GH_LOG"]
    entry = {"args": args}
    if args[:2] == ["secret", "set"]:
        entry["secret"], entry["value"] = args[2], sys.stdin.read()
    with open(log, "a") as f:
        f.write(json.dumps(entry) + "\\n")
    if args[:2] == ["repo", "view"]:
        q = args[args.index("-q") + 1] if "-q" in args else ""
        print("sahiltalwar88/job-scraper" if "parent" in q else "someone/job-scraper")
    elif args[:2] == ["workflow", "list"]:
        print(os.environ.get("FAKE_ACTIVE_WORKFLOWS", ""))
    elif args[:1] == ["api"] and args[1].endswith("/pages") and "--method" not in args:
        if os.environ.get("FAKE_PAGES") != "on":
            # Like the real gh: the 404 body goes to stdout.
            print('{"message":"Not Found","status":"404"}')
            sys.exit(1)
        print("https://someone.github.io/job-scraper/")
    # everything else (auth status, variable set, workflow run, ...) succeeds silently
''')


def run_setup(tmp_path, answers, files, env=None):
    """Run setup.sh; return (secrets set, every gh call's args)."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for rel in ("scripts/setup.sh", "scripts/export-config-secret.sh", "notify.py"):
        shutil.copy(REPO_ROOT / rel, repo / rel)
    for rel, content in files.items():
        (repo / rel).write_text(content)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    log = tmp_path / "gh.log"
    log.write_text("")
    subprocess.run(["bash", "scripts/setup.sh"], cwd=repo, input="\n".join(answers) + "\n" * 20,
                   capture_output=True, text=True, timeout=60,
                   env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
                        "FAKE_GH_LOG": str(log), **(env or {})})
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    return ({e["secret"]: e["value"] for e in entries if "secret" in e},
            [e["args"] for e in entries])


CONFIG = {"keywords": {"include": ["data analyst"]}, "profile": {"title": "Café tracker"}}


def test_sets_config_json_from_default_path(tmp_path):
    secrets, _ = run_setup(tmp_path, answers=[""], files={"config.json": json.dumps(CONFIG, indent=2)})

    assert json.loads(secrets["CONFIG_JSON"]) == CONFIG
    assert "\n" not in secrets["CONFIG_JSON"].strip()


def test_sets_config_json_from_a_path_the_user_gives(tmp_path):
    secrets, _ = run_setup(tmp_path, answers=["my-search.json"],
                        files={"my-search.json": json.dumps(CONFIG)})

    assert json.loads(secrets["CONFIG_JSON"]) == CONFIG


def pages_created(calls):
    return [c for c in calls if c[0] == "api" and c[1].endswith("/pages") and "POST" in c]


def test_turns_on_pages_for_a_fork_without_it(tmp_path):
    _, calls = run_setup(tmp_path, answers=[""], files={"config.json": "{}"})

    assert pages_created(calls)


def test_leaves_pages_alone_when_already_on(tmp_path):
    _, calls = run_setup(tmp_path, answers=[""], files={"config.json": "{}"}, env={"FAKE_PAGES": "on"})

    assert not pages_created(calls)


def test_skipping_pushover_does_not_swallow_the_next_answer(tmp_path):
    # config path, Pushover token (skip), Anthropic key, backfill
    secrets, _ = run_setup(tmp_path, answers=["", "", "sk-ant-test", "n"], files={"config.json": "{}"})

    assert secrets.get("ANTHROPIC_API_KEY") == "sk-ant-test"
    assert "PUSHOVER_TOKEN" not in secrets and "PUSHOVER_USER" not in secrets


ACTIVE = "\n".join(f".github/workflows/{wf}" for wf in (
    "linkedin_watch.yml", "linkedin_backfill.yml", "scrape_jobs.yml", "indeed_watch.yml",
    "usajobs_watch.yml", "backfill_queue.yml"))


def backfill_dispatches(tmp_path, linkedin_answer):
    # config path, Pushover token (skip), Anthropic key (skip), backfill: yes, LinkedIn mode
    _, calls = run_setup(tmp_path, answers=["", "", "", "y", linkedin_answer],
                         files={"config.json": "{}"}, env={"FAKE_ACTIVE_WORKFLOWS": ACTIVE})
    return [c for c in calls if c[:2] == ["workflow", "run"]]


def queued(dispatch):
    return dispatch[dispatch.index("-f") + 1].removeprefix("backfills=").split()


def test_backfill_starts_only_the_queue_with_linkedin_last(tmp_path):
    runs = backfill_dispatches(tmp_path, "")  # Enter: parallel LinkedIn

    assert len(runs) == 1 and runs[0][2] == "backfill_queue.yml"
    assert queued(runs[0]) == ["indeed_watch.yml:backfill", "scrape_jobs.yml:backfill",
                               "usajobs_watch.yml", "linkedin_backfill.yml"]


def test_backfill_can_use_linkedins_single_run(tmp_path):
    runs = backfill_dispatches(tmp_path, "s")

    assert queued(runs[0])[-1] == "linkedin_watch.yml:backfill"
    assert "linkedin_backfill.yml" not in queued(runs[0])
