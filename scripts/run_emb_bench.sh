#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_emb_bench.sh [--env-file /etc/ai-stack/secrets.env] -- <emb_bench args...>

Examples:
  ./scripts/run_emb_bench.sh -- python -m emb_bench run --config config.local_only.yaml --phase local_vs_remote
  ./scripts/run_emb_bench.sh --env-file /etc/ai-stack/secrets.env -- python -m emb_bench run --config config.example.yaml --phase mrl --subset-docs 200 --subset-queries 50

Notes:
  - Runs via Docker Compose in `emb-bench/`.
  - Sets DOCKER_UID/DOCKER_GID so outputs under `emb-bench/runs_out/` are writable.
EOF
}

env_file=""
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --env-file)
      env_file="${2:-}"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Unknown flag: $1"
      usage
      exit 2
      ;;
  esac
done

if [[ "${1:-}" != "python" && -z "${1:-}" ]]; then
  echo "ERROR: missing command after --"
  usage
  exit 2
fi

uid="$(id -u)"
gid="$(id -g)"

cd /home/wasti/ai_stack/emb-bench

if [[ -n "$env_file" ]]; then
  DOCKER_UID="$uid" DOCKER_GID="$gid" \
    docker compose --env-file "$env_file" run --rm emb-bench "$@"
else
  DOCKER_UID="$uid" DOCKER_GID="$gid" \
    docker compose run --rm emb-bench "$@"
fi
