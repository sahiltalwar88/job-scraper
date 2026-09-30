"""scripts/refork-keeping-data.sh: a fresh fork that still has the user's data and settings.

"GitHub" is a folder of bare repos (GH_URL=file://...) and a fake `gh` that
implements the handful of commands the script uses.
"""
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "refork-keeping-data.sh"
HER_JOBS = json.dumps({"jobs": [{"url": "https://example.com/hers"}]})
OWNER_JOBS = json.dumps({"jobs": [{"url": "https://example.com/owners"}]})

FAKE_GH = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, shutil, subprocess, sys
    root = os.environ["FAKE_GH_ROOT"]
    state_path = os.path.join(root, "state.json")
    state = json.load(open(state_path))
    args = sys.argv[1:]
    def opt(name):
        return args[args.index(name) + 1] if name in args else None
    def bare(repo):
        return os.path.join(root, repo + ".git")
    def save():
        json.dump(state, open(state_path, "w"))
    if args[:2] == ["api", "user"]:
        print("manj")
    elif args[:2] == ["repo", "view"]:
        sys.exit(0 if os.path.isdir(bare(args[2])) else 1)
    elif args[:2] == ["secret", "list"]:
        print("\\n".join(state["secrets"].get(opt("--repo"), {})))
    elif args[:2] == ["variable", "list"]:
        vs = state["variables"].get(opt("--repo"), {})
        print(json.dumps([{"name": k, "value": v} for k, v in vs.items()]))
    elif args[:2] == ["repo", "delete"]:
        shutil.rmtree(bare(args[2]))
        state["secrets"].pop(args[2], None); state["variables"].pop(args[2], None); save()
    elif args[:2] == ["repo", "fork"]:
        assert "--default-branch-only" in args
        subprocess.run(["git", "clone", "-q", "--bare", "--single-branch", "-b", "main",
                        bare(args[2]), bare("manj/job-scraper")], check=True)
    elif args[:2] == ["variable", "set"]:
        state["variables"].setdefault(opt("--repo"), {})[args[2]] = opt("--body"); save()
    elif args[:2] == ["secret", "set"]:
        state["secrets"].setdefault(opt("--repo"), {})[args[2]] = sys.stdin.read(); save()
    elif args[0] == "api":
        state.setdefault("api", []).append(args[1:]); save()
    else:
        sys.exit(f"fake gh: unsupported {args}")
''')


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def make_repo(root, name, files, branches=("main",)):
    seed = root / "seeds" / name.replace("/", "_")
    for rel, content in files.items():
        (seed / rel).parent.mkdir(parents=True, exist_ok=True)
        (seed / rel).write_text(content)
    git(seed, "init", "-q")
    git(seed, "add", "-A", "-f")
    git(seed, "commit", "-q", "-m", f"{name} contents")
    for b in branches[1:]:
        git(seed, "branch", b)
    (root / "gh" / name).parent.mkdir(parents=True, exist_ok=True)
    git(root, "clone", "-q", "--bare", str(seed), str(root / "gh" / f"{name}.git"))
    for b in branches[1:]:
        git(root / "gh" / f"{name}.git", "fetch", "-q", str(seed), f"{b}:{b}")


@pytest.fixture
def github(tmp_path, monkeypatch):
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n"
                         "[protocol \"file\"]\n\tallow = always\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    export = (REPO_ROOT / "scripts" / "export-config-secret.sh").read_text()
    make_repo(tmp_path, "sahiltalwar88/job-scraper",
              {"code.py": "VERSION = 2\n", "output/all_jobs.json": json.dumps({"jobs": []}),
               "scripts/export-config-secret.sh": export})
    make_repo(tmp_path, "manj/job-scraper",
              {"code.py": "VERSION = 1\n", "output/all_jobs.json": HER_JOBS, "output/notified.json": "{}"})
    (tmp_path / "gh" / "state.json").write_text(json.dumps({
        "secrets": {"manj/job-scraper": {"CONFIG_JSON": "old", "PUSHOVER_TOKEN": "x"}},
        "variables": {"manj/job-scraper": {"ENABLE_DATA_COMMITS": "true", "NOTIFY_MIN_FIT": "60"}},
    }))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    work = tmp_path / "work"
    work.mkdir()
    (work / "config.json").write_text(json.dumps({"keywords": {"include": ["nurse"]}}))
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_GH_ROOT": str(tmp_path / "gh"),
           "GH_URL": f"file://{tmp_path / 'gh'}"}
    return tmp_path, work, env


def refork(work, env, *args, answers=""):
    return subprocess.run(["bash", str(SCRIPT), *args], cwd=work, env=env, input=answers,
                          capture_output=True, text=True, timeout=120)


def state(root):
    return json.loads((root / "gh" / "state.json").read_text())


def test_dry_run_changes_nothing(github):
    root, work, env = github
    result = refork(work, env)

    assert result.returncode == 0, result.stderr
    assert "PUSHOVER_TOKEN" in result.stdout
    assert git(root / "gh" / "manj/job-scraper.git", "show", "main:code.py") == "VERSION = 1"
    assert not (work / "job-scraper-backup.git").exists()


def test_wrong_confirmation_deletes_nothing(github):
    root, work, env = github
    result = refork(work, env, "--apply", answers="nope\n")

    assert result.returncode != 0
    assert (root / "gh" / "manj/job-scraper.git").is_dir()


def test_refork_restores_her_data_and_settings(github):
    root, work, env = github
    result = refork(work, env, "--apply", answers="manj/job-scraper\n\n")

    assert result.returncode == 0, result.stdout + result.stderr
    new = root / "gh" / "manj/job-scraper.git"
    assert git(new, "show", "main:code.py") == "VERSION = 2"          # fresh fork of the source
    assert git(new, "show", "main:output/all_jobs.json") == HER_JOBS  # her jobs, not the owner's
    s = state(root)
    assert s["variables"]["manj/job-scraper"] == {"ENABLE_DATA_COMMITS": "true", "NOTIFY_MIN_FIT": "60"}
    assert json.loads(s["secrets"]["manj/job-scraper"]["CONFIG_JSON"]) == {"keywords": {"include": ["nurse"]}}
    assert "re-add secret PUSHOVER_TOKEN" in result.stdout
    backup = work / "job-scraper-backup.git"
    assert git(backup, "show", "main:output/all_jobs.json") == HER_JOBS
