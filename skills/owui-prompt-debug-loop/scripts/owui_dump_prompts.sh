#!/usr/bin/env bash
set -euo pipefail

MODEL_ID=""
FOLDER_NAME=""

usage() {
  cat <<'EOF'
Usage:
  owui_dump_prompts.sh --model-id <id> --folder-name <name>

Prints (without secrets):
  - model system prompt (model.params.system)
  - folder system prompt (folder.data.system_prompt)
  - RAG template (config.id=1 -> rag.template)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-id) MODEL_ID="${2:-}"; shift 2;;
    --folder-name) FOLDER_NAME="${2:-}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [[ -z "$MODEL_ID" || -z "$FOLDER_NAME" ]]; then
  usage >&2
  exit 2
fi

docker exec -i owui python - <<PY
import json, sqlite3, sys

DB='/app/backend/data/webui.db'
MODEL_ID=${MODEL_ID!r}
FOLDER_NAME=${FOLDER_NAME!r}

def die(msg):
    print(msg, file=sys.stderr)
    raise SystemExit(2)

con=sqlite3.connect(DB)
con.row_factory=sqlite3.Row
cur=con.cursor()

def load_json(s):
    try:
        return json.loads(s) if s else None
    except Exception:
        return None

# Model prompt
cur.execute('SELECT id,name,params FROM model WHERE id=?', (MODEL_ID,))
r=cur.fetchone()
if not r:
    die(f"Model not found: {MODEL_ID}")
params=load_json(r['params'])
system=None
if isinstance(params, dict):
    system=params.get('system')
print("=== model.system ===")
print(f"id: {r['id']}  name: {r['name']}")
print(system or "")
print()

# Folder prompt
cur.execute('SELECT id,name,data FROM folder WHERE name=? COLLATE NOCASE', (FOLDER_NAME,))
rf=cur.fetchone()
if not rf:
    die(f"Folder not found: {FOLDER_NAME}")
fdata=load_json(rf['data'])
fsys=None
if isinstance(fdata, dict):
    fsys=fdata.get('system_prompt')
print("=== folder.data.system_prompt ===")
print(f"id: {rf['id']}  name: {rf['name']}")
print(fsys or "")
print()

# RAG template
cur.execute('SELECT data FROM config WHERE id=1')
rc=cur.fetchone()
if not rc:
    die("Config id=1 not found")
cfg=load_json(rc['data'])
rag={}
if isinstance(cfg, dict):
    rag=cfg.get('rag') or {}
tmpl=rag.get('template') if isinstance(rag, dict) else None
print("=== config.rag.template ===")
print(tmpl or "")
print()
PY

