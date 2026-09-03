"""Test backward compatibility of the shipped config.example.json defaults.

With only config.example.json (no personal config.json), the scraper must
honor the contract documented in config.example.json. These tests verify
that the shipped defaults don't accidentally drift:

- The fuzzy pre-filter is enabled (the fork ships non-empty fuzzy_seniority
  and fuzzy_domain lists in config.example.json).
- LinkedIn partition states are NOT enabled by default (empty list).
- role_is_relevant() uses the fuzzy matcher when fuzzy is enabled.

On CI (no config.json) these always run. On developer machines with a
personal config.json that may override these defaults, these tests are
skipped.

Fork note: upstream's config.example.json has EMPTY fuzzy lists (fuzzy
disabled). The fork's config.example.json ships populated fuzzy lists
(toxicology/domain-focused), so fuzzy IS enabled by default here. This
test verifies the fork's contract, not upstream's.
"""
import os

import pytest

import scrape_jobs


def _has_personal_config():
    """True if a personal config.json exists (overriding example defaults)."""
    return os.path.exists("config.json")


@pytest.mark.skipif(_has_personal_config(),
                    reason="Personal config.json present — example config defaults not active")
def test_fuzzy_enabled_with_example_config():
    """Fuzzy pre-filter should be enabled with the fork's config.example.json.

    The fork ships non-empty fuzzy_seniority and fuzzy_domain lists, so
    _FUZZY_ENABLED must be True. This catches regressions where the fuzzy
    lists are accidentally emptied.
    """
    assert scrape_jobs._FUZZY_ENABLED is True, (
        "Fuzzy filter should be enabled with the fork's config.example.json "
        "(non-empty fuzzy_seniority/fuzzy_domain)"
    )


@pytest.mark.skipif(_has_personal_config(),
                    reason="Personal config.json present — example config defaults not active")
def test_no_partition_states_with_example_config():
    """LinkedIn partition states should be empty with config.example.json."""
    assert scrape_jobs.LINKEDIN_PARTITION_STATES == [], (
        "Partition states should be empty with config.example.json"
    )


@pytest.mark.skipif(_has_personal_config(),
                    reason="Personal config.json present — example config defaults not active")
def test_role_is_relevant_uses_fuzzy_matching():
    """role_is_relevant() should use fuzzy matching when fuzzy is enabled.

    With fuzzy enabled (the fork's default), a title matching both a
    seniority term and a domain term should be relevant. A title matching
    neither should not be relevant.
    """
    # A title matching both fuzzy seniority ("director") and fuzzy domain
    # ("environmental") should be relevant. Note: fuzzy domain terms use
    # word-boundary regex, so "toxicolog" matches "Toxicolog" but NOT
    # "Toxicology" (the trailing "y" breaks the \b boundary). Use a title
    # where the domain term appears as a whole word.
    assert scrape_jobs.role_is_relevant("Director of Environmental Science") is True
    # A generic title matching neither fuzzy list should not be relevant.
    assert scrape_jobs.role_is_relevant("Accountant") is False
    # Empty title is never relevant.
    assert scrape_jobs.role_is_relevant("") is False
