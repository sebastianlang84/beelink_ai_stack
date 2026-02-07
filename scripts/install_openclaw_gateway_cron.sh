#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SUPERVISOR_SCRIPT="${SCRIPT_DIR}/openclaw_gateway_supervise.sh"

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/openclaw"
LOG_FILE="${STATE_DIR}/openclaw-gateway-cron.log"

if [[ ! -x "${SUPERVISOR_SCRIPT}" ]]; then
  echo "ERROR required script missing or not executable: ${SUPERVISOR_SCRIPT}" >&2
  exit 50
fi

mkdir -p "${STATE_DIR}"

BEGIN_MARK="# BEGIN AI_STACK_OPENCLAW_GATEWAY"
END_MARK="# END AI_STACK_OPENCLAW_GATEWAY"
TMP_CRON="$(mktemp)"
trap 'rm -f "$TMP_CRON"' EXIT

crontab -l 2>/dev/null | awk -v b="$BEGIN_MARK" -v e="$END_MARK" '
  index($0, b) == 1 { skip=1; next }
  index($0, e) == 1 { skip=0; next }
  !skip { print }
' >"$TMP_CRON" || true

cat >>"$TMP_CRON" <<CRON
${BEGIN_MARK}
@reboot /bin/bash -lc '${SUPERVISOR_SCRIPT} ensure >> ${LOG_FILE} 2>&1'
*/5 * * * * /bin/bash -lc '${SUPERVISOR_SCRIPT} ensure >> ${LOG_FILE} 2>&1'
${END_MARK}
CRON

crontab "$TMP_CRON"

echo "Installed OpenClaw gateway cron jobs"
echo "repo_root=${REPO_ROOT}"
echo "log_file=${LOG_FILE}"
echo "verify with: crontab -l"

