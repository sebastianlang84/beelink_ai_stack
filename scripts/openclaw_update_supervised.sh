#!/usr/bin/env bash
set -euo pipefail

# Safe update wrapper for hosts without systemd --user.
# Strategy:
# 1) run "openclaw update" with "--no-restart" to avoid failing on missing user bus
# 2) restart/ensure the gateway via local supervisor

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUPERVISOR_SCRIPT="${SCRIPT_DIR}/openclaw_gateway_supervise.sh"
OPENCLAW_BIN="${OPENCLAW_BIN:-$(command -v openclaw || true)}"

usage() {
  cat <<'USAGE'
Usage: scripts/openclaw_update_supervised.sh [openclaw update args]

Examples:
  ./scripts/openclaw_update_supervised.sh
  ./scripts/openclaw_update_supervised.sh --yes
  ./scripts/openclaw_update_supervised.sh --channel stable --yes
  ./scripts/openclaw_update_supervised.sh status
USAGE
}

require_bins() {
  if [[ -z "${OPENCLAW_BIN}" || ! -x "${OPENCLAW_BIN}" ]]; then
    echo "ERROR openclaw CLI not found in PATH (set OPENCLAW_BIN=...)" >&2
    exit 50
  fi
  if [[ ! -x "${SUPERVISOR_SCRIPT}" ]]; then
    echo "ERROR required script missing or not executable: ${SUPERVISOR_SCRIPT}" >&2
    exit 51
  fi
}

has_flag() {
  local needle="$1"
  shift || true
  local arg
  for arg in "$@"; do
    if [[ "${arg}" == "${needle}" ]]; then
      return 0
    fi
  done
  return 1
}

is_meta_subcommand() {
  local arg
  for arg in "$@"; do
    case "${arg}" in
      -*) continue ;;
      status|wizard) return 0 ;;
      *) return 1 ;;
    esac
  done
  return 1
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
  fi

  require_bins

  local -a raw_args=("$@")
  if [[ "${raw_args[0]:-}" == "update" || "${raw_args[0]:-}" == "--update" ]]; then
    raw_args=("${raw_args[@]:1}")
  fi

  local -a update_args=("${raw_args[@]}")
  local -a cmd=("${OPENCLAW_BIN}" update)

  if ! is_meta_subcommand "${update_args[@]}"; then
    if ! has_flag "--no-restart" "${update_args[@]}"; then
      cmd+=("--no-restart")
    fi
  fi
  cmd+=("${update_args[@]}")

  set +e
  "${cmd[@]}"
  local update_rc=$?
  set -e

  if is_meta_subcommand "${update_args[@]}"; then
    exit "${update_rc}"
  fi

  if ! "${SUPERVISOR_SCRIPT}" ensure; then
    echo "ERROR gateway ensure failed after update" >&2
    if [[ "${update_rc}" -eq 0 ]]; then
      exit 70
    fi
  fi

  exit "${update_rc}"
}

main "$@"
