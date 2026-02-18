# Policy — Secrets & Environment Variables (ai_stack)

Stand: 2026-01-21

Ziel: Secrets werden repo-lokal verwaltet, aber **nie committed**:
- Shared Secrets: `/home/wasti/ai_stack/.env` (gitignored)
- Shared Config (non-secret): `/home/wasti/ai_stack/.config.env` (gitignored)
- Service-Config (non-secret): `/home/wasti/ai_stack/<service>/.config.env` (gitignored)

Gleichzeitig: klare Trennung zwischen shared vs service-spezifisch, damit `.env` nicht wieder „alles auf einmal“ wird.

---

## 0) Scope

Diese Policy gilt für:
- Docker Compose Stacks unter `/home/wasti/ai_stack/…`
- Services wie:
  - Open WebUI
  - Transcript Miner MCP Server (`mcp-transcript-miner`)
  - Qdrant, Traefik, SearXNG (falls vorhanden)

Nicht im Scope:
- Vollwertige Secret-Manager (Vault, AWS Secrets Manager, etc.).

---

## 1) Begriffe

- **Secret**: API Key, Token, Passwort, private Schlüssel.
- **SSOT (Single Source of Truth)**: pro-Stack Quelle für Secrets (kein „eine Datei für alles“).
- **Least Privilege**: ein Container erhält nur die Secrets, die er zwingend benötigt.
- **Env File**: Datei im Format `KEY=value`, von Docker Compose mit `--env-file` eingelesen.
- **Config (non-secret)**: Host-/Setup-spezifische Werte, die nicht geheim sind (z. B. Pfade/Hosts/IDs/Mappings), aber trotzdem nicht ins Repo gehören.

---

## 2) Harte Regeln (Do / Don’t)

### 2.1 Do

- Committe **niemals** `.env` Dateien (gitignored).
- Shared Secrets in `.env` (nur Secrets, keine Pfade/Hosts/IDs/Mappings).
- Non-Secrets in `.config.env` und `<service>/.config.env` (Pfade/Hosts/Ports/IDs/Mappings).
- **Dateirechte restriktiv** halten (empfohlen):
  - `chmod 600 .env .config.env <service>/.config.env`
  - Repo-Verzeichnis selbst nicht world-readable.
- **Provider-Keys** (OpenAI/OpenRouter/etc.) nicht global an alle Container durchreichen, sondern nur dort, wo sie gebraucht werden.

### 2.2 Don’t

- Keine Secrets in:
  - Git
  - Dockerfiles
  - Logs
  - Screenshots/Chat
- Keine „ungefilterten“ Debug-Outputs teilen, die Env-Werte enthalten (z. B. `docker compose ... config`).
  - Safe: `docker compose ... config >/dev/null`
  - Wenn du Output teilen musst: `docker compose ... config | ./scripts/redact_secrets_output.sh`
- Keine „ein File für alles“ Mentalität: shared `.env` bleibt klein; alles Service-Spezifische gehört in den jeweiligen Service-Ordner.

---

## 3) Ordnerstruktur (Repo)

### 3.1 Shared Secrets (Default)

- `/home/wasti/ai_stack/.env` (gitignored; nur Secrets)

Beispiel-Keys (nur als Liste, **keine Werte**):
- `OPENROUTER_API_KEY`
- `TAVILY_API_KEY` (optional; für Tavily MCP / Doc Fetching)
- `YOUTUBE_API_KEY`
- `OPEN_WEBUI_API_KEY` (Open WebUI JWT Bearer; für Tool-Indexer / Admin API falls Role=admin)
- `WEBUI_SECRET_KEY`
- `POSTGRES_PASSWORD` (falls für einen Service verwendet)

Wichtig (Namenskonvention):
- **`OPEN_WEBUI_API_KEY` ist der primäre Name** für den Open WebUI JWT (Bearer Token).
- `OWUI_API_KEY` ist nur ein **deprecated Alias** (ältere Doku/Configs). Falls du ihn noch irgendwo hast: auf `OPEN_WEBUI_API_KEY` umstellen.

Optionales Secret-Artefakt (Datei):
- `/home/wasti/ai_stack/youtube_cookies.txt` (gitignored; nur falls nötig, z. B. bei 429/Block auf YouTube)

### 3.2 Config Env (non-secret)

