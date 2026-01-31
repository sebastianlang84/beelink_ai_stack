#!/usr/bin/env bash
set -euo pipefail

# OWUI prompt test loop via API + debug-proxy flow report
# - Resolves a chat_id from a folder name (latest chat) if not provided
# - Sends a single user prompt via OWUI /api/v1/chat/completions
# - Extracts + reports the last N debug-proxy flows

MODEL_ID="google/gemini-3-flash-preview"
FOLDER_NAME="Investing"
CHAT_ID=""
PROMPT_FILE=""
PROMPT_TEXT=""
STREAM="false"
FLOWS_N=5
FLOWS_OUT="debug-proxy/last_flows.local.json"
NO_FLOWS="false"

usage() {
  cat <<'USAGE'
Usage:
  owui_prompt_api_loop.sh [options]

Options:
  --model-id <id>        Model id (default: google/gemini-3-flash-preview)
  --folder-name <name>   Folder name to resolve chat (default: Investing)
  --chat-id <id>         Use specific chat id (skips folder lookup)
  --prompt-file <path>   Read prompt from file
  --prompt-text <text>   Prompt text (if no file)
  --stream <true|false>  Pass stream flag (default: false)
  --flows-n <n>          Number of flows to report (default: 5)
  --flows-out <path>     Flow extract output path (default: debug-proxy/last_flows.local.json)
  --no-flows             Skip flow extract/report
  -h|--help              Show help

Notes:
  - Requires OPEN_WEBUI_API_KEY in .env
  - Uses OPEN_WEBUI_BIND_ADDRESS/OPEN_WEBUI_HOST_PORT from open-webui/.config.env
    or .config.env (fallback). Defaults to http://127.0.0.1:3000
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-id) MODEL_ID="${2:-}"; shift 2;;
    --folder-name) FOLDER_NAME="${2:-}"; shift 2;;
    --chat-id) CHAT_ID="${2:-}"; shift 2;;
    --prompt-file) PROMPT_FILE="${2:-}"; shift 2;;
    --prompt-text) PROMPT_TEXT="${2:-}"; shift 2;;
    --stream) STREAM="${2:-}"; shift 2;;
    --flows-n) FLOWS_N="${2:-}"; shift 2;;
    --flows-out) FLOWS_OUT="${2:-}"; shift 2;;
    --no-flows) NO_FLOWS="true"; shift 1;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [[ -z "$PROMPT_FILE" && -z "$PROMPT_TEXT" ]]; then
  echo "ERROR: Provide --prompt-file or --prompt-text" >&2
  exit 2
fi

if [[ -n "$PROMPT_FILE" && ! -f "$PROMPT_FILE" ]]; then
  echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
  exit 2
fi

# Load secrets/config (do not echo values)
if [[ -f "/home/wasti/ai_stack/.env" ]]; then
  # shellcheck disable=SC1091
  source /home/wasti/ai_stack/.env
fi
if [[ -f "/home/wasti/ai_stack/open-webui/.config.env" ]]; then
  # shellcheck disable=SC1091
  source /home/wasti/ai_stack/open-webui/.config.env
elif [[ -f "/home/wasti/ai_stack/.config.env" ]]; then
  # shellcheck disable=SC1091
  source /home/wasti/ai_stack/.config.env
fi

: "${OPEN_WEBUI_API_KEY:?OPEN_WEBUI_API_KEY missing in .env}"

bind_addr="${OPEN_WEBUI_BIND_ADDRESS:-127.0.0.1}"
port="${OPEN_WEBUI_HOST_PORT:-3000}"
base_url="http://${bind_addr}:${port}"

if [[ -z "$CHAT_ID" ]]; then
  CHAT_ID=$(docker exec -i \
    -e FOLDER_NAME="$FOLDER_NAME" \
    owui python - <<'PY'
import sqlite3
import os
DB='/app/backend/data/webui.db'
folder_name = os.environ.get("FOLDER_NAME", "")
con=sqlite3.connect(DB)
cur=con.cursor()
cur.execute("SELECT id FROM folder WHERE name=? COLLATE NOCASE", (folder_name,))
row=cur.fetchone()
if not row:
    raise SystemExit("Folder not found: %s" % folder_name)
folder_id=row[0]
cur.execute("SELECT id FROM chat WHERE folder_id=? ORDER BY updated_at DESC LIMIT 1", (folder_id,))
row=cur.fetchone()
if not row:
    raise SystemExit("No chats in folder: %s" % folder_name)
print(row[0])
PY
  )
fi

payload_file=$(mktemp)
MODEL_ID="${MODEL_ID}" \
CHAT_ID="${CHAT_ID}" \
STREAM="${STREAM}" \
PROMPT_FILE="${PROMPT_FILE}" \
PROMPT_TEXT="${PROMPT_TEXT}" \
python3 - <<'PY' >"$payload_file"
import json
import os
model_id = os.environ.get("MODEL_ID", "")
chat_id = os.environ.get("CHAT_ID", "")
prompt_file = os.environ.get("PROMPT_FILE", "")
prompt_text = os.environ.get("PROMPT_TEXT", "")
if prompt_file:
    with open(prompt_file, "r", encoding="utf-8") as f:
        prompt = f.read()
else:
    prompt = prompt_text
stream = os.environ.get("STREAM", "false").lower() == "true"
body = {
    "model": model_id,
    "chat_id": chat_id,
    "stream": stream,
    "messages": [
        {"role": "user", "content": prompt}
    ]
}
print(json.dumps(body, ensure_ascii=True))
PY

curl -sS -N \
  -X POST "${base_url}/api/v1/chat/completions" \
  -H "Authorization: Bearer ${OPEN_WEBUI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @"${payload_file}" >/dev/null

rm -f "$payload_file"

if [[ "$NO_FLOWS" != "true" ]]; then
  python3 /home/wasti/ai_stack/skills/owui-prompt-debug-loop/scripts/flow_extract.py \
    --in /home/wasti/ai_stack/debug-proxy/flows.jsonl \
    --out "/home/wasti/ai_stack/${FLOWS_OUT}" \
    --n "${FLOWS_N}"

  python3 /home/wasti/ai_stack/skills/owui-prompt-debug-loop/scripts/flow_report.py \
    --in "/home/wasti/ai_stack/${FLOWS_OUT}"
fi
