#!/usr/bin/env bash
set -euo pipefail

TOPIC="${1:-investing_test}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/home/wasti/ai_stack_data/transcript-miner/output}"
OPEN_WEBUI_BASE_URL="${OPEN_WEBUI_BASE_URL:-http://127.0.0.1:3000}"
TM_CONTAINER="${TM_CONTAINER:-tm}"

if [[ "${2:-}" != "--force" ]]; then
  echo "Usage: $0 <topic> --force"
  echo "Example: $0 investing_test --force"
  exit 1
fi

INDEX_DIR="${OUTPUT_ROOT}/data/indexes/${TOPIC}/current"
TRANSCRIPTS_JSONL="${INDEX_DIR}/transcripts.jsonl"

echo "Purging topic: ${TOPIC}"
echo "OUTPUT_ROOT: ${OUTPUT_ROOT}"

run_in_container() {
  OPEN_WEBUI_BASE_URL_INNER="${OPEN_WEBUI_BASE_URL_INNER:-http://owui:8080}"
  docker exec -e OPEN_WEBUI_API_KEY="${OPEN_WEBUI_API_KEY:-}" -e OPEN_WEBUI_BASE_URL="${OPEN_WEBUI_BASE_URL_INNER}" -i "${TM_CONTAINER}" python - <<'PY' "${TOPIC}"
import json, os, sys
from pathlib import Path
import urllib.request

topic = sys.argv[1]
output_root = Path("/transcript_miner_output")
base = os.environ.get("OPEN_WEBUI_BASE_URL", "http://owui:8080").rstrip("/")
key = os.environ.get("OPEN_WEBUI_API_KEY", "")

index_dir = output_root / "data" / "indexes" / topic / "current"
transcripts_jsonl = index_dir / "transcripts.jsonl"

video_ids = set()
if transcripts_jsonl.exists():
    for line in transcripts_jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            vid = data.get("video_id")
            if vid:
                video_ids.add(vid)
        except Exception:
            pass

for vid in sorted(video_ids):
    (output_root / "data" / "transcripts" / "by_video_id" / f"{vid}.txt").unlink(missing_ok=True)
    (output_root / "data" / "transcripts" / "by_video_id" / f"{vid}.meta.json").unlink(missing_ok=True)
    (output_root / "data" / "summaries" / "by_video_id" / f"{vid}.summary.md").unlink(missing_ok=True)

for p in [output_root / "data" / "indexes" / topic, output_root / "reports" / topic, output_root / "history" / topic]:
    if p.exists():
        for child in p.rglob("*"):
            if child.is_file():
                child.unlink(missing_ok=True)
        for child in sorted(p.rglob("*"), reverse=True):
            if child.is_dir():
                child.rmdir()
        p.rmdir()

if not key:
    print("OPEN_WEBUI_API_KEY not set; skipping knowledge deletion.")
    raise SystemExit(0)

def req(url, method="GET"):
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    r = urllib.request.Request(url, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.status, resp.read()

status, body = req(f"{base}/api/v1/knowledge/")
data = json.loads(body.decode("utf-8")) if body else {}
items = data.get("items") if isinstance(data, dict) else data
kid = None
if isinstance(items, list):
    for item in items:
        if isinstance(item, dict) and item.get("name") == topic:
            kid = item.get("id")
            break

if not kid:
    print("Knowledge collection not found; skipping.")
    raise SystemExit(0)

status, _ = req(f"{base}/api/v1/knowledge/{kid}/delete", method="DELETE")
print(f"Deleted knowledge collection: {topic} ({kid}) status={status}")
PY
}

python3_ok=0
if command -v python3 >/dev/null 2>&1; then
  python3_ok=1
fi

write_ok=0
if [[ -d "${OUTPUT_ROOT}" && -w "${OUTPUT_ROOT}" ]]; then
  write_ok=1
fi

if [[ "${python3_ok}" -eq 0 || "${write_ok}" -eq 0 ]]; then
  echo "Host python3 or permissions missing; running purge inside container '${TM_CONTAINER}'."
  run_in_container
  echo "Done."
  exit 0
fi

video_ids=()
if [[ -f "${TRANSCRIPTS_JSONL}" ]]; then
  mapfile -t video_ids < <(
    python3 - <<'PY' "${TRANSCRIPTS_JSONL}"
import json, sys
path = sys.argv[1]
ids = []
with open(path, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            vid = data.get("video_id")
            if vid:
                ids.append(vid)
        except Exception:
            pass
for vid in sorted(set(ids)):
    print(vid)
PY
  )
fi

if [[ "${#video_ids[@]}" -gt 0 ]]; then
  echo "Deleting transcripts/summaries for ${#video_ids[@]} video_ids from index..."
  for vid in "${video_ids[@]}"; do
    rm -f "${OUTPUT_ROOT}/data/transcripts/by_video_id/${vid}.txt"
    rm -f "${OUTPUT_ROOT}/data/transcripts/by_video_id/${vid}.meta.json"
    rm -f "${OUTPUT_ROOT}/data/summaries/by_video_id/${vid}.summary.md"
    find "${OUTPUT_ROOT}/data/views/by_channel" -type f -name "*__${vid}__*.txt" -delete 2>/dev/null || true
    find "${OUTPUT_ROOT}/data/views/by_channel" -type f -name "*__${vid}__*.md" -delete 2>/dev/null || true
  done
else
  echo "No transcripts.jsonl found (or empty); skipping per-video deletes."
fi

echo "Deleting topic-specific outputs..."
rm -rf "${OUTPUT_ROOT}/data/indexes/${TOPIC}"
rm -rf "${OUTPUT_ROOT}/reports/${TOPIC}"
rm -rf "${OUTPUT_ROOT}/history/${TOPIC}"

if [[ -n "${OPEN_WEBUI_API_KEY:-}" ]]; then
  echo "Deleting Open WebUI knowledge collection for topic=${TOPIC}..."
  python3 - <<'PY' "${OPEN_WEBUI_BASE_URL}" "${TOPIC}"
import json, os, sys, urllib.request
base = sys.argv[1].rstrip("/")
topic = sys.argv[2]
key = os.environ.get("OPEN_WEBUI_API_KEY", "")

def req(url, method="GET"):
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    r = urllib.request.Request(url, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.status, resp.read()

status, body = req(f"{base}/api/v1/knowledge/")
data = json.loads(body.decode("utf-8")) if body else {}
items = data.get("items") if isinstance(data, dict) else data
if not isinstance(items, list):
    print("Unexpected knowledge list response")
    raise SystemExit(1)

kid = None
for item in items:
    if isinstance(item, dict) and item.get("name") == topic:
        kid = item.get("id")
        break

if not kid:
    print("Knowledge collection not found; skipping.")
    raise SystemExit(0)

status, _ = req(f"{base}/api/v1/knowledge/{kid}/delete", method="DELETE")
print(f"Deleted knowledge collection: {topic} ({kid}) status={status}")
PY
else
  echo "OPEN_WEBUI_API_KEY not set; skipping knowledge deletion."
fi

echo "Done."
