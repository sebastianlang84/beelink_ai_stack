#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Migrate ai_stack naming (v1) to the new SSOT scheme:
  - external docker network: ai-stack
  - docker volumes: owui-data, tm-data, context6-data, context6-cache, qdrant-data, emb-bench-cache

This script is intentionally conservative:
  - It copies data from old volumes to new volumes (does not delete old by default).
  - It can optionally delete old volumes/networks when --cleanup-old is set.

Usage:
  ./scripts/migrate_ai_stack_naming_v1.sh [--env-file /etc/ai-stack/secrets.env] [--cleanup-old]

Options:
  --env-file PATH     Secrets env file (default: /etc/ai-stack/secrets.env, fallback: /etc/ai_stack/secrets.env)
  --cleanup-old       Delete old volumes/networks after successful migration + smoke test.
  -h, --help          Show help
EOF
}

env_file="/etc/ai-stack/secrets.env"
if [[ ! -e "$env_file" && -e "/etc/ai_stack/secrets.env" ]]; then
  env_file="/etc/ai_stack/secrets.env"
fi
cleanup_old="false"

while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --env-file)
      env_file="${2:-}"
      shift 2
      ;;
    --cleanup-old)
      cleanup_old="true"
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

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: missing command: $cmd" >&2
    exit 1
  fi
}

require_cmd docker
if [[ ! -e "$env_file" ]]; then
  echo "ERROR: secrets env file not found: $env_file" >&2
  exit 1
fi

echo "==> Ensuring docker network: ai-stack"
if ! docker network inspect ai-stack >/dev/null 2>&1; then
  docker network create ai-stack >/dev/null
fi

copy_volume_if_exists() {
  local old="$1"
  local new="$2"

  if ! docker volume inspect "$old" >/dev/null 2>&1; then
    echo "SKIP: old volume not found: $old"
    return 0
  fi
  if ! docker volume inspect "$new" >/dev/null 2>&1; then
    docker volume create "$new" >/dev/null
  fi

  echo "==> Copying volume: $old -> $new"
  docker run --rm \
    -v "${old}:/from:ro" \
    -v "${new}:/to" \
    alpine:3.20 \
    sh -euc 'cd /from && tar cf - . | tar xf - -C /to' >/dev/null
}

find_legacy_volume_by_labels() {
  # Finds a single legacy volume name by docker-compose labels, without hardcoding the actual volume name string.
  local compose_volume_label="$1"   # e.g. open_webui_data
  local out
  out="$(
    docker volume ls -q \
      --filter "label=com.docker.compose.volume=${compose_volume_label}" \
      | head -n 1
  )"
  printf "%s" "$out"
}

echo "==> Migrating volumes (copy)"
copy_volume_if_exists ai-stack-open-webui-data owui-data
copy_volume_if_exists ai-stack-mcp-transcript-miner-data tm-data
copy_volume_if_exists ai-stack-mcp-context6-data context6-data
copy_volume_if_exists ai-stack-mcp-context6-cache context6-cache
copy_volume_if_exists ai-stack-qdrant-data qdrant-data
copy_volume_if_exists ai-stack-emb-bench-cache emb-bench-cache

echo "==> Stopping old containers (by legacy names, ignore if missing)"
for c in \
  owui tm context6 qdrant \
  ai-stack-open-webui-openwebui-1 ai-stack-mcp-transcript-miner-tm-tool-1 ai-stack-mcp-context6-context6-1 ai-stack-qdrant-qdrant-1 \
  open-webui mcp-transcript-miner mcp-context6 \
; do
  docker rm -f "$c" >/dev/null 2>&1 || true
done

echo "==> Starting stacks with new compose (build where needed)"
docker compose --env-file "$env_file" -f open-webui/docker-compose.yml up -d
docker compose --env-file "$env_file" -f mcp-transcript-miner/docker-compose.yml up -d --build
docker compose --env-file "$env_file" -f mcp-context6/docker-compose.yml up -d --build
docker compose --env-file "$env_file" -f qdrant/docker-compose.yml up -d

echo "==> Smoke test"
./scripts/smoke_test_ai_stack.sh --env-file "$env_file" --up --build

if [[ "$cleanup_old" == "true" ]]; then
  echo "==> Cleanup old networks/volumes (best-effort)"
  legacy_openwebui_default_net_id="$(docker network ls -q --filter label=com.docker.compose.project=open-webui --filter label=com.docker.compose.network=default | head -n 1)"
  [[ -n "$legacy_openwebui_default_net_id" ]] && docker network rm "$legacy_openwebui_default_net_id" >/dev/null 2>&1 || true

  docker network rm ai_stack >/dev/null 2>&1 || true

  docker volume rm ai-stack-open-webui-data >/dev/null 2>&1 || true
  docker volume rm ai-stack-mcp-transcript-miner-data >/dev/null 2>&1 || true
  docker volume rm ai-stack-mcp-context6-data >/dev/null 2>&1 || true
  docker volume rm ai-stack-mcp-context6-cache >/dev/null 2>&1 || true
  docker volume rm ai-stack-qdrant-data >/dev/null 2>&1 || true
  docker volume rm ai-stack-emb-bench-cache >/dev/null 2>&1 || true

  # Remove legacy images from the previous naming scheme (best-effort).
  docker rmi ai-stack/mcp-transcript-miner:latest ai-stack/mcp-transcript-miner:dev >/dev/null 2>&1 || true
  docker rmi ai-stack/mcp-context6:latest ai-stack/mcp-context6:dev >/dev/null 2>&1 || true
fi

echo "OK: migration complete"
