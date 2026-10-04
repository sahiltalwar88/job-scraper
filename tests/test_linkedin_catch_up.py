"""The LinkedIn watcher looks back to its last recorded run, not a fixed hour.

GitHub starts scheduled runs late or not at all; with a fixed one-hour window,
everything posted between runs was missed.
"""
import json
from datetime import datetime, timedelta, timezone

from scrape_jobs import _linkedin_catch_up_seconds

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def record(output_dir, *runs):
    lines = [json.dumps({"workflow": wf, "timestamp": (NOW - ago).strftime("%Y-%m-%dT%H:%M:%SZ")})
             for wf, ago in runs]
    (output_dir / "workflow_runs.jsonl").write_text("\n".join(lines) + "\n")


def test_covers_the_gap_since_the_last_run_with_some_overlap(tmp_output_dir):
    record(tmp_output_dir, ("linkedin", timedelta(hours=9)), ("linkedin", timedelta(hours=5)))

    assert _linkedin_catch_up_seconds(NOW) == 5 * 3600 + 600


def test_a_parallel_backfill_counts_as_a_run(tmp_output_dir):
    record(tmp_output_dir, ("linkedin", timedelta(hours=9)),
           ("linkedin-backfill-2phase", timedelta(hours=2)))

    assert _linkedin_catch_up_seconds(NOW) == 2 * 3600 + 600


def test_other_boards_runs_do_not_count(tmp_output_dir):
    record(tmp_output_dir, ("linkedin", timedelta(hours=6)), ("indeed", timedelta(minutes=5)))

    assert _linkedin_catch_up_seconds(NOW) == 6 * 3600 + 600


def test_never_less_than_an_hour_or_more_than_a_day(tmp_output_dir):
    record(tmp_output_dir, ("linkedin", timedelta(minutes=5)))
    assert _linkedin_catch_up_seconds(NOW) == 3600

    record(tmp_output_dir, ("linkedin", timedelta(days=3)))
    assert _linkedin_catch_up_seconds(NOW) == 24 * 3600


def test_one_hour_without_a_record(tmp_output_dir):
    assert _linkedin_catch_up_seconds(NOW) == 3600

    (tmp_output_dir / "workflow_runs.jsonl").write_text('not json\n{"workflow": "linkedin"}\n')
    assert _linkedin_catch_up_seconds(NOW) == 3600


GEO = [{"name": "United States", "location": "United States", "geoId": ""}]


def search(monkeypatch, pages, max_results):
    """Run the LinkedIn search against canned pages ("" = LinkedIn ran out)."""
    import scrape_jobs
    feed = iter(pages)
    monkeypatch.setattr(scrape_jobs, "fetch", lambda url: next(feed, ""))
    monkeypatch.setattr(scrape_jobs.time, "sleep", lambda s: None)
    return scrape_jobs._linkedin_search(["Director of Engineering"], 86400, geos=GEO,
                                        max_results=max_results)


def test_a_search_that_reaches_the_cap_says_so(monkeypatch, capsys, linkedin_search_results_html):
    search(monkeypatch, [linkedin_search_results_html] * 5, max_results=30)

    assert 'CAP-HIT: "Director of Engineering" in United States reached 30' in capsys.readouterr().out


def test_a_search_that_runs_out_first_does_not(monkeypatch, capsys, linkedin_search_results_html):
    search(monkeypatch, [linkedin_search_results_html] * 2, max_results=30)

    assert "CAP-HIT" not in capsys.readouterr().out
