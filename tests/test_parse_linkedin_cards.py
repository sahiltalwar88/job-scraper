"""Test _parse_linkedin_cards with real LinkedIn HTML.

Uses ca_raw_5pages.html (50 real cards from California) saved from a
previous scraping session.
"""
from scrape_jobs import _parse_linkedin_cards, is_leadership_role


def test_parses_50_raw_cards(ca_raw_html):
    """Real HTML should contain 50 raw cards."""
    jobs, raw_count = _parse_linkedin_cards(ca_raw_html)
    assert raw_count == 50


def test_parsed_jobs_have_required_fields(ca_raw_html):
    """Each parsed job must have id, company, title, location, date_posted."""
    jobs, _ = _parse_linkedin_cards(ca_raw_html)
    assert len(jobs) > 0
    for job in jobs:
        assert "id" in job
        assert "company" in job
        assert "title" in job
        assert "location" in job
        assert "date_posted" in job


def test_parsed_jobs_pass_leadership_filter(ca_raw_html):
    """Every parsed job title should pass is_leadership_role (that's the filter)."""
    jobs, _ = _parse_linkedin_cards(ca_raw_html)
    for job in jobs:
        assert is_leadership_role(job["title"], job["company"]), (
            f'"{job["title"]}" @ {job["company"]} passed _parse_linkedin_cards '
            f'but failed is_leadership_role — filter mismatch'
        )


def test_company_parsed_before_filter(ca_raw_html):
    """Company must be available to is_leadership_role at filter time."""
    jobs, _ = _parse_linkedin_cards(ca_raw_html)
    # If company wasn't parsed before the filter, priority-company matches
    # would fail. Verify at least one job has a non-Unknown company.
    companies = [j["company"] for j in jobs]
    assert any(c != "Unknown" for c in companies), (
        "All companies are 'Unknown' — company may not be parsed before filter"
    )


def test_empty_html():
    """Empty HTML should return ([], 0)."""
    jobs, raw_count = _parse_linkedin_cards("")
    assert jobs == []
    assert raw_count == 0


def test_no_matching_titles():
    """HTML with no leadership titles should return ([], raw_count)."""
    html = """
    <li>
      <div class="base-card" data-entity-urn="urn:li:jobPosting:123">
        <a class="base-card__full-link" href="/jobs/view/123/">
          <span class="sr-only">Software Engineer at TechCorp</span>
        </a>
        <h3 class="base-search-card__title">Software Engineer</h3>
        <h4 class="base-search-card__subtitle">
          <a>TechCorp</a>
        </h4>
        <span class="job-search-card__location">San Francisco, CA</span>
        <time datetime="2026-08-14"></time>
      </div>
    </li>
    """
    jobs, raw_count = _parse_linkedin_cards(html)
    assert raw_count == 1
    assert jobs == []  # "Software Engineer" doesn't pass is_leadership_role
