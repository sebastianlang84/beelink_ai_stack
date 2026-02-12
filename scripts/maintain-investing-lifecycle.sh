#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TM_CONTAINER="${TM_CONTAINER:-tm}"
TM_BASE_URL="${TM_BASE_URL:-http://127.0.0.1:8000}"
TM_LIFECYCLE_TOPIC="${TM_LIFECYCLE_TOPIC:-investing}"
TM_CREATE_KNOWLEDGE_IF_MISSING="${TM_CREATE_KNOWLEDGE_IF_MISSING:-true}"
TM_OUTPUT_ROOT="${TM_OUTPUT_ROOT:-/home/wasti/ai_stack_data/transcript-miner/output}"
TM_OUTPUT_ROOT_CONTAINER="${TM_OUTPUT_ROOT_CONTAINER:-/transcript_miner_output}"
GLOBAL_CONFIG_PATH="${GLOBAL_CONFIG_PATH:-${REPO_ROOT}/transcript-miner/config/config_global.yaml}"
HOT_MAX_AGE_DAYS="${HOT_MAX_AGE_DAYS:-}"
PRUNE_ORPHAN_STALE_HOT="${PRUNE_ORPHAN_STALE_HOT:-true}"

HOT_SUMMARIES_DIR="${HOT_SUMMARIES_DIR:-${TM_OUTPUT_ROOT}/data/summaries/by_video_id}"
COLD_SUMMARIES_DIR="${COLD_SUMMARIES_DIR:-${TM_OUTPUT_ROOT}/data/summaries/cold/by_video_id}"
TRANSCRIPTS_META_DIR="${TRANSCRIPTS_META_DIR:-${TM_OUTPUT_ROOT}/data/transcripts/by_video_id}"
INDEX_JSONL="${INDEX_JSONL:-${TM_OUTPUT_ROOT}/data/indexes/${TM_LIFECYCLE_TOPIC}/current/transcripts.jsonl}"

HOT_SUMMARIES_DIR_CONTAINER="${HOT_SUMMARIES_DIR_CONTAINER:-${TM_OUTPUT_ROOT_CONTAINER}/data/summaries/by_video_id}"
COLD_SUMMARIES_DIR_CONTAINER="${COLD_SUMMARIES_DIR_CONTAINER:-${TM_OUTPUT_ROOT_CONTAINER}/data/summaries/cold/by_video_id}"
TRANSCRIPTS_META_DIR_CONTAINER="${TRANSCRIPTS_META_DIR_CONTAINER:-${TM_OUTPUT_ROOT_CONTAINER}/data/transcripts/by_video_id}"
INDEX_JSONL_CONTAINER="${INDEX_JSONL_CONTAINER:-${TM_OUTPUT_ROOT_CONTAINER}/data/indexes/${TM_LIFECYCLE_TOPIC}/current/transcripts.jsonl}"

FRESHNESS_CHECK_SCRIPT="${SCRIPT_DIR}/check-hot-summaries-freshness.sh"

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

usage() {
  cat <<'USAGE'
Usage: scripts/maintain-investing-lifecycle.sh <cmd>

Commands:
  sync    Run lifecycle sync only (no freshness check).
  check   Run hot-summaries freshness guard only.
  ensure  Run lifecycle sync, then freshness guard (default).
  dry-run Call lifecycle endpoint with dry_run=true, then run guard.

Notes:
- This maintenance script is intentionally independent from download schedules.
- It does NOT read/obey schedulers.disabled kill-switch.
USAGE
}

require_prereqs() {
  if ! command -v docker >/dev/null 2>&1; then
    log "ERROR missing command: docker"
    exit 50
  fi
  if [[ ! -x "${FRESHNESS_CHECK_SCRIPT}" ]]; then
    log "ERROR missing executable guard script: ${FRESHNESS_CHECK_SCRIPT}"
    exit 51
  fi
}

resolve_max_age_days() {
  if [[ -n "${HOT_MAX_AGE_DAYS}" ]]; then
    echo "${HOT_MAX_AGE_DAYS}"
    return 0
  fi
  if [[ ! -f "${GLOBAL_CONFIG_PATH}" ]]; then
    log "ERROR config not found: ${GLOBAL_CONFIG_PATH}"
    exit 53
  fi
  local parsed
  parsed="$(
    awk '
      /^[[:space:]]*archive_max_age_days:[[:space:]]*[0-9]+/ {
        gsub(/#.*/, "", $0)
        split($0, a, ":")
        gsub(/[[:space:]]/, "", a[2])
        print a[2]
        exit
      }
    ' "${GLOBAL_CONFIG_PATH}"
  )"
  if [[ -z "${parsed}" ]]; then
    log "ERROR could not parse archive_max_age_days from ${GLOBAL_CONFIG_PATH}"
    exit 53
  fi
  echo "${parsed}"
}

ensure_tm_running() {
  if ! docker ps --format '{{.Names}}' | grep -qx "${TM_CONTAINER}"; then
    log "ERROR container not running: ${TM_CONTAINER}"
    exit 52
  fi
}

