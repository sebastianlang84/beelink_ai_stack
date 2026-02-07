# openclaw — Betrieb (Host-native)

Ziel: OpenClaw laeuft nativ auf dem Host.

Operations/Recovery: `openclaw/OPERATIONS.md`

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

## Persistenter Start (ohne sudo/systemd)
Auf diesem Host ist `systemd --user` oft nicht verfuegbar (kein User-Bus in non-login shells). Deshalb nutzen wir einen
kleinen user-level Supervisor + Cron (idempotent).

Gateway sicher starten/halten:

```bash
./scripts/openclaw_gateway_supervise.sh ensure
./scripts/openclaw_gateway_supervise.sh status
```

Cron installieren (`@reboot` + alle 5 Minuten `ensure`):

```bash
./scripts/install_openclaw_gateway_cron.sh
```

## Tailscale Zugriff (VPN-only)
OpenClaw nutzt absolute Pfade (`/api`, `/ws`). Deshalb eigenen Hostnamen oder eigenen HTTPS-Port bevorzugen.

Beispiel:

```bash
sudo tailscale serve --bg --https=443 --set-path /openclaw http://127.0.0.1:18789
```
