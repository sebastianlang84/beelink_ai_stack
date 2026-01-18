#!/usr/bin/env bash
set -euo pipefail

SECRETS_FILE="${1:-/etc/ai_stack/secrets.env}"

required_keys=(
  WEBUI_SECRET_KEY
  YOUTUBE_API_KEY
  OPENROUTER_API_KEY
)

optional_keys=(
  OPENAI_API_KEY
  OPEN_WEBUI_API_KEY
  OWUI_API_KEY
  OPEN_WEBUI_KNOWLEDGE_ID
  OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON
  OPEN_WEBUI_BASE_URL
  YOUTUBE_COOKIES_FILE
  HTTP_PROXY
  HTTPS_PROXY
  NO_PROXY
)

_stat() {
  local fmt="$1"
  if stat -c "$fmt" "$SECRETS_FILE" >/dev/null 2>&1; then
    stat -c "$fmt" "$SECRETS_FILE"
  else
    sudo stat -c "$fmt" "$SECRETS_FILE"
  fi
}

echo "Secrets doctor: ${SECRETS_FILE}"

if [[ ! -e "$SECRETS_FILE" ]]; then
  echo "ERROR: secrets file not found: ${SECRETS_FILE}"
  echo "Create it via: sudo mkdir -p /etc/ai_stack && sudo touch ${SECRETS_FILE} && sudo chmod 600 ${SECRETS_FILE}"
  exit 1
fi

if [[ ! -r "$SECRETS_FILE" ]]; then
  echo "ERROR: secrets file not readable (current user). Try: sudo chmod 600 ${SECRETS_FILE} && sudo chown $USER:$USER ${SECRETS_FILE}"
  exit 1
fi

mode="$(_stat '%a')"
owner="$(_stat '%U:%G')"

if [[ "$mode" != "600" ]]; then
  echo "WARN: permissions should be 600, got ${mode} (fix: sudo chmod 600 ${SECRETS_FILE})"
fi
echo "OK: owner=${owner} mode=${mode}"

missing_required=()
for key in "${required_keys[@]}"; do
  if ! rg -n --no-line-number "^${key}=" "$SECRETS_FILE" >/dev/null 2>&1; then
    missing_required+=("$key")
  fi
done

if ((${#missing_required[@]} > 0)); then
  echo "ERROR: missing required keys:"
  for key in "${missing_required[@]}"; do
    echo "  - ${key}"
  done
  echo "See: docs/runbook_secrets_env_files.md"
  exit 1
fi
echo "OK: base required keys present"

empty_required=()
for key in "${required_keys[@]}"; do
  value="$(sed -n "s/^${key}=//p" "$SECRETS_FILE" | tail -n 1 | tr -d '\r')"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  if [[ -z "$value" ]]; then
    empty_required+=("$key")
  fi
done

if ((${#empty_required[@]} > 0)); then
  echo "ERROR: required keys present but empty:"
  for key in "${empty_required[@]}"; do
    echo "  - ${key}"
  done
  exit 1
fi

# Auth: accept either OPEN_WEBUI_API_KEY (preferred) or OWUI_API_KEY (deprecated alias)
if ! rg -n --no-line-number "^OPEN_WEBUI_API_KEY=" "$SECRETS_FILE" >/dev/null 2>&1 \
  && ! rg -n --no-line-number "^OWUI_API_KEY=" "$SECRETS_FILE" >/dev/null 2>&1; then
  echo "ERROR: missing auth key for Open WebUI API."
  echo "Set one of:"
  echo "  - OPEN_WEBUI_API_KEY (preferred)"
  echo "  - OWUI_API_KEY (deprecated alias)"
  exit 1
fi

auth_value="$(sed -n 's/^OPEN_WEBUI_API_KEY=//p' "$SECRETS_FILE" | tail -n 1 | tr -d '\r')"
auth_value="${auth_value#"${auth_value%%[![:space:]]*}"}"
auth_value="${auth_value%"${auth_value##*[![:space:]]}"}"
fallback_auth_value="$(sed -n 's/^OWUI_API_KEY=//p' "$SECRETS_FILE" | tail -n 1 | tr -d '\r')"
fallback_auth_value="${fallback_auth_value#"${fallback_auth_value%%[![:space:]]*}"}"
fallback_auth_value="${fallback_auth_value%"${fallback_auth_value##*[![:space:]]}"}"
if [[ -z "$auth_value" && -z "$fallback_auth_value" ]]; then
  echo "ERROR: OWUI_API_KEY/OPEN_WEBUI_API_KEY is present but empty"
  exit 1
fi
echo "OK: Open WebUI API auth key present (OPEN_WEBUI_API_KEY or OWUI_API_KEY)"

# Knowledge target: require either topic mapping JSON or default knowledge id
has_mapping=0
has_default_knowledge_id=0
if rg -n --no-line-number "^OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON=" "$SECRETS_FILE" >/dev/null 2>&1; then
  has_mapping=1
fi
if rg -n --no-line-number "^OPEN_WEBUI_KNOWLEDGE_ID=" "$SECRETS_FILE" >/dev/null 2>&1; then
  has_default_knowledge_id=1
fi
if [[ "$has_mapping" -eq 0 && "$has_default_knowledge_id" -eq 0 ]]; then
  echo "ERROR: missing Open WebUI Knowledge target."
  echo "Set one of:"
  echo "  - OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON (recommended)"
  echo "  - OPEN_WEBUI_KNOWLEDGE_ID (fallback default)"
  exit 1
fi
echo "OK: Knowledge target configured"

if rg -n --no-line-number "^OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON=" "$SECRETS_FILE" >/dev/null 2>&1; then
  raw_json="$(sed -n 's/^OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON=//p' "$SECRETS_FILE" | tail -n 1 | tr -d '\r')"
  raw_json="${raw_json#"${raw_json%%[![:space:]]*}"}"
  raw_json="${raw_json%"${raw_json##*[![:space:]]}"}"

  if [[ "$raw_json" == \"*\" && "$raw_json" == *\" ]]; then
    raw_json="${raw_json:1:${#raw_json}-2}"
  elif [[ "$raw_json" == \'*\' && "$raw_json" == *\' ]]; then
    raw_json="${raw_json:1:${#raw_json}-2}"
  fi

  if ! echo "$raw_json" | jq -e 'type == "object"' >/dev/null 2>&1; then
    echo "ERROR: OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON is not valid JSON object"
    exit 1
  fi

  topics="$(echo "$raw_json" | jq -r 'keys | join(", ")' 2>/dev/null || true)"
  if [[ -z "$topics" ]]; then
    echo "WARN: OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON has no keys"
  else
    echo "OK: OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON topics: ${topics}"
  fi

  if echo "$raw_json" | rg -n --no-line-number "<[^>]+>" >/dev/null 2>&1; then
    echo "WARN: OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON still contains placeholder values like <...>"
  fi
fi

echo "Note: OPEN_WEBUI_API_KEY is a JWT; rotate it in Open WebUI if it was ever exposed, then update ${SECRETS_FILE}."
