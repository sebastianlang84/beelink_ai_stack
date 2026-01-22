# AGENTS.md — Home-Server (Start: Open WebUI)

Dieses Repository ist die Code-/Config-Basis für einen Home-Server. Primäres Ziel ist eine saubere, reproduzierbare Installation von **Open WebUI** (inkl. Indexer für Knowledge/RAG), später erweiterbar um weitere Services (z. B. Qdrant).

## 0) Regel-Dateien & Skills (Priorität)
- `AGENTS.md` (dieses File, Repo-Root) ist das **hierarchisch oberste Dokument** für Agents in diesem Repo (Auftrag + Regeln).
  - Keine zusätzlichen `AGENTS.md` in Unterordnern anlegen.
  - Service-spezifische Regeln gehören in den jeweiligen Service-Ordner.
- Optionaler Fallback: `AGENT.md` (falls jemals vorhanden) hat **niedrigere Priorität** als `AGENTS.md`.
- `SKILL.md`:
  - Skills (sofern vorhanden) sind **gleichrangig** zu `AGENTS.md` (projektweite Arbeitsanweisungen).
  - Wenn ein Skill angefordert wird (per Name) oder klar passt: **Skill zuerst öffnen und befolgen**.
  - Projekt-spezifische Skills (falls wir welche anlegen) liegen unter `skills/<skill-name>/SKILL.md` (optional mit `scripts/`, `assets/`, `references/`).
  - Kontext klein halten: nur die Teile aus `SKILL.md` laden, die für den aktuellen Schritt nötig sind (keine Bulk-Reads).
  - Bei Widersprüchen zwischen `AGENTS.md` und `SKILL.md`: **Stop & Ask** (kurz rückfragen/entscheiden lassen), bevor Änderungen umgesetzt werden.

## 0.1) Living Docs (müssen immer aktuell sein)
- `README.md`, `TODO.md`, `CHANGELOG.md` sind **lebende Dokumente** und müssen **perfekt** zum aktuellen Projektzustand passen.
- Keine Doku darf dem Projekt hinterherhinken: Wenn Code/Compose/Prozesse geändert werden, müssen diese Dateien im gleichen Zug aktualisiert werden (oder die Änderung wird als „unvollständig“ behandelt).

## 1) Agent Rules (global, verbindlich)

### Arbeitsstil
- Bei Unklarheiten zuerst **1–3 gezielte Rückfragen** stellen (Ziel, Umgebung, Constraints).
- **Repo-first**: erst vorhandene Dateien/Docs prüfen, dann Vorschläge machen; nichts „raten“.
- **„Recherchiere“ heißt Context7-first**: bei Produkt-/Tool-Fragen (Open WebUI, RooCode, Qdrant, MCP/OpenAPI, etc.) zuerst Context7 nutzen; `curl`/Logs nur für lokale Verifikation (läuft Endpoint wirklich so?).
- **No-Fluff**: direkt mit Ergebnis/Schritten/Code starten, kurze Bulletpoints.
- Änderungen als **kleine, nachvollziehbare Diffs**; keine unnötigen Refactors.

### Sicherheit & Betrieb
- **Keine Secrets committen** (Tokens, Passwörter, Private Keys).
- Secrets-Handling: siehe `docs/policy_secrets_environment_variables_ai_stack.md` (Repo-Layout: `.env` = secrets-only; `.config.env` + `<service>/.config.env` = non-secrets; alles gitignored; Start immer via `--env-file`).
- **Glasklar (Wasti-Policy): In `.env` stehen NUR Secrets.**
  - `.env` enthält ausschließlich: API Keys, Tokens, Passwörter, private Schlüssel.
  - Nicht-Secrets (Pfade/Hosts/Ports/IDs/Mappings) gehören **nicht** in `.env`, sondern in `.config.env` oder `<service>/.config.env`.
  - Beispiele **kein Secret**: `YOUTUBE_COOKIES_FILE`, `OPEN_WEBUI_KNOWLEDGE_ID`, `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON`, `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON_PATH`, `OPEN_WEBUI_BASE_URL`, `*_DIR_HOST`, `*_HOST_PORT`, `*_BIND_ADDRESS`.
