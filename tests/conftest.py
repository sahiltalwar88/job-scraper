"""Shared fixtures for job-scraper tests."""
import json
import os
import sys
from pathlib import Path

import pytest

# Make scrape_jobs importable
SCRAPER_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRAPER_DIR))

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def ca_raw_html():
    """Real LinkedIn search results HTML (5 pages, 50 cards) from California."""
    path = FIXTURES_DIR / "ca_raw_5pages.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def linkedin_posting_html():
    """Real LinkedIn posting detail page HTML."""
    path = FIXTURES_DIR / "linkedin_posting_page.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def all_jobs_sample():
    """Synthetic all_jobs.json with 10 jobs (mix of feasible/infeasible/unchecked)."""
    path = FIXTURES_DIR / "all_jobs_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def partition_files():
    """List of 3 synthetic partition JSON file paths."""
    return sorted((FIXTURES_DIR / "partition_files").glob("partition*.json"))


@pytest.fixture
def tmp_output_dir(tmp_path, monkeypatch):
    """Redirect OUTPUT_DIR to a temp directory and copy fixtures there."""
    import scrape_jobs
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setattr(scrape_jobs, "OUTPUT_DIR", str(output))
    return output
