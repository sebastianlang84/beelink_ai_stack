# openclaw — Betrieb (Host-native)

Ziel: OpenClaw laeuft nativ auf dem Host.

## Ist-Zustand (dieses Setup)
- CLI: `/home/wasti/.local/bin/openclaw`
- Config: `~/.openclaw/openclaw.json`
- Gateway: `127.0.0.1:18789`
- Workspace: `~/.openclaw/workspace`
- Sessions: `~/.openclaw/agents/main/sessions`

## Konfiguration
Interaktiv:

```bash
openclaw configure
```

Einzelwert setzen (Beispiel):

```bash
openclaw config set gateway.mode local
```

Wert pruefen:

```bash
openclaw config get gateway.mode
```

## Betrieb
Status:

```bash
openclaw gateway status
```

Probe:

```bash
openclaw gateway probe
```

Foreground-Start (falls noetig):

```bash
openclaw gateway run --bind loopback --port 18789
```

## Tailscale Zugriff (VPN-only)
OpenClaw nutzt absolute Pfade (`/api`, `/ws`). Deshalb eigenen Hostnamen oder eigenen HTTPS-Port bevorzugen.

Beispiel:

```bash
sudo tailscale serve --bg --https=443 --set-path /openclaw http://127.0.0.1:18789
```
