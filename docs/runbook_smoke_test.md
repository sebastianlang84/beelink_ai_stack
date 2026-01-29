# Runbook — Smoke Test (P0) für ai_stack

Ziel: Ein reproduzierbarer Minimal-Check, dass **Open WebUI** + das **Transcript Miner Tool** laufen, lokal erreichbar sind und die Tool→Open-WebUI-API Auth funktioniert.

Hinweis: Dieser Smoke-Test prüft **nicht** die inhaltliche Qualität der Summaries. Dafür gibt es am Ende einen optionalen End-to-End Test (1 Topic, 2–3 Videos).

## 0) Voraussetzungen

- Docker + Compose Plugin installiert
- Tailscale optional (für VPN-only Zugriff über HTTPS)
- Env-Files vorhanden (gitignored; keine Werte im Git):
  - `/home/wasti/ai_stack/.env`
  - `/home/wasti/ai_stack/.config.env` (optional)
  - `/home/wasti/ai_stack/open-webui/.config.env` (optional)
  - `/home/wasti/ai_stack/mcp-transcript-miner/.config.env` (optional)

## 1) Secrets validieren (ohne Leaks)

```bash
./scripts/env_doctor.sh
```

Wenn du Output teilen musst:
```bash
docker compose --env-file .env --env-file .config.env --env-file mcp-transcript-miner/.config.env -f mcp-transcript-miner/docker-compose.yml config | ./scripts/redact_secrets_output.sh
```

## 2) Compose-Stacks starten

Shared Docker-Netz (einmalig):
```bash
./scripts/provision_ai_stack_docker_objects.sh
```

Open WebUI:
```bash
cd /home/wasti/ai_stack
docker compose --env-file .env --env-file .config.env --env-file open-webui/.config.env -f open-webui/docker-compose.yml up -d
```

Transcript Miner Tool:
```bash
cd /home/wasti/ai_stack
docker compose --env-file .env --env-file .config.env --env-file mcp-transcript-miner/.config.env -f mcp-transcript-miner/docker-compose.yml up -d --build
```

## 2.1) Optional: YouTube 429/Block (Cookies-Bypass)

Wenn YouTube 429/Block auftritt, nutze einen Cookies-Export (z. B. aus dem Browser).

1) Datei im Repo-Root ablegen (gitignored):
```bash
/home/wasti/ai_stack/youtube_cookies.txt
```
2) In `mcp-transcript-miner/.config.env` setzen:
```bash
YOUTUBE_COOKIES_FILE=/host_secrets/youtube_cookies.txt
```

Hinweis: Der Container mountet per Default den Repo-Root nach `/host_secrets`.

## 3) Smoke-Test Script (empfohlen)

```bash
./scripts/smoke_test_ai_stack.sh --up --build
```

Erwartung:
- Open WebUI: `http://127.0.0.1:3000/` → `200`
- Tool: `/healthz` ok
- Tool → Open WebUI API: `/api/v1/files/` → `200` (erfordert gültiges `OPEN_WEBUI_API_KEY`)

## 4) Tailscale Serve (VPN-only Zugriff über HTTPS)

Wenn du Open WebUI im Tailnet bereitstellen willst:
```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:3000
sudo tailscale serve status
```

Erwartung: Zugriff im VPN über `https://<node>.<tailnet>.ts.net/` lädt Open WebUI.

## 5) Optional: End-to-End (1 Topic, 2–3 Videos)

Ziel: Ein echter Indexing-Durchlauf in eine Knowledge Collection.

1. In Open WebUI eine Knowledge Collection anlegen, **Name = Topic** (z. B. `investing`).
2. Optional: Nur wenn der Name nicht dem Topic entspricht, Mapping setzen:
   - `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON='{"investing":"<knowledge_id>"}'`
3. Mit dem Tool einen Topic-Sync triggern:
   - In Open WebUI als External Tool „Transcript Miner“ verwenden: `sync.topic` mit `topic=investing`
4. Prüfen:
   - Knowledge Collection enthält neue Summary-Dokumente
   - Chat-Retrieval mit der Collection liefert passende Zitate/Referenzen

Hinweis (Open WebUI UI): Die Collection-Anzeige „Updated …“ wird bei File-Adds in manchen OWUI-Versionen **nicht** aktualisiert. Verlasse dich daher auf `/api/v1/knowledge/<id>/files` (Count + `created_at`) statt auf die UI-Zeitstempel.

Hinweis: Optional kann Auto-Sync aktiviert werden (Service-Config):
- `OPEN_WEBUI_AUTO_SYNC_AFTER_RUN=true`
Optional: Collections automatisch anlegen:
- `OPEN_WEBUI_CREATE_KNOWLEDGE_IF_MISSING=true`
