#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_SCRIPT="${SCRIPT_DIR}/openclaw_update_supervised.sh"
BASHRC="${HOME}/.bashrc"

if [[ ! -x "${WRAPPER_SCRIPT}" ]]; then
  echo "ERROR required script missing or not executable: ${WRAPPER_SCRIPT}" >&2
  exit 50
fi

BEGIN_MARK="# BEGIN AI_STACK_OPENCLAW_UPDATE_GUARD"
END_MARK="# END AI_STACK_OPENCLAW_UPDATE_GUARD"
TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

if [[ -f "${BASHRC}" ]]; then
  awk -v b="${BEGIN_MARK}" -v e="${END_MARK}" '
    index($0, b) == 1 { skip=1; next }
    index($0, e) == 1 { skip=0; next }
    !skip { print }
  ' "${BASHRC}" >"${TMP_FILE}"
else
  : >"${TMP_FILE}"
fi

cat >>"${TMP_FILE}" <<EOF
${BEGIN_MARK}
openclaw() {
  if [[ "\$#" -gt 0 ]] && [[ "\$1" == "update" || "\$1" == "--update" ]]; then
    "${WRAPPER_SCRIPT}" "\$@"
    return \$?
  fi
  command openclaw "\$@"
}
${END_MARK}
EOF

mv "${TMP_FILE}" "${BASHRC}"
echo "Installed OpenClaw update guard into ${BASHRC}"
echo "Reload with: source ${BASHRC}"
