#!/usr/bin/env bash
set -euo pipefail

DEVTOOLS_REMOTE_PORT="${DEVTOOLS_REMOTE_PORT:-9223}"
BROWSER_URL="${BROWSER_URL:-http://127.0.0.1:${DEVTOOLS_REMOTE_PORT}}"
CHROME_MCP_BIN="${CHROME_MCP_BIN:-$HOME/.local/share/chrome-devtools-mcp/node_modules/.bin/chrome-devtools-mcp}"

if [[ ! -x "${CHROME_MCP_BIN}" ]]; then
  echo "Missing chrome-devtools-mcp binary at: ${CHROME_MCP_BIN}" >&2
  echo "Install once with:" >&2
  echo "  npm install --prefix \"$HOME/.local/share/chrome-devtools-mcp\" chrome-devtools-mcp@0.17.3" >&2
  exit 1
fi

exec "${CHROME_MCP_BIN}" --browserUrl "${BROWSER_URL}" --no-usage-statistics "$@"

