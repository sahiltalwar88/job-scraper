"""Job data can live on a separate branch (DATA_BRANCH) so main, which forks copy, stays empty.

Runs scripts/use-data-branch.sh and the LinkedIn watcher's real commit step
against a bare "GitHub" repo with main (code, empty output/) and a data
branch (code + the maintainer's jobs).
"""
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = (REPO_ROOT / "scripts" / "use-data-branch.sh").read_text()
EMPTY = json.dumps({"updated_at": None, "jobs": []})
FULL = json.dumps({"updated_at": "2026-09-30", "jobs": [{"url": "https://example.com/1"}]})


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True).stdout.strip()


class Remote:
    def __init__(self, root):
        self.root = root
        self.bare = root / "origin.git"
        self.url = f"file://{self.bare}"
        self.dev = root / "dev"

    def write_commit_push(self, branch, files, msg):
        git(self.dev, "checkout", "-q", "-B", branch, f"origin/{branch}")
        for rel, content in files.items():
            (self.dev / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.dev / rel).write_text(content)
        git(self.dev, "add", "-A", "-f")
        git(self.dev, "commit", "-q", "-m", msg)
        git(self.dev, "push", "-q", "origin", f"HEAD:{branch}")
        git(self.dev, "fetch", "-q", "origin")

    def show(self, ref, path):
        return git(self.bare, "show", f"{ref}:{path}", check=False)

    def runner(self, name="runner", shallow=True):
        """A fresh checkout like actions/checkout makes (shallow, on main)."""
        path = self.root / name
        args = ["clone", "-q"] + (["--depth", "1"] if shallow else []) + [self.url, str(path)]
        git(self.root, *args)
        return path

    def use_data_branch(self, runner, branch=None, commits="true"):
        env = {**os.environ, "ENABLE_DATA_COMMITS": commits}
        env.pop("DATA_BRANCH", None)
        if branch:
            env["DATA_BRANCH"] = branch
        result = subprocess.run(["bash", "-c", SCRIPT], cwd=runner, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return result


@pytest.fixture
def remote(tmp_path, monkeypatch):
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n"
                         "[protocol \"file\"]\n\tallow = always\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    r = Remote(tmp_path)
    seed = tmp_path / "seed"
    (seed / "output").mkdir(parents=True)
    (seed / "code.py").write_text("VERSION = 1\n")
    (seed / "output" / "all_jobs.json").write_text(EMPTY)
    git(seed, "init", "-q")
    git(seed, "add", "-A", "-f")
    git(seed, "commit", "-q", "-m", "main: code + empty output")
    git(tmp_path, "clone", "-q", "--bare", str(seed), str(r.bare))
    git(tmp_path, "clone", "-q", r.url, str(r.dev))
    git(r.dev, "push", "-q", "origin", "HEAD:sahil-data")
    git(r.dev, "fetch", "-q", "origin")
    r.write_commit_push("sahil-data", {"output/all_jobs.json": FULL}, "data: maintainer's jobs")
    return r


def test_default_is_the_latest_main(remote):
    runner = remote.runner()
    remote.write_commit_push("main", {"code.py": "VERSION = 2\n"}, "main: newer code")

    remote.use_data_branch(runner)

    assert (runner / "code.py").read_text() == "VERSION = 2\n"
    assert git(runner, "rev-parse", "--abbrev-ref", "HEAD") == "main"


@pytest.mark.parametrize("shallow", [True, False])
def test_data_branch_gets_mains_code_and_keeps_its_data(remote, shallow):
    remote.write_commit_push("main", {"code.py": "VERSION = 2\n"}, "main: newer code")
    old_data_tip = git(remote.bare, "rev-parse", "sahil-data")
    runner = remote.runner(shallow=shallow)

    remote.use_data_branch(runner, "sahil-data")

    assert (runner / "code.py").read_text() == "VERSION = 2\n"
    assert (runner / "output" / "all_jobs.json").read_text() == FULL
    assert remote.show("sahil-data", "code.py") == "VERSION = 2"
    assert remote.show("sahil-data", "output/all_jobs.json") == FULL
    assert remote.show("main", "output/all_jobs.json") == EMPTY
    # moved forward from the old tip, so clones of the data branch can fast-forward
    assert git(remote.bare, "merge-base", "--is-ancestor", old_data_tip, "sahil-data", check=False) == ""


def test_update_works_without_a_git_identity(remote, tmp_path, monkeypatch):
    """GitHub runners have no git identity until a workflow's commit step sets one."""
    remote.write_commit_push("main", {"code.py": "VERSION = 2\n"}, "main: newer code")
    runner = remote.runner()
    bare_config = tmp_path / "no-identity-gitconfig"
    bare_config.write_text("[protocol \"file\"]\n\tallow = always\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(bare_config))
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(var, "")  # like a runner: git can't work out a name

    remote.use_data_branch(runner, "sahil-data")

    assert remote.show("sahil-data", "code.py") == "VERSION = 2"


def test_data_branch_unchanged_when_main_has_nothing_new(remote):
    tip = git(remote.bare, "rev-parse", "sahil-data")
    runner = remote.runner()

    remote.use_data_branch(runner, "sahil-data")

    assert git(remote.bare, "rev-parse", "sahil-data") == tip
    assert git(runner, "rev-parse", "HEAD") == tip


def test_missing_data_branch_starts_from_main_and_exists_remotely(remote):
    runner = remote.runner()

    remote.use_data_branch(runner, "someone-data")

    assert git(runner, "rev-parse", "--abbrev-ref", "HEAD") == "someone-data"
    assert remote.show("someone-data", "output/all_jobs.json") == EMPTY


def test_job_hunter_clone_of_the_data_branch_fast_forwards(remote):
    """job-hunter pulls its clone with --ff-only and detects new data by HEAD changing."""
    reader = remote.root / "reader"
    git(remote.root, "clone", "-q", "-b", "sahil-data", remote.url, str(reader))
    before = git(reader, "rev-parse", "HEAD")
    remote.write_commit_push("main", {"code.py": "VERSION = 2\n"}, "main: newer code")

    remote.use_data_branch(remote.runner(), "sahil-data")
    git(reader, "fetch", "-q", "origin")
    git(reader, "pull", "-q", "--ff-only")

    assert git(reader, "rev-parse", "HEAD") != before
    assert (reader / "code.py").read_text() == "VERSION = 2\n"
    assert (reader / "output" / "all_jobs.json").read_text() == FULL


def test_watcher_commit_step_writes_to_the_data_branch_only(remote):
    runner = remote.runner()
    remote.use_data_branch(runner, "sahil-data")
    new_data = json.dumps({"updated_at": "2026-10-01", "jobs": [{"url": "https://example.com/2"}]})
    for name in ("all_jobs.json", "linkedin_jobs.json", "notified.json", "workflow_runs.jsonl",
                 "dashboard_config.json"):
        (runner / "output" / name).write_text(new_data)
    for ext in ("md", "html"):
        (runner / "output" / f"linkedin_jobs.{ext}").write_text("x")
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "linkedin_watch.yml").read_text())
    step = next(s for s in wf["jobs"]["scrape"]["steps"] if s.get("name") == "Commit results to repo")

    subprocess.run(["bash", "-eo", "pipefail", "-c", step["run"].replace("${{ github.actor }}", "t")],
                   cwd=runner, check=True, capture_output=True, text=True,
                   env={**os.environ, "DATA_BRANCH": "sahil-data"})

    assert remote.show("sahil-data", "output/all_jobs.json") == new_data
    assert remote.show("main", "output/all_jobs.json") == EMPTY
