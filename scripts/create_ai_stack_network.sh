#!/usr/bin/env bash
set -euo pipefail

NETWORK_NAME="${1:-ai_stack}"

if docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
  echo "docker network '${NETWORK_NAME}' already exists"
  exit 0
fi

docker network create "${NETWORK_NAME}" >/dev/null
echo "created docker network '${NETWORK_NAME}'"

