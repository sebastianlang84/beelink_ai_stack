#!/usr/bin/env bash
set -euo pipefail

TM_CONTAINER="tm"
CONFIG_ID="config_investing.yaml"
RUNS_URL="http://127.0.0.1:8000/runs/start"

if ! docker ps --format '{{.Names}}' | grep -qx "$TM_CONTAINER"; then
  echo "ERROR: container not running: $TM_CONTAINER" >&2
  exit 1
fi

docker exec -i "$TM_CONTAINER" python - <<'PY'
import json
import sys
import urllib.request

payload = {"config_id": "config_investing.yaml"}
req = urllib.request.Request(
    "http://127.0.0.1:8000/runs/start",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=30) as resp:
    sys.stdout.write(resp.read().decode("utf-8"))
PY
echo
