#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack"
KILL_SWITCH_FILE="${STATE_DIR}/schedulers.disabled"
if [[ -f "$KILL_SWITCH_FILE" ]]; then
  echo "ai_stack: schedulers disabled via ${KILL_SWITCH_FILE}; skipping investing run"
  exit 0
fi

TM_CONTAINER="tm"
CONFIG_ID="config_investing.yaml"
RUNS_URL="http://127.0.0.1:8000/runs/start"
TOPIC="investing"

if ! docker ps --format '{{.Names}}' | grep -qx "$TM_CONTAINER"; then
  echo "ERROR: container not running: $TM_CONTAINER" >&2
  exit 1
fi

docker exec -i "$TM_CONTAINER" python - <<'PY'
import json
import sys
import time
import urllib.request

CONFIG_ID = "config_investing.yaml"
TOPIC = "investing"
BASE = "http://127.0.0.1:8000"

payload = {"config_id": CONFIG_ID}
req = urllib.request.Request(
    f"{BASE}/runs/start",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=30) as resp:
    raw = resp.read().decode("utf-8")
    sys.stdout.write(raw)
    sys.stdout.write("\n")
    data = json.loads(raw)

run_id = data.get("run_id")
if not run_id:
    sys.exit(1)

deadline = time.time() + 60 * 120
while True:
    if time.time() > deadline:
        raise SystemExit("Timeout waiting for run completion")
    with urllib.request.urlopen(f"{BASE}/runs/{run_id}", timeout=30) as resp:
        status = json.loads(resp.read().decode("utf-8"))
    state = status.get("state")
    if state in ("finished", "failed"):
        exit_code = status.get("exit_code")
        if state == "failed" or (isinstance(exit_code, int) and exit_code != 0):
            raise SystemExit(f"Run failed: state={state} exit_code={exit_code}")
        break
    time.sleep(15)

sync_req = urllib.request.Request(
    f"{BASE}/sync/topic/{TOPIC}",
    data=b"{}",
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(sync_req, timeout=300) as resp:
    sys.stdout.write(resp.read().decode("utf-8"))
    sys.stdout.write("\n")
PY
echo
