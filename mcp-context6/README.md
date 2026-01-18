# mcp-context6 — context6 MCP Server (PoC)

MCP Streamable HTTP Server für `context6` (Doku-Fetch/Normalize/Chunk/Search/Get).

PRD: `docs/prd_context6_poc_working_draft.md:1`

## Quickstart (Docker)

1) External Docker network (einmalig, falls noch nicht vorhanden):
```bash
./scripts/create_ai_stack_network.sh
```

2) Secrets (außerhalb Repo) sicherstellen:
- `OPEN_WEBUI_API_KEY` (Admin Token) in `/etc/ai_stack/secrets.env` (für Knowledge Indexing)

3) Start:
```bash
cd /home/wasti/ai_stack/mcp-context6
docker compose --env-file /etc/ai_stack/secrets.env up -d --build
```

4) MCP Endpoint (für Open WebUI / RooCode):
- `http://127.0.0.1:8816/mcp` (localhost-only; empfohlen via Tailscale Serve)

Tailscale Serve (Beispiel):
```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8816
sudo tailscale serve status
```

## Open WebUI Import JSON
- Template: `open-webui/tool-imports/tool_import_context6.json` (URL auf deine `*.ts.net` Serve-URL anpassen)

## MCP Tools (Auszug)
- `capabilities.get` (optional: `{ "max_chars": 2000 }`)
- `sync.prepare` (liefert Vorschlag + bestehende Open WebUI Knowledge Bases)
- `owui.knowledge.list` / `owui.knowledge.create` (Knowledge Bases anzeigen/anlegen)
- `sync.start`:
  - lokal-only: `{ "source_id": "...", "mode": "full" }`
  - in Open WebUI Knowledge: `{ "source_id": "...", "knowledge_name": "open-webui-docs", "create_knowledge_if_missing": true }`
  - alternativ per ID: `{ "source_id": "...", "knowledge_id": "<open-webui-knowledge-id>" }`
- `sources.create` GitHub Config (empfohlen): `{"config":{"github":{"repo":"open-webui/docs","ref":"main"}}}` (Compat: auch `{"config":{"repo":"open-webui/docs"}}` oder `{"config":{"url":"https://github.com/open-webui/docs"}}`)

Empfohlener Flow (LLM + User-Entscheidung):
1) `sync.prepare` → LLM zeigt `suggested_knowledge_name` + `existing`
2) User wählt: bestehend / Vorschlag / neuer Name
3) `sync.start` mit `knowledge_name` (+ optional `create_knowledge_if_missing`)

Hinweis: Upload-Filenames in Open WebUI sind jetzt sprechend (aus `canonical_path`) + stabiler Kurz-Hash, z. B. `context6__getting-started__abc123...md`.

## Storage / Backup
- `mcp_context6_context6_data` (SQLite + Artefakte)
- `mcp_context6_context6_cache` (Cache)

Runbook: `docs/runbook_backup_restore.md:1` (Volume-Backup via `scripts/backup_docker_volume.sh`)
