# Runbook — Secrets als Env-Files (ai_stack)

Stand: 2026-01-14

Ziel: Keine Secrets im Repo (`/home/wasti/ai_stack/...`), sondern zentrale Ablage am Server und Start der Stacks via `docker compose --env-file ...`.

Hinweis: Dieses Runbook enthält **keine** Secret-Werte.

---

## 1) Zielpfade (Server)

Wir verwenden (privater Home-Server, User `wasti` darf Owner sein):

- Verzeichnis: `/etc/ai-stack/`
- SSOT (Secrets): `/etc/ai-stack/secrets.env` (nur Secrets, zentral)
- Config (non-secret): `/etc/ai-stack/config.env` (nur Nicht-Secrets: Pfade/Hosts/IDs/Mappings)

Least-Privilege erreichst du trotzdem, weil nur Variablen, die in einem `docker-compose.yml` unter `environment:` referenziert werden, im jeweiligen Container landen.

---

## 2) Verzeichnis anlegen + Rechte

```bash
sudo mkdir -p /etc/ai-stack
sudo chown wasti:wasti /etc/ai-stack
sudo chmod 700 /etc/ai-stack
```

---

## 3) SSOT-Datei anlegen (Standard)

```bash
touch /etc/ai-stack/secrets.env
chmod 600 /etc/ai-stack/secrets.env
```

Dann mit Editor befüllen (Beispiel-Keys, ohne Werte; **nur Secrets**):
- `WEBUI_SECRET_KEY=...` (Open WebUI; stabil halten)
- `YOUTUBE_API_KEY=...` (TranscriptMiner Runs / YouTube API)
- `OPENROUTER_API_KEY=...` (TranscriptMiner Runs / LLM)
- `OPEN_WEBUI_API_KEY=...` (Open WebUI JWT Bearer; für Knowledge Indexing)
  - Hinweis: `OWUI_API_KEY` ist ein deprecated Alias (falls noch vorhanden: migrieren).

Hinweis: JSON-Werte am besten in **einfachen Anführungszeichen** notieren, damit Shell/Compose das nicht “zerlegt”.

## 3.1 Config-Datei anlegen (Standard, non-secret)

```bash
touch /etc/ai-stack/config.env
chmod 600 /etc/ai-stack/config.env
```

Dann mit Editor befüllen (**nur Nicht-Secrets**):
- `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON='{"ai_knowledge":"<knowledge_id_here>"}'` (Topic → Knowledge Collection)
  - optional auch für `context6` (Embeddings via OpenRouter)
- `OPEN_WEBUI_KNOWLEDGE_ID=...` (Fallback: Default Knowledge Collection, falls Topic-Mapping fehlt)
- `OPEN_WEBUI_BASE_URL=http://owui:8080` (optional; Default ist im Container gesetzt)
- `YOUTUBE_COOKIES_FILE=/host_secrets/youtube_cookies.txt` (optional; falls 429/Block)

---

## 4) Repo-Secrets vermeiden (damit nichts “aus Versehen” liegen bleibt)

Diese Dateien sollen **keine echten Secrets** enthalten:
- `**/.env` innerhalb des Repo (nicht anlegen, nicht committen)

---

## 5) Stacks starten (immer explizit mit `--env-file`)

Beispiele:

Open WebUI:
```bash
cd /home/wasti/ai_stack/open-webui
docker compose --env-file /etc/ai-stack/config.env --env-file /etc/ai-stack/secrets.env up -d
```

Transcript Miner Tool (inkl. Knowledge Indexing):
```bash
cd /home/wasti/ai_stack/mcp-transcript-miner
docker compose --env-file /etc/ai-stack/config.env --env-file /etc/ai-stack/secrets.env up -d --build
```

Validierung:
```bash
docker compose --env-file /etc/ai-stack/config.env --env-file /etc/ai-stack/secrets.env config >/dev/null
docker compose --env-file /etc/ai-stack/config.env --env-file /etc/ai-stack/secrets.env ps
```

Wenn du Output teilen musst (Debug/Chat), immer redacted:
```bash
docker compose --env-file /etc/ai-stack/config.env --env-file /etc/ai-stack/secrets.env config | ./scripts/redact_secrets_output.sh
```

---

## 6) API Keys (wohin damit?)

API Keys gehören nur dann in Container-Env, wenn der jeweilige Service sie zur Laufzeit benötigt.

Keys für **Clients** (z. B. eigene Scripts), die nicht in Containern laufen, gehören **nicht** in Container-Env.
Empfehlung:
- in Passwortmanager, oder
- separates Client-File, z. B. `/etc/ai-stack/clients.env` (chmod 600), das nur von Scripts genutzt wird.

---

## 7) Key-Generierung (Beispiel)

Open WebUI `WEBUI_SECRET_KEY` (32 bytes hex):
```bash
openssl rand -hex 32
```
