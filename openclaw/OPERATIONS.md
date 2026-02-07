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

## Control UI Pairing (Device, typischer Blocker)

Symptom im Dashboard/Control UI: `disconnected (1008): pairing required`

Das ist **Device Pairing** fuer die Control UI (Browser/Device), nicht Telegram.

1. Pending device(s) anzeigen:

```bash
openclaw devices list
```

2. Pending Request approven (falls vorhanden):

```bash
openclaw devices approve <requestId>
```

3. Danach Dashboard neu laden.

Debug:

```bash
openclaw logs --follow
```

## Telegram DM Access (Pairing/Allowlist)

Wenn Telegram so konfiguriert ist, dass DMs per `dmPolicy: "pairing"` abgesichert sind:

1. In Telegram dem Bot eine DM schicken.
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

Hinweis Gruppen:
- Default ist mention-gated in Gruppen. Wenn du im Group-Chat testest: bot mit `@wasticlaw1_bot` mentionen.
- Wenn der Bot in Gruppen gar nichts sieht: @BotFather → "Group Privacy" auf OFF (und Bot ggf. re-add).

## Agent Error: "Unknown model: openrouter/auto"

Symptom: In der Control UI / Logs steht:
- `Agent failed before reply: Unknown model: openrouter/auto`

Ursache: `openrouter/auto` ist **kein** gueltiger Model-Key im aktuellen OpenClaw Model-Katalog. OpenClaw erwartet
ein explizites `openrouter/<vendor>/<model>` (oder einen Alias).

Fix:

```bash
# Kandidaten finden (OpenRouter Katalog)
openclaw models list --all --provider openrouter --plain | head -n 50

# Default setzen
openclaw models set openrouter/google/gemini-3-flash-preview

# Gateway neu starten (wenn noetig)
./scripts/openclaw_gateway_supervise.sh ensure
```

Optional (Security, Gruppen): Sender-Allowlist setzen, damit nicht jeder im Group-Chat Commands triggern kann.

## Backup / Restore (was sichern)

Wichtig fuer Wiederherstellung:
- Config: `~/.openclaw/openclaw.json`
- Workspace: `~/.openclaw/workspace`
- Sessions: `~/.openclaw/agents/main/sessions`

## Security Notes (kurz)

Aktuell ist Telegram sehr offen konfigurierbar (DM/Groups). Fuer sicheren Betrieb:
- `dmPolicy`/`groupPolicy` bevorzugt auf Allowlist/Pairs begrenzen.
- DMs pro Sender isolieren (OpenClaw gibt dafuer Hinweise in `openclaw status` / `openclaw doctor`).
