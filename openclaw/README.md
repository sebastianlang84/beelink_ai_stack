# openclaw — Betrieb (Host-native)

Ziel: OpenClaw laeuft nativ auf dem Host (kein Docker-Compose-Run fuer Gateway/CLI).

## Ist-Zustand (dieses Repo)
- CLI: `/home/wasti/.local/bin/openclaw`
- Config: `~/.openclaw/openclaw.json`
- Gateway: lokal auf `127.0.0.1:18789`

## Konfiguration
Interaktiv:

```bash
openclaw configure
```

Einzelwert setzen (Beispiel `gateway.mode=local`):

```bash
openclaw config set gateway.mode local
```

Wert pruefen:

```bash
openclaw config get gateway.mode
```

## Betrieb / Status
Gateway-Status:

```bash
openclaw gateway status
```

Gateway-Probe:

```bash
openclaw gateway probe
```

Foreground-Start (falls noetig):

```bash
openclaw gateway run --bind loopback --port 18789
```

## Tailscale Zugriff (VPN-only)
Hinweis: OpenClaw nutzt absolute Pfade (`/api`, `/ws`). Pfad-Serve unter `/openclaw` kollidiert leicht mit OWUI.
Empfohlen: eigener Hostname oder eigener HTTPS-Port.

Beispiel:

```bash
sudo tailscale serve --bg --https=443 --set-path /openclaw http://127.0.0.1:18789
```

## Legacy (nur wenn explizit gewuenscht)
`openclaw/docker-compose.yml` existiert weiterhin als Fallback, ist aber nicht der Standardbetrieb.

## Cleanup (empfohlen nach Migration auf host-native)
Alte OpenClaw-Container/Images aus Docker entfernen:

```bash
docker rm -f openclaw-gateway openclaw-cli 2>/dev/null || true
docker rmi openclaw-openclaw-gateway:latest openclaw-openclaw-cli:latest openclaw:local 2>/dev/null || true
```
