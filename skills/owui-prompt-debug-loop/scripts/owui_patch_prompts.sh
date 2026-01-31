#!/usr/bin/env bash
set -euo pipefail

MODEL_ID=""
MODEL_SYSTEM_FILE=""
FOLDER_NAME=""
FOLDER_SYSTEM_FILE=""
RAG_TEMPLATE_FILE=""

usage() {
  cat <<'EOF'
Usage:
  owui_patch_prompts.sh [args]

Required:
  --model-id <id>
  --model-system-file <path>
  --folder-name <name>
  --folder-system-file <path>
  --rag-template-file <path>

Behavior:
  - Creates a timestamped backup of /app/backend/data/webui.db (inside the owui volume)
  - Patches ONLY:
      model.params.system
      folder.data.system_prompt
      config.id=1 rag.template
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-id) MODEL_ID="${2:-}"; shift 2;;
    --model-system-file) MODEL_SYSTEM_FILE="${2:-}"; shift 2;;
    --folder-name) FOLDER_NAME="${2:-}"; shift 2;;
    --folder-system-file) FOLDER_SYSTEM_FILE="${2:-}"; shift 2;;
    --rag-template-file) RAG_TEMPLATE_FILE="${2:-}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

for p in "$MODEL_SYSTEM_FILE" "$FOLDER_SYSTEM_FILE" "$RAG_TEMPLATE_FILE"; do
  [[ -f "$p" ]] || { echo "Missing file: $p" >&2; exit 2; }
done

if [[ -z "$MODEL_ID" || -z "$FOLDER_NAME" ]]; then
  usage >&2
  exit 2
fi

MODEL_SYSTEM="$(cat "$MODEL_SYSTEM_FILE")"
FOLDER_SYSTEM="$(cat "$FOLDER_SYSTEM_FILE")"
RAG_TEMPLATE="$(cat "$RAG_TEMPLATE_FILE")"

docker exec owui sh -lc 'mkdir -p /app/backend/data/backups && cp /app/backend/data/webui.db "/app/backend/data/backups/webui.db.$(date -u +%Y%m%dT%H%M%SZ)"'

docker exec -i owui python - <<PY
import json, sqlite3, sys

DB='/app/backend/data/webui.db'
MODEL_ID=${MODEL_ID!r}
FOLDER_NAME=${FOLDER_NAME!r}
MODEL_SYSTEM=${MODEL_SYSTEM!r}
FOLDER_SYSTEM=${FOLDER_SYSTEM!r}
RAG_TEMPLATE=${RAG_TEMPLATE!r}

def die(msg):
    print(msg, file=sys.stderr)
    raise SystemExit(2)

def load_json(s):
    try:
        return json.loads(s) if s else None
    except Exception:
        return None

def dump_json(obj):
    return json.dumps(obj, ensure_ascii=True)

con=sqlite3.connect(DB)
con.row_factory=sqlite3.Row
cur=con.cursor()

# Patch model.params.system
cur.execute('SELECT id,params FROM model WHERE id=?', (MODEL_ID,))
r=cur.fetchone()
if not r:
    die(f"Model not found: {MODEL_ID}")
params=load_json(r['params'])
if not isinstance(params, dict):
    params={}
params['system']=MODEL_SYSTEM
cur.execute('UPDATE model SET params=?, updated_at=strftime(\"%s\",\"now\") WHERE id=?', (dump_json(params), MODEL_ID))

# Patch folder.data.system_prompt
cur.execute('SELECT id,data FROM folder WHERE name=? COLLATE NOCASE', (FOLDER_NAME,))
rf=cur.fetchone()
if not rf:
    die(f"Folder not found: {FOLDER_NAME}")
fdata=load_json(rf['data'])
if not isinstance(fdata, dict):
    fdata={}
fdata['system_prompt']=FOLDER_SYSTEM
cur.execute('UPDATE folder SET data=?, updated_at=strftime(\"%s\",\"now\") WHERE id=?', (dump_json(fdata), rf['id']))

# Patch config.rag.template
cur.execute('SELECT id,data FROM config WHERE id=1')
rc=cur.fetchone()
if not rc:
    die('Config id=1 not found')
cfg=load_json(rc['data'])
if not isinstance(cfg, dict):
    cfg={}
rag=cfg.get('rag')
if not isinstance(rag, dict):
    rag={}
rag['template']=RAG_TEMPLATE
cfg['rag']=rag
cur.execute('UPDATE config SET data=?, updated_at=datetime(\"now\") WHERE id=1', (dump_json(cfg),))

con.commit()
print('OK: patched model, folder, rag template')
PY

echo "Restart owui to ensure changes are picked up (if needed):"
echo "  docker restart owui"
