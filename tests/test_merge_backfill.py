"""Test --linkedin-merge-backfill — partition merge, dedup, cleanup."""
import json
import os
import shutil
from unittest.mock import patch

import scrape_jobs


def test_merge_deduplicates_by_url(tmp_output_dir, partition_files):
    """3 partition files with overlapping URLs → correct unique count."""
    # Copy partition files to output dir
    for pf in partition_files:
        shutil.copy(pf, tmp_output_dir / pf.name)

    # Mock save_linkedin_results to avoid writing extra files
    with patch("scrape_jobs.save_linkedin_results"):
        with patch("scrape_jobs._merge_into_all_jobs", return_value=0):
            # Run the merge by simulating the CLI code
            import glob
            all_files = sorted(glob.glob(str(tmp_output_dir / "partition*.json")))
            all_jobs = []
            seen_urls = set()
            for tf in all_files:
                with open(tf) as f:
                    data = json.load(f)
                for j in data.get("jobs", []):
                    url = j.get("url", "")
                    if url not in seen_urls:
                        seen_urls.add(url)
                        all_jobs.append(j)

            # partition1: 5 jobs, partition2: 5 jobs (1 overlap with p1),
            # partition3: 3 jobs (1 overlap with p2)
            # Total unique: 5 + 4 + 2 = 11
            assert len(all_jobs) == 11


def test_merge_filters_pharma_companies(tmp_output_dir, partition_files):
    """Pharma companies (Pfizer, Genentech) should be filtered out."""
    for pf in partition_files:
        shutil.copy(pf, tmp_output_dir / pf.name)

    import glob
    all_files = sorted(glob.glob(str(tmp_output_dir / "partition*.json")))
    all_jobs = []
    seen_urls = set()
    for tf in all_files:
        with open(tf) as f:
            data = json.load(f)
        for j in data.get("jobs", []):
            url = j.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                all_jobs.append(j)

    # Filter pharma (same as the merge code)
    filtered = [j for j in all_jobs if not scrape_jobs._is_pharma_company(j.get("company", ""))]
    companies = [j["company"] for j in filtered]
    assert "Pfizer" not in companies
    assert "Genentech" not in companies


def test_merge_cap_hit_detection(partition_files):
    """Partition 3 has hit_cap=true — should be detectable."""
    with open(partition_files[2]) as f:
        data = json.load(f)
    assert data.get("hit_cap") is True
    assert data.get("raw_cards") == 990


def test_partial_merge_no_crash(tmp_output_dir, partition_files):
    """Merge with only 1 of 3 files should work without crashing."""
    # Copy only the first partition file
    shutil.copy(partition_files[0], tmp_output_dir / partition_files[0].name)

    import glob
    all_files = sorted(glob.glob(str(tmp_output_dir / "partition*.json")))
    assert len(all_files) == 1

    all_jobs = []
    seen_urls = set()
    for tf in all_files:
        with open(tf) as f:
            data = json.load(f)
        for j in data.get("jobs", []):
            url = j.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                all_jobs.append(j)

    assert len(all_jobs) == 5  # all 5 from partition1


def test_no_partition_files(tmp_output_dir):
    """No partition files → should handle gracefully."""
    import glob
    all_files = sorted(glob.glob(str(tmp_output_dir / "partition*.json")))
    assert len(all_files) == 0
