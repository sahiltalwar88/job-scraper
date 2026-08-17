"""Test the FeasibilityChecker ABC and DevinCLIChecker adapter.

Uses unittest.mock to mock subprocess.run — no real Devin CLI calls.
"""
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from scrape_jobs import FeasibilityChecker, DevinCLIChecker


def test_feasibility_checker_is_abstract():
    """FeasibilityChecker cannot be instantiated directly."""
    with pytest.raises(TypeError):
        FeasibilityChecker()  # type: ignore[abstract]


def test_devin_cli_checker_is_subclass():
    assert issubclass(DevinCLIChecker, FeasibilityChecker)


def test_batch_size_is_10():
    assert DevinCLIChecker.BATCH_SIZE == 10


def test_check_batch_parses_yes_no():
    """Valid PREFERRED/YES/NO responses should be parsed correctly."""
    jobs = [
        {"url": "https://linkedin.com/jobs/view/1/", "title": "Director of Engineering",
         "company": "A", "location": "SF"},
        {"url": "https://linkedin.com/jobs/view/2/", "title": "Director of Sales",
         "company": "B", "location": "NYC"},
        {"url": "https://linkedin.com/jobs/view/3/", "title": "VP of Engineering",
         "company": "C", "location": "LA"},
    ]
    mock_result = MagicMock(stdout="1. YES\n2. NO\n3. PREFERRED\n", returncode=0)
    with patch("scrape_jobs.subprocess.run", return_value=mock_result):
        checker = DevinCLIChecker()
        verdicts = checker.check_batch(jobs)
    assert verdicts == {
        "https://linkedin.com/jobs/view/1/": "YES",
        "https://linkedin.com/jobs/view/2/": "NO",
        "https://linkedin.com/jobs/view/3/": "PREFERRED",
    }


def test_check_batch_malformed_output():
    """Malformed output should return empty dict (safe default)."""
    jobs = [{"url": "https://linkedin.com/jobs/view/1/", "title": "T",
             "company": "C", "location": "L"}]
    mock_result = MagicMock(stdout="This is not a valid response", returncode=0)
    with patch("scrape_jobs.subprocess.run", return_value=mock_result):
        checker = DevinCLIChecker()
        verdicts = checker.check_batch(jobs)
    assert verdicts == {}


def test_check_batch_empty_output():
    """Empty stdout should return empty dict."""
    jobs = [{"url": "https://linkedin.com/jobs/view/1/", "title": "T",
             "company": "C", "location": "L"}]
    mock_result = MagicMock(stdout="", returncode=0)
    with patch("scrape_jobs.subprocess.run", return_value=mock_result):
        checker = DevinCLIChecker()
        verdicts = checker.check_batch(jobs)
    assert verdicts == {}


def test_check_batch_tolerant_of_extra_whitespace():
    """Parser should handle extra whitespace and blank lines."""
    jobs = [
        {"url": "https://linkedin.com/jobs/view/1/", "title": "T",
         "company": "C", "location": "L"},
    ]
    mock_result = MagicMock(stdout="\n\n  1.   YES  \n\n", returncode=0)
    with patch("scrape_jobs.subprocess.run", return_value=mock_result):
        checker = DevinCLIChecker()
        verdicts = checker.check_batch(jobs)
    assert verdicts == {"https://linkedin.com/jobs/view/1/": "YES"}


def test_check_batch_timeout():
    """subprocess.TimeoutExpired should propagate (caller handles safe default)."""
    jobs = [{"url": "https://linkedin.com/jobs/view/1/", "title": "T",
             "company": "C", "location": "L"}]
    with patch("scrape_jobs.subprocess.run",
               side_effect=subprocess.TimeoutExpired("devin", 60)):
        checker = DevinCLIChecker()
        with pytest.raises(subprocess.TimeoutExpired):
            checker.check_batch(jobs)


def test_check_batch_empty_jobs():
    """Empty job list should return {} without calling subprocess."""
    checker = DevinCLIChecker()
    with patch("scrape_jobs.subprocess.run") as mock_run:
        verdicts = checker.check_batch([])
        assert verdicts == {}
        mock_run.assert_not_called()


def test_check_batch_case_insensitive():
    """YES/NO should be case-insensitive."""
    jobs = [
        {"url": "https://linkedin.com/jobs/view/1/", "title": "T",
         "company": "C", "location": "L"},
        {"url": "https://linkedin.com/jobs/view/2/", "title": "T",
         "company": "C", "location": "L"},
    ]
    mock_result = MagicMock(stdout="1. yes\n2. No\n", returncode=0)
    with patch("scrape_jobs.subprocess.run", return_value=mock_result):
        checker = DevinCLIChecker()
        verdicts = checker.check_batch(jobs)
    assert verdicts == {
        "https://linkedin.com/jobs/view/1/": "YES",
        "https://linkedin.com/jobs/view/2/": "NO",
    }
