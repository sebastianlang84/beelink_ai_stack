# mcp-owui-connector — Env Layout (ohne Werte)

Start:
`docker compose --env-file .env --env-file .config.env --env-file mcp-owui-connector/.config.env -f mcp-owui-connector/docker-compose.yml up -d --build`

## Shared Secrets (`/home/wasti/ai_stack/.env`)
- `OPEN_WEBUI_API_KEY` (Bearer Token fuer Open WebUI API)

Optional Alias:
- `OWUI_API_KEY` (deprecated alias; wird als Fallback akzeptiert)

## Service Config (`/home/wasti/ai_stack/mcp-owui-connector/.config.env`)
Siehe `mcp-owui-connector/.config.env.example`.

