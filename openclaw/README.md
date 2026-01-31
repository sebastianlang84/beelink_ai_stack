# openclaw — Betrieb (Docker)

Ziel: OpenClaw als Containerized Gateway (Docker Compose), isoliert und lokal gebunden.

## Prereqs
- Docker Engine + Docker Compose v2

## Install (Docker, empfohlene Quick-Start)
1) Offizielles OpenClaw Repo in `openclaw/upstream/` bereitstellen (Repo-Root muss `docker-setup.sh` enthalten).
2) Von dort aus:

```bash
cd /home/wasti/ai_stack/openclaw/upstream
./docker-setup.sh
```

Das Script:
- baut das Gateway-Image
- startet Onboarding
- startet das Gateway via Compose
- erzeugt ein Gateway-Token und schreibt es in `.env`
- schreibt Config/Workspace auf den Host unter `~/.openclaw/`

Nach dem Lauf:
- UI oeffnen: `http://127.0.0.1:18789/`
- Token im Control UI unter Settings eintragen

Control UI Referenz: citeturn0search3

Quelle: Docker-Setup in der offiziellen Doku. citeturn0search1

## Compose in diesem Repo (optional)
Dieser Ordner enthaelt ein eigenes `docker-compose.yml`, das auf `openclaw/upstream/` als Build-Context zeigt.
Start:

```bash
docker compose --env-file .env --env-file .config.env --env-file openclaw/.config.env \
  -f openclaw/docker-compose.yml up -d --build
```

Wichtig:
- Host-Port ist `127.0.0.1:18789` (lokal). Keine LAN-Expose ohne Reverse Proxy.
- Host-Config liegt unter `~/.openclaw/` und wird in den Container gemountet.

## Telegram Channel (CLI-Container)
Wenn der Bot-Token in `.env` liegt:

```bash
docker compose --env-file .env --env-file .config.env --env-file openclaw/.config.env \
  -f openclaw/docker-compose.yml run --rm openclaw-cli \
  channels add --channel telegram --token "$OPENCLAW_TELEGRAM_BOT_TOKEN"
```

Quelle: Docker-CLI Channel Setup in der Doku. citeturn0search1

## Telegram Security (Config)
Die Telegram-Policies werden in `~/.openclaw/openclaw.json` gesetzt.
Beispiel (Allowlist + Mention-Gate):

```json
{
  "channels": {
    "telegram": {
      "dmPolicy": "pairing",
      "groupPolicy": "allowlist",
      "groups": {
        "<chat_id>": {
          "requireMention": true
        }
      }
    }
  }
}
```

Config-Referenz + Telegram-Policy Keys: citeturn0search0turn0search2

## Healthcheck (optional)

```bash
docker compose -f openclaw/docker-compose.yml exec openclaw-gateway \
  node dist/index.js health --token "$OPENCLAW_GATEWAY_TOKEN"
```

Quelle: Docker Healthcheck in der Doku. citeturn0search1