run_lifecycle_sync() {
  local dry_run="$1"
  ensure_tm_running

  log "sync.start topic=${TM_LIFECYCLE_TOPIC} dry_run=${dry_run} create_knowledge_if_missing=${TM_CREATE_KNOWLEDGE_IF_MISSING}"
  docker exec -i \
    -e TM_BASE_URL="${TM_BASE_URL}" \
    -e TM_LIFECYCLE_TOPIC="${TM_LIFECYCLE_TOPIC}" \
    -e TM_DRY_RUN="${dry_run}" \
    -e TM_CREATE_KNOWLEDGE_IF_MISSING="${TM_CREATE_KNOWLEDGE_IF_MISSING}" \
    "${TM_CONTAINER}" \
    python - <<'PY'
import json
import os
import urllib.request

base = os.environ["TM_BASE_URL"].rstrip("/")
topic = os.environ["TM_LIFECYCLE_TOPIC"]
dry_run = str(os.environ.get("TM_DRY_RUN", "false")).lower() == "true"
create_knowledge = str(os.environ.get("TM_CREATE_KNOWLEDGE_IF_MISSING", "true")).lower() == "true"

payload = {
    "dry_run": dry_run,
    "create_knowledge_if_missing": create_knowledge,
}

req = urllib.request.Request(
    f"{base}/sync/lifecycle/{topic}",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=1800) as resp:
    print(resp.read().decode("utf-8"))
PY
  log "sync.done topic=${TM_LIFECYCLE_TOPIC} dry_run=${dry_run}"
}

prune_orphan_stale_hot() {
  local max_age_days
  max_age_days="$(resolve_max_age_days)"

  if [[ "${PRUNE_ORPHAN_STALE_HOT}" != "true" ]]; then
    log "prune.skip reason=disabled"
    return 0
  fi

  ensure_tm_running
  log "prune.start max_age_days=${max_age_days}"
  docker exec -i \
    -e HOT_SUMMARIES_DIR="${HOT_SUMMARIES_DIR_CONTAINER}" \
    -e COLD_SUMMARIES_DIR="${COLD_SUMMARIES_DIR_CONTAINER}" \
    -e TRANSCRIPTS_META_DIR="${TRANSCRIPTS_META_DIR_CONTAINER}" \
    -e INDEX_JSONL="${INDEX_JSONL_CONTAINER}" \
    -e HOT_MAX_AGE_DAYS="${max_age_days}" \
    "${TM_CONTAINER}" \
    python - <<'PY'
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

hot_dir = Path(os.environ["HOT_SUMMARIES_DIR"])
cold_dir = Path(os.environ["COLD_SUMMARIES_DIR"])
meta_dir = Path(os.environ["TRANSCRIPTS_META_DIR"])
index_jsonl = Path(os.environ["INDEX_JSONL"])
max_age_days = int(os.environ["HOT_MAX_AGE_DAYS"])

if not hot_dir.is_dir():
    raise SystemExit(f"missing hot dir: {hot_dir}")
if not meta_dir.is_dir():
    raise SystemExit(f"missing meta dir: {meta_dir}")

index_ids: set[str] = set()
if index_jsonl.is_file():
    for line in index_jsonl.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        video_id = str(obj.get("video_id") or "").strip()
        if video_id:
            index_ids.add(video_id)

cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
checked = 0
moved = 0
stale_in_index = 0
missing_meta = 0

cold_dir.mkdir(parents=True, exist_ok=True)

for summary_path in sorted(hot_dir.glob("*.summary.md")):
    checked += 1
    video_id = summary_path.name[:-11]
    meta_path = meta_dir / f"{video_id}.meta.json"
    if not meta_path.is_file():
        missing_meta += 1
        continue

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8", errors="replace"))
        published_raw = meta.get("published_at")
        if not published_raw:
            continue
        published_dt = datetime.fromisoformat(str(published_raw).replace("Z", "+00:00"))
    except Exception:
        continue
    if published_dt.tzinfo is None:
        published_dt = published_dt.replace(tzinfo=timezone.utc)
    else:
        published_dt = published_dt.astimezone(timezone.utc)

    if published_dt >= cutoff:
        continue

    if video_id in index_ids:
        stale_in_index += 1
        continue

    target = cold_dir / summary_path.name
    os.replace(summary_path, target)
    moved += 1

print(
    "prune_orphan_stale_hot",
    f"checked={checked}",
    f"moved={moved}",
    f"stale_in_index={stale_in_index}",
    f"missing_meta={missing_meta}",
    f"max_age_days={max_age_days}",
)
PY
  log "prune.done"
}

run_guard() {
  log "guard.start"
  local max_age_days
  max_age_days="$(resolve_max_age_days)"
  HOT_SUMMARIES_DIR="${HOT_SUMMARIES_DIR}" \
  TRANSCRIPTS_META_DIR="${TRANSCRIPTS_META_DIR}" \
  GLOBAL_CONFIG_PATH="${GLOBAL_CONFIG_PATH}" \
  HOT_MAX_AGE_DAYS="${max_age_days}" \
  "${FRESHNESS_CHECK_SCRIPT}"
  log "guard.done"
}

cmd_sync() {
  run_lifecycle_sync "false"
}

cmd_check() {
  run_guard
}

cmd_ensure() {
  run_lifecycle_sync "false"
  prune_orphan_stale_hot
  run_guard
}

cmd_dry_run() {
  run_lifecycle_sync "true"
  log "prune.skip reason=dry-run"
  run_guard
}

main() {
  require_prereqs
  case "${1:-ensure}" in
    sync) cmd_sync ;;
    check) cmd_check ;;
    ensure) cmd_ensure ;;
    dry-run) cmd_dry_run ;;
    -h|--help) usage; exit 0 ;;
    *) log "ERROR unknown command: ${1}"; usage; exit 2 ;;
  esac
}

main "${1:-ensure}"
