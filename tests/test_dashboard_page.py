"""triage.html behaviour that depends on where it's served from.

Runs the page's own snippets in Node with a stubbed browser environment.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PAGE = (Path(__file__).parent.parent / "triage.html").read_text(encoding="utf-8")
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs Node.js")


def node(script):
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def links_when_served_from(url):
    iife = re.search(r"\(function linkToOwnRepo\(\) \{.*?\n  \}\)\(\);", PAGE, re.S).group(0)
    return node(f"""
      const u = new URL({json.dumps(url)});
      const els = {{ 'repo-link': {{ href: 'SOURCE', style: {{}} }},
                    'clear-data-link': {{ href: 'SOURCE_CLEAR', style: {{}} }} }};
      global.location = {{ hostname: u.hostname, pathname: u.pathname }};
      global.document = {{ getElementById: id => els[id] }};
      {iife}
      console.log(JSON.stringify({{ repo: els['repo-link'].href,
        clear: els['clear-data-link'].href, clearHidden: els['clear-data-link'].style.display === 'none' }}));
    """)


def test_links_point_at_the_repo_the_dashboard_is_published_from():
    links = links_when_served_from("https://someone.github.io/job-scraper/triage.html")

    assert links == {"repo": "https://github.com/someone/job-scraper",
                     "clear": "https://github.com/someone/job-scraper/actions/workflows/clear_data.yml",
                     "clearHidden": False}


def test_clear_data_link_hidden_when_not_on_github_pages():
    links = links_when_served_from("http://localhost:8000/triage.html")

    assert links["clearHidden"] is True
    assert links["repo"] == "SOURCE"


@pytest.mark.parametrize("available, expected", [
    ({"config.json": {"profile": {"title": "local"}},
      "output/dashboard_config.json": {"profile": {"title": "pages"}}}, "local"),
    ({"output/dashboard_config.json": {"profile": {"title": "pages"}}}, "pages"),
    ({}, None),
])
def test_dashboard_uses_config_json_locally_else_the_committed_subset(available, expected):
    loop = re.search(r"for \(const path of \['config\.json', 'output/dashboard_config\.json'\]\) \{.*?\n      \}",
                     PAGE, re.S).group(0)
    result = node(f"""
      const files = {json.dumps(available)};
      let applied = null;
      const applyConfig = cfg => {{ applied = cfg.profile.title; }};
      global.fetch = async url => {{
        const path = url.split('?')[0];
        return path in files ? {{ ok: true, json: async () => files[path] }} : {{ ok: false }};
      }};
      (async () => {{ {loop}
        console.log(JSON.stringify(applied)); }})();
    """)

    assert result == expected