- `/home/wasti/ai_stack/.config.env` (gitignored)
- `/home/wasti/ai_stack/<service>/.config.env` (gitignored)
  - enthält non-secret Variablen (Ports, Bind-Address, Host-Pfade, Knowledge-ID-Mappings, etc.)

Beispiel-Keys in `*.config.env` (nur als Liste, **keine Werte**):
- `YOUTUBE_COOKIES_FILE=/host_secrets/youtube_cookies.txt` (Pfad im Container)
- `OPEN_WEBUI_BASE_URL=http://owui:8080`
- `OPEN_WEBUI_KNOWLEDGE_ID=...`
- `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON='{"topic":"<knowledge_id>"}'`
- `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON_PATH=/config/knowledge_ids.json` (optional; Datei statt Inline-JSON)
- `*_DIR_HOST=...` (Host-Pfade für Bind-Mounts)

### 3.3 Warum pro Stack?

- Verhindert, dass die shared `.env` wieder „alles“ enthält.
- Macht Ownership klar (Variable gehört zu genau einem Service, außer sie ist wirklich shared).

---

## 5) Docker Compose Start-Policy

### 5.1 Grundsatz

- Compose wird immer vom Repo-Root gestartet und bekommt beide Files:
  - `docker compose --env-file .env --env-file .config.env --env-file <service>/.config.env -f <service>/docker-compose.yml up -d`

### 5.2 Keine impliziten .env im Repo

- Keine Nutzung von automatisch geladenen `.env` Dateien im Repo.
- Wenn ein Stack zwingend `.env` erwartet:
  - dann nur als Template ohne Werte (`.env.example`)
  - echte Werte außerhalb des Repo.

---

## 6) Optional: Docker “secrets” Feature

- Kann verwendet werden, wenn ein Service Secrets als Datei lesen kann.
- Nicht als Ersatz für SSOT gedacht.

Policy:
- Wenn Docker Secrets genutzt werden:
  - pro Service scope-bar
  - Name klar dokumentieren
  - keine Provider-Keys doppelt in Env + Secretfile (ein Pattern wählen)

---

## 7) Rotation & Incident Policy

### 7.1 Rotation

Keys rotieren, wenn:
- ein Secret in Chat/Log/Screenshot sichtbar war
- ein Container kompromittiert wirkt
- ein Backup/Export unkontrolliert geteilt wurde

### 7.2 Incident Ablauf (kurz)

1. Betroffene Keys identifizieren.
2. Keys rotieren (Provider-Seite).
3. `.env` (und ggf. `.config.env` / `<service>/.config.env`) aktualisieren.
4. Stacks neu starten.
5. Nachträgliche Log- und Repo-Prüfung.

---

## 8) Dokumentationspflicht

Für jeden Stack existiert eine kurze `SECRETS.md` im Repo (ohne Werte), die dokumentiert:
- Welche Variablen benötigt werden
- Ob sie als Env (Container) oder außerhalb (Client) verwaltet werden
- Wo sie herkommen (`.env` / `.config.env` / `<service>/.config.env`)

Beispiel (open-webui):
- `WEBUI_SECRET_KEY` — Container Env — `.env`
- `OPEN_WEBUI_API_KEY` — Tool/Indexer Env — `.env`

---

## 8.1 Required Keys (ohne Werte)

### owui (Open WebUI)

- Shared `.env`: `WEBUI_SECRET_KEY`
- Optional Secrets: `OPENAI_API_KEY`

### tm (Transcript Miner Tool)

- Shared `.env`: `YOUTUBE_API_KEY`, `OPENROUTER_API_KEY`, `OPEN_WEBUI_API_KEY` (oder `OWUI_API_KEY` deprecated)
- Service `.config.env` (`mcp-transcript-miner/.config.env`): `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON` (oder `OPEN_WEBUI_KNOWLEDGE_ID`) oder `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON_PATH`

### mcp-context6 (context6 PoC)

- Shared `.env` (für Knowledge Upload): `OPEN_WEBUI_API_KEY` (oder `OWUI_API_KEY` deprecated)

---

## 9) Offene Entscheidungen (zu tracken)

- Nutzen wir systemd, um Compose Stacks beim Boot zu starten?
  - Wenn ja: systemd Unit referenziert `EnvironmentFile=/home/wasti/ai_stack/.env` (+ optional `.config.env` / `<service>/.config.env` über Wrapper).
- Welche Services brauchen wirklich shared Secrets?
  - Ziel: möglichst wenig Sharing.
