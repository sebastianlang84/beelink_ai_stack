#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  backup_path.sh <path> [backup_dir]

Creates a gzipped tar archive of a host path.

Defaults:
  backup_dir: /srv/ai-stack/backups

Examples:
  ./scripts/backup_path.sh /home/wasti/ai_stack_data/transcript-miner/output
  ./scripts/backup_path.sh /home/wasti/ai_stack_data/transcript-miner/output /srv/ai-stack/backups
EOF
}

src="${1:-}"
backup_dir="${2:-/srv/ai-stack/backups}"

if [[ -z "$src" || "$src" == "-h" || "$src" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -d "$src" && ! -f "$src" ]]; then
  echo "ERROR: path not found: $src"
  exit 1
fi

mkdir -p "$backup_dir"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
safe_name="$(echo "$src" | sed 's#^/##; s#[^A-Za-z0-9._-]#_#g')"
out="${backup_dir}/${safe_name}__${ts}.tar.gz"

echo "Backing up path: ${src}"
echo "Output: ${out}"

tar -czf "$out" -C "$(dirname "$src")" "$(basename "$src")"
echo "OK"
