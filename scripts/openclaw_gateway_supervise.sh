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
FORCE_KILL_LISTENER="${OPENCLAW_GATEWAY_FORCE:-0}"

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

is_listening() {
  ss -ltn 2>/dev/null | rg -q ":${PORT}\\b"
}

listen_pid() {
  # Best-effort PID lookup. Not all environments expose process info without sudo.
  local pid
  pid="$(
    ss -ltnp 2>/dev/null \
      | rg ":${PORT}\\b" \
      | perl -ne 'if(/pid=(\\d+)/){print "$1\\n"; exit 0}'
  )"
  if [[ -n "${pid}" ]]; then
    echo "${pid}"
    return 0
  fi

  pgrep -u "${RUN_USER}" -f 'openclaw-gateway' 2>/dev/null | head -n 1 || true
}

gateway_pid() {
  # Prefer PID file, fall back to process lookup.
  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && ps -p "${pid}" >/dev/null 2>&1; then
      # Ensure the PID file points at the actual gateway process (not a short-lived wrapper).
      local args
      args="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
      if [[ "${args}" =~ ^openclaw-gateway([[:space:]]|$) ]]; then
        echo "${pid}"
        return 0
      fi
      if [[ "${args}" =~ ^.*openclaw-gateway([[:space:]]|$) ]]; then
        echo "${pid}"
        return 0
      fi
      # Stale/incorrect PID file: ignore and fall back to process search.
    fi
  fi

  # Debian's proc comm name is capped to 15 chars; "openclaw-gateway" is longer and won't match with pgrep -x.
  # Use -f to match the full command line instead.
  pgrep -u "${RUN_USER}" -f 'openclaw-gateway' 2>/dev/null | head -n 1 || true
}

is_running() {
  is_listening
}

cmd_status() {
  if ! is_listening; then
    echo "openclaw-gateway: stopped"
    return 3
  fi

  local pid
  pid="$(listen_pid)"
  if [[ -n "${pid}" ]]; then
    echo "openclaw-gateway: running pid=${pid} bind=${BIND} port=${PORT}"
  else
    echo "openclaw-gateway: running pid=? bind=${BIND} port=${PORT}"
  fi
}

cmd_start() {
  require_openclaw
  mkdir -p "${STATE_DIR}"

  if is_running; then
    cmd_status
    return 0
  fi

  local force_flag=()
  if [[ "${FORCE_KILL_LISTENER}" == "1" ]]; then
    force_flag+=(--force)
  fi

  nohup "${OPENCLAW_BIN}" gateway run \
    --bind "${BIND}" \
    --port "${PORT}" \
    --compact \
    "${force_flag[@]}" \
    >>"${LOG_FILE}" 2>&1 &

  # The CLI may exec/spawn into the real gateway process; record the actual listener PID when possible.
  echo "$!" >"${PID_FILE}"
  sleep 0.6
  local pid
  pid="$(listen_pid)"
  if [[ -n "${pid}" ]]; then
    echo "${pid}" >"${PID_FILE}"
  fi

  cmd_status || true
  echo "log_file=${LOG_FILE}"
}

cmd_stop() {
  local pid
  pid="$(listen_pid)"
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
