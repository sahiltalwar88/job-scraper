"""Test the fuzzy leadership pre-filter (is_leadership_role).

Test cases derived from the California 50-title sample and user-specified
edge cases. This is the core decision gate — false positives waste LLM
calls, false negatives miss real jobs.
"""
import pytest
from scrape_jobs import is_leadership_role


# ---------------------------------------------------------------------------
# SHOULD PASS — software engineering leadership, Director+ level
# ---------------------------------------------------------------------------
PASS_CASES = [
    ("Director of Engineering", ""),
    ("Director, Engineering", ""),
    ("VP of Engineering", ""),
    ("Vice President of Engineering", ""),
    ("Head of Engineering", ""),
    ("Senior Engineering Manager", ""),
    ("Director of Platform Engineering", ""),
    ("Director, Core Runtime & Platform Engineering", ""),
    ("Head of Software Tools", ""),
    ("Director Production Engineering", ""),
    ("Director of Engineering, Developer Productivity", ""),
    ("Director, Shopify Engineering", ""),
    ("Director of Engineering, Strategic Initiatives & Technology Enablement", ""),
    ("Global Capability Center Product Engineering Director", ""),
    ("Director of Engineering (Product Dev)", ""),
    ("Director of Engineering - Design", ""),
    ("Director, Yield Architecture & Engineering", ""),
    # Passes fuzzy filter, LLM decides
    ("Director, Systems Engineering, CCDI", ""),
    ("Director, Product Engineering - UGG Footwear", ""),
]

# ---------------------------------------------------------------------------
# SHOULD REJECT — non-software domains (excluded by fuzzy_exclude tokens)
# ---------------------------------------------------------------------------
EXCLUDE_CASES = [
    ("Director, Hardware Engineering", ""),
    ("Director of Engineering - Defense Electronics", ""),
    ("Director of Engineering, Manufacturing", ""),
    ("Director of Engineering - Aerospace Manufacturing", ""),
    ("Director of Energy and Engineering (On-site)", ""),
    ("Director, Hardware Lifecycle Engineering", ""),
    ("Director of Engineering, Energy Storage", ""),
    ("Engineering Manager/Director - Hardware Systems & Integration", ""),
    ("Associate Director of Materials & Process Technology (Onsite)", ""),
    ("Director of Technical Project Delivery", ""),
    ("Program Chief Engineer (Onsite)", ""),
    ("Portfolio Chief Engineer - Emerging Innovation (Onsite)", ""),
    ("Programs Chief Engineer, Dive XL", ""),
]

# ---------------------------------------------------------------------------
# SHOULD REJECT — below Director+ level or wrong role type
# ---------------------------------------------------------------------------
BELOW_LEVEL_CASES = [
    ("Engineering Manager", ""),
    ("Chief Engineer", ""),
    ("Lead Product Engineer", ""),
    ("Principal Engineering Lead", ""),
    ("Lead Member of Technical Staff", ""),
    ("Chief Engineer WSISS", ""),
]

# ---------------------------------------------------------------------------
# SHOULD REJECT — wrong domain entirely
# ---------------------------------------------------------------------------
WRONG_DOMAIN_CASES = [
    ("Director of Marketing", ""),
    ("Software Engineer", ""),
    ("Junior Developer", ""),
    ("Product Manager", ""),
]


@pytest.mark.parametrize("title,company", PASS_CASES)
def test_should_pass(title, company):
    assert is_leadership_role(title, company) is True, (
        f'Expected True for "{title}" but got False'
    )


@pytest.mark.parametrize("title,company", EXCLUDE_CASES)
def test_should_reject_excluded_domains(title, company):
    assert is_leadership_role(title, company) is False, (
        f'Expected False for "{title}" (excluded domain) but got True'
    )


@pytest.mark.parametrize("title,company", BELOW_LEVEL_CASES)
def test_should_reject_below_level(title, company):
    assert is_leadership_role(title, company) is False, (
        f'Expected False for "{title}" (below Director+) but got True'
    )


@pytest.mark.parametrize("title,company", WRONG_DOMAIN_CASES)
def test_should_reject_wrong_domain(title, company):
    assert is_leadership_role(title, company) is False, (
        f'Expected False for "{title}" (wrong domain) but got True'
    )


def test_head_of_dropbox_priority_company():
    """Head of Dropbox passes via priority company rule (Dropbox in priority list)."""
    assert is_leadership_role("Head of Dropbox", "Dropbox") is True


def test_head_of_sales_priority_company():
    """Head of Sales at a priority company passes — LLM decides."""
    # Google is in the priority list
    assert is_leadership_role("Head of Sales", "Google") is True


def test_head_of_sales_non_priority():
    """Head of Sales at non-priority company without domain token is rejected."""
    assert is_leadership_role("Head of Sales", "Acme Corp") is False


def test_empty_title():
    assert is_leadership_role("") is False


def test_none_title():
    assert is_leadership_role(None) is False  # type: ignore[arg-type]


def test_vp_at_priority_company():
    """VP at a priority company passes even without domain token."""
    assert is_leadership_role("VP", "Google") is True
