#!/usr/bin/env bash
set -euo pipefail

# Dumps a Markdown snapshot of Open WebUI RAG settings from webui.db.
#
# Usage:
#   ./scripts/openwebui_snapshot_rag_settings.sh [output_file]
#
# Example:
#   ./scripts/openwebui_snapshot_rag_settings.sh docs/owui_rag_settings_snapshot.md

OWUI_CONTAINER="${OWUI_CONTAINER:-owui}"
DB_PATH="${OWUI_DB_PATH:-/app/backend/data/webui.db}"
OUT_FILE="${1:-}"

TMP_FILE="$(mktemp)"
trap 'rm -f "${TMP_FILE}"' EXIT

docker exec -i -e OWUI_DB_PATH="${DB_PATH}" -e OWUI_CONTAINER_NAME="${OWUI_CONTAINER}" "${OWUI_CONTAINER}" python - <<'PY' > "${TMP_FILE}"
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv("OWUI_DB_PATH", "/app/backend/data/webui.db")
CONTAINER_NAME = os.getenv("OWUI_CONTAINER_NAME", "owui")
con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.execute("SELECT data FROM config WHERE id=1")
row = cur.fetchone()
if not row:
    raise SystemExit("config row id=1 not found")

cfg = json.loads(row[0])
rag = cfg.get("rag", {})

keys = [
    "embedding_engine",
    "embedding_model",
    "openai_api_base_url",
    "top_k",
    "top_k_reranker",
    "relevance_threshold",
    "enable_hybrid_search",
    "hybrid_bm25_weight",
    "chunk_size",
    "chunk_overlap",
    "chunk_min_size_target",
    "text_splitter",
    "reranking_engine",
    "reranking_model",
]

def fmt(value):
    return json.dumps(value, ensure_ascii=True)

same_day_gate = "### Same-day sufficiency gate (MUST for day-sensitive queries)" in (rag.get("template") or "")
generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

print("# Open WebUI RAG Settings Snapshot")
print("")
print(f"- generated_at_utc: `{generated_at}`")
print(f"- source: container `{CONTAINER_NAME}`, db path `{DB_PATH}`, table `config.id=1`")
print("")
print("| key | value |")
print("| --- | --- |")
for key in keys:
    print(f"| `{key}` | `{fmt(rag.get(key))}` |")
print(f"| `same_day_sufficiency_gate_enabled` | `{fmt(same_day_gate)}` |")
PY

if [[ -n "${OUT_FILE}" ]]; then
  mkdir -p "$(dirname "${OUT_FILE}")"
  cat "${TMP_FILE}" > "${OUT_FILE}"
  echo "Wrote snapshot to ${OUT_FILE}"
else
  cat "${TMP_FILE}"
fi
