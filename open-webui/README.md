# open-webui — Betrieb

Ziel: Open WebUI läuft persistent, upgradesicher und ohne Secrets im Repo. Image ist auf **0.8.3** gepinnt.

## Quickstart
1. Shared Secrets setzen: `/home/wasti/ai_stack/.env.example` → `/home/wasti/ai_stack/.env` (nicht committen).
2. Shared Config setzen (non-secret): `.config.env.example` → `.config.env` (nicht committen).
3. Service-Config setzen (non-secret): `open-webui/.config.env.example` → `open-webui/.config.env` (nicht committen, optional).
4. Start (vom Repo-Root): `docker compose --env-file .env --env-file .config.env --env-file open-webui/.config.env -f open-webui/docker-compose.yml up -d`
5. Zugriff lokal am Server: `http://127.0.0.1:3000`

## Zugriff (VPN-only empfohlen)
Default ist **localhost-only** gemappt: `127.0.0.1:3000 -> 8080` (kein LAN-Port).

Option A (einfach, VPN-only): im Tailnet bereitstellen:
- `sudo tailscale serve --bg --https=443 http://127.0.0.1:3000`

Option B (Pfad /owui, Tailnet-HTTPS): zusätzliche Pfade fuer Assets/API erforderlich:

```bash
sudo tailscale serve reset
sudo tailscale serve --bg --https=443 --set-path /owui          http://127.0.0.1:3000/
sudo tailscale serve --bg --https=443 --set-path /_app          http://127.0.0.1:3000/_app
sudo tailscale serve --bg --https=443 --set-path /static        http://127.0.0.1:3000/static
sudo tailscale serve --bg --https=443 --set-path /manifest.json http://127.0.0.1:3000/manifest.json
sudo tailscale serve --bg --https=443 --set-path /api           http://127.0.0.1:3000/api
```

Hinweis: Ohne die Asset/API-Pfade kommt es zu "Backend Required" oder 404 auf `_app`-Bundles.
Wichtig: OWUI redirectet nach Login auf `/`. Ein reines `/owui`-Setup ist daher fragil; Root-Serve ist der stabile Weg.

Option C (spater): Reverse Proxy (Traefik/Caddy) im Docker-Netz.

## 502 Auto-Recovery (Tailscale Serve Upstream)
Wenn `owui` gestoppt ist, liefert die `ts.net` URL typischerweise sofort `502`.

Ops-Commands:
- Status: `./scripts/ensure-owui-up.sh status`
- Auto-Recover: `./scripts/ensure-owui-up.sh ensure`

Persistenter Guard (systemd timer):
- `scripts/systemd/ai-stack-owui-ensure.service`
- `scripts/systemd/ai-stack-owui-ensure.timer`

Runbook: `docs/runbook-owui-502-autorecover.md:1`

## Persistenz / Backup
- Volume: `owui-data` (Pfad im Container: `/app/backend/data`)

Runbook: `docs/runbook_backup_restore.md:1`

## Integration (RAG / Knowledge Auto-Indexing)
- Für Cross-Stack Kommunikation (z. B. Tool ↔ `owui`) wird ein externes Docker-Netz `ai-stack` verwendet:
  - `./scripts/provision_ai_stack_docker_objects.sh`
- Indexer-Service: `mcp-transcript-miner/README.md:1`

## Optional: Debug Proxy (OpenRouter Request Tracing)
Ziel: Prompt-Ketten + Tool-Calls als JSONL mitschneiden.
1. Debug-Proxy starten: `debug-proxy/README.md:1`
2. In `open-webui/.config.env` setzen:
   - `OWUI_HTTP_PROXY=http://debug-proxy:8080`
   - `OWUI_HTTPS_PROXY=http://debug-proxy:8080`
   - `OWUI_NO_PROXY=owui,tika,tm,context6,qdrant,localhost,127.0.0.1`
   - `OWUI_CA_BUNDLE_PATH=/debug-proxy/mitmproxy/mitmproxy-ca-cert.pem`
   - `DEBUG_PROXY_DATA_DIR_HOST=/home/wasti/ai_stack_data/debug-proxy`
3. OWUI neu starten.

## Optional: Apache Tika (Content Extraction fuer Documents/RAG)
Ziel: bessere Text-Extraktion (inkl. OCR bei Scan-PDFs mit `latest-full`).

1. Tika Service starten (ist im Compose enthalten):
   - `docker compose --env-file .env --env-file .config.env --env-file open-webui/.config.env -f open-webui/docker-compose.yml up -d`
2. In Open WebUI:
   - Admin Panel -> Settings -> Documents
   - Content Extraction Engine: `Tika`
   - Tika Server URL: `http://tika:9998/tika`

Notizen:
- Wenn Debug-Proxy aktiv ist: `tika` muss in `OWUI_NO_PROXY` stehen, sonst versucht OWUI ggf. den internen Call zu proxien.

## RAG Retrieval (aktueller Stand)
- Embedder RAG Setting: Top-K = 30 (reduziert von 100) via Open WebUI UI.

## API Keys (aktueller Stand)
- Default User Permissions: `features.api_keys=true` (aktiviert ueber Admin API; API-Key Erstellung erlaubt).
- OpenClaw user record: `open-webui/openclaw_user.txt` (email + role; no secrets).

## External Tools (Import JSON)
Templates: `open-webui/tool-imports/README.md:1`

Optional (statt UI-Import): Tools per Admin API setzen:
- Script: `scripts/openwebui_apply_tool_imports.sh`
- Voraussetzung: Admin Bearer Token (primär: `OPEN_WEBUI_API_KEY`; `OWUI_API_KEY` ist deprecated Alias)
