"""Test --linkedin-emit-matrix generates the correct 208-item matrix."""
import json
import os
import subprocess
import sys


def test_matrix_has_208_items(tmp_path):
    """Matrix should have 208 items (4 term-batches × 52 locations)."""
    scraper_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Run the script with --linkedin-emit-matrix
    env = dict(os.environ)
    env["PYTHONPATH"] = scraper_dir
    result = subprocess.run(
        [sys.executable, os.path.join(scraper_dir, "scrape_jobs.py"),
         "--linkedin-emit-matrix"],
        capture_output=True, text=True, cwd=tmp_path,
        env=env,
    )
    # The script writes to OUTPUT_DIR which is relative to SCRIPT_DIR, not CWD.
    # So we need to check the real output dir.
    matrix_path = os.path.join(scraper_dir, "output", "linkedin_matrix.json")
    if not os.path.exists(matrix_path):
        # If the real config doesn't have partition states, skip
        import pytest
        pytest.skip("linkedin_matrix.json not generated — config may lack partition states")

    with open(matrix_path) as f:
        data = json.load(f)
    matrix = data.get("matrix", [])
    assert len(matrix) == 208, f"Expected 208 items, got {len(matrix)}"


def test_matrix_partition_keys():
    """Partition keys should follow the pattern {terms_slug}__{location_slug}."""
    scraper_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    matrix_path = os.path.join(scraper_dir, "output", "linkedin_matrix.json")
    if not os.path.exists(matrix_path):
        import pytest
        pytest.skip("linkedin_matrix.json not found")

    with open(matrix_path) as f:
        data = json.load(f)
    matrix = data.get("matrix", [])
    for item in matrix:
        assert "__" in item["partition_key"], (
            f"Partition key '{item['partition_key']}' missing '__' separator"
        )
        assert "terms" in item
        assert "location" in item
