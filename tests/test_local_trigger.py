"""scripts/local-trigger.py: an opt-in cron job that fills GitHub's missed slots.

Each hour it starts a workflow only in an hour that workflow's own schedule
covers, and only if it hasn't run in that hour yet. Install and uninstall touch
only its own crontab line. Runs against a fake `gh` and a fake `crontab`.
"""
import base64
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "local-trigger.py"

FAKE_GH = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    state = json.load(open(os.environ["FAKE_STATE"]))
    if args[:1] == ["api"]:
        wf = args[1].rsplit("/", 1)[1]
        if wf in state.get("broken", []):
            sys.stderr.write("HTTP 404"); sys.exit(1)
        print(state["schedules"][wf])
    elif args[:2] == ["run", "list"]:
        wf = args[args.index("--workflow") + 1]
        for created, status in state["runs"].get(wf, []):
            print(created, status)
    elif args[:2] == ["workflow", "run"]:
        state.setdefault("dispatched", []).append(args[2:])
    elif args[:2] == ["auth", "status"]:
        pass
    json.dump(state, open(os.environ["FAKE_STATE"], "w"))
''')

FAKE_CRONTAB = textwrap.dedent('''\
    #!/usr/bin/env python3
    import os, sys
    path = os.environ["FAKE_CRONTAB"]
    if sys.argv[1:] == ["-l"]:
        if not os.path.exists(path):
            sys.stderr.write("no crontab for user"); sys.exit(1)
        print(open(path).read(), end="")
    elif sys.argv[1:] == ["-"]:
        open(path, "w").write(sys.stdin.read())
''')


def encoded(cron):
    text = f'name: X\non:\n  schedule:\n    - cron: "{cron}"\n  workflow_dispatch:\n'
    return base64.b64encode(text.encode()).decode()


SCHEDULES = {"linkedin_watch.yml": encoded("17 12-23,0-3 * * *"), "scrape_jobs.yml": encoded("13 3 * * *")}


def trigger(tmp_path, *args, now=None, runs=None, broken=(), crontab=None):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name, body in (("gh", FAKE_GH), ("crontab", FAKE_CRONTAB)):
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"schedules": SCHEDULES, "runs": runs or {}, "broken": list(broken)}))
    cron_file = tmp_path / "crontab.txt"
    if crontab is not None:
        cron_file.write_text(crontab)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_STATE": str(state),
           "FAKE_CRONTAB": str(cron_file), "HOME": str(tmp_path / "home")}
    if now:
        env["LOCAL_TRIGGER_NOW"] = now
    result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                            env=env, timeout=60)
    return result, json.loads(state.read_text()), cron_file


def dispatched(state):
    return [d[0] for d in state.get("dispatched", [])]


def test_starts_a_workflow_github_missed_in_its_scheduled_hour(tmp_path):
    result, state, _ = trigger(tmp_path, "run", "--repo", "me/job-scraper", now="2026-10-03T15:20:00Z",
                               runs={"linkedin_watch.yml": [["2026-10-03T08:34:32Z", "completed"]]})

    assert result.returncode == 0, result.stdout + result.stderr
    assert state["dispatched"] == [["linkedin_watch.yml", "--repo", "me/job-scraper"]]


def test_leaves_alone_hours_outside_the_schedule(tmp_path):
    _, state, _ = trigger(tmp_path, "run", "--repo", "me/job-scraper", now="2026-10-03T08:20:00Z")

    assert dispatched(state) == []


def test_does_not_double_a_run_github_already_made(tmp_path):
    # LinkedIn already ran this hour; the digest's run is still going.
    runs = {"linkedin_watch.yml": [["2026-10-03T03:17:40Z", "completed"]],
            "scrape_jobs.yml": [["2026-10-03T02:59:00Z", "in_progress"]]}
    _, state, _ = trigger(tmp_path, "run", "--repo", "me/job-scraper", now="2026-10-03T03:20:00Z",
                          runs=runs)

    assert dispatched(state) == []


def test_daily_workflow_runs_in_its_hour(tmp_path):
    _, state, _ = trigger(tmp_path, "run", "--repo", "me/job-scraper", now="2026-10-03T03:20:00Z")

    assert dispatched(state) == ["linkedin_watch.yml", "scrape_jobs.yml"]


def test_one_workflows_error_does_not_stop_the_others(tmp_path):
    result, state, _ = trigger(tmp_path, "run", "--repo", "me/job-scraper", now="2026-10-03T03:20:00Z",
                               broken=["linkedin_watch.yml"])

    assert dispatched(state) == ["scrape_jobs.yml"]
    assert result.returncode != 0 and "linkedin_watch.yml: error" in result.stdout


def test_install_adds_one_line_and_keeps_the_rest(tmp_path):
    existing = "30 5 * * * /usr/bin/bash /home/me/other-job.sh\n"
    result, _, cron = trigger(tmp_path, "install", "--repo", "me/job-scraper", crontab=existing)
    assert result.returncode == 0, result.stderr
    trigger(tmp_path, "install", "--repo", "me/job-scraper")  # again: still one line

    lines = cron.read_text().splitlines()
    assert lines[0] == existing.strip()
    ours = [line for line in lines if "local-trigger.py run --repo me/job-scraper" in line]
    assert len(ours) == 1 and len(lines) == 2


def test_uninstall_removes_only_its_own_line(tmp_path):
    existing = "30 5 * * * /usr/bin/bash /home/me/other-job.sh\n"
    trigger(tmp_path, "install", "--repo", "me/job-scraper", crontab=existing)
    trigger(tmp_path, "uninstall")

    assert (tmp_path / "crontab.txt").read_text() == existing


def test_nothing_is_installed_by_default(tmp_path):
    result, _, cron = trigger(tmp_path, "status")

    assert "Not installed" in result.stdout and not cron.exists()
