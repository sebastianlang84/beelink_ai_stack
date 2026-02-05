#!/usr/bin/env bash
set -euo pipefail

TM_CONTAINER="${TM_CONTAINER:-tm}"

if ! docker ps --format '{{.Names}}' | grep -qx "$TM_CONTAINER"; then
  echo "ERROR: container not running: $TM_CONTAINER" >&2
  exit 1
fi

docker exec -i "$TM_CONTAINER" python - <<'PY'
import json
import urllib.request

BASE = "http://127.0.0.1:8000"
payload = {
    "dry_run": False,
    "create_knowledge_if_missing": True,
}
req = urllib.request.Request(
    f"{BASE}/sync/lifecycle/investing",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=1800) as resp:
    print(resp.read().decode("utf-8"))
PY
