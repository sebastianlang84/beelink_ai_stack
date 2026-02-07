#!/usr/bin/env bash
set -euo pipefail

BEGIN_MARK="# BEGIN AI_STACK_OPENCLAW_GATEWAY"
END_MARK="# END AI_STACK_OPENCLAW_GATEWAY"
TMP_CRON="$(mktemp)"
trap 'rm -f "$TMP_CRON"' EXIT

crontab -l 2>/dev/null | awk -v b="$BEGIN_MARK" -v e="$END_MARK" '
  index($0, b) == 1 { skip=1; next }
  index($0, e) == 1 { skip=0; next }
  !skip { print }
' >"$TMP_CRON" || true

crontab "$TMP_CRON"

echo "Removed OpenClaw gateway cron jobs (marked block only)"
echo "verify with: crontab -l"

