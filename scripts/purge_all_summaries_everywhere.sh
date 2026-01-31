#!/usr/bin/env bash
set -euo pipefail

# Purge summaries locally and delete all Open WebUI Knowledge Collections.
# Transcripts are preserved.

if [[ "${1:-}" != "--force" ]]; then
  echo "Usage: $0 --force"
  echo "Purges local summaries + derived outputs and deletes ALL Open WebUI Knowledge Collections."
  exit 1
fi

# Load secrets if present (secrets-only by repo policy).
if [[ -f ".env" ]]; then
  # shellcheck disable=SC1091
  set -a; source ".env"; set +a
fi

OUTPUT_ROOT="${OUTPUT_ROOT:-/home/wasti/ai_stack_data/transcript-miner/output}"
OPEN_WEBUI_BASE_URL="${OPEN_WEBUI_BASE_URL:-http://127.0.0.1:3000}"
OPEN_WEBUI_BASE_URL="${OPEN_WEBUI_BASE_URL%/}"

echo "Purging summaries locally..."
echo "OUTPUT_ROOT=${OUTPUT_ROOT}"

run_local_purge=1
if [[ -d "${OUTPUT_ROOT}/data/summaries/by_video_id" && ! -w "${OUTPUT_ROOT}/data/summaries/by_video_id" ]]; then
  run_local_purge=0
fi

if [[ "${run_local_purge}" -eq 1 ]]; then
  # Best-effort local purge (may fail if files are root-owned from containers).
  find "${OUTPUT_ROOT}/data/summaries/by_video_id" -type f -name "*.md" -delete 2>/dev/null || true
  if [[ -d "${OUTPUT_ROOT}/data/views/by_channel" ]]; then
    find "${OUTPUT_ROOT}/data/views/by_channel" -type f -name "*.md" -delete 2>/dev/null || true
  fi
  rm -rf "${OUTPUT_ROOT}/reports" "${OUTPUT_ROOT}/history" "${OUTPUT_ROOT}/data/indexes" || true
else
  echo "Local output dir is not writable; purging inside tm container (root-owned files expected)."
  docker exec -i tm sh -lc '
set -eu
rm -f /transcript_miner_output/data/summaries/by_video_id/* 2>/dev/null || true
rm -rf /transcript_miner_output/reports /transcript_miner_output/history /transcript_miner_output/data/indexes || true
mkdir -p /transcript_miner_output/data/summaries/by_video_id
'
fi

mkdir -p "${OUTPUT_ROOT}/data/summaries/by_video_id" || true

echo "Local purge done."

if [[ -z "${OPEN_WEBUI_API_KEY:-}" ]]; then
  echo "OPEN_WEBUI_API_KEY not set; skipping Open WebUI Knowledge deletion."
  exit 0
fi

echo "Deleting ALL Open WebUI Knowledge Collections..."
tmp_json="$(mktemp)"
trap 'rm -f "${tmp_json}"' EXIT

curl -sS \
  -H "Authorization: Bearer ${OPEN_WEBUI_API_KEY}" \
  -H "Accept: application/json" \
  "${OPEN_WEBUI_BASE_URL}/api/v1/knowledge/" > "${tmp_json}"

# Response shapes observed across versions:
# - { items: [...] }
# - { knowledge: [...] }
# - [ ... ]
jq -r '(.items // .knowledge // .data // .)[]? | "\(.id)\t\(.name)"' "${tmp_json}" | while IFS=$'\t' read -r kid name; do
  [[ -z "${kid}" ]] && continue
  echo "Deleting knowledge: ${name} (${kid})"
  curl -sS -X DELETE \
    -H "Authorization: Bearer ${OPEN_WEBUI_API_KEY}" \
    -H "Accept: application/json" \
    "${OPEN_WEBUI_BASE_URL}/api/v1/knowledge/${kid}/delete" >/dev/null || true
done

echo "Open WebUI knowledge purge done."
