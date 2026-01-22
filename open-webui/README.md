# open-webui — Betrieb

Ziel: Open WebUI läuft persistent, upgradesicher und ohne Secrets im Repo. Image ist auf **0.7.2** gepinnt.

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

Option B (später): Reverse Proxy (Traefik/Caddy) im Docker-Netz.

## Persistenz / Backup
- Volume: `owui-data` (Pfad im Container: `/app/backend/data`)

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
