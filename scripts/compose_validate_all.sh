#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Validate all docker-compose.yml files in this repo.

Checks:
  - `docker compose config` succeeds for every stack.
  - Published ports are bound to localhost only (127.0.0.1 / ::1).

Usage:
  ./scripts/compose_validate_all.sh

Options:
  --warn-only   Do not fail on non-localhost published ports.
EOF
}

warn_only="false"
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --warn-only)
      warn_only="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown flag: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# Some stacks intentionally require these for safe file ownership (e.g. emb-bench).
export DOCKER_UID="${DOCKER_UID:-$(id -u)}"
export DOCKER_GID="${DOCKER_GID:-$(id -g)}"

tmp="$(mktemp -t ai_stack_compose_config.XXXXXX.yml)"
trap 'rm -f "$tmp" >/dev/null 2>&1 || true' EXIT

mapfile -t compose_files < <(find . -maxdepth 2 -name docker-compose.yml -print | sort)
if [[ "${#compose_files[@]}" -eq 0 ]]; then
  echo "ERROR: no docker-compose.yml files found" >&2
  exit 1
fi

fail=0
for f in "${compose_files[@]}"; do
  echo "==> $f"
  if ! docker compose -f "$f" config >"$tmp"; then
    echo "ERROR: docker compose config failed: $f" >&2
    fail=1
    continue
  fi

  # Compose `config` output uses this structure:
  #   - mode: ingress
  #     host_ip: 127.0.0.1
  #     target: 8080
  #     published: "3000"
  #
  # If host_ip is missing, Docker binds to 0.0.0.0 by default.
  if ! awk -v file="$f" -v warn_only="$warn_only" '
    function is_local(ip) {
      return ip == "127.0.0.1" || ip == "::1"
    }
    $1=="host_ip:" { host_ip=$2 }
    $1=="published:" {
      published=$2
      gsub(/"/, "", published)
      ip=host_ip
      if (ip == "") ip="0.0.0.0"
      if (!is_local(ip)) {
        printf("%s: non-localhost published port %s (host_ip=%s)\n", file, published, ip) > "/dev/stderr"
        bad=1
      }
      host_ip=""
    }
    END {
      if (bad && warn_only == "true") exit 0
      exit bad
    }
  ' "$tmp"; then
    if [[ "$warn_only" == "true" ]]; then
      echo "WARN: non-localhost port publishing detected: $f" >&2
    else
      echo "ERROR: non-localhost port publishing detected: $f" >&2
      fail=1
    fi
  fi
done

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "OK: all compose stacks validate"
