# qdrant — Env Layout (ohne Werte)

Default ist localhost-only. Einen API-Key brauchst du erst, wenn Qdrant über localhost hinaus erreichbar wird.

Start-Pattern (vom Repo-Root):
`docker compose --env-file .env --env-file .config.env --env-file qdrant/.config.env -f qdrant/docker-compose.yml up -d`

## Shared Secrets (`/home/wasti/ai_stack/.env`)

Optional:
- `QDRANT_API_KEY`

## Service Config (`/home/wasti/ai_stack/qdrant/.config.env`)

Typische Non-Secrets:
- `QDRANT_BIND_ADDRESS`
- `QDRANT_HTTP_PORT`
