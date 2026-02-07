#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  ./scripts/tavily_search.sh <query> [max_results]

Notes:
  - Reads TAVILY_API_KEY from the environment or from repo-local .env (gitignored).
  - Does not print the API key.
EOF
}

json_escape() {
  local s="${1-}"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  printf '%s' "$s"
}

query="${1-}"
max_results="${2-5}"

if [[ -z "$query" ]]; then
  usage
  exit 2
fi

if ! [[ "$max_results" =~ ^[0-9]+$ ]]; then
  echo "error: max_results must be an integer" >&2
  exit 2
fi

key="${TAVILY_API_KEY-}"
if [[ -z "$key" ]] && [[ -f .env ]]; then
  # .env is secrets-only (gitignored). We intentionally avoid 'set -x' or echoing values.
  key="$(sed -n 's/^TAVILY_API_KEY=//p' .env | tail -n 1 || true)"
fi

if [[ -z "$key" ]]; then
  echo "error: TAVILY_API_KEY not set and .env does not contain TAVILY_API_KEY" >&2
  exit 2
fi

payload="$(mktemp)"
response="$(mktemp)"
trap 'rm -f "$payload" "$response"' EXIT

q_esc="$(json_escape "$query")"
key_esc="$(json_escape "$key")"

cat >"$payload" <<EOF
{"api_key":"$key_esc","query":"$q_esc","search_depth":"basic","max_results":$max_results}
EOF

http_code="$(
  curl -sS -o "$response" -w "%{http_code}" \
    -H 'Content-Type: application/json' \
    --data-binary @"$payload" \
    https://api.tavily.com/search || true
)"

if [[ "$http_code" != "200" ]]; then
  echo "error: tavily search failed (http $http_code)" >&2
  if command -v jq >/dev/null 2>&1; then
    jq -c '{error:(.error//null), message:(.message//null)}' "$response" 2>/dev/null || true
  else
    head -c 400 "$response" | tr '\n' ' ' >&2 || true
    echo >&2
  fi
  exit 1
fi

if command -v jq >/dev/null 2>&1; then
  jq -r '
    if (.results | type) != "array" then
      "No results array in response."
    else
      .results[]
      | "\(.title)\n\(.url)\n\((.content // "") | tostring | gsub("\\s+"; " ") | .[0:240])\n"
    end
  ' "$response"
else
  cat "$response"
fi
