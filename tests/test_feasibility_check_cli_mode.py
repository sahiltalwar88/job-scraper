"""Test the --feasibility-check CLI mode via run_feasibility_check().

Uses a mock checker — no real Devin CLI calls.
"""
import json
from unittest.mock import MagicMock

from scrape_jobs import run_feasibility_check, FeasibilityChecker


class MockChecker(FeasibilityChecker):
    """Deterministic mock checker for testing."""
    BATCH_SIZE = 10

    def __init__(self, verdicts=None):
        self._verdicts = verdicts or {}
        self.call_count = 0

    def check_batch(self, jobs):
        self.call_count += 1
        return {j["url"]: self._verdicts.get(j["url"], "yes") for j in jobs}


def test_tags_all_unchecked_jobs(tmp_output_dir, sample_all_jobs):
    """All jobs without a `feasible` field should get tagged."""
    path = tmp_output_dir / "all_jobs.json"
    path.write_text(json.dumps(sample_all_jobs, separators=(",", ":")))

    checker = MockChecker(verdicts={
        "https://www.linkedin.com/jobs/view/4400000005/": "preferred",
        "https://www.linkedin.com/jobs/view/4400000006/": "no",
        "https://www.linkedin.com/jobs/view/4400000007/": "yes",
        "https://www.linkedin.com/jobs/view/4400000010/": "no",
    })
    run_feasibility_check(checker)

    data = json.loads(path.read_text())
    for job in data["jobs"]:
        assert "feasible" in job, f"Job {job['url']} missing feasible field"
        assert "feasibility" in job, f"Job {job['url']} missing feasibility field"


def test_does_not_recheck_tagged_jobs(tmp_output_dir, sample_all_jobs):
    """Jobs with existing `feasible` field should NOT be rechecked."""
    path = tmp_output_dir / "all_jobs.json"
    path.write_text(json.dumps(sample_all_jobs, separators=(",", ":")))

    checker = MockChecker()
    run_feasibility_check(checker)

    # 9 jobs have feasible field, only 1 doesn't (the last one)
    # So only 1 batch should be called
    assert checker.call_count == 1


def test_safe_default_on_empty_verdicts(tmp_output_dir, sample_all_jobs):
    """If checker returns empty dict, jobs default to feasible: True, feasibility: yes."""
    path = tmp_output_dir / "all_jobs.json"
    # Remove all feasible fields so all jobs are unchecked
    sample = json.loads(json.dumps(sample_all_jobs))
    for job in sample["jobs"]:
        job.pop("feasible", None)
        job.pop("feasibility", None)
    path.write_text(json.dumps(sample, separators=(",", ":")))

    checker = MockChecker(verdicts={})  # empty → all default to "yes"
    run_feasibility_check(checker)

    data = json.loads(path.read_text())
    for job in data["jobs"]:
        assert job.get("feasible") is True
        assert job.get("feasibility") == "yes"


def test_tripartite_verdicts_set_correct_fields(tmp_output_dir, sample_all_jobs):
    """PREFERRED/YES/NO verdicts should set feasible + feasibility correctly."""
    path = tmp_output_dir / "all_jobs.json"
    # Remove all feasible fields so all jobs are unchecked
    sample = json.loads(json.dumps(sample_all_jobs))
    for job in sample["jobs"]:
        job.pop("feasible", None)
        job.pop("feasibility", None)
    path.write_text(json.dumps(sample, separators=(",", ":")))

    checker = MockChecker(verdicts={
        "https://www.linkedin.com/jobs/view/4400000001/": "preferred",
        "https://www.linkedin.com/jobs/view/4400000002/": "yes",
        "https://www.linkedin.com/jobs/view/4400000008/": "no",
    })
    run_feasibility_check(checker)

    data = json.loads(path.read_text())
    by_url = {j["url"]: j for j in data["jobs"]}

    # preferred → feasible=True, feasibility="preferred"
    assert by_url["https://www.linkedin.com/jobs/view/4400000001/"]["feasible"] is True
    assert by_url["https://www.linkedin.com/jobs/view/4400000001/"]["feasibility"] == "preferred"

    # yes → feasible=True, feasibility="yes"
    assert by_url["https://www.linkedin.com/jobs/view/4400000002/"]["feasible"] is True
    assert by_url["https://www.linkedin.com/jobs/view/4400000002/"]["feasibility"] == "yes"

    # no → feasible=False, feasibility="no"
    assert by_url["https://www.linkedin.com/jobs/view/4400000008/"]["feasible"] is False
    assert by_url["https://www.linkedin.com/jobs/view/4400000008/"]["feasibility"] == "no"


