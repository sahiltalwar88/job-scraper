#!/usr/bin/env python3
"""Optional: start your fork's scheduled scrapes from your own computer.

GitHub starts scheduled workflows late or not at all when it's busy (some days
only a handful of the LinkedIn Watcher's hourly slots run). This adds an hourly
cron job on your computer that fills those gaps. It's off unless you install it.

  python3 scripts/local-trigger.py install [--repo OWNER/NAME]
  python3 scripts/local-trigger.py status
  python3 scripts/local-trigger.py uninstall
  python3 scripts/local-trigger.py run --repo OWNER/NAME     # what cron runs

Each hour, for each workflow in WORKFLOWS, it reads that workflow's schedule
from GitHub and starts it only in an hour the schedule covers, and only if it
hasn't already run (or isn't running) in that hour. So it never doubles a run
GitHub made on time. The repo defaults to this clone's `origin` remote.

Needs the GitHub CLI (gh), logged in. Cron runs only while your computer is on
(on Windows, only while WSL is running).
"""
import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

WORKFLOWS = ["linkedin_watch.yml", "scrape_jobs.yml"]
MARKER = "# job-scraper local trigger"
# Local minute past each hour. A few minutes after the workflows' own slots, so
# a run GitHub started on time is already visible and is left alone.
CRON_MINUTE = 20
LOG = os.path.expanduser("~/.local/state/job-scraper/local-trigger.log")


def gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def hours_in(field: str) -> set:
    """The hours a cron hour field covers: *, 5, 1-3, */2, 12-23/2, and lists of these."""
    hours = set()
    for part in field.split(","):
        rng, _, step = part.partition("/")
        if rng == "*":
            lo, hi = 0, 23
        elif "-" in rng:
            lo, hi = (int(x) for x in rng.split("-"))
        else:
            lo = hi = int(rng)
            if step:
                hi = 23
        hours.update(range(lo, hi + 1, int(step or 1)))
    return hours


def scheduled_hours(repo: str, workflow: str) -> set:
    """UTC hours the workflow's `schedule` crons cover, read from GitHub."""
    content = gh("api", f"repos/{repo}/contents/.github/workflows/{workflow}", "-q", ".content")
    text = base64.b64decode(content).decode("utf-8")
    hours = set()
    for cron in re.findall(r"""^\s*-\s*cron:\s*["']([^"']+)["']""", text, re.M):
        hours |= hours_in(cron.split()[1])
    return hours


def ran_this_hour(repo: str, workflow: str, now: datetime) -> bool:
    out = gh("run", "list", "--repo", repo, "--workflow", workflow, "--limit", "5",
             "--json", "createdAt,status", "-q", '.[] | "\\(.createdAt) \\(.status)"')
    this_hour = now.strftime("%Y-%m-%dT%H")
    for line in out.splitlines():
        created, _, status = line.partition(" ")
        if status != "completed" or created.startswith(this_hour):
            return True
    return False


def run(repo: str) -> int:
    now = datetime.now(timezone.utc)
    if os.environ.get("LOCAL_TRIGGER_NOW"):  # tests
        now = datetime.strptime(os.environ["LOCAL_TRIGGER_NOW"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%MZ")
    failed = 0
    for workflow in WORKFLOWS:
        try:
            if now.hour not in scheduled_hours(repo, workflow):
                continue
            if ran_this_hour(repo, workflow, now):
                print(f"{stamp} {workflow}: already ran this hour")
                continue
            gh("workflow", "run", workflow, "--repo", repo)
            print(f"{stamp} {workflow}: started")
        except Exception as e:  # one workflow's trouble mustn't stop the others
            failed += 1
            print(f"{stamp} {workflow}: error: {e}")
    return 1 if failed else 0


def origin_repo() -> str:
    url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True,
                         text=True).stdout.strip()
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    if not match:
        sys.exit("Couldn't tell which GitHub repo this is; pass --repo OWNER/NAME.")
    return match.group(1)


def read_crontab() -> list:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return result.stdout.splitlines() if result.returncode == 0 else []


def write_crontab(lines: list) -> None:
    subprocess.run(["crontab", "-"], input="".join(f"{line}\n" for line in lines),
                   text=True, check=True)


def install(repo: str) -> int:
    gh_path = shutil.which("gh")
    if not gh_path:
        sys.exit("Install the GitHub CLI (gh) and run `gh auth login` first.")
    if subprocess.run(["gh", "auth", "status"], capture_output=True).returncode != 0:
        sys.exit("Log in to the GitHub CLI first: gh auth login")
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    path = ":".join(dict.fromkeys([os.path.dirname(gh_path), "/usr/local/bin", "/usr/bin", "/bin"]))
    entry = (f"{CRON_MINUTE} * * * * PATH={path} {sys.executable} {os.path.abspath(__file__)} "
             f"run --repo {repo} >> {LOG} 2>&1 {MARKER} ({repo})")
    write_crontab([line for line in read_crontab() if MARKER not in line] + [entry])
    print(f"Installed: every hour at :{CRON_MINUTE:02d} (local time), starts {repo}'s "
          f"scheduled workflows that GitHub hasn't run that hour.")
    print(f"Log: {LOG}")
    print("Remove with: python3 scripts/local-trigger.py uninstall")
    return 0


def uninstall() -> int:
    lines = read_crontab()
    kept = [line for line in lines if MARKER not in line]
    if len(kept) == len(lines):
        print("Not installed.")
        return 0
    write_crontab(kept)
    print("Removed the local trigger from your crontab.")
    return 0


def status() -> int:
    ours = [line for line in read_crontab() if MARKER in line]
    print("Installed:" if ours else "Not installed.")
    for line in ours:
        print(f"  {line}")
    if os.path.exists(LOG):
        with open(LOG, encoding="utf-8") as f:
            tail = f.readlines()[-10:]
        print(f"Last log lines ({LOG}):")
        print("".join(f"  {line}" for line in tail), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["install", "uninstall", "status", "run"])
    parser.add_argument("--repo", help="OWNER/NAME (default: this clone's origin)")
    args = parser.parse_args()
    if args.command == "uninstall":
        return uninstall()
    if args.command == "status":
        return status()
    repo = args.repo or origin_repo()
    return install(repo) if args.command == "install" else run(repo)


if __name__ == "__main__":
    sys.exit(main())
