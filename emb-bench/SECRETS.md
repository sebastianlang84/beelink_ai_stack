# emb-bench — Env Layout (ohne Werte)

Start-Pattern (vom Repo-Root):
`./scripts/run_emb_bench.sh --env-file .env -- <args>`

## Shared Secrets (`/home/wasti/ai_stack/.env`)

Required (wenn OpenRouter genutzt wird):
- `OPENROUTER_API_KEY`

## Config (Non-Secrets)

Optional (meist als Shell-Env gesetzt; kein Env-File nötig):
- `DOCKER_UID`, `DOCKER_GID`