- Compose-Start (Docker Compose unterstützt mehrere `--env-file`):
  - `docker compose --env-file .env --env-file .config.env --env-file <service>/.config.env -f <service>/docker-compose.yml up -d`
- **Keine neuen Host-Ports** ohne Begründung + Doku (was, warum, Risiko).
- Bevorzugt **Reverse Proxy** statt direktes Exposing; intern auf Docker-Netzwerk halten, wo möglich.
- Persistenz/Backups mitdenken: Volumes/Bind-Mounts klar benennen; Hinweis, was gesichert werden muss.

### Docker/Compose Konventionen
- Ordnernamen sind **kebab-case** (z. B. `open-webui/`, `mcp-transcript-miner/`, `mcp-context6/`, `emb-bench/`).
- Pro Service ein Ordner (z. B. `open-webui/`, `mcp-transcript-miner/`, `qdrant/`) mit:
  - `docker-compose.yml`
  - `.config.env.example` (committen); echte Werte in `.config.env`/`<service>/.config.env` (gitignored)
  - optional `README.md`/`OPERATIONS.md` für Bedienung & Recovery
- Nach Compose-Änderungen: `docker compose config` (oder äquivalent) ausführen, soweit möglich.
- Healthchecks verwenden, wenn Services es unterstützen.

## 2) Repo-Struktur (Stand heute)
- `open-webui/` — Open WebUI Service (Docker Compose)
- `mcp-transcript-miner/` — **Transcript Miner** MCP Server (Streamable HTTP; OpenAPI optional/legacy; Configs/Runs/Outputs + Knowledge Indexing)
- `transcript-miner/` — TranscriptMiner Pipeline-Engine (Python; Transcripts + Summaries)
- `mcp-owui-roo-connector/` — MCP Connector (Open WebUI / Roo)
- `qdrant/` — Qdrant Service (optional)

## 3) Service-Zielbild

### Open WebUI (Primary)
- Ziel: Open WebUI läuft persistent, upgradesicher, mit sauberer Secrets-Handhabung.
- Erwartete Dateien:
  - `open-webui/docker-compose.yml`
  - `open-webui/.config.env.example` (im Repo); echte Werte in `open-webui/.config.env` + shared `.env`/`.config.env` (gitignored)
- Muss-Parameter (typisch, empfohlen):
  - `WEBUI_SECRET_KEY` (stabil halten)
- Zugriff:
  - Lokal/VPN-only bevorzugt via localhost-Port + Tailscale Serve.
  - Home-Server bevorzugt via Domain + TLS (z. B. Caddy/Traefik/Nginx Proxy Manager), statt direkt Host-Ports zu exposen.

### MCP Server (Primary Add-on)
- Ziel: LLMs in Open WebUI sollen **MCP Server** als External Tools nutzen können (bevorzugt **MCP Streamable HTTP**).
- Integrations-Pattern:
  - Native: Open WebUI → External Tools → **MCP (Streamable HTTP)** (direkte Verbindung zu MCP-HTTP-Endpunkten).
  - Bridge: für MCP-Server, die nur `stdio` sprechen → via **MCPO** (MCP→OpenAPI) in Open WebUI als OpenAPI-Tool anbinden.

### Open WebUI Indexer (Primary Add-on)
- Ziel: Automatisches Indexing in Open WebUI Knowledge Collections (RAG).
- Status: **in `mcp-transcript-miner/` integriert** (`POST /index/transcript`, `POST /sync/topic/{topic}`).

### Qdrant (Optional)
- Ziel: Vektor-DB für spätere RAG/Automationen.
- Erwartete Dateien:
  - `qdrant/docker-compose.yml`
  - `qdrant/.config.env.example`
- Security: API-Key aktivieren, falls über geteilte Netze erreichbar.

## 4) Doku-Standard
- Service-spezifische Details (Ports, URLs, Volumes, Restore) gehören in den jeweiligen Service-Ordner.
- Produkt-/Anforderungsnotizen können in `*/PRD.md` gepflegt werden.
