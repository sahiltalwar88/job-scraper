#!/usr/bin/env bash
# Export config.json as a minified JSON string for the CONFIG_JSON GitHub secret.
# Usage: bash scripts/export-config-secret.sh
# Copy the output and paste it into:
#   Settings → Secrets and variables → Actions → New repository secret
#   Name:  CONFIG_JSON
#   Value: <paste output here>

set -euo pipefail

CONFIG_PATH="${1:-config.json}"

if [ ! -f "$CONFIG_PATH" ]; then
  echo "Error: $CONFIG_PATH not found" >&2
  exit 1
fi

python3 -c "
import json, sys
with open('$CONFIG_PATH') as f:
    data = json.load(f)
print(json.dumps(data, separators=(',', ':')))
"
