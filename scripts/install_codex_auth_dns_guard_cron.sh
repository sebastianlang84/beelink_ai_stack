#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CHECK_SCRIPT="${SCRIPT_DIR}/check_codex_auth_dns.sh"
REMEDIATE_SCRIPT="${SCRIPT_DIR}/remediate_codex_auth_dns.sh"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack"
LOG_FILE="${STATE_DIR}/codex-auth-dns-guard.log"

if [[ ! -x "$CHECK_SCRIPT" || ! -x "$REMEDIATE_SCRIPT" ]]; then
  echo "ERROR required scripts are missing or not executable"
  exit 50
fi

mkdir -p "$STATE_DIR"

BEGIN_MARK="# BEGIN AI_STACK_CODEX_AUTH_DNS_GUARD"
END_MARK="# END AI_STACK_CODEX_AUTH_DNS_GUARD"
TMP_CRON="$(mktemp)"
trap 'rm -f "$TMP_CRON"' EXIT

crontab -l 2>/dev/null | awk -v b="$BEGIN_MARK" -v e="$END_MARK" '
  index($0, b) == 1 { skip=1; next }
  index($0, e) == 1 { skip=0; next }
  !skip { print }
' >"$TMP_CRON" || true

cat >>"$TMP_CRON" <<CRON
${BEGIN_MARK}
@reboot /bin/bash -lc '${REMEDIATE_SCRIPT} --reason reboot >> ${LOG_FILE} 2>&1'
*/10 * * * * /bin/bash -lc '${CHECK_SCRIPT} --quiet || ${REMEDIATE_SCRIPT} --reason periodic >> ${LOG_FILE} 2>&1'
${END_MARK}
CRON

crontab "$TMP_CRON"

echo "Installed Codex auth DNS guard cron jobs"
echo "repo_root=${REPO_ROOT}"
echo "log_file=${LOG_FILE}"
echo "verify with: crontab -l"
