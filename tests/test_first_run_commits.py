"""A fresh fork's first run saves what it scraped.

main ships only placeholder output files, so a fork's first runs lack files that
appear later (notified.json is written only once a notification has been sent).
Each data workflow's own commit step runs here against a clone of such a fork,
with "GitHub" a local bare repo.
"""
import glob
import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
NOT_YET_WRITTEN = {"output/notified.json", "output/workflow_runs.jsonl"}


def commit_steps():
    for path in sorted(glob.glob(str(REPO_ROOT / ".github/workflows/**/*.yml"), recursive=True)):
        jobs = yaml.safe_load(Path(path).read_text())["jobs"]
        for job_name, job in jobs.items():
            for step in job.get("steps", []):
                if "git push" in step.get("run", "") and "output/" in step["run"] and "clear" not in path:
                    yield pytest.param(step["run"], id=f"{Path(path).name}:{job_name}")


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.mark.parametrize("script", list(commit_steps()))
def test_first_run_in_a_fresh_fork_commits_its_results(tmp_path, monkeypatch, script):
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    # The fork as main ships it: placeholders only.
    seed = tmp_path / "seed"
    (seed / "output" / "deltas").mkdir(parents=True)
    (seed / "output" / "all_jobs.json").write_text('{"updated_at": null, "jobs": []}')
    (seed / "output" / "deltas" / "index.jsonl").write_text("")
    (seed / "scripts").mkdir()
    for name in ("add-output.sh", "use-data-branch.sh"):
        (seed / "scripts" / name).write_text((REPO_ROOT / "scripts" / name).read_text())
    git(seed, "init", "-q")
    git(seed, "add", "-A", "-f")
    git(seed, "commit", "-q", "-m", "fork")
    origin = tmp_path / "origin.git"
    git(tmp_path, "clone", "-q", "--bare", str(seed), str(origin))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), str(work))

    # What the run produced: every output file its commit step names, except
    # the ones a first run doesn't write.
    produced = sorted(set(re.findall(r"output/[\w.]+\.\w+", script)) - NOT_YET_WRITTEN)
    for rel in produced:
        (work / rel).write_text(json.dumps({"jobs": [{"title": "Data Analyst"}], "from": rel}))

    result = subprocess.run(
        ["bash", "-eo", "pipefail", "-c", script.replace("${{ github.actor }}", "tester")],
        cwd=work, capture_output=True, text=True,
        env={**os.environ, "DATA_BRANCH": "main", "ENABLE_DATA_COMMITS": "true"})

    assert result.returncode == 0, result.stderr
    for rel in produced:
        assert json.loads(git(origin, "show", f"main:{rel}"))["from"] == rel
