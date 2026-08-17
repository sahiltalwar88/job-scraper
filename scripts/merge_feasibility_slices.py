#!/usr/bin/env python3
"""Merge feasibility slice files back into all_jobs.json.

Reads output/feasibility_slice_*.json files and applies the verdicts to
all_jobs.json. Safe to run after all slice scripts have completed.

Usage:
    python3 scripts/merge_feasibility_slices.py

Environment variables:
    ALL_JOBS_PATH — path to all_jobs.json (default: ~/dev/job-scraper/output/all_jobs.json)
"""
import glob
import json
import os
import sys

ALL_JOBS = os.environ.get("ALL_JOBS_PATH",
                          os.path.join(os.path.expanduser("~/dev/job-scraper"), "output", "all_jobs.json"))


def merge_slices():
    output_dir = os.path.dirname(ALL_JOBS)
    slice_files = sorted(glob.glob(os.path.join(output_dir, "feasibility_slice_*.json")))

    if not slice_files:
        print("No slice files found.")
        return

    print(f"Found {len(slice_files)} slice files:")
    for f in slice_files:
        print(f"  {f}")

    # Load all verdicts
    all_verdicts = {}
    for sf in slice_files:
        with open(sf, encoding="utf-8") as f:
            verdicts = json.load(f)
        all_verdicts.update(verdicts)
    print(f"\nTotal verdicts to merge: {len(all_verdicts)}")

    # Load all_jobs.json and apply verdicts
    with open(ALL_JOBS, encoding="utf-8") as f:
        data = json.load(f)
    jobs = data.get("jobs", [])

    applied = 0
    for job in jobs:
        url = job.get("url", "")
        if url in all_verdicts:
            v = all_verdicts[url]
            job["feasible"] = v["feasible"]
            job["feasibility"] = v["feasibility"]
            if v.get("feasibility_error"):
                job["feasibility_error"] = True
            applied += 1

    # Write back
    with open(ALL_JOBS, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)

    # Summary
    from collections import Counter
    tiers = Counter(j.get("feasibility") for j in jobs if "feasibility" in j)
    errors = sum(1 for j in jobs if j.get("feasibility_error"))
    unchecked = sum(1 for j in jobs if "feasible" not in j)
    print(f"\n✅ Applied {applied} verdicts to all_jobs.json")
    print(f"✅ Tiers: {dict(tiers)}")
    print(f"✅ Errors: {errors}")
    print(f"✅ Remaining unchecked: {unchecked}")

    # Clean up slice files
    for sf in slice_files:
        os.remove(sf)
        print(f"  🗑️  Removed {sf}")


if __name__ == "__main__":
    merge_slices()
