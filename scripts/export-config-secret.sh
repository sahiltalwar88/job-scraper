#!/usr/bin/env bash
# Export config.json as a single-line, ASCII-safe JSON string for the
# CONFIG_JSON GitHub Actions secret.
#
# Why single-line and ASCII-safe:
#   - GitHub Actions treats each LINE of a multi-line secret as a separate
#     secret pattern for masking. If config.json is stored multi-line, each
#     line (e.g. '"Director of Engineering",') becomes its own secret, and
#     any step output containing that substring gets redacted — including
#     the partition matrix, which breaks the backfill workflow.
#   - Non-ASCII characters (em-dashes, emoji) can get corrupted when pasted
#     through Windows clipboard tools (clip.exe). ensure_ascii=True escapes
#     them as \uXXXX so the JSON is pure ASCII.
#
# Usage:
#   bash scripts/export-config-secret.sh              # print to stdout
#   bash scripts/export-config-secret.sh --clip        # copy to Windows clipboard (WSL)
#   bash scripts/export-config-secret.sh scoring_profile.json   # for the SCORING_PROFILE_JSON secret
#
# Then paste the output into:
#   Settings → Secrets and variables → Actions → New repository secret
#   Name:  CONFIG_JSON
#   Value: <paste output here>

set -euo pipefail

CLIP=false
CONFIG_PATH=""

for arg in "$@"; do
  case "$arg" in
    --clip) CLIP=true ;;
    *) CONFIG_PATH="$arg" ;;
  esac
done

CONFIG_PATH="${CONFIG_PATH:-config.json}"

if [ ! -f "$CONFIG_PATH" ]; then
  echo "Error: $CONFIG_PATH not found" >&2
  exit 1
fi

SECRET_NAME=CONFIG_JSON
case "$(basename "$CONFIG_PATH")" in
  scoring_profile*) SECRET_NAME=SCORING_PROFILE_JSON ;;
esac

# scoring_profile.json regexes are often written with single backslashes
# ("\bword\b"), which strict JSON rejects; repair them the way notify.py does.
OUTPUT=$(python3 - "$CONFIG_PATH" "$(cd "$(dirname "$0")/.." && pwd)" <<'PY'
import json, sys
path, repo = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
try:
    data = json.loads(text)
except json.JSONDecodeError:
    sys.path.insert(0, repo)
    from notify import _repair_json_regex_escapes
    data = json.loads(_repair_json_regex_escapes(text))
print(json.dumps(data, separators=(",", ":"), ensure_ascii=True))
PY
)

if [ "$CLIP" = true ]; then
  if command -v clip.exe &>/dev/null; then
    echo -n "$OUTPUT" | clip.exe
    echo "Copied to Windows clipboard. Paste into the $SECRET_NAME secret field."
  else
    echo "Error: clip.exe not found (not running under WSL?)" >&2
    echo "$OUTPUT"
    exit 1
  fi
else
  echo "$OUTPUT"
fi
