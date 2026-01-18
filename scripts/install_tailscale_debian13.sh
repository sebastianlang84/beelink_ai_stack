#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install Tailscale on Debian 13 (trixie).

Requires interactive sudo.

Usage:
  ./scripts/install_tailscale_debian13.sh
EOF
}

case "${1:-}" in
  "" ) ;;
  -h|--help) usage; exit 0 ;;
  *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
esac

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

echo "== Prereqs =="
sudo apt update
sudo apt install -y ca-certificates curl gnupg

echo "== Add Tailscale APT repo (trixie) =="
# Use the same layout as tailscale.com/install.sh to avoid Signed-By conflicts.
sudo rm -f /etc/apt/sources.list.d/tailscale.sources || true
sudo rm -f /etc/apt/keyrings/tailscale.gpg || true

if [[ ! -f /etc/apt/sources.list.d/tailscale.list ]]; then
  sudo mkdir -p --mode=0755 /usr/share/keyrings
  curl -fsSL "https://pkgs.tailscale.com/stable/debian/${VERSION_CODENAME}.noarmor.gpg" \
    | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
  sudo chmod 0644 /usr/share/keyrings/tailscale-archive-keyring.gpg

  sudo tee /etc/apt/sources.list.d/tailscale.list >/dev/null <<EOF
# Tailscale packages for debian ${VERSION_CODENAME}
deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] https://pkgs.tailscale.com/stable/debian ${VERSION_CODENAME} main
EOF
  sudo chmod 0644 /etc/apt/sources.list.d/tailscale.list
fi

echo "== Install tailscale =="
sudo apt update
sudo apt install -y tailscale

echo "== Enable service =="
sudo systemctl enable --now tailscaled
systemctl is-active tailscaled

echo "OK: Tailscale installed. Next: run 'sudo tailscale up' (interactive auth)."
