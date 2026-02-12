#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OWUI_CONTAINER="${OWUI_CONTAINER:-owui}"
OWUI_HEALTH_URL="${OWUI_HEALTH_URL:-http://127.0.0.1:3000/}"
OWUI_WAIT_SECONDS="${OWUI_WAIT_SECONDS:-60}"
OWUI_WAIT_INTERVAL_SECONDS="${OWUI_WAIT_INTERVAL_SECONDS:-3}"

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

usage() {
  cat <<'USAGE'
Usage: scripts/ensure-owui-up.sh <cmd>

Commands:
  status  Print current OWUI container/app status (no changes).
  ensure  Idempotent check; auto-recovers OWUI via docker compose when needed.
  recover Force recovery (`docker compose up -d owui`) and verify health.

Environment overrides:
  OWUI_CONTAINER              Default: owui
  OWUI_HEALTH_URL             Default: http://127.0.0.1:3000/
  OWUI_WAIT_SECONDS           Default: 60
  OWUI_WAIT_INTERVAL_SECONDS  Default: 3
USAGE
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "ERROR missing command: $1"
    exit 50
  fi
}

container_running() {
  docker ps --format '{{.Names}}' | grep -qx "${OWUI_CONTAINER}"
}

container_health() {
  docker inspect --format '{{if .State.Running}}{{if .State.Health}}{{.State.Health.Status}}{{else}}running_no_healthcheck{{end}}{{else}}stopped{{end}}' "${OWUI_CONTAINER}" 2>/dev/null || echo "missing"
}

http_code() {
  curl -sS -o /dev/null --connect-timeout 3 --max-time 8 -w '%{http_code}' "${OWUI_HEALTH_URL}" || echo "000"
}

http_ok() {
  local code
  code="$(http_code)"
  [[ "${code}" =~ ^[23] ]]
}

compose_env_args() {
  local env_file
  for env_file in \
    "${REPO_ROOT}/.env" \
    "${REPO_ROOT}/.config.env" \
    "${REPO_ROOT}/open-webui/.config.env"
  do
    if [[ -f "${env_file}" ]]; then
      printf -- '--env-file\n%s\n' "${env_file}"
    fi
  done
}

compose_up_owui() {
  local args=()
  local line
  while IFS= read -r line; do
    args+=("${line}")
  done < <(compose_env_args)

  log "recover: docker compose up -d owui"
  docker compose "${args[@]}" -f "${REPO_ROOT}/open-webui/docker-compose.yml" up -d owui
}

wait_until_healthy() {
  local deadline now code
  deadline=$(( $(date +%s) + OWUI_WAIT_SECONDS ))
  while true; do
    if http_ok; then
      code="$(http_code)"
      log "ok: http=${code} container_health=$(container_health)"
      return 0
    fi

    now="$(date +%s)"
    if (( now >= deadline )); then
      code="$(http_code)"
      log "ERROR timeout waiting for OWUI health (http=${code}, container_health=$(container_health))"
      return 1
    fi
    sleep "${OWUI_WAIT_INTERVAL_SECONDS}"
  done
}

cmd_status() {
  local running health code
  if container_running; then
    running="yes"
  else
    running="no"
  fi
  health="$(container_health)"
  code="$(http_code)"
  log "status: running=${running} health=${health} http=${code} url=${OWUI_HEALTH_URL}"

  if [[ "${running}" == "yes" ]] && [[ "${code}" =~ ^[23] ]]; then
    return 0
  fi
  return 3
}

cmd_recover() {
  compose_up_owui
  wait_until_healthy
}

cmd_ensure() {
  local health code
  health="$(container_health)"
  code="$(http_code)"

  if container_running && [[ "${health}" != "unhealthy" ]] && [[ "${code}" =~ ^[23] ]]; then
    log "ok: running=yes health=${health} http=${code}"
    return 0
  fi

  log "degraded: running=$(container_running && echo yes || echo no) health=${health} http=${code}; starting recovery"
  cmd_recover
}

main() {
  require_cmd docker
  require_cmd curl

  case "${1:-}" in
    status) cmd_status ;;
    ensure) cmd_ensure ;;
    recover) cmd_recover ;;
    -h|--help|"") usage; exit 2 ;;
    *) log "ERROR unknown command: ${1}"; usage; exit 2 ;;
  esac
}

main "${1:-}"
