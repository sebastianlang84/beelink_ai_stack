#!/usr/bin/env bash
set -euo pipefail

# Backup all persistent ai_stack data to a target directory.
# Does not print secret values, but backups contain raw data -> treat as secrets.

BACKUP_DIR="${BACKUP_DIR:-/srv/ai_stack/backups}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/home/wasti/ai_stack_data/transcript-miner/output}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

OPEN_WEBUI_VOLUME="${OPEN_WEBUI_VOLUME:-open-webui_open_webui_data}"
TOOL_TM_VOLUME="${TOOL_TM_VOLUME:-tool-transcript-miner_tool_transcript_miner_data}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "ai_stack backup_all"
echo "BACKUP_DIR=${BACKUP_DIR}"
echo "OUTPUT_ROOT=${OUTPUT_ROOT}"
echo "RETENTION_DAYS=${RETENTION_DAYS}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR" || true

"$SCRIPT_DIR/backup_docker_volume.sh" "$OPEN_WEBUI_VOLUME" "$BACKUP_DIR"
"$SCRIPT_DIR/backup_docker_volume.sh" "$TOOL_TM_VOLUME" "$BACKUP_DIR"

if [[ -e "$OUTPUT_ROOT" ]]; then
  "$SCRIPT_DIR/backup_path.sh" "$OUTPUT_ROOT" "$BACKUP_DIR"
else
  echo "WARN: OUTPUT_ROOT not found, skipping: ${OUTPUT_ROOT}"
fi

echo "Retention: deleting backups older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -type f -name '*.tar.gz' -mtime "+${RETENTION_DAYS}" -print -delete

echo "OK"
