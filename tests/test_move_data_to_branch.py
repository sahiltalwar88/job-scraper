"""scripts/move-data-to-branch.sh: data moves to a branch, main ships empty, nothing is lost.

Runs the script against a bare "GitHub" repo and a fake `gh` that records what
it's asked to change.
"""
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
FULL = json.dumps({"updated_at": "2026-09-30", "jobs": [{"url": "https://example.com/1"}]})

FAKE_GH = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    def log(entry):
        with open(os.environ["FAKE_GH_LOG"], "a") as f:
            f.write(json.dumps(entry) + "\\n")
    if args[:2] == ["repo", "view"]:
        print("someone/job-scraper")
    elif args[:2] == ["variable", "set"]:
        log({"variable": args[2], "value": args[args.index("--body") + 1]})
    elif args[:2] == ["run", "list"]:
        pass  # nothing running
    elif args[0] == "api":
        log({"api": args[1:], "input": sys.stdin.read() if "--input" in args else ""})
''')


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    seed = tmp_path / "seed"
    for rel in ("scripts/move-data-to-branch.sh", "scripts/use-data-branch.sh",
                ".github/workflows/linkedin_watch.yml"):
        (seed / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / rel, seed / rel)
    (seed / "output" / "deltas").mkdir(parents=True)
    (seed / "output" / "all_jobs.json").write_text(FULL)
    (seed / "output" / "linkedin_jobs.json").write_text(FULL)
    (seed / "output" / "deltas" / "index.jsonl").write_text('{"file": "a.json"}\n')
    (seed / "output" / "deltas" / "a.json").write_text("{}")
    git(seed, "init", "-q")
    git(seed, "add", "-A", "-f")
    git(seed, "commit", "-q", "-m", "main with the maintainer's data")
    origin = tmp_path / "origin.git"
    git(tmp_path, "clone", "-q", "--bare", str(seed), str(origin))
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(origin), str(clone))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    log = tmp_path / "gh.log"
    log.write_text("")
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_GH_LOG": str(log)}
    return origin, clone, env, log


def move(clone, env, *args):
    result = subprocess.run(["bash", "scripts/move-data-to-branch.sh", "sahil-data", *args], cwd=clone,
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_dry_run_changes_nothing(setup):
    origin, clone, env, log = setup
    main_before = git(origin, "rev-parse", "main")

    move(clone, env)

    assert git(origin, "rev-parse", "main") == main_before
    assert git(origin, "branch", "--list", "sahil-data") == ""
    assert log.read_text() == ""


def test_apply_keeps_all_data_on_the_branch_and_empties_main(setup):
    origin, clone, env, log = setup
    data_before = git(origin, "ls-tree", "-r", "main", "output/")

    move(clone, env, "--apply")

    assert git(origin, "ls-tree", "-r", "sahil-data", "output/") == data_before
    assert json.loads(git(origin, "show", "main:output/all_jobs.json")) == {"updated_at": None, "jobs": []}
    assert git(origin, "ls-tree", "-r", "--name-only", "main", "output/").split() == \
        ["output/.gitkeep", "output/all_jobs.json", "output/deltas/index.jsonl"]
    assert git(origin, "show", "main:output/deltas/index.jsonl") == ""
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert {"variable": "DATA_BRANCH", "value": "sahil-data"} in calls
    pages = [c for c in calls if "api" in c]
    assert pages and json.loads(pages[0]["input"])["source"]["branch"] == "sahil-data"


def test_next_scheduled_run_keeps_the_moved_data(setup):
    """Emptying main must not reach the data branch when workflows next update it from main."""
    origin, clone, env, log = setup
    move(clone, env, "--apply")
    runner = clone.parent / "runner"
    git(clone.parent, "clone", "-q", str(origin), str(runner))

    subprocess.run(["bash", "scripts/use-data-branch.sh"], cwd=runner, check=True, capture_output=True,
                   env={**env, "DATA_BRANCH": "sahil-data", "ENABLE_DATA_COMMITS": "true"})

    assert git(origin, "show", "sahil-data:output/all_jobs.json") == FULL
