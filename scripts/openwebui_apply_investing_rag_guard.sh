#!/usr/bin/env bash
set -euo pipefail

# Applies stricter OWUI RAG settings for day-sensitive investing queries:
# - relevance_threshold -> 0.4
# - top_k -> 15
# - top_k_reranker -> 5
# - injects strict same-day sufficiency gate into rag.template
#
# Usage:
#   ./scripts/openwebui_apply_investing_rag_guard.sh

OWUI_CONTAINER="${OWUI_CONTAINER:-owui}"
DB_PATH="${OWUI_DB_PATH:-/app/backend/data/webui.db}"

docker exec -i "${OWUI_CONTAINER}" python - <<'PY'
import json
import re
import sqlite3

DB_PATH = "/app/backend/data/webui.db"
con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.execute("SELECT data FROM config WHERE id=1")
row = cur.fetchone()
if not row:
    raise SystemExit("config row id=1 not found")

cfg = json.loads(row[0])
rag = cfg.setdefault("rag", {})

rag["relevance_threshold"] = 0.4
rag["top_k"] = 15
rag["top_k_reranker"] = 5

tpl = rag.get("template") or ""

gate = """### Same-day sufficiency gate (MUST for day-sensitive queries)
- Trigger: user asks for "today/heute/des Tages/latest/current" hot lists, rankings, or picks.
- Parse only explicit metadata in <context>: `source_id` and `published_at`.
- Compute on unique `source_id` values:
  - `dated_sources` = count with explicit `published_at`.
  - `same_day_sources` = count where `published_at` is today (UTC date).
- If `dated_sources < 3` OR `same_day_sources < 3`, you MUST NOT output a "today" ranking/list.
- In that case, return ONLY:
  - Direct answer: "Nicht genug tagesaktuelle Quellen im Kontext (same_day_sources=<n>, dated_sources=<m>, Mindestwert=3)."
  - Missing info: ask for (a) today-only filter, (b) fresh sync/retrieval retry, or (c) direct upload of missing transcripts.

"""

if "### Same-day sufficiency gate (MUST for day-sensitive queries)" in tpl:
    tpl = re.sub(
        r"### Same-day sufficiency gate \(MUST for day-sensitive queries\)\n(?:.*?\n)(?=### Output format)",
        gate,
        tpl,
        flags=re.S,
    )
else:
    marker = "### Output format\n"
    if marker in tpl:
        tpl = tpl.replace(marker, gate + marker)
    else:
        tpl = tpl + ("\n\n" if tpl else "") + gate

rag["template"] = tpl
cfg["rag"] = rag

cur.execute("UPDATE config SET data=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (json.dumps(cfg),))
con.commit()
print("Applied OWUI RAG guard settings.")
print(f"relevance_threshold={rag.get('relevance_threshold')}")
print(f"top_k={rag.get('top_k')}")
print(f"top_k_reranker={rag.get('top_k_reranker')}")
print(f"same_day_gate_enabled={'### Same-day sufficiency gate (MUST for day-sensitive queries)' in rag.get('template', '')}")
PY

docker restart "${OWUI_CONTAINER}" >/dev/null
echo "Restarted ${OWUI_CONTAINER}."
