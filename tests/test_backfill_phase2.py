"""When the parallel backfill has no Phase 2 work, Phase 2 only records the run.

It must leave Phase 1's results as they are: re-merging them would re-save
linkedin_jobs.json with none marked new, so the LinkedIn digest would say
"No new roles" right after a backfill. Runs the merge-phase2 job's own steps,
skipping the ones GitHub would skip, against a clone whose "GitHub" is a local
bare repo.
"""
import json
import os
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "linkedin_backfill.yml"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def step_runs(step, fanout_result):
    condition = step.get("if", "")
    if "fanout-phase2.result" in condition:
        return f"== '{fanout_result}'" in condition
    return "run" in step and "secrets." not in json.dumps(step)


def test_phase2_without_work_keeps_phase1_results_and_records_the_run(tmp_path, monkeypatch):
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    # The repo right after Phase 1 committed: its jobs are new.
    job = {"url": "https://www.linkedin.com/jobs/view/1/", "title": "Director of Engineering",
           "company": "Acme", "location": "Remote"}
    phase1 = {"scraped_at": "x", "total": 1, "new_count": 1, "jobs": [job], "new_jobs": [job]}
    seed = tmp_path / "seed"
    (seed / "output").mkdir(parents=True)
    (seed / "output" / "linkedin_jobs.json").write_text(json.dumps(phase1))
    (seed / "output" / "all_jobs.json").write_text(json.dumps({"jobs": [dict(job, first_seen="2026-10-01T00:00:00Z")]}))
    (seed / "scripts").mkdir()
    for name in ("add-output.sh", "use-data-branch.sh"):
        (seed / "scripts" / name).write_text((REPO_ROOT / "scripts" / name).read_text())
    for name in ("scrape_jobs.py", "notify.py", "config.example.json"):
        (seed / name).write_text((REPO_ROOT / name).read_text())
    git(seed, "init", "-q")
    git(seed, "add", "-A", "-f")
    git(seed, "commit", "-q", "-m", "phase 1")
    origin = tmp_path / "origin.git"
    git(tmp_path, "clone", "-q", "--bare", str(seed), str(origin))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), str(work))
    # Phase 1's partition files, as the artifact download would bring them.
    (work / "output" / "linkedin_partition_a.json").write_text(json.dumps({"jobs": [job]}))

    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["merge-phase2"]["steps"]
    for step in steps:
        if step_runs(step, fanout_result="skipped"):
            script = step["run"].replace("${{ github.actor }}", "tester")
            result = subprocess.run(["bash", "-eo", "pipefail", "-c", script], cwd=work, capture_output=True,
                                    text=True, env={**os.environ, "DATA_BRANCH": "main",
                                                    "ENABLE_DATA_COMMITS": "true"})
            assert result.returncode == 0, f"{step.get('name')}: {result.stderr}"

    saved = json.loads(git(origin, "show", "main:output/linkedin_jobs.json"))
    assert saved["new_jobs"] == [job]
    runs = git(origin, "show", "main:output/workflow_runs.jsonl").splitlines()
    assert json.loads(runs[-1])["workflow"] == "linkedin-backfill-2phase"
