#!/usr/bin/env bash
set -euo pipefail

REASON="manual"
if [[ "${1:-}" == "--reason" && -n "${2:-}" ]]; then
  REASON="$2"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_SCRIPT="${SCRIPT_DIR}/check_codex_auth_dns.sh"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack"
LOG_FILE="${STATE_DIR}/codex-auth-dns-guard.log"
LOCK_FILE="${STATE_DIR}/codex-auth-dns-guard.lock"

mkdir -p "$STATE_DIR"

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "$(date -Is) skip reason=${REASON} lock=busy" >>"$LOG_FILE"
    exit 0
  fi
fi

{
  echo "$(date -Is) start reason=${REASON} action=set_accept_dns_false"

  if tailscale set --accept-dns=false >/dev/null 2>&1; then
    echo "$(date -Is) tailscale_set=ok"
  else
    echo "$(date -Is) tailscale_set=failed"
    exit 41
  fi

  if "$CHECK_SCRIPT" --quiet; then
    echo "$(date -Is) verify=ok"
  else
    rc=$?
    echo "$(date -Is) verify=failed rc=${rc}"
    exit "$rc"
  fi

  echo "$(date -Is) done reason=${REASON}"
} >>"$LOG_FILE" 2>&1
