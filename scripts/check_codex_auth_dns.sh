#!/usr/bin/env bash
set -euo pipefail

QUIET=0
if [[ "${1:-}" == "--quiet" ]]; then
  QUIET=1
fi

AUTH_HOST="auth.openai.com"
AUTH_TOKEN_URL="https://auth.openai.com/oauth/token"

log() {
  if [[ "$QUIET" -eq 0 ]]; then
    echo "$*"
  fi
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "ERROR missing command: $1"
    exit 10
  fi
}

require_cmd tailscale
require_cmd jq
require_cmd curl
require_cmd getent

if ! tailscale status --json >/dev/null 2>&1; then
  log "ERROR tailscale status unavailable"
  exit 11
fi

corp_dns="$(tailscale debug prefs | jq -r '.CorpDNS // false')"
resolver_lines="$(grep -E '^nameserver ' /etc/resolv.conf || true)"
lookup_ok=1
http_code="000"

if ! getent hosts "$AUTH_HOST" >/dev/null 2>&1; then
  lookup_ok=0
fi

http_code="$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$AUTH_TOKEN_URL" || true)"
http_code="${http_code:-000}"

log "corp_dns=${corp_dns}"
if [[ -n "$resolver_lines" ]]; then
  log "resolvers=$(echo "$resolver_lines" | awk '{print $2}' | paste -sd ',' -)"
else
  log "resolvers=unknown"
fi
log "lookup_${AUTH_HOST}=${lookup_ok}"
log "oauth_token_http_code=${http_code}"

if [[ "$corp_dns" == "true" ]]; then
  log "ERROR tailscale DNS override is enabled"
  exit 21
fi

if [[ "$lookup_ok" -ne 1 ]]; then
  log "ERROR DNS lookup failed for ${AUTH_HOST}"
  exit 31
fi

if [[ "$http_code" == "000" ]]; then
  log "ERROR OAuth token endpoint unreachable"
  exit 32
fi

if [[ "$http_code" =~ ^5 ]]; then
  log "ERROR OAuth token endpoint returned 5xx (${http_code})"
  exit 33
fi

log "OK codex auth DNS check passed"
