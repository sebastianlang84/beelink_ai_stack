#!/usr/bin/env bash
set -euo pipefail

TM_CONTAINER="${TM_CONTAINER:-tm}"
RUN_ID="${1:-}"

if [[ -z "${RUN_ID}" ]]; then
  echo "Usage: $0 <run_id>"
  echo "Env: TM_CONTAINER (default: tm)"
  exit 1
fi

docker exec -i "${TM_CONTAINER}" python - <<'PY'
import json
import os
import sys
from urllib.request import Request, urlopen

run_id = sys.argv[1]
base = "http://127.0.0.1:8000"

def fetch_run():
    req = Request(f"{base}/runs/{run_id}")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def check_cookies():
    path = os.environ.get("YOUTUBE_COOKIES_FILE") or ""
    if not path:
        return {"path": None, "exists": False}
    return {"path": path, "exists": os.path.isfile(path)}

data = fetch_run()

summary = {
    "status": data.get("status"),
    "state": data.get("state"),
    "pid": data.get("pid"),
    "started_at": data.get("started_at"),
    "finished_at": data.get("finished_at"),
    "exit_code": data.get("exit_code"),
    "topic": data.get("topic"),
    "config_id": data.get("config_id"),
}

log_tail = data.get("log_tail") or ""

flags = {
    "youtube_ip_block": "YouTube IP Block detected" in log_tail,
    "cookie_load_failed": "cookie" in log_tail.lower() and "load" in log_tail.lower(),
}

out = {
    "summary": summary,
    "flags": flags,
    "cookies": check_cookies(),
    "log_tail": log_tail,
}

print(json.dumps(out, ensure_ascii=False, indent=2))
PY "${RUN_ID}"
