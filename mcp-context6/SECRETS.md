# mcp-context6 — Env Layout (ohne Werte)

Start-Pattern (vom Repo-Root):
`docker compose --env-file .env --env-file .config.env --env-file mcp-context6/.config.env -f mcp-context6/docker-compose.yml up -d --build`

## Shared Secrets (`/home/wasti/ai_stack/.env`)

Required (für Open WebUI Knowledge Upload):
- `OPEN_WEBUI_API_KEY` (preferred) **oder** `OWUI_API_KEY` (deprecated Alias)

## Service Config (`/home/wasti/ai_stack/mcp-context6/.config.env`)

Typische Non-Secrets:
- `CONTEXT6_BIND_ADDRESS`
- `CONTEXT6_HOST_PORT`
- `CONTEXT6_LOG_LEVEL`
- `CONTEXT6_BASE_URL` (optional; wenn hinter Reverse Proxy)
- `OPEN_WEBUI_BASE_URL`
- `OPEN_WEBUI_PROCESS_POLL_INTERVAL_SECONDS`, `OPEN_WEBUI_PROCESS_TIMEOUT_SECONDS`
