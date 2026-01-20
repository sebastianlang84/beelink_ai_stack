#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Smoke-test for ai_stack P0 (Open WebUI + Transcript Miner tool).

Checks (offline / localhost-only):
  - ai-stack docker network exists (creates it if missing)
  - secrets file passes ./scripts/secrets_env_doctor.sh (unless --skip-secrets-doctor)
  - docker compose config succeeds for required stacks
  - containers are running + healthy (if --up)
  - Open WebUI responds on http://127.0.0.1:3000
  - Transcript Miner tool responds on /healthz inside the container
  - Tool can reach Open WebUI API /api/v1/files/ (auth required)

Usage:
  ./scripts/smoke_test_ai_stack.sh [--env-file /etc/ai-stack/secrets.env] [--up] [--build]

Options:
  --env-file PATH          Secrets env file path (default: /etc/ai-stack/secrets.env)
  --up                     Bring stacks up (recommended for first run)
  --build                  Build mcp-transcript-miner image when starting
  --skip-secrets-doctor    Skip secrets validation (useful for Open WebUI-only checks)
  -h, --help               Show this help
EOF
}

if [[ -e "/etc/ai-stack/secrets.env" ]]; then
  env_file="/etc/ai-stack/secrets.env"
else
  env_file="/etc/ai_stack/secrets.env"
fi
do_up="false"
do_build="false"
skip_secrets_doctor="false"

while [[ "${1:-}" == --* || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; do
  case "${1:-}" in
    --env-file)
      env_file="${2:-}"
      shift 2
      ;;
    --up)
      do_up="true"
      shift
      ;;
    --build)
      do_build="true"
      shift
      ;;
    --skip-secrets-doctor)
      skip_secrets_doctor="true"
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
require_cmd curl

echo "==> Ensuring docker network: ai-stack"
if ! docker network inspect ai-stack >/dev/null 2>&1; then
  ./scripts/create_ai_stack_network.sh
fi

if [[ "$skip_secrets_doctor" != "true" ]]; then
  echo "==> Validating secrets file: $env_file"
  ./scripts/secrets_env_doctor.sh "$env_file" >/dev/null
  echo "OK: secrets validation"
else
  echo "==> Skipping secrets validation (--skip-secrets-doctor)"
fi

echo "==> Compose config validation (with --env-file)"
docker compose --env-file "$env_file" -f open-webui/docker-compose.yml config >/dev/null
docker compose --env-file "$env_file" -f mcp-transcript-miner/docker-compose.yml config >/dev/null
echo "OK: compose config"

if [[ "$do_up" == "true" ]]; then
  echo "==> Starting Open WebUI"
  docker compose --env-file "$env_file" -f open-webui/docker-compose.yml up -d

  echo "==> Starting Transcript Miner tool"
  if [[ "$do_build" == "true" ]]; then
    docker compose --env-file "$env_file" -f mcp-transcript-miner/docker-compose.yml up -d --build
  else
    docker compose --env-file "$env_file" -f mcp-transcript-miner/docker-compose.yml up -d
  fi
fi

wait_healthy() {
  local compose_file="$1"
  local service="$2"
  local timeout_seconds="${3:-180}"
  local start
  start="$(date +%s)"

  while true; do
    local cid
    cid="$(docker compose --env-file "$env_file" -f "$compose_file" ps -q "$service" 2>/dev/null || true)"
    if [[ -z "$cid" ]]; then
      echo "WAIT: container not created yet ($compose_file:$service)"
      sleep 2
      continue
    fi

    local status health
    status="$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || true)"
    health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$cid" 2>/dev/null || true)"

    if [[ "$status" != "running" ]]; then
      echo "WAIT: $service status=$status"
    elif [[ -z "$health" || "$health" == "healthy" ]]; then
      echo "OK: $service status=$status health=${health:-n/a}"
      return 0
    else
      echo "WAIT: $service status=$status health=$health"
    fi

    local now
    now="$(date +%s)"
    if (( now - start > timeout_seconds )); then
      echo "ERROR: timeout waiting for healthy service: $compose_file:$service" >&2
      docker compose --env-file "$env_file" -f "$compose_file" ps || true
      docker compose --env-file "$env_file" -f "$compose_file" logs --tail 200 "$service" || true
      return 1
    fi
    sleep 2
  done
}

echo "==> Health checks"
wait_healthy open-webui/docker-compose.yml owui 240
wait_healthy mcp-transcript-miner/docker-compose.yml tm 240

echo "==> HTTP checks (host)"
code="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/ || true)"
if [[ "$code" != "200" ]]; then
  echo "ERROR: Open WebUI not responding as expected (http://127.0.0.1:3000/ -> $code)" >&2
  exit 1
fi
echo "OK: Open WebUI http://127.0.0.1:3000/ -> $code"

echo "==> Tool service checks (inside container)"
docker compose --env-file "$env_file" -f mcp-transcript-miner/docker-compose.yml exec -T tm python - <<'PY'
import os
import sys
import urllib.request

def must_get(url: str, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read()
        return resp.status, body

status, _ = must_get("http://127.0.0.1:8000/healthz")
if status != 200:
    print(f"ERROR: tool /healthz returned {status}", file=sys.stderr)
    sys.exit(1)
print("OK: tool /healthz")

base_url = os.environ.get("OPEN_WEBUI_BASE_URL", "http://owui:8080").rstrip("/")
token = (os.environ.get("OPEN_WEBUI_API_KEY") or os.environ.get("OWUI_API_KEY") or "").strip()
if not token:
    print("SKIP: Open WebUI API auth not set (OPEN_WEBUI_API_KEY/OWUI_API_KEY).", file=sys.stderr)
    sys.exit(0)

status, _ = must_get(f"{base_url}/api/v1/files/", headers={"Authorization": f"Bearer {token}"})
if status != 200:
    print(f"ERROR: Open WebUI API /api/v1/files/ returned {status}", file=sys.stderr)
    sys.exit(1)
print("OK: tool -> Open WebUI API /api/v1/files/")
PY

echo "OK: smoke test passed"
