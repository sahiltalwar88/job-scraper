"""config.json is layered over config.example.json; the example's search must not leak in.

A user config that leaves out optional filter keys (e.g. keywords.fuzzy_*) must
get neutral defaults, not the example author's search.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def relevant(tmp_path, user_config, titles):
    for name in ("scrape_jobs.py", "config.example.json"):
        shutil.copy(REPO_ROOT / name, tmp_path / name)
    (tmp_path / "config.json").write_text(json.dumps(user_config))
    code = ("import json, sys, scrape_jobs as s\n"
            "print(json.dumps([s.role_is_relevant(t, 'Acme') for t in json.loads(sys.argv[1])]))")
    out = subprocess.run([sys.executable, "-c", code, json.dumps(titles)], cwd=tmp_path,
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


def test_minimal_config_matches_its_own_keywords(tmp_path):
    config = {"keywords": {"include": ["data analyst"]}, "search_terms": {"linkedin": ["Data Analyst"]}}

    kept = relevant(tmp_path, config, ["Senior Data Analyst", "Data Analyst II", "Line Cook"])

    assert kept == [True, True, False]
