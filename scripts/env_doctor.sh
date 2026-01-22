#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Validate repo-local env files for ai_stack.

Default layout:
  - Shared secrets:         .env
  - Shared config:          .config.env
  - Service config:         <service>/.config.env

Usage:
  ./scripts/env_doctor.sh [--secrets .env] [--config .config.env] [--service-config <path/to/service/.config.env>]...

Checks:
  - `.env` contains required shared secrets for P0 (owui + tm)
  - `.env` does not contain obvious non-secret config keys (guardrail)
  - config env files do not contain secrets keys (guardrail)
EOF
}

secrets_env=".env"
config_env=".config.env"
service_config_envs=()

while [[ "${1:-}" == --* || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; do
  case "${1:-}" in
    --secrets)
      secrets_env="${2:-}"
      shift 2
      ;;
    --config)
      config_env="${2:-}"
      shift 2
      ;;
    --service-config)
      service_config_envs+=("${2:-}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown flag: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

require_file() {
  local label="$1"
  local path="$2"
  if [[ ! -e "$path" ]]; then
    echo "ERROR: missing ${label}: $path" >&2
    exit 1
  fi
}

require_file "secrets env file" "$secrets_env"

read_keys() {
  local file="$1"
  awk -F= '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    /^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=/ {
      key=$1
      sub(/^[[:space:]]+/, "", key)
      sub(/[[:space:]]+$/, "", key)
      print key
    }
  ' "$file" | sort -u
}

has_nonempty() {
  local file="$1"
  local key="$2"
  local value
  value="$(sed -n "s/^${key}=//p" "$file" | tail -n 1 | tr -d '\r')"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  [[ -n "$value" ]]
}

echo "==> Checking secrets env: $secrets_env"

required_shared=(WEBUI_SECRET_KEY YOUTUBE_API_KEY OPENROUTER_API_KEY)
missing=()
empty=()
for key in "${required_shared[@]}"; do
  if ! rg -n --no-line-number "^${key}=" "$secrets_env" >/dev/null 2>&1; then
    missing+=("$key")
  elif ! has_nonempty "$secrets_env" "$key"; then
    empty+=("$key")
  fi
done
if ((${#missing[@]} > 0)); then
  echo "ERROR: missing required keys in $secrets_env:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi
if ((${#empty[@]} > 0)); then
  echo "ERROR: required keys present but empty in $secrets_env:" >&2
  printf '  - %s\n' "${empty[@]}" >&2
  exit 1
fi

auth_keys=(OPEN_WEBUI_API_KEY OWUI_API_KEY)
has_auth=0
for key in "${auth_keys[@]}"; do
  if rg -n --no-line-number "^${key}=" "$secrets_env" >/dev/null 2>&1 && has_nonempty "$secrets_env" "$key"; then
    has_auth=1
    break
  fi
done
if [[ "$has_auth" -ne 1 ]]; then
  echo "ERROR: missing Open WebUI API auth key in $secrets_env (one of: OPEN_WEBUI_API_KEY, OWUI_API_KEY)" >&2
  exit 1
fi

forbidden_in_secrets=(
  '^OPEN_WEBUI_KNOWLEDGE_ID$'
  '^OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON$'
  '^OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON_PATH$'
  '^OPEN_WEBUI_BASE_URL$'
  '^YOUTUBE_COOKIES_FILE$'
  '(_DIR_HOST)$'
  '(_OUTPUT_ROOT_HOST)$'
  '(_HOST_PORT)$'
  '(_BIND_ADDRESS)$'
)
while IFS= read -r key; do
  for rx in "${forbidden_in_secrets[@]}"; do
    if [[ "$key" =~ $rx ]]; then
      echo "ERROR: non-secret key found in secrets file ($secrets_env): $key" >&2
      echo "Move it to a config env file (.config.env / <service>/.config.env)." >&2
      exit 1
    fi
  done
done < <(read_keys "$secrets_env")

secret_keys_regex='^(OPENAI_API_KEY|OPENROUTER_API_KEY|TAVILY_API_KEY|WEBSHARE_API_KEY|YOUTUBE_API_KEY|OPEN_WEBUI_API_KEY|OWUI_API_KEY|WEBUI_SECRET_KEY|QDRANT_API_KEY)='

check_config_no_secrets() {
  local label="$1"
  local path="$2"
  if [[ -z "$path" || ! -e "$path" ]]; then
    return 0
  fi
  if rg -n "$secret_keys_regex" "$path" >/dev/null 2>&1; then
    echo "ERROR: secrets-like keys found in ${label}: $path" >&2
    echo "Move secrets to: $secrets_env" >&2
    exit 1
  fi
}

check_config_no_secrets "shared config env" "$config_env"
for svc in "${service_config_envs[@]}"; do
  require_file "service config env file" "$svc"
  check_config_no_secrets "service config env" "$svc"
  echo "==> Found service config env: $svc"
done

echo "OK: env validation"
