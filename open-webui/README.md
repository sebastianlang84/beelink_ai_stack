# open-webui — Betrieb

Ziel: Open WebUI läuft persistent, upgradesicher und ohne Secrets im Repo. Image ist auf **0.7.2** gepinnt.

## Quickstart
1. In `open-webui/` wechseln: `cd open-webui`
2. Secrets außerhalb des Repo setzen (siehe `open-webui/SECRETS.md:1`):
   - mindestens `WEBUI_SECRET_KEY` (z. B. `openssl rand -hex 32`)
3. Start: `docker compose --env-file /etc/ai-stack/secrets.env up -d`
4. Zugriff lokal am Server: `http://127.0.0.1:3000`

## Zugriff (VPN-only empfohlen)
Default ist **localhost-only** gemappt: `127.0.0.1:3000 -> 8080` (kein LAN-Port).

Option A (einfach, VPN-only): im Tailnet bereitstellen:
- `sudo tailscale serve --bg --https=443 http://127.0.0.1:3000`

Option B (später): Reverse Proxy (Traefik/Caddy) im Docker-Netz.

## Persistenz / Backup
- Volume: `open_webui_data` (Pfad im Container: `/app/backend/data`)

Runbook: `docs/runbook_backup_restore.md:1`

## Integration (RAG / Knowledge Auto-Indexing)
- Für Cross-Stack Kommunikation (z. B. Tool ↔ `owui`) wird ein externes Docker-Netz `ai-stack` verwendet:
  - `./scripts/provision_ai_stack_docker_objects.sh`
- Indexer-Service: `mcp-transcript-miner/README.md:1`

## External Tools (Import JSON)
Templates: `open-webui/tool-imports/README.md:1`

Optional (statt UI-Import): Tools per Admin API setzen:
- Script: `scripts/openwebui_apply_tool_imports.sh`
- Voraussetzung: Admin Bearer Token (primär: `OPEN_WEBUI_API_KEY`; `OWUI_API_KEY` ist deprecated Alias)
