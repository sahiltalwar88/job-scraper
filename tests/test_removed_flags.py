"""Removed command-line flags must stop, not fall through to a full default scrape."""
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_feasibility_check_flag_stops_without_scraping(tmp_path):
    for name in ("scrape_jobs.py", "config.example.json"):
        shutil.copy(REPO_ROOT / name, tmp_path / name)

    result = subprocess.run([sys.executable, "scrape_jobs.py", "--feasibility-check"], cwd=tmp_path,
                            capture_output=True, text=True, timeout=60)

    assert result.returncode != 0
    assert "was removed" in result.stderr
    assert not (tmp_path / "output").exists() or not any((tmp_path / "output").iterdir())
