# mcp-transcript-miner — Env Layout (ohne Werte)

Start-Pattern (vom Repo-Root):
`docker compose --env-file .env --env-file .config.env --env-file mcp-transcript-miner/.config.env -f mcp-transcript-miner/docker-compose.yml up -d --build`

## Shared Secrets (`/home/wasti/ai_stack/.env`)

Required:
- `YOUTUBE_API_KEY`
- `OPENROUTER_API_KEY`
- `OPEN_WEBUI_API_KEY` (preferred) **oder** `OWUI_API_KEY` (deprecated Alias)

## Service Config (`/home/wasti/ai_stack/mcp-transcript-miner/.config.env`)

Knowledge Target (optional Mapping):
- Default: Knowledge-Name = Topic (z. B. `investing`)
- Optional: `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON` (Mapping) **oder** `OPEN_WEBUI_KNOWLEDGE_ID` (Fallback)
  - optional: `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON_PATH=/config/knowledge_ids.json` (Datei statt Inline-JSON)

Recommended:
- `OPEN_WEBUI_BASE_URL` (Default im Container: `http://owui:8080`)
- `TRANSCRIPT_MINER_OUTPUT_ROOT_HOST` (z. B. `/home/wasti/ai_stack_data/transcript-miner/output`)

Optional:
- `YOUTUBE_COOKIES_FILE=/host_secrets/youtube_cookies.txt`
- `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`
- `TRANSCRIPT_MINER_DEFAULT_LANGUAGES`, `TRANSCRIPT_MINER_LOG_LEVEL`

## Optionales Secret-Artefakt (Datei)

- `/home/wasti/ai_stack/youtube_cookies.txt` (gitignored; falls YouTube 429/Block)
