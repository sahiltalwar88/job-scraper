"""Config-dependent location filter tests.

These tests rely on the user's specific config.json having "united states"
and state abbreviations (e.g. ", tx") in location_filter.terms. They are
excluded from CI (which runs against config.example.json) and only run
locally where the real config.json is present.

Run locally with:
    pytest tests/local/ -v
"""
from scrape_jobs import is_target_location


def test_state_abbreviation():
    """State abbreviations should also be accepted."""
    assert is_target_location("Austin, TX") is True
    assert is_target_location("San Francisco, CA") is True
    assert is_target_location("New York, NY") is True


def test_united_states():
    assert is_target_location("United States") is True
