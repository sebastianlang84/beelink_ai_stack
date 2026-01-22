# Runbook — Secrets als Env-Files (ai_stack)

Stand: 2026-01-21

Ziel: Secrets in `/home/wasti/ai_stack/.env` (secrets-only) und Non-Secrets in `/home/wasti/ai_stack/.config.env` + `/home/wasti/ai_stack/<service>/.config.env` (alles **gitignored**) und Start der Stacks via `docker compose --env-file ...`.

Hinweis: Dieses Runbook enthält **keine** Secret-Werte.

---

## 1) Zielpfade (Repo)

Wir verwenden:
- Shared Secrets: `/home/wasti/ai_stack/.env` (**nur Secrets**)
- Shared Config (non-secret): `/home/wasti/ai_stack/.config.env`
- Pro Service Config (non-secret): `/home/wasti/ai_stack/<service>/.config.env`

Beides ist gitignored (niemals committen).

---

## 2) Rechte (empfohlen)

```bash
chmod 600 /home/wasti/ai_stack/.env
chmod 600 /home/wasti/ai_stack/.config.env
chmod 600 /home/wasti/ai_stack/open-webui/.config.env
chmod 600 /home/wasti/ai_stack/mcp-transcript-miner/.config.env
```

---

## 3) Env-Files anlegen (secrets + config)

1) Shared Secrets (Template → `.env`):
- `/home/wasti/ai_stack/.env.example`
- `/home/wasti/ai_stack/.env`

2) Shared Config (Template → `.config.env`):
- `/home/wasti/ai_stack/.config.env.example` → `/home/wasti/ai_stack/.config.env`

3) Service-Config (Template → `.config.env`):
- `/home/wasti/ai_stack/open-webui/.config.env.example` → `/home/wasti/ai_stack/open-webui/.config.env`
- `/home/wasti/ai_stack/mcp-transcript-miner/.config.env.example` → `/home/wasti/ai_stack/mcp-transcript-miner/.config.env`

Shared `.env` (**nur Secrets**, ohne Werte hier):
- `WEBUI_SECRET_KEY=...`
- `YOUTUBE_API_KEY=...`
- `OPENROUTER_API_KEY=...`
- `OPEN_WEBUI_API_KEY=...` (preferred) **oder** `OWUI_API_KEY=...` (deprecated Alias)

Config `.config.env` (Beispiele, **non-secret**):
- `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON='{"ai_knowledge":"<knowledge_id_here>"}'` (oder fallback `OPEN_WEBUI_KNOWLEDGE_ID=...`)
- alternativ: `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON_PATH=/config/knowledge_ids.json`
- optional: `OPEN_WEBUI_BASE_URL=http://owui:8080`
- optional: `YOUTUBE_COOKIES_FILE=/host_secrets/youtube_cookies.txt`
- optional: `TRANSCRIPT_MINER_OUTPUT_ROOT_HOST=/srv/ai-stack/transcript-miner/output`

Hinweis: JSON-Werte am besten in **einfachen Anführungszeichen** notieren, damit Shell/Compose das nicht “zerlegt”.

---

## 4) Repo-Secrets vermeiden (damit nichts “aus Versehen” liegen bleibt)

Diese Dateien sollen **keine echten Secrets** enthalten:
- `**/.env` innerhalb des Repo (nicht anlegen, nicht committen)

---

## 5) Stacks starten (immer explizit mit `--env-file`)

Beispiele:

Open WebUI (vom Repo-Root):
```bash
cd /home/wasti/ai_stack
docker compose --env-file .env --env-file .config.env --env-file open-webui/.config.env -f open-webui/docker-compose.yml up -d
```

Transcript Miner Tool (inkl. Knowledge Indexing):
```bash
cd /home/wasti/ai_stack
docker compose --env-file .env --env-file .config.env --env-file mcp-transcript-miner/.config.env -f mcp-transcript-miner/docker-compose.yml up -d --build
```

Validierung:
```bash
docker compose --env-file .env --env-file .config.env --env-file open-webui/.config.env -f open-webui/docker-compose.yml config >/dev/null
docker compose --env-file .env --env-file .config.env --env-file mcp-transcript-miner/.config.env -f mcp-transcript-miner/docker-compose.yml config >/dev/null
```

Wenn du Output teilen musst (Debug/Chat), immer redacted:
```bash
docker compose --env-file .env --env-file .config.env --env-file mcp-transcript-miner/.config.env -f mcp-transcript-miner/docker-compose.yml config | ./scripts/redact_secrets_output.sh
```

---

## 6) API Keys (wohin damit?)

API Keys gehören nur dann in Container-Env, wenn der jeweilige Service sie zur Laufzeit benötigt.

Keys für **Clients** (z. B. eigene Scripts), die nicht in Containern laufen, gehören **nicht** in Container-Env.
Empfehlung: Passwortmanager oder separates, gitignored File außerhalb von Docker/Compose.

---

## 7) Key-Generierung (Beispiel)

Open WebUI `WEBUI_SECRET_KEY` (32 bytes hex):
```bash
openssl rand -hex 32
```
