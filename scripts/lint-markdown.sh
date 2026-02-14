#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ $# -gt 0 ]]; then
  exec npx --yes markdownlint-cli2 --config .markdownlint-cli2.yaml "$@"
fi

exec npx --yes markdownlint-cli2 --config .markdownlint-cli2.yaml
