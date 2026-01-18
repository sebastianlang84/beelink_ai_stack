#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  backup_docker_volume.sh <volume_name> [backup_dir]

Creates a gzipped tar archive of a Docker volume (contents only).
Does NOT print secret values; archive contains the raw data.

Defaults:
  backup_dir: /srv/ai_stack/backups

Examples:
  ./scripts/backup_docker_volume.sh open-webui_open_webui_data
  ./scripts/backup_docker_volume.sh tool-transcript-miner_tool_transcript_miner_data /srv/ai_stack/backups
EOF
}

volume="${1:-}"
backup_dir="${2:-/srv/ai_stack/backups}"

if [[ -z "$volume" || "$volume" == "-h" || "$volume" == "--help" ]]; then
  usage
  exit 0
fi

mkdir -p "$backup_dir"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="${backup_dir}/${volume}__${ts}.tar.gz"

echo "Backing up volume: ${volume}"
echo "Output: ${out}"

docker run --rm \
  -v "${volume}:/volume:ro" \
  -v "${backup_dir}:/backup" \
  alpine:3.20 \
  sh -euc "cd /volume && tar -czf \"/backup/$(basename "$out")\" ."

echo "OK"
