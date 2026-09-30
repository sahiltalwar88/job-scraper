"""Config notices show when scrape_jobs.py runs, not when another tool imports it.

job-hunter imports scrape_jobs from a clone with no config.json; a notice printed
on import lands in its log and reads like a job-hunter config error.
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
NOTICE = "config.json not found"


def run(tmp_path, *args):
    shutil.copy(REPO_ROOT / "scrape_jobs.py", tmp_path / "scrape_jobs.py")
    shutil.copy(REPO_ROOT / "config.example.json", tmp_path / "config.example.json")
    return subprocess.run([sys.executable, *args], cwd=tmp_path,
                          capture_output=True, text=True, timeout=60, check=True)


def test_importing_without_config_json_prints_nothing(tmp_path):
    result = run(tmp_path, "-c", "import scrape_jobs")

    assert NOTICE not in result.stdout + result.stderr


def test_running_without_config_json_says_the_example_is_used(tmp_path):
    result = run(tmp_path, "scrape_jobs.py", "--linkedin-emit-matrix")

    assert NOTICE in result.stdout
