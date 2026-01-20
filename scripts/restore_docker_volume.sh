#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  restore_docker_volume.sh <volume_name> <backup_tar_gz> --force

Restores a Docker volume from a tar.gz archive created by backup_docker_volume.sh.
WARNING: This deletes all existing data in the volume.

Examples:
  ./scripts/restore_docker_volume.sh owui-data /srv/ai-stack/backups/owui-data__20260118T120000Z.tar.gz --force
EOF
}

volume="${1:-}"
archive="${2:-}"
force="${3:-}"

if [[ -z "$volume" || -z "$archive" || "$volume" == "-h" || "$volume" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$force" != "--force" ]]; then
  echo "ERROR: restore requires --force"
  usage
  exit 1
fi

if [[ ! -f "$archive" ]]; then
  echo "ERROR: archive not found: $archive"
  exit 1
fi

backup_dir="$(cd "$(dirname "$archive")" && pwd)"
archive_name="$(basename "$archive")"

echo "Restoring volume: ${volume}"
echo "From: ${archive}"
echo "WARNING: deleting existing volume data"

docker run --rm \
  -v "${volume}:/volume" \
  -v "${backup_dir}:/backup:ro" \
  alpine:3.20 \
  sh -euc "rm -rf /volume/* && tar -xzf \"/backup/${archive_name}\" -C /volume"

echo "OK"
