#!/usr/bin/env bash
set -euo pipefail

# Redact likely secret values from stdin.
#
# Supports:
# - env style: KEY=value
# - yaml style: KEY: value
#
# Intended for safe sharing of outputs like:
#   docker compose --env-file /etc/ai-stack/secrets.env config | ./scripts/redact_secrets_output.sh

sed -E \
  -e 's/^([[:space:]]*[A-Z0-9_]*(API_KEY|TOKEN|PASSWORD|SECRET|PRIVATE_KEY)[A-Z0-9_]*[[:space:]]*=[[:space:]]*).*/\1***REDACTED***/I' \
  -e 's/^([[:space:]]*[A-Z0-9_]*(API_KEY|TOKEN|PASSWORD|SECRET|PRIVATE_KEY)[A-Z0-9_]*[[:space:]]*:[[:space:]]*).*/\1***REDACTED***/I'
