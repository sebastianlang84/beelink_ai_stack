#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOT_SUMMARIES_DIR="${HOT_SUMMARIES_DIR:-/home/wasti/ai_stack_data/transcript-miner/output/data/summaries/by_video_id}"
TRANSCRIPTS_META_DIR="${TRANSCRIPTS_META_DIR:-/home/wasti/ai_stack_data/transcript-miner/output/data/transcripts/by_video_id}"
GLOBAL_CONFIG_PATH="${GLOBAL_CONFIG_PATH:-${REPO_ROOT}/transcript-miner/config/config_global.yaml}"
HOT_MAX_AGE_DAYS="${HOT_MAX_AGE_DAYS:-}"
MAX_SAMPLE="${MAX_SAMPLE:-10}"

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

usage() {
  cat <<'USAGE'
Usage: scripts/check-hot-summaries-freshness.sh

Checks whether hot summary files are older than the configured age threshold.
Exit codes:
  0 = OK (no stale summaries)
  3 = stale summaries found
  4 = summary/meta paths missing
  5 = invalid config / parse errors

Environment overrides:
  HOT_SUMMARIES_DIR     Default: /home/wasti/ai_stack_data/transcript-miner/output/data/summaries/by_video_id
  TRANSCRIPTS_META_DIR  Default: /home/wasti/ai_stack_data/transcript-miner/output/data/transcripts/by_video_id
  GLOBAL_CONFIG_PATH    Default: <repo>/transcript-miner/config/config_global.yaml
  HOT_MAX_AGE_DAYS      Default: read from archive_max_age_days in GLOBAL_CONFIG_PATH
  MAX_SAMPLE            Default: 10 stale IDs shown
USAGE
}

resolve_max_age_days() {
  if [[ -n "${HOT_MAX_AGE_DAYS}" ]]; then
    echo "${HOT_MAX_AGE_DAYS}"
    return 0
  fi

  if [[ ! -f "${GLOBAL_CONFIG_PATH}" ]]; then
    log "ERROR config not found: ${GLOBAL_CONFIG_PATH}"
    exit 5
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
    exit 5
  fi
  echo "${parsed}"
}

main() {
  case "${1:-}" in
    -h|--help)
      usage
      exit 0
      ;;
    "")
      ;;
    *)
      log "ERROR unknown arg: ${1}"
      usage
      exit 2
      ;;
  esac

  if [[ ! -d "${HOT_SUMMARIES_DIR}" ]]; then
    log "ERROR hot summaries dir missing: ${HOT_SUMMARIES_DIR}"
    exit 4
  fi
  if [[ ! -d "${TRANSCRIPTS_META_DIR}" ]]; then
    log "ERROR transcripts meta dir missing: ${TRANSCRIPTS_META_DIR}"
    exit 4
  fi

  local max_age_days
  max_age_days="$(resolve_max_age_days)"

  HOT_SUMMARIES_DIR="${HOT_SUMMARIES_DIR}" \
  TRANSCRIPTS_META_DIR="${TRANSCRIPTS_META_DIR}" \
  HOT_MAX_AGE_DAYS="${max_age_days}" \
  MAX_SAMPLE="${MAX_SAMPLE}" \
  python3 - <<'PY'
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

hot_dir = Path(os.environ["HOT_SUMMARIES_DIR"])
meta_dir = Path(os.environ["TRANSCRIPTS_META_DIR"])
max_age_days = int(os.environ["HOT_MAX_AGE_DAYS"])
max_sample = int(os.environ["MAX_SAMPLE"])

now = datetime.now(timezone.utc)
cutoff = now - timedelta(days=max_age_days)

total = 0
stale = []
missing_meta = []
missing_published = []
parse_errors = []

for path in sorted(hot_dir.glob("*.summary.md")):
    total += 1
    video_id = path.name[:-11]  # "<video_id>.summary.md"
    meta_path = meta_dir / f"{video_id}.meta.json"
    if not meta_path.is_file():
        missing_meta.append(video_id)
        continue

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        parse_errors.append(video_id)
        continue

    published_raw = meta.get("published_at")
    if not published_raw:
        missing_published.append(video_id)
        continue

    try:
        published_dt = datetime.fromisoformat(str(published_raw).replace("Z", "+00:00"))
    except Exception:
        parse_errors.append(video_id)
        continue
    if published_dt.tzinfo is None:
        published_dt = published_dt.replace(tzinfo=timezone.utc)
    else:
        published_dt = published_dt.astimezone(timezone.utc)

    if published_dt < cutoff:
        stale.append((video_id, published_dt.isoformat()))

def sample(items):
    return ",".join(items[:max_sample]) if items else ""

stale_ids = [x[0] for x in stale]

print(
    "freshness_check",
    f"total={total}",
    f"max_age_days={max_age_days}",
    f"stale={len(stale)}",
    f"missing_meta={len(missing_meta)}",
    f"missing_published={len(missing_published)}",
    f"parse_errors={len(parse_errors)}",
)
if stale_ids:
    print("stale_sample", sample(stale_ids))
if missing_meta:
    print("missing_meta_sample", sample(missing_meta))
if missing_published:
    print("missing_published_sample", sample(missing_published))
if parse_errors:
    print("parse_errors_sample", sample(parse_errors))

if stale:
    raise SystemExit(3)
PY
}

main "$@"
