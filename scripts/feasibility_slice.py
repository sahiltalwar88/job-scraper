#!/usr/bin/env python3
"""Run feasibility check on a slice of unchecked jobs.

Writes verdicts to a separate file (output/feasibility_slice_N.json) to avoid
race conditions when running multiple slices in parallel. Merge with
merge_feasibility_slices.py after all slices complete.

Usage:
    python3 scripts/feasibility_slice.py --slice 0 --total-slices 3
    python3 scripts/feasibility_slice.py --slice 1 --total-slices 3 --limit 10

Environment variables:
    JOB_SCRAPER_DIR  — path to the scraper repo (default: ~/dev/job-scraper)
    ALL_JOBS_PATH    — path to all_jobs.json (default: $JOB_SCRAPER_DIR/output/all_jobs.json)
"""
import json
import os
import sys
import time

SCRAPER_DIR = os.environ.get("JOB_SCRAPER_DIR", os.path.expanduser("~/dev/job-scraper"))
ALL_JOBS = os.environ.get("ALL_JOBS_PATH", os.path.join(SCRAPER_DIR, "output", "all_jobs.json"))

sys.path.insert(0, SCRAPER_DIR)
from scrape_jobs import DevinCLIChecker, _FEASIBILITY_PROMPT


def run_slice(slice_num: int, total_slices: int, limit: int = 0):
    """Process a slice of unchecked jobs and write verdicts to a separate file."""
    with open(ALL_JOBS, encoding="utf-8") as f:
        data = json.load(f)
    jobs = data.get("jobs", [])
    unchecked = [j for j in jobs if "feasible" not in j]

    # Split unchecked jobs into slices by index
    # Slice N gets indices N, N+total_slices, N+2*total_slices, ...
    my_jobs = unchecked[slice_num::total_slices]

    if limit > 0:
        my_jobs = my_jobs[:limit]

    print(f"🔍 Slice {slice_num}/{total_slices}: {len(my_jobs)} jobs to check "
          f"(of {len(unchecked)} total unchecked)")
    if not my_jobs:
        print("  No jobs in this slice.")
        return

    checker = DevinCLIChecker()
    batch_size = checker.BATCH_SIZE
    verdicts = {}
    checked = 0
    errors = 0

    for i in range(0, len(my_jobs), batch_size):
        batch = my_jobs[i:i + batch_size]
        try:
            batch_verdicts = checker.check_batch(batch)
            if not batch_verdicts:
                # Empty verdicts = batch failed, mark as error
                for job in batch:
                    url = job.get("url", "")
                    verdicts[url] = {"feasibility": "yes", "feasible": True, "feasibility_error": True}
                    errors += 1
            else:
                for url, verdict in batch_verdicts.items():
                    tier = verdict.lower() if isinstance(verdict, str) else ("yes" if verdict else "no")
                    verdicts[url] = {
                        "feasibility": tier,
                        "feasible": tier != "no",
                        "feasibility_error": False,
                    }
        except Exception as e:
            print(f"  ⚠️  Batch {i//batch_size + 1} failed: {e}")
            for job in batch:
                url = job.get("url", "")
                verdicts[url] = {"feasibility": "yes", "feasible": True, "feasibility_error": True}
                errors += 1

        checked += len(batch)
        preferred = sum(1 for v in verdicts.values() if v["feasibility"] == "preferred")
        yes = sum(1 for v in verdicts.values() if v["feasibility"] == "yes" and not v.get("feasibility_error"))
        no = sum(1 for v in verdicts.values() if v["feasibility"] == "no")
        print(f"  📊 Checked {checked}/{len(my_jobs)} "
              f"({preferred} preferred, {yes} yes, {no} no, {errors} error)")

    # Write verdicts to a separate file
    output_path = os.path.join(os.path.dirname(ALL_JOBS), f"feasibility_slice_{slice_num}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(verdicts, f, separators=(",", ":"), ensure_ascii=False)

    preferred = sum(1 for v in verdicts.values() if v["feasibility"] == "preferred")
    yes = sum(1 for v in verdicts.values() if v["feasibility"] == "yes" and not v.get("feasibility_error"))
    no = sum(1 for v in verdicts.values() if v["feasibility"] == "no")
    print(f"\n✅ Slice {slice_num} done: {preferred} preferred, {yes} yes, {no} no, {errors} error")
    print(f"📄 Wrote {len(verdicts)} verdicts to {output_path}")


def main():
    slice_num = 0
    total_slices = 1
    limit = 0

    if "--slice" in sys.argv:
        idx = sys.argv.index("--slice")
        slice_num = int(sys.argv[idx + 1])
    if "--total-slices" in sys.argv:
        idx = sys.argv.index("--total-slices")
        total_slices = int(sys.argv[idx + 1])
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        limit = int(sys.argv[idx + 1])

    run_slice(slice_num, total_slices, limit)


if __name__ == "__main__":
    main()
