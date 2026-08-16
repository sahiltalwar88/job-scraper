"""Test Phase 2 day-slice filtering in _linkedin_search_partition.

The target_date parameter filters jobs to a single calendar date (YYYY-MM-DD).
This is used by Phase 2 workers to split high-volume locations into 1-day slices
that stay under LinkedIn's 1000-card cap.

These tests mock the network fetch so no real LinkedIn calls are made.
"""
from unittest.mock import patch

import scrape_jobs


def _make_card(job_id, date_posted, title="Director of Engineering"):
    """Build a minimal LinkedIn card HTML matching the guest API format.

    The guest API returns datetime="YYYY-MM-DD" (date only, no time component).
    Uses data-entity-urn for the job ID and base-search-card__title for the title.
    """
    return f'''
    <li>
        <div data-entity-urn="urn:li:jobPosting:{job_id}">
            <h3 class="base-search-card__title">{title}</h3>
            <h4 class="base-search-card__subtitle"><a>TestCo</a></h4>
            <span class="job-search-card__location">San Francisco, CA</span>
            <time datetime="{date_posted}">{date_posted}</time>
        </div>
    </li>'''


def _make_page_html(cards):
    """Wrap card snippets into a full LinkedIn search results page."""
    return f'<div class="jobs-search__results-list">{"".join(cards)}</div>'


def test_target_date_filters_to_single_day():
    """target_date should keep only jobs matching that date."""
    cards = [
        _make_card("1001", "2026-08-15"),
        _make_card("1002", "2026-08-15"),
        _make_card("1003", "2026-08-14"),
    ]
    page_html = _make_page_html(cards)

    with patch("scrape_jobs.fetch", return_value=page_html):
        with patch("scrape_jobs.time.sleep"):
            jobs, raw, cap = scrape_jobs._linkedin_search_partition(
                "Director of Engineering", "California, United States",
                lookback_seconds=86400, max_results=10,
                target_date="2026-08-15"
            )

    assert len(jobs) == 2
    assert all(j["date_posted"] == "2026-08-15" for j in jobs)
    assert raw == 3  # all 3 cards were fetched


def test_target_date_filters_out_other_days():
    """target_date should filter out jobs from other days."""
    cards = [
        _make_card("1001", "2026-08-14"),
        _make_card("1002", "2026-08-13"),
        _make_card("1003", "2026-08-12"),
    ]
    page_html = _make_page_html(cards)

    with patch("scrape_jobs.fetch", return_value=page_html):
        with patch("scrape_jobs.time.sleep"):
            jobs, raw, cap = scrape_jobs._linkedin_search_partition(
                "Director of Engineering", "California, United States",
                lookback_seconds=86400, max_results=10,
                target_date="2026-08-15"
            )

    assert len(jobs) == 0  # none match target date
    assert raw == 3  # cards were still fetched


def test_no_target_date_keeps_all_jobs():
    """Without target_date, all jobs should be kept (Phase 1 behavior)."""
    cards = [
        _make_card("1001", "2026-08-15"),
        _make_card("1002", "2026-08-14"),
        _make_card("1003", "2026-08-13"),
    ]
    page_html = _make_page_html(cards)

    with patch("scrape_jobs.fetch", return_value=page_html):
        with patch("scrape_jobs.time.sleep"):
            jobs, raw, cap = scrape_jobs._linkedin_search_partition(
                "Director of Engineering", "California, United States",
                lookback_seconds=604800, max_results=10,
            )

    assert len(jobs) == 3  # all kept, no date filtering


def test_target_date_with_no_matching_jobs():
    """target_date filter with no matching jobs should return empty list."""
    cards = [_make_card("1001", "2026-08-15")]
    page_html = _make_page_html(cards)

    with patch("scrape_jobs.fetch", return_value=page_html):
        with patch("scrape_jobs.time.sleep"):
            jobs, raw, cap = scrape_jobs._linkedin_search_partition(
                "Director of Engineering", "California, United States",
                lookback_seconds=86400, max_results=10,
                target_date="2026-01-01"  # no jobs from January
            )

    assert len(jobs) == 0


def test_target_date_with_mixed_dates():
    """target_date should correctly filter from a mix of dates."""
    cards = [
        _make_card("1001", "2026-08-15"),
        _make_card("1002", "2026-08-14"),
        _make_card("1003", "2026-08-15"),
        _make_card("1004", "2026-08-13"),
        _make_card("1005", "2026-08-15"),
        _make_card("1006", "2026-08-12"),
    ]
    page_html = _make_page_html(cards)

    with patch("scrape_jobs.fetch", return_value=page_html):
        with patch("scrape_jobs.time.sleep"):
            jobs, raw, cap = scrape_jobs._linkedin_search_partition(
                "Director of Engineering", "California, United States",
                lookback_seconds=604800, max_results=10,
                target_date="2026-08-15"
            )

    assert len(jobs) == 3  # 3 jobs from 2026-08-15
    assert all(j["date_posted"] == "2026-08-15" for j in jobs)
    # Verify the right job IDs were kept
    ids = {j["url"].split("/")[-2] for j in jobs}
    assert ids == {"1001", "1003", "1005"}


def test_target_date_empty_string_keeps_all():
    """Empty target_date string should not filter (falsy, like None)."""
    cards = [
        _make_card("1001", "2026-08-15"),
        _make_card("1002", "2026-08-14"),
    ]
    page_html = _make_page_html(cards)

    with patch("scrape_jobs.fetch", return_value=page_html):
        with patch("scrape_jobs.time.sleep"):
            jobs, raw, cap = scrape_jobs._linkedin_search_partition(
                "Director of Engineering", "California, United States",
                lookback_seconds=604800, max_results=10,
                target_date=""
            )

    assert len(jobs) == 2  # all kept, empty string is falsy
