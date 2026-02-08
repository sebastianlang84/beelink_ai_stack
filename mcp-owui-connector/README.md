# mcp-owui-connector — Open WebUI Connector (MCP)

MCP Streamable HTTP Server, der ausgewählte Open WebUI APIs als Tools bereitstellt:
- Knowledge Collections (listen, files listen, optional upload/add/remove)
- Admin: External Tools config (`/api/v1/configs/tool_servers`) lesen, optional aus Repo-Templates anwenden

Hinweis: Im Repo gab es bisher **kein** PRD fuer diesen Connector; die offene Architektur-Notiz stand in `TODO.md` (OpenClaw ↔ OWUI Knowledge). Dieses Service-README und `mcp-owui-connector/PRD.md` definieren jetzt den Scope.

## Quickstart (Docker)

1) Shared Docker objects (einmalig):
```bash
./scripts/provision_ai_stack_docker_objects.sh
```

2) Secrets (außerhalb Repo) sicherstellen:
- `OPEN_WEBUI_API_KEY` (Bearer Token) in `/home/wasti/ai_stack/.env` (nicht committen)

3) Config (non-secret) anlegen:
```bash
cp -n mcp-owui-connector/.config.env.example mcp-owui-connector/.config.env
```

4) Start:
```bash
docker compose --env-file .env --env-file .config.env --env-file mcp-owui-connector/.config.env -f mcp-owui-connector/docker-compose.yml up -d --build
```

5) MCP Endpoint (für RooCode / externe Clients):
- `http://127.0.0.1:8877/mcp` (localhost-only; empfohlen via Tailscale Serve)

## Security / Modes

Default ist read-only fuer Write-Operationen:
- `OWUI_CONNECTOR_ALLOW_KNOWLEDGE_WRITE=false`
- `OWUI_CONNECTOR_ALLOW_ADMIN_WRITE=false`

Wenn du Write-Tools aktivieren willst: in `mcp-owui-connector/.config.env` auf `true` setzen.

## Tools (Auszug)
- `capabilities.get`
- `owui.knowledge.list`
- `owui.knowledge.files.list`
- `owui.files.process.status`
- `owui.tool_servers.get`
- `owui.tool_servers.apply_from_repo` (nur wenn `OWUI_CONNECTOR_ALLOW_ADMIN_WRITE=true`)
- `owui.knowledge.upload_markdown` (nur wenn `OWUI_CONNECTOR_ALLOW_KNOWLEDGE_WRITE=true`)

## Beispiel (MCP: tools/list)

```bash
curl -sS http://127.0.0.1:8877/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Roo Code (VS Code) Integration

In VS Code (Remote auf dem Server):
1) Roo Code -> **MCP servers** -> **Add server**
2) Name: `owui-connector`
3) Type: `streamable-http`
4) URL: `http://127.0.0.1:8877/mcp`

Wenn du per Datei konfigurieren willst (Host-spezifischer Pfad):
- `~/.vscode-server/data/User/globalStorage/rooveterinaryinc.roo-cline/settings/mcp_settings.json`

## Storage / Backup
- Volume: `owui-connector-data` (Backups der Tool-Server Config)

Runbook: `docs/runbook_backup_restore.md:1`
