# open-webui — Env Layout (ohne Werte)

Start-Pattern (vom Repo-Root):
`docker compose --env-file .env --env-file .config.env --env-file open-webui/.config.env -f open-webui/docker-compose.yml up -d`

## Shared Secrets (`/home/wasti/ai_stack/.env`)

Required:
- `WEBUI_SECRET_KEY`

Optional (nur wenn Open WebUI selbst Provider nutzt):
- `OPENAI_API_KEY`

## Service Config (`/home/wasti/ai_stack/open-webui/.config.env`)

Typische Non-Secrets:
- `TZ`
- `OPEN_WEBUI_IMAGE_TAG`
- `OPEN_WEBUI_BIND_ADDRESS`
- `OPEN_WEBUI_HOST_PORT`
- `OLLAMA_BASE_URL`
- `OWUI_HTTP_PROXY`
- `OWUI_HTTPS_PROXY`
- `OWUI_NO_PROXY`
- `OWUI_CA_BUNDLE_PATH`
- `DEBUG_PROXY_DATA_DIR_HOST`

## Hinweise
- `WEBUI_SECRET_KEY` stabil halten (nicht bei jedem Deploy ändern). Generieren z. B. mit `openssl rand -hex 32`.
