"""scripts/run-backfill-queue.sh runs backfills one at a time, in order.

The watchers share one concurrency group that holds a single waiting run, so
each backfill must start only after the previous one finished. Runs against a
fake `gh` that keeps a list of workflow runs: each finishes after a couple of
status checks, with the outcome the test scripts for it.
"""
import json
import os
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

FAKE_GH = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, re, sys
    from datetime import datetime, timezone
    args = sys.argv[1:]
    state_path = os.environ["FAKE_GH_STATE"]
    state = json.load(open(state_path))
    outcomes = json.loads(os.environ.get("FAKE_OUTCOMES", "{}"))

    def opt(name):
        return args[args.index(name) + 1]

    if args[:2] == ["workflow", "run"]:
        wf = args[2]
        tried = sum(1 for r in state["runs"] if r["wf"] == wf)
        planned = outcomes.get(wf, ["success"])
        state["runs"].append({
            "id": len(state["runs"]) + 1, "wf": wf,
            "inputs": [a for a in args[3:] if "=" in a],
            "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "checks": 0, "outcome": planned[min(tried, len(planned) - 1)],
            "others_running": sum(1 for r in state["runs"] if r["checks"] < 2)})
        state["log"].append(["dispatch", wf])
    elif args[:2] == ["run", "list"]:
        q = opt("-q")
        since = re.search(r'createdAt >= "([^"]+)"', q).group(1)
        newer_than = int(re.search(r"databaseId > (\\d+)", q).group(1))
        runs = [r for r in state["runs"] if r["wf"] == opt("--workflow")
                and r["createdAt"] >= since and r["id"] > newer_than]
        if runs:
            print(runs[0]["id"])
    elif args[:2] == ["run", "view"]:
        run = state["runs"][int(args[2]) - 1]
        if opt("--json") == "status":
            run["checks"] += 1
            done = run["checks"] >= 2
            if done:
                state["log"].append(["finished", run["wf"]])
            print("completed" if done else "in_progress")
        else:
            print(run["outcome"])
    json.dump(state, open(state_path, "w"))
''')


def run_queue(tmp_path, specs, outcomes=None):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"runs": [], "log": []}))
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts/run-backfill-queue.sh"), *specs],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_GH_STATE": str(state),
             "GITHUB_REPOSITORY": "someone/job-scraper", "POLL_SECONDS": "0",
             "FAKE_OUTCOMES": json.dumps(outcomes or {})})
    return result, json.loads(state.read_text())


def test_each_backfill_starts_after_the_previous_one_finished(tmp_path):
    result, state = run_queue(tmp_path, ["indeed_watch.yml:backfill", "scrape_jobs.yml:backfill",
                                         "linkedin_backfill.yml"])

    assert result.returncode == 0, result.stderr
    assert state["log"] == [
        ["dispatch", "indeed_watch.yml"], ["finished", "indeed_watch.yml"],
        ["dispatch", "scrape_jobs.yml"], ["finished", "scrape_jobs.yml"],
        ["dispatch", "linkedin_backfill.yml"], ["finished", "linkedin_backfill.yml"]]
    assert all(r["others_running"] == 0 for r in state["runs"])


def test_backfill_suffix_turns_on_the_backfill_input(tmp_path):
    _, state = run_queue(tmp_path, ["indeed_watch.yml:backfill", "linkedin_backfill.yml"])

    assert [r["inputs"] for r in state["runs"]] == [["backfill=true"], []]


def test_a_cancelled_run_is_started_again(tmp_path):
    result, state = run_queue(tmp_path, ["scrape_jobs.yml:backfill"],
                              outcomes={"scrape_jobs.yml": ["cancelled", "success"]})

    assert result.returncode == 0, result.stderr
    assert [r["outcome"] for r in state["runs"]] == ["cancelled", "success"]


def test_a_failed_backfill_is_reported_and_the_rest_still_run(tmp_path):
    result, state = run_queue(tmp_path, ["indeed_watch.yml:backfill", "linkedin_backfill.yml"],
                              outcomes={"indeed_watch.yml": ["failure"]})

    assert result.returncode != 0
    assert "indeed_watch.yml:backfill (failure)" in result.stderr
    assert [r["wf"] for r in state["runs"]] == ["indeed_watch.yml", "linkedin_backfill.yml"]


def test_the_workflow_runs_the_queue_outside_the_commit_group(tmp_path):
    import yaml
    wf = yaml.safe_load((REPO_ROOT / ".github/workflows/backfill_queue.yml").read_text())

    assert "concurrency" not in wf and "concurrency" not in wf["jobs"]["queue"]
    assert wf["jobs"]["queue"]["permissions"]["actions"] == "write"
    assert any("run-backfill-queue.sh" in s.get("run", "") for s in wf["jobs"]["queue"]["steps"])
