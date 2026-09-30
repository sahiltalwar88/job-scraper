"""scripts/setup.sh must put the user's config into the CONFIG_JSON secret.

Runs the whole script against a fake `gh` that records every secret it's asked
to set, answering the script's prompts from stdin.
"""
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

FAKE_GH = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    log = os.environ["FAKE_GH_LOG"]
    if args[:2] == ["secret", "set"]:
        with open(log, "a") as f:
            f.write(json.dumps({"secret": args[2], "value": sys.stdin.read()}) + "\\n")
    elif args[:2] == ["repo", "view"]:
        q = args[args.index("-q") + 1] if "-q" in args else ""
        print("sahiltalwar88/job-scraper" if "parent" in q else "someone/job-scraper")
    elif args[:2] == ["auth", "status"]:
        pass
    # everything else (api, variable set, workflow run, ...) succeeds silently
''')


def run_setup(tmp_path, answers, files):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for rel in ("scripts/setup.sh", "scripts/export-config-secret.sh", "notify.py"):
        shutil.copy(REPO_ROOT / rel, repo / rel)
    for rel, content in files.items():
        (repo / rel).write_text(content)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    log = tmp_path / "gh.log"
    log.write_text("")
    subprocess.run(["bash", "scripts/setup.sh"], cwd=repo, input="\n".join(answers) + "\n" * 20,
                   capture_output=True, text=True, timeout=60,
                   env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_GH_LOG": str(log)})
    return {e["secret"]: e["value"] for e in map(json.loads, log.read_text().splitlines())}


CONFIG = {"keywords": {"include": ["data analyst"]}, "profile": {"title": "Café tracker"}}


def test_sets_config_json_from_default_path(tmp_path):
    secrets = run_setup(tmp_path, answers=[""], files={"config.json": json.dumps(CONFIG, indent=2)})

    assert json.loads(secrets["CONFIG_JSON"]) == CONFIG
    assert "\n" not in secrets["CONFIG_JSON"].strip()


def test_sets_config_json_from_a_path_the_user_gives(tmp_path):
    secrets = run_setup(tmp_path, answers=["my-search.json"],
                        files={"my-search.json": json.dumps(CONFIG)})

    assert json.loads(secrets["CONFIG_JSON"]) == CONFIG
