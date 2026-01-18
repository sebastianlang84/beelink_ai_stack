---
name: ai-stack-openwebui-tool-imports
description: Manage Open WebUI External Tools imports in ai_stack (MCP Streamable HTTP and legacy OpenAPI), update tool import JSON templates, and apply them via the Open WebUI Admin API script. Use when adding/updating MCP servers, changing tool URLs, or troubleshooting tool discovery in Open WebUI.
---

# Open WebUI tool imports (External Tools)

## Files and workflow

1) Update or add a template under `open-webui/tool-imports/`:
- MCP tools: `type: "mcp"` and `url: "http(s)://.../mcp"`
- Legacy OpenAPI tools: `type: "openapi"` and `spec: "http(s)://.../openapi.json"`

2) Keep templates compatible with Open WebUI 0.7.x:
- Ensure each connection has `config: {}` (avoid response validation crashes).

3) Apply to Open WebUI (overwrites current tool server config):
- Run: `OPEN_WEBUI_TOKEN=<admin> ./scripts/openwebui_apply_tool_imports.sh`

The script writes a backup into `open-webui/tool-imports/backup_tool_servers__*.json`.

## URL patterns

- Docker-to-Docker (same network): `http://<service-name>:<port>/mcp`
- Host-localhost published port: `http://host.docker.internal:<port>/mcp`
- Tailnet HTTPS (Tailscale Serve): `https://<node>.<tailnet>.ts.net/mcp`

## Troubleshooting

- “No tools / discovery fails”: verify the MCP endpoint responds to `POST /mcp`.
- “Chunk too big”: prefer `capabilities.get` short output or pass `max_chars` if supported by the tool server.

