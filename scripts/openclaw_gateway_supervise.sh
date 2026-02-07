#!/usr/bin/env bash
set -euo pipefail

# Minimal, user-level supervisor for the host-native OpenClaw gateway.
# Rationale: systemd --user is not always available in non-login shells, and sudo may not be available.

PORT_DEFAULT="18789"
BIND_DEFAULT="loopback"

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/openclaw"
LOG_FILE="${STATE_DIR}/openclaw-gateway.log"
PID_FILE="${STATE_DIR}/openclaw-gateway.pid"

OPENCLAW_BIN="${OPENCLAW_BIN:-$(command -v openclaw || true)}"
PORT="${OPENCLAW_HOST_PORT:-${PORT_DEFAULT}}"
BIND="${OPENCLAW_BIND_MODE:-${BIND_DEFAULT}}"
RUN_USER="${RUN_USER:-$(id -un)}"

usage() {
  cat <<'USAGE'
Usage: scripts/openclaw_gateway_supervise.sh <cmd>

Commands:
  status   Print whether openclaw-gateway is running and on which PID.
  start    Start gateway if not running (nohup; logs to XDG_STATE_HOME).
  stop     Stop gateway (best-effort).
  ensure   Idempotent: start if not running; then run a lightweight probe.

Env overrides:
  OPENCLAW_BIN         Path to openclaw CLI (default: auto-detect).
  OPENCLAW_HOST_PORT   Port (default: 18789).
  OPENCLAW_BIND_MODE   Bind mode (default: loopback).
USAGE
}

require_openclaw() {
  if [[ -z "${OPENCLAW_BIN}" || ! -x "${OPENCLAW_BIN}" ]]; then
    echo "ERROR openclaw CLI not found in PATH (set OPENCLAW_BIN=...)" >&2
    exit 50
  fi
}

gateway_pid() {
  # Prefer PID file, fall back to process lookup.
  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && ps -p "${pid}" >/dev/null 2>&1; then
      echo "${pid}"
      return 0
    fi
  fi

  # Debian's proc comm name is capped to 15 chars; "openclaw-gateway" is longer and won't match with pgrep -x.
  # Use -f to match the full command line instead.
  pgrep -u "${RUN_USER}" -f '^openclaw-gateway(\\s|$)' 2>/dev/null | head -n 1 || true
}

is_running() {
  [[ -n "$(gateway_pid)" ]]
}

cmd_status() {
  local pid
  pid="$(gateway_pid)"
  if [[ -z "${pid}" ]]; then
    echo "openclaw-gateway: stopped"
    return 3
  fi
  echo "openclaw-gateway: running pid=${pid} bind=${BIND} port=${PORT}"
}

cmd_start() {
  require_openclaw
  mkdir -p "${STATE_DIR}"

  if is_running; then
    cmd_status
    return 0
  fi

  # Use --force so restarts after crashes don’t get stuck on stale listeners.
  nohup "${OPENCLAW_BIN}" gateway run \
    --bind "${BIND}" \
    --port "${PORT}" \
    --force \
    --compact \
    >>"${LOG_FILE}" 2>&1 &

  echo "$!" >"${PID_FILE}"
  sleep 0.3

  cmd_status || true
  echo "log_file=${LOG_FILE}"
}

cmd_stop() {
  local pid
  pid="$(gateway_pid)"
  if [[ -z "${pid}" ]]; then
    echo "openclaw-gateway: already stopped"
    return 0
  fi

  kill "${pid}" 2>/dev/null || true
  sleep 0.2
  kill -9 "${pid}" 2>/dev/null || true

  rm -f "${PID_FILE}" 2>/dev/null || true
  cmd_status || true
}

cmd_ensure() {
  cmd_start
  # Lightweight check: don’t fail the cron job just because probe is flaky at boot.
  "${OPENCLAW_BIN}" gateway probe >/dev/null 2>&1 || true
}

main() {
  local cmd="${1:-}"
  case "${cmd}" in
    status) cmd_status ;;
    start) cmd_start ;;
    stop) cmd_stop ;;
    ensure) cmd_ensure ;;
    -h|--help|"") usage; exit 2 ;;
    *) echo "ERROR unknown cmd: ${cmd}" >&2; usage; exit 2 ;;
  esac
}

main "$@"
