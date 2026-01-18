#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install Docker Engine + Docker Compose plugin on Debian 13 (trixie).

Usage:
  scripts/install_docker_debian13.sh [--with-docker-group]

Options:
  --with-docker-group   Add current user to `docker` group (root-equivalent power).
EOF
}

with_docker_group=false
for arg in "$@"; do
  case "$arg" in
    --with-docker-group) with_docker_group=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; usage; exit 2 ;;
  esac
done

if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
else
  echo "ERROR: /etc/os-release not readable" >&2
  exit 1
fi

if [[ "${ID:-}" != "debian" || "${VERSION_CODENAME:-}" != "trixie" ]]; then
  echo "ERROR: Expected Debian trixie; got ID='${ID:-}' VERSION_CODENAME='${VERSION_CODENAME:-}'" >&2
  exit 1
fi

echo "== Preflight =="
cat /etc/os-release
uname -a
ip -br a || true
getent hosts download.docker.com || true

echo "== APT update =="
sudo apt update

echo "== Remove conflicting packages (ignore errors) =="
sudo apt remove -y docker.io docker-doc docker-compose podman-docker containerd runc || true
sudo apt autoremove -y || true

echo "== Install prerequisites =="
sudo apt update
sudo apt install -y ca-certificates curl gnupg

echo "== Add Docker repo keyring =="
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "== Add Docker APT repo (trixie) =="
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<'EOF'
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: trixie
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

echo "== Install Docker Engine + plugins =="
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "== Enable/start docker service =="
sudo systemctl enable --now docker
systemctl is-active docker
systemctl status docker --no-pager | sed -n '1,120p'

echo "== Smoke tests =="
docker --version
docker compose version
sudo docker run --rm hello-world

if [[ "$with_docker_group" == "true" ]]; then
  echo "== Optional: add user to docker group (security note: root-equivalent) =="
  sudo usermod -aG docker "$USER"
  echo "Added '$USER' to group 'docker'. Log out/in for it to take effect."
  echo "Trying in a subshell via newgrp (optional)..."
  newgrp docker <<'EOF'
docker ps || true
docker run --rm hello-world || true
EOF
fi

echo "OK: Docker installation finished."
