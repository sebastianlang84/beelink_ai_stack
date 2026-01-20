#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Provision shared Docker objects for ai_stack (SSOT naming).

Creates (idempotent):
  - external network: ai-stack
  - named volumes:
      owui-data
      tm-data
      context6-data
      context6-cache
      qdrant-data
      emb-bench-cache

Usage:
  ./scripts/provision_ai_stack_docker_objects.sh
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: missing command: $cmd" >&2
    exit 1
  fi
}

require_cmd docker

ensure_network() {
  local name="$1"
  if docker network inspect "$name" >/dev/null 2>&1; then
    return 0
  fi
  docker network create "$name" >/dev/null
}

ensure_volume() {
  local name="$1"
  if docker volume inspect "$name" >/dev/null 2>&1; then
    return 0
  fi
  docker volume create "$name" >/dev/null
}

echo "==> Network"
ensure_network ai-stack

echo "==> Volumes"
ensure_volume owui-data
ensure_volume tm-data
ensure_volume context6-data
ensure_volume context6-cache
ensure_volume qdrant-data
ensure_volume emb-bench-cache

echo "OK: provisioned docker objects"
