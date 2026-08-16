"""Test --linkedin-emit-matrix generates correct matrices for both phases.

Phase 1: low-volume locations, 7-day lookback (172 workers).
Phase 2: high-volume locations, 1-day slices (252 workers).
Both must be under GitHub's 256 matrix limit.
"""
import json
import os
import subprocess
import sys

import pytest

SCRAPER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_emit_matrix(phase):
    """Run --linkedin-emit-matrix with the given phase and return the matrix."""
    result = subprocess.run(
        [sys.executable, os.path.join(SCRAPER_DIR, "scrape_jobs.py"),
         "--linkedin-emit-matrix", "--phase", phase],
        capture_output=True, text=True, cwd=SCRAPER_DIR,
    )
    assert result.returncode == 0, f"emit-matrix failed: {result.stderr}"
    matrix_path = os.path.join(SCRAPER_DIR, "output", "linkedin_matrix.json")
    with open(matrix_path) as f:
        data = json.load(f)
    return data["matrix"]


def test_phase1_matrix_under_256():
    """Phase 1 matrix must be under GitHub's 256 limit."""
    matrix = _run_emit_matrix("low")
    assert len(matrix) <= 256, f"Phase 1 has {len(matrix)} items, exceeds 256"
    assert len(matrix) > 0


def test_phase1_matrix_has_expected_size():
    """Phase 1: 4 term-batches × 43 low-volume locations = 172."""
    matrix = _run_emit_matrix("low")
    assert len(matrix) == 172, f"Expected 172, got {len(matrix)}"


def test_phase1_no_high_volume_locations():
    """Phase 1 should NOT include high-volume locations."""
    matrix = _run_emit_matrix("low")
    high_vol_names = {"California", "Texas", "New York", "Washington",
                      "Virginia", "Massachusetts", "Illinois"}
    for item in matrix:
        loc = item["location"].split(",")[0]
        assert loc not in high_vol_names, (
            f"Phase 1 includes high-volume location: {item['location']}"
        )


def test_phase1_no_time_slice_fields():
    """Phase 1 items should NOT have lookback_seconds or target_date."""
    matrix = _run_emit_matrix("low")
    for item in matrix:
        assert "lookback_seconds" not in item
        assert "target_date" not in item


def test_phase2_matrix_under_256():
    """Phase 2 matrix must be under GitHub's 256 limit."""
    matrix = _run_emit_matrix("high")
    assert len(matrix) <= 256, f"Phase 2 has {len(matrix)} items, exceeds 256"
    assert len(matrix) > 0


def test_phase2_matrix_has_expected_size():
    """Phase 2: 4 term-batches × 9 high-volume locations × 7 days = 252."""
    matrix = _run_emit_matrix("high")
    assert len(matrix) == 252, f"Expected 252, got {len(matrix)}"


def test_phase2_has_time_slice_fields():
    """Phase 2 items should have lookback_seconds and target_date."""
    matrix = _run_emit_matrix("high")
    for item in matrix:
        assert "lookback_seconds" in item, (
            f"Phase 2 item missing lookback_seconds: {item['partition_key']}"
        )
        assert "target_date" in item, (
            f"Phase 2 item missing target_date: {item['partition_key']}"
        )


def test_phase2_cumulative_lookback():
    """Day N should have lookback_seconds = (N+1) * 86400."""
    matrix = _run_emit_matrix("high")
    for item in matrix:
        key = item["partition_key"]
        day = int(key.split("_d")[-1])
        expected_lookback = (day + 1) * 24 * 3600
        assert item["lookback_seconds"] == expected_lookback, (
            f"Day {day} has lookback {item['lookback_seconds']}, "
            f"expected {expected_lookback}"
        )


def test_phase2_target_dates_are_recent():
    """Target dates should be within the last 7 days (allowing for timezone drift)."""
    from datetime import datetime, timedelta
    matrix = _run_emit_matrix("high")
    now = datetime.now()
    for item in matrix:
        target = datetime.strptime(item["target_date"], "%Y-%m-%d")
        delta = (now - target).days
        # Allow -1 to 7 to handle UTC midnight boundary (target_date may be "today"
        # in UTC but "tomorrow" in local time, or vice versa)
        assert -1 <= delta <= 7, (
            f"Target date {item['target_date']} is {delta} days ago, expected -1 to 7"
        )


def test_phase2_only_high_volume_locations():
    """Phase 2 should ONLY include high-volume locations."""
    matrix = _run_emit_matrix("high")
    high_vol_locs = {
        "California, United States", "Texas, United States",
        "New York, United States", "Washington, United States",
        "Virginia, United States", "Massachusetts, United States",
        "Illinois, United States", "United States", "Remote",
    }
    for item in matrix:
        assert item["location"] in high_vol_locs, (
            f"Phase 2 includes non-high-volume location: {item['location']}"
        )


def test_phase2_partition_keys_include_day_suffix():
    """Phase 2 partition keys should include _d{day} suffix."""
    matrix = _run_emit_matrix("high")
    for item in matrix:
        assert "_d" in item["partition_key"], (
            f"Partition key missing day suffix: {item['partition_key']}"
        )
        day = item["partition_key"].split("_d")[-1]
        assert day.isdigit(), f"Day suffix is not numeric: {day}"
        assert 0 <= int(day) <= 6


def test_both_phases_fit_in_github_limit():
    """Both phases individually must be under 256."""
    p1 = _run_emit_matrix("low")
    p2 = _run_emit_matrix("high")
    assert len(p1) <= 256
    assert len(p2) <= 256
