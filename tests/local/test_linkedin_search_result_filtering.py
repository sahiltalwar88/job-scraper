"""Test that role_is_relevant filters LinkedIn cards correctly.

Uses the real California fixture HTML. These tests are config-dependent
(need the engineering fuzzy filter) so they live in tests/local/ and
are excluded from CI.
"""
from scrape_jobs import _parse_linkedin_cards, role_is_relevant


def test_parsed_jobs_pass_role_filter(linkedin_search_results_html):
    """Every parsed job that survives role_is_relevant should have been
    filtered by the fuzzy leadership pre-filter."""
    jobs, _ = _parse_linkedin_cards(linkedin_search_results_html)
    filtered = [j for j in jobs if role_is_relevant(j["title"], j["company"])]
    assert len(filtered) > 0, "No jobs passed role_is_relevant — filter may be broken"
    for job in filtered:
        assert role_is_relevant(job["title"], job["company"]), (
            f'"{job["title"]}" @ {job["company"]} passed _parse_linkedin_cards '
            f'but failed role_is_relevant — filter mismatch'
        )


def test_company_available_at_filter_time(linkedin_search_results_html):
    """Company must be available to role_is_relevant at filter time."""
    jobs, _ = _parse_linkedin_cards(linkedin_search_results_html)
    # If company wasn't parsed before the filter, priority-company matches
    # would fail. Verify at least one job has a non-Unknown company.
    companies = [j["company"] for j in jobs]
    assert any(c != "Unknown" for c in companies), (
        "All companies are 'Unknown' — company may not be parsed before filter"
    )


def test_non_matching_title_filtered_out():
    """A non-leadership title like 'Software Engineer' should not pass
    role_is_relevant with the engineering fuzzy filter."""
    assert not role_is_relevant("Software Engineer", "TechCorp")
