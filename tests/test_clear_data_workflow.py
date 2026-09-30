"""Clear Job Data must leave no jobs, scores or notification history in the pushed repo.

Runs the workflow's own steps against a local clone whose "GitHub" is a bare repo.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "clear_data.yml"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.mark.parametrize("data_branch", ["main", "sahil-data"])
def test_clear_job_data_empties_every_output_file(tmp_path, monkeypatch, data_branch):
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    seed = tmp_path / "seed"
    (seed / "output" / "deltas").mkdir(parents=True)
    job = {"url": "https://example.com/1", "title": "Data Analyst", "company": "Acme"}
    for name in ("all_jobs.json", "linkedin_jobs.json", "csucareers_jobs.json"):
        (seed / "output" / name).write_text(json.dumps({"jobs": [job]}))
    (seed / "output" / "scores.json").write_text(json.dumps({"scores": {job["url"]: {"score": 80}}}))
    (seed / "output" / "notified.json").write_text(json.dumps({"ids": ["x"]}))
    (seed / "output" / "deltas" / "index.jsonl").write_text('{"file": "a.json"}\n')
    (seed / "scripts").mkdir()
    (seed / "scripts" / "use-data-branch.sh").write_text((REPO_ROOT / "scripts" / "use-data-branch.sh").read_text())
    git(seed, "init", "-q")
    git(seed, "add", "-A", "-f")
    git(seed, "commit", "-q", "-m", "seed")
    origin = tmp_path / "origin.git"
    git(tmp_path, "clone", "-q", "--bare", str(seed), str(origin))
    if data_branch != "main":
        git(origin, "branch", data_branch, "main")
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), str(work))

    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]
    for job_def in steps.values():
        for step in job_def["steps"]:
            if "run" in step:
                script = step["run"].replace("${{ github.actor }}", "tester")
                subprocess.run(["bash", "-eo", "pipefail", "-c", script], cwd=work, check=True,
                               capture_output=True, text=True, env={**os.environ, "GITHUB_ACTIONS": "true",
                                                         "DATA_BRANCH": data_branch, "ENABLE_DATA_COMMITS": "true"})

    def pushed(path):
        return json.loads(git(origin, "show", f"{data_branch}:output/{path}"))

    for name in ("all_jobs.json", "linkedin_jobs.json", "csucareers_jobs.json"):
        assert pushed(name)["jobs"] == [], name
    assert pushed("scores.json") == {"scores": {}}
    assert pushed("notified.json") == {"ids": []}
    assert "deltas" not in git(origin, "ls-tree", "--name-only", data_branch, "output/")
    if data_branch != "main":  # main is left alone
        assert json.loads(git(origin, "show", "main:output/all_jobs.json"))["jobs"] == [job]
