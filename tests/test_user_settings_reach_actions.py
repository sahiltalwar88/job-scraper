"""A user's config.json and scoring_profile.json must reach Actions runners and the dashboard.

Both files are gitignored: Actions get them from the CONFIG_JSON and
SCORING_PROFILE_JSON secrets, and the GitHub Pages dashboard gets the
display-only part of config.json from output/dashboard_config.json.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")) + \
    sorted((REPO_ROOT / ".github" / "workflows" / "disabled").glob("*.yml"))
SCRIPT_RE = re.compile(r"python3? (scrape_jobs|notify|triage_agent|eval_triage)\.py")

USER_CONFIG = {
    "profile": {"title": "Data Analyst Tracker", "subtitle": "Chicago · Remote", "emoji": "📊"},
    "keywords": {"include": ["data analyst"]},
    "search_terms": {"linkedin": ["Data Analyst"]},
    "locations": {"linkedin": [{"name": "Chicago", "location": "Chicago, Illinois", "geoId": ""}]},
    "employers": {"priority": ["Acme"], "exclude": ["staffing"]},
    "role_categories": {"terms": [["Analyst", "analyst"]]},
    "priority_topics": {"terms": [["SQL", "\\bsql\\b"]]},
}


def save_results(tmp_path, config):
    """Run the scraper's save step (as every watcher does) with no new jobs."""
    for name in ("scrape_jobs.py", "notify.py", "config.example.json"):
        shutil.copy(REPO_ROOT / name, tmp_path / name)
    (tmp_path / "config.json").write_text(json.dumps(config))
    code = ("import scrape_jobs as s\n"
            "s.save_jobs_output([], basename='linkedin_jobs', title='t', subtitle='s', accent='#000',"
            " empty_message='none', window_label='1h')")
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True, capture_output=True)
    return json.loads((tmp_path / "output" / "dashboard_config.json").read_text())


def test_dashboard_config_has_the_display_sections_and_no_search(tmp_path):
    dashboard = save_results(tmp_path, USER_CONFIG)

    assert dashboard == {
        "profile": USER_CONFIG["profile"],
        "role_categories": USER_CONFIG["role_categories"],
        "priority_topics": USER_CONFIG["priority_topics"],
        "employers": {"exclude": ["staffing"]},
    }


def test_dashboard_config_never_shows_the_examples_sections(tmp_path):
    """Sections the user didn't set stay unset, instead of showing the example author's."""
    dashboard = save_results(tmp_path, {"keywords": {"include": ["data analyst"]}})

    assert dashboard == {}


def _secret_steps():
    for path in WORKFLOWS:
        wf = yaml.safe_load(path.read_text())
        for job_name, job in wf["jobs"].items():
            steps = job.get("steps", [])
            script_steps = [i for i, s in enumerate(steps) if SCRIPT_RE.search(s.get("run", ""))]
            if not script_steps:
                continue
            writers = [i for i, s in enumerate(steps) if "> config.json" in s.get("run", "")]
            yield path, job_name, steps, script_steps, writers


@pytest.mark.parametrize("path, job, steps, script_steps, writers",
                         [pytest.param(*t, id=f"{t[0].name}:{t[1]}") for t in _secret_steps()])
def test_workflow_puts_user_settings_in_place_before_running_scripts(tmp_path, path, job, steps,
                                                                      script_steps, writers):
    assert writers and writers[0] < script_steps[0], \
        f"{path.name}:{job} runs a script before writing config.json from CONFIG_JSON"
    run = steps[writers[0]]["run"]

    def run_step(config_secret, profile_secret):
        (tmp_path / "config.json").write_text("committed config")
        (tmp_path / "scoring_profile.json").write_text("committed profile")
        subprocess.run(["bash", "-eo", "pipefail", "-c", run], cwd=tmp_path, check=True,
                       env={**os.environ, "CONFIG_JSON": config_secret,
                            "SCORING_PROFILE_JSON": profile_secret})
        return (tmp_path / "config.json").read_text().strip(), \
            (tmp_path / "scoring_profile.json").read_text().strip()

    assert run_step("", "") == ("committed config", "committed profile")
    assert run_step('{"c":1}', '{"p":1}') == ('{"c":1}', '{"p":1}')


def test_exported_scoring_profile_scores_jobs_the_same(tmp_path):
    """The one-line SCORING_PROFILE_JSON secret must score exactly like the file it came from."""
    source = REPO_ROOT / "scoring_profile.example.json"
    exported = subprocess.run(["bash", str(REPO_ROOT / "scripts" / "export-config-secret.sh"), str(source)],
                              capture_output=True, text=True, check=True).stdout
    assert len(exported.strip().splitlines()) == 1

    def fit(profile_text, title):
        d = tmp_path / str(abs(hash(profile_text)))
        d.mkdir(exist_ok=True)
        shutil.copy(REPO_ROOT / "notify.py", d / "notify.py")
        (d / "scoring_profile.json").write_text(profile_text)
        code = "import sys, notify; print(notify._fit(sys.argv[1], ''))"
        return subprocess.run([sys.executable, "-c", code, title], cwd=d,
                              capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]

    for title in ("Senior Toxicologist", "Microplastics Researcher", "Line Cook"):
        assert fit(exported, title) == fit(source.read_text(), title), title
