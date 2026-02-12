#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROMPT_FILE_DEFAULT="${REPO_ROOT}/transcript-miner/tests/prompt-engineering/_promptnew.md"
TRANSCRIPT_FILE_DEFAULT="${REPO_ROOT}/transcript-miner/tests/prompt-engineering/1TD3WHTg3gQ_transcript.md"
OUTPUT_DIR_DEFAULT="${REPO_ROOT}/transcript-miner/tests/prompt-engineering/_out_gemini_cli_poc"

PROMPT_FILE="${PROMPT_FILE:-${PROMPT_FILE_DEFAULT}}"
TRANSCRIPT_FILE="${TRANSCRIPT_FILE:-${TRANSCRIPT_FILE_DEFAULT}}"
OUTPUT_DIR="${OUTPUT_DIR:-${OUTPUT_DIR_DEFAULT}}"
MODEL="${GEMINI_MODEL:-gemini-3-flash}"

VIDEO_ID="${VIDEO_ID:-}"
TOPIC="${TOPIC:-investing_test}"
TITLE="${TITLE:-POC Gemini CLI Summary}"
CHANNEL_NAMESPACE="${CHANNEL_NAMESPACE:-poc_channel}"
PUBLISHED_AT="${PUBLISHED_AT:-unknown}"
FETCHED_AT="$(date -u +'%Y-%m-%d %H:%M UTC')"

usage() {
  cat <<'USAGE'
Usage: scripts/run-gemini-cli-summary-poc.sh [options]

Minimal headless POC for summary generation via Gemini CLI (instead of OpenRouter API calls).
No pipeline refactor; this script is test-only.

Options:
  --prompt-file <path>      Default: transcript-miner/tests/prompt-engineering/_promptnew.md
  --transcript-file <path>  Default: transcript-miner/tests/prompt-engineering/1TD3WHTg3gQ_transcript.md
  --output-dir <path>       Default: transcript-miner/tests/prompt-engineering/_out_gemini_cli_poc
  --model <name>            Default: gemini-3-flash (pro models blocked)
  --video-id <id>           Optional; default derived from transcript filename prefix
  --topic <topic>           Default: investing_test
  --title <text>            Default: "POC Gemini CLI Summary"
  --channel <name>          Default: poc_channel
  --published-at <text>     Default: unknown
  -h, --help                Show this help

Required auth for gemini CLI:
  - GEMINI_API_KEY
  OR
  - Gemini CLI settings auth (see ~/.gemini/settings.json)
USAGE
}

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "ERROR missing command: $1"
    exit 50
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt-file) PROMPT_FILE="${2:?missing value for --prompt-file}"; shift 2 ;;
    --transcript-file) TRANSCRIPT_FILE="${2:?missing value for --transcript-file}"; shift 2 ;;
    --output-dir) OUTPUT_DIR="${2:?missing value for --output-dir}"; shift 2 ;;
    --model) MODEL="${2:?missing value for --model}"; shift 2 ;;
    --video-id) VIDEO_ID="${2:?missing value for --video-id}"; shift 2 ;;
    --topic) TOPIC="${2:?missing value for --topic}"; shift 2 ;;
    --title) TITLE="${2:?missing value for --title}"; shift 2 ;;
    --channel) CHANNEL_NAMESPACE="${2:?missing value for --channel}"; shift 2 ;;
    --published-at) PUBLISHED_AT="${2:?missing value for --published-at}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) log "ERROR unknown arg: $1"; usage; exit 2 ;;
  esac
done

require_cmd gemini
require_cmd python3
require_cmd mktemp

if [[ ! -f "${PROMPT_FILE}" ]]; then
  log "ERROR prompt file not found: ${PROMPT_FILE}"
  exit 3
fi
if [[ ! -f "${TRANSCRIPT_FILE}" ]]; then
  log "ERROR transcript file not found: ${TRANSCRIPT_FILE}"
  exit 4
fi

if [[ -z "${VIDEO_ID}" ]]; then
  b="$(basename "${TRANSCRIPT_FILE}")"
  if [[ "${b}" == *_transcript.md ]]; then
    VIDEO_ID="${b%_transcript.md}"
  else
    VIDEO_ID="${b%%.*}"
  fi
fi

model_lc="$(printf '%s' "${MODEL}" | tr '[:upper:]' '[:lower:]')"
if [[ "${model_lc}" == *pro* ]]; then
  log "ERROR model '${MODEL}' is blocked by policy (no pro models). Use gemini-3-flash."
  exit 5
fi

mkdir -p "${OUTPUT_DIR}"
ts="$(date -u +'%Y%m%d_%H%M%SZ')"
output_file="${OUTPUT_DIR}/${VIDEO_ID}.gemini_cli.${ts}.summary.md"

tmp_prompt="$(mktemp)"
tmp_err="$(mktemp)"
tmp_out="$(mktemp)"
trap 'rm -f "${tmp_prompt}" "${tmp_err}" "${tmp_out}"' EXIT

cat >"${tmp_prompt}" <<EOF
You are generating transcript summaries for Open WebUI RAG indexing.
Follow ALL instructions from the prompt specification below.
Output must be Markdown only.
Do not use thinking/reasoning mode. Return only the final answer.

===== BEGIN SYSTEM/FORMAT INSTRUCTIONS =====
$(cat "${PROMPT_FILE}")
===== END SYSTEM/FORMAT INSTRUCTIONS =====

Video metadata:
- topic: ${TOPIC}
- video_id: ${VIDEO_ID}
- url: https://www.youtube.com/watch?v=${VIDEO_ID}
- title: ${TITLE}
- channel_namespace: ${CHANNEL_NAMESPACE}
- published_at: ${PUBLISHED_AT}
- fetched_at: ${FETCHED_AT}

Transcript:
$(cat "${TRANSCRIPT_FILE}")
EOF

log "gemini-poc.start model=${MODEL} video_id=${VIDEO_ID}"
if ! gemini --model "${MODEL}" -o text --approval-mode yolo -p "Use the full prompt from stdin." \
  <"${tmp_prompt}" >"${tmp_out}" 2>"${tmp_err}"; then
  log "gemini-poc.error command failed"
  cat "${tmp_err}" >&2
  if rg -q "Please set an Auth method|GEMINI_API_KEY|GOOGLE_GENAI_USE_VERTEXAI|GOOGLE_GENAI_USE_GCA" "${tmp_err}"; then
    cat >&2 <<'HINT'
Hint: Gemini CLI auth is missing.
Set one of:
  - GEMINI_API_KEY=<your_key>
  - or configure auth in ~/.gemini/settings.json
HINT
  fi
  exit 41
fi

mv "${tmp_out}" "${output_file}"
doc_count="$(rg -o '<<<DOC_START>>>' "${output_file}" | wc -l | tr -d ' ')"
size_bytes="$(wc -c <"${output_file}" | tr -d ' ')"
log "gemini-poc.done output=${output_file} bytes=${size_bytes} wrapped_docs=${doc_count}"
echo "${output_file}"