def test_boolean_verdict_backward_compat(tmp_output_dir, sample_all_jobs):
    """Boolean verdicts (True/False) should still work, normalized to yes/no."""
    path = tmp_output_dir / "all_jobs.json"
    sample = json.loads(json.dumps(sample_all_jobs))
    for job in sample["jobs"]:
        job.pop("feasible", None)
        job.pop("feasibility", None)
    path.write_text(json.dumps(sample, separators=(",", ":")))

    class BoolChecker(FeasibilityChecker):
        BATCH_SIZE = 10
        def __init__(self):
            self.call_count = 0
        def check_batch(self, jobs):
            self.call_count += 1
            return {j["url"]: True for j in jobs}  # boolean True

    run_feasibility_check(BoolChecker())
    data = json.loads(path.read_text())
    for job in data["jobs"]:
        assert job.get("feasible") is True
        assert job.get("feasibility") == "yes"  # True → "yes"


def test_idempotent_second_run(tmp_output_dir, sample_all_jobs):
    """Running twice should not recheck any jobs on the second run."""
    path = tmp_output_dir / "all_jobs.json"
    path.write_text(json.dumps(sample_all_jobs, separators=(",", ":")))

    checker = MockChecker()
    run_feasibility_check(checker)
    first_calls = checker.call_count

    run_feasibility_check(checker)
    assert checker.call_count == first_calls  # no new calls


def test_zero_pending_jobs(tmp_output_dir, sample_all_jobs):
    """All jobs already checked → should not call checker."""
    path = tmp_output_dir / "all_jobs.json"
    # Add feasible to all jobs
    sample = json.loads(json.dumps(sample_all_jobs))
    for job in sample["jobs"]:
        job["feasible"] = True
    path.write_text(json.dumps(sample, separators=(",", ":")))

    checker = MockChecker()
    run_feasibility_check(checker)
    assert checker.call_count == 0


def test_preserves_other_fields(tmp_output_dir, sample_all_jobs):
    """Existing fields (description, salary, etc.) should be preserved."""
    path = tmp_output_dir / "all_jobs.json"
    path.write_text(json.dumps(sample_all_jobs, separators=(",", ":")))

    checker = MockChecker()
    run_feasibility_check(checker)

    data = json.loads(path.read_text())
    for job in data["jobs"]:
        assert "title" in job
        assert "company" in job
        assert "url" in job
        assert "location" in job


def test_feasibility_limit_caps_batch(tmp_output_dir, sample_all_jobs):
    """--feasibility-limit should cap the number of jobs checked."""
    path = tmp_output_dir / "all_jobs.json"
    # Remove all feasible fields so all 10 jobs are unchecked
    sample = json.loads(json.dumps(sample_all_jobs))
    for job in sample["jobs"]:
        job.pop("feasible", None)
        job.pop("feasibility", None)
    path.write_text(json.dumps(sample, separators=(",", ":")))

    checker = MockChecker()
    run_feasibility_check(checker, limit=3)

    data = json.loads(path.read_text())
    tagged = [j for j in data["jobs"] if "feasible" in j]
    untagged = [j for j in data["jobs"] if "feasible" not in j]
    assert len(tagged) == 3, f"Expected 3 tagged, got {len(tagged)}"
    assert len(untagged) == 7, f"Expected 7 untagged, got {len(untagged)}"


def test_feasibility_limit_zero_means_all(tmp_output_dir, sample_all_jobs):
    """limit=0 should check all unchecked jobs (no limit)."""
    path = tmp_output_dir / "all_jobs.json"
    sample = json.loads(json.dumps(sample_all_jobs))
    for job in sample["jobs"]:
        job.pop("feasible", None)
        job.pop("feasibility", None)
    path.write_text(json.dumps(sample, separators=(",", ":")))

    checker = MockChecker()
    run_feasibility_check(checker, limit=0)

    data = json.loads(path.read_text())
    tagged = [j for j in data["jobs"] if "feasible" in j]
    assert len(tagged) == 10, f"Expected all 10 tagged, got {len(tagged)}"
