# OpenClaw Operations (Host-native)

Ziel: OpenClaw Gateway laeuft stabil (ohne `sudo`, ohne `systemd --user`) und Telegram kann Messages verarbeiten.

Siehe auch: `openclaw/README.md`

## Status / Health

```bash
openclaw status
openclaw gateway probe
openclaw channels list
```

Wenn `openclaw status`/`gateway status` ueber `systemd --user` meckert: das ist in dieser Umgebung normal, weil der User-Bus oft nicht verfuegbar ist. Wir nutzen den Supervisor + Cron (siehe unten).

## Gateway Start/Stop (Supervisor)

```bash
./scripts/openclaw_gateway_supervise.sh status
./scripts/openclaw_gateway_supervise.sh start
./scripts/openclaw_gateway_supervise.sh stop
./scripts/openclaw_gateway_supervise.sh ensure
```

Logs:
- Gateway: `${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/openclaw/openclaw-gateway.log`
- Cron: `${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/openclaw/openclaw-gateway-cron.log`

## Gateway Persistenz (Cron)

Installiert `@reboot` + einen periodischen `ensure` alle 5 Minuten:

```bash
./scripts/install_openclaw_gateway_cron.sh
crontab -l | tail -n 50
```

Uninstall (entfernt nur den markierten Block):

```bash
./scripts/uninstall_openclaw_gateway_cron.sh
crontab -l | tail -n 50
```

## Dashboard Hinter Proxy (Tailscale Serve)

Wenn du das Dashboard ueber `https://openclaw.tail...` (Tailscale Serve) oeffnest und im Gateway-Log steht:
`Proxy headers detected from untrusted address ... gateway.trustedProxies`, dann wird der Client nicht als "local"
behandelt und du landest oft in `pairing required` bzw. die UI zeigt falsche `Configured/Running` Werte.

Fix (trust the local proxy hop) und Gateway neu starten:

```bash
openclaw config set gateway.trustedProxies '["127.0.0.1","::1","172.21.0.1","100.100.0.0/16"]'
./scripts/openclaw_gateway_supervise.sh stop
./scripts/openclaw_gateway_supervise.sh start
```

## Telegram Pairing (typischer Blocker)

Symptom in Chat: `disconnected (1008): pairing required`

1. In Telegram dem Bot eine DM schicken und/oder in der Gruppe den Bot mentionen.
2. Dann auf dem Server:

```bash
openclaw pairing list --channel telegram
```

3. Falls ein Code auftaucht:

```bash
openclaw pairing approve --channel telegram --code <CODE_OHNE_KLAMMERN>
```

Debug:

```bash
openclaw channels logs --channel telegram --lines 200
openclaw logs --follow
```

## Backup / Restore (was sichern)

Wichtig fuer Wiederherstellung:
- Config: `~/.openclaw/openclaw.json`
- Workspace: `~/.openclaw/workspace`
- Sessions: `~/.openclaw/agents/main/sessions`

## Security Notes (kurz)

Aktuell ist Telegram sehr offen konfigurierbar (DM/Groups). Fuer sicheren Betrieb:
- `dmPolicy`/`groupPolicy` bevorzugt auf Allowlist/Pairs begrenzen.
- DMs pro Sender isolieren (OpenClaw gibt dafuer Hinweise in `openclaw status` / `openclaw doctor`).
