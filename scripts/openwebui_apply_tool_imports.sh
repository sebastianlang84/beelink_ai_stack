#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Apply Open WebUI External Tools from repo templates.

This uses the Open WebUI Admin API endpoint:
  POST /api/v1/configs/tool_servers

Important:
  - This OVERWRITES the current Tool Server connections in Open WebUI.
  - A backup is written to ./open-webui/tool-imports/backup_tool_servers__<ts>.json
  - Requires an *admin* Bearer token; non-admin tokens will return HTTP 401.

Env vars:
  OPEN_WEBUI_BASE_URL   default: http://127.0.0.1:3000
  OPEN_WEBUI_TOKEN      Bearer token (admin). Fallback: OPEN_WEBUI_API_KEY (preferred), OWUI_API_KEY (deprecated alias)

Usage:
  OPEN_WEBUI_TOKEN=... ./scripts/openwebui_apply_tool_imports.sh

Optional flags:
  --imports-dir <dir>   default: open-webui/tool-imports
  --dry-run             only prints what would be sent
EOF
}

imports_dir="open-webui/tool-imports"
base_url="${OPEN_WEBUI_BASE_URL:-http://127.0.0.1:3000}"

# Load .env (secrets) if present so OPEN_WEBUI_API_KEY is available.
if [[ -z "${OPEN_WEBUI_TOKEN:-}" && -z "${OPEN_WEBUI_API_KEY:-}" && -z "${OWUI_API_KEY:-}" ]]; then
  if [[ -f ".env" ]]; then
    set -a
    source ./.env
    set +a
  fi
fi

token="${OPEN_WEBUI_TOKEN:-${OPEN_WEBUI_API_KEY:-${OWUI_API_KEY:-}}}"
dry_run="false"

while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --imports-dir)
      imports_dir="${2:-}"
      shift 2
      ;;
    --dry-run)
      dry_run="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown flag: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$token" ]]; then
  echo "ERROR: Missing OPEN_WEBUI_TOKEN (admin) (or OPEN_WEBUI_API_KEY / OWUI_API_KEY fallback)." >&2
  exit 2
fi

if [[ ! -d "$imports_dir" ]]; then
  echo "ERROR: imports dir not found: $imports_dir" >&2
  exit 2
fi

mapfile -t import_files < <(find "$imports_dir" -maxdepth 1 -type f -name '*.json' ! -name 'backup_tool_servers__*.json' | sort)
if [[ "${#import_files[@]}" -eq 0 ]]; then
  echo "ERROR: no import json files found under $imports_dir" >&2
  exit 2
fi

join_import_arrays() {
  local first="true"
  printf "["
  for f in "${import_files[@]}"; do
    # Remove outer [ ... ] and condense to one line for safe concatenation.
    # This assumes our repo templates are JSON arrays (as exported/imported by Open WebUI).
    frag="$(
      sed -e '1s/^[[:space:]]*\[//' -e '$s/\][[:space:]]*$//' "$f" \
        | tr -d '\n' \
        | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
    )"
    [[ -z "$frag" ]] && continue
    if [[ "$first" == "true" ]]; then
      first="false"
      printf "%s" "$frag"
    else
      printf ",%s" "$frag"
    fi
  done
  printf "]"
}

connections="$(join_import_arrays)"
payload="{\"TOOL_SERVER_CONNECTIONS\":$connections}"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="$imports_dir/backup_tool_servers__${ts}.json"

if [[ "$dry_run" == "true" ]]; then
  echo "DRY RUN"
  echo "base_url=$base_url"
  echo "imports_dir=$imports_dir"
  echo "files:"
  printf '  - %s\n' "${import_files[@]}"
  echo "payload:"
  echo "$payload"
  exit 0
fi

echo "Backing up current tool server config to $backup_path ..."
code="$(
  curl -sS \
    -H "Authorization: Bearer $token" \
    -o "$backup_path" \
    -w '%{http_code}' \
    "$base_url/api/v1/configs/tool_servers" || true
)"
if [[ "$code" != "200" ]]; then
  echo "WARN: backup GET /api/v1/configs/tool_servers failed (http $code). Writing payload snapshot into backup file instead."
  printf '{\"note\":\"backup failed\",\"http_code\":\"%s\",\"payload\":%s}\n' "$code" "$payload" > "$backup_path"
fi

echo "Applying ${#import_files[@]} tool import files to Open WebUI ..."
curl -fsS \
  -H "Authorization: Bearer $token" \
  -H "Content-Type: application/json" \
  -X POST \
  "$base_url/api/v1/configs/tool_servers" \
  -d "$payload" \
  > /dev/null

echo "Done. Open WebUI should now list the tools under Admin → External Tools."
