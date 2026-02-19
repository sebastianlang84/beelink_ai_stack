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
- Wenn bei einem Task **keine** Living-Docs-Aenderung noetig ist: in `MEMORY.md` oder im Commit-Text explizit festhalten (z. B. "README/TODO/CHANGELOG geprueft: keine Aenderungen noetig").

## 0.2) Reset-Resilienz (Context-Window uebergreifend, verpflichtend)
- Chat-Zusagen sind nur in-session gueltig und duerfen nicht als persistente Verbindlichkeit behandelt werden.
- Verbindliche Absprachen muessen in Repo-Dateien stehen (mindestens `MEMORY.md`, plus relevante Living Docs).
- `MEMORY.md` ist das verpflichtende Uebergabe- und Langzeitgedaechtnis-Dokument fuer den naechsten Context.

## 0.3) Doku-Vertrag (stabil, minimal)
- `AGENTS.md`
  - Purpose: Normative Agent-Regeln.
  - Contains: Prozess, Pflichten, Doku-Vertraege.
  - Does not contain: Projektstand, Historie, TODO-Inhalte.
- `README.md`
  - Purpose: Operator-Guide.
  - Contains: Setup, Run, Test, Deploy, Troubleshooting.
  - Does not contain: Link-Sammlung ohne Kontext, laufende Entscheidungen.
- `INDEX.md`
  - Purpose: Navigation.
  - Contains: kurze Links auf Hauptdokumente/Service-Dokus.
  - Does not contain: laengere Erklaertexte.
- `MEMORY.md`
  - Purpose: 1-Seiten Snapshot + reset-resilientes Langzeitgedaechtnis.
  - Contains: Current State, Long-Term Memory, Open Decisions, Next Steps, Risiken/Blocker.
  - Does not contain: How-to, Regeln, unstrukturierte Task-Historie.
- `TODO.md`
  - Purpose: aktive Arbeit.
  - Contains: offene Aufgaben mit Prioritaet/Status.
  - Does not contain: erledigte Historie, Change-Logs.
- `CHANGELOG.md`
  - Purpose: release-/userrelevante Aenderungen.
  - Contains: Added/Changed/Fixed/Breaking.
  - Does not contain: rein interne, nicht spuerbare Detailaenderungen.
- `docs/adr/`
  - Purpose: Entscheidungen.
  - Contains: Context -> Decision -> Consequences -> Alternatives.
  - Does not contain: Task-Logs.

## 1) Agent Rules (global, verbindlich)

### 1.0) Non-Negotiables (hart, fail-closed)
- Keine "Action-first" Ausfuehrung: erst verifizieren, dann handeln.
- Keine Scope-Vermischung: pro Task genau **ein** technisches Ziel.
- Keine impliziten Annahmen: Unklarheiten explizit markieren, nicht raten.
- Keine Ausreden/Meta-Begruendungen: nur technische Ursachen und konkrete Massnahmen.
- Wenn eine dieser Regeln verletzt wird: sofort benennen, stoppen, korrigierten Plan liefern.

### 1.1) Ausfuehrungsprotokoll (verpflichtend pro Task)
- **Gate A: Preflight (immer zuerst)**
  - Vor dem ersten schreibenden Kommando muss der Agent kurz ausgeben:
    - `Ziel`
    - `Scope (in/out)`
    - `Gelesene Quellen` (konkrete Dateien, mind. `AGENTS.md` + `MEMORY.md` + betroffene Service-Docs/Runbooks)
- **Gate B: Read-Only Diagnose**
  - Zuerst nur lesen/pruefen (z. B. `rg`, `cat`, Status, Logs, `docker inspect`, `docker compose config`).
  - In dieser Phase keine mutierenden Aktionen (keine Datei-Schreibzugriffe, keine Service-Restarts, keine Upgrades, keine Deletes).
- **Gate C: Umsetzungsfreigabe**
  - Erst nach Diagnosezusammenfassung und User-Freigabe (`go`/`mach`) in die Umsetzung.
  - Ausnahme: Der User fordert explizit sofortige Umsetzung; trotzdem bleibt Gate A/B Pflicht in Kurzform.
- **Gate D: Verifikation nach Umsetzung**
  - Nach jeder Aenderung zwingend Erfolg verifizieren (Status/Health/Endpoint/Output).
  - Wenn Verifikation fehlt oder fehlschlaegt: Task nicht als abgeschlossen melden.

### 1.2) Antwortformat (verbindlich, knapp, eindeutig)
- Kein vager Sprachgebrauch ("wirklich", "eigentlich", "sollte").
- Standardstruktur bei technischen Antworten:
  1. `Ist-Zustand`
  2. `Naechster Schritt`
  3. `Risiko/Blocker` (nur wenn vorhanden)
- Bei Fehlern:
  - Ursache in 1 Satz
  - konkrete Korrektur in 1-3 Schritten
  - kein blame, keine Ausreden

### 1.3) Memory Routing (verpflichtend)
- `MEMORY.md` ist immer-geladener Bootstrap und bleibt operativ kompakt (Richtwert: 1 Seite, <= ~200 Zeilen).
- Beim Task-Abschluss waehlt der Agent genau **ein primaeres Memory-Ziel**:
  - `MEMORY.md` (semantisch/stabile Defaults + aktueller Status)
  - `docs/runbooks/*` (prozedural/How-to)
  - `docs/memory/daily/YYYY-MM-DD.md` (episodisch/zeitgebundener Verlauf)
  - `docs/adr/*` (echte Entscheidung mit Alternativen/Folgen)
- Regeln:
  - Keine episodische Historie in `MEMORY.md` (Status statt Verlauf).
  - Keine Duplikate in `MEMORY.md` (alte Formulierung ersetzen, nicht addieren).
  - Keine Secrets in Memory-Dateien.
- Prioritaet bei Konflikt:
  1. `AGENTS.md` (Policy)
  2. `MEMORY.md` (aktueller Stand + Defaults)
  3. `docs/adr/*` und `docs/runbooks/*` (Details)
  4. `docs/memory/daily/*` (Verlauf)

### Pflicht: ADR + Abschluss-Tasks
- Architektur-/Prozessentscheidungen werden in `docs/adr/` festgehalten (statt Task-Diary).
- **Pflicht am Ende jeder Aufgabe**:
  1. `MEMORY.md` aktualisieren/prüfen. Wenn keine inhaltliche Aenderung noetig ist, explizit dokumentieren: `MEMORY.md geprueft: keine Aenderung noetig`.
  2. Falls Entscheidung finalisiert wurde: ADR in `docs/adr/` schreiben/aktualisieren.
  3. Living Docs pruefen/aktualisieren (mindestens: `README.md`, `TODO.md`, `CHANGELOG.md`).
  4. Commit erstellen, **sofern der User nicht explizit etwas anderes sagt**.

### Merge-Check (ohne Optionen)
- Wenn Setup/Bedienung geaendert: `README.md` aktualisieren.
- Wenn userrelevant/release: `CHANGELOG.md` aktualisieren.
- Wenn Entscheidung final: ADR schreiben.
- Immer: `MEMORY.md` Snapshot pruefen.

### Commit-Regeln
- Keine Secrets committen.
- Ein Task = ein Commit (inkl. MEMORY/Living-Docs-Abschluss), ausser der User wuenscht etwas anderes.
- Commit-Message-Format: `type(scope): kurze beschreibung`
  - `type` in {`docs`, `fix`, `feat`, `chore`, `ops`, `refactor`, `test`}
  - `scope` kurz, z. B. `agent`, `docs`, `open-webui`, `mcp-tm`
  - Beispiel: `docs(agent): tighten memory policy`

### Arbeitsstil
- Bei Unklarheiten zuerst **1–3 gezielte Rückfragen** stellen (Ziel, Umgebung, Constraints).
- **Repo-first**: erst vorhandene Dateien/Docs prüfen, dann Vorschläge machen; nichts „raten“.
- **„Recherchiere“ heißt Context7-first**: bei Produkt-/Tool-Fragen (Open WebUI, RooCode, Qdrant, MCP/OpenAPI, etc.) zuerst Context7 nutzen; `curl`/Logs nur für lokale Verifikation (läuft Endpoint wirklich so?).
- **No-Fluff**: direkt mit Ergebnis/Schritten/Code starten, kurze Bulletpoints.
- Änderungen als **kleine, nachvollziehbare Diffs**; keine unnötigen Refactors.
- **Stetige Verbesserung**: bei jedem Task prüfen, ob ein wiederholbarer/komplexer Workflow als Skill abgebildet werden sollte; Skills bei komplexen Workflows bevorzugt nutzen/erstellen.
- **Stop & Ask bei Dirty Worktree**: Wenn im Git-Status unerwartete/unrelated Aenderungen auftauchen, die nicht Teil des aktuellen Tasks sind, erst kurz nachfragen, bevor irgendetwas davon committed/reverted wird.
- **Single-Service-Fokus**: keine parallelen Eingriffe in mehrere Services, ausser User fordert es explizit.
- **Change Isolation**: nur Dateien aendern, die fuer den Task notwendig sind; keine opportunistischen Neben-Edits.

### Sicherheit & Betrieb
- **Keine Secrets committen** (Tokens, Passwörter, Private Keys).
- Secrets-Handling: siehe `docs/policies/policy_secrets_env.md` (Repo-Layout: `.env` = secrets-only; `.config.env` + `<service>/.config.env` = non-secrets; alles gitignored; Start immer via `--env-file`).
- **Glasklar (Wasti-Policy): In `.env` stehen NUR Secrets.**
  - `.env` enthält ausschließlich: API Keys, Tokens, Passwörter, private Schlüssel.
  - Nicht-Secrets (Pfade/Hosts/Ports/IDs/Mappings) gehören **nicht** in `.env`, sondern in `.config.env` oder `<service>/.config.env`.
  - Beispiele **kein Secret**: `YOUTUBE_COOKIES_FILE`, `OPEN_WEBUI_KNOWLEDGE_ID`, `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON`, `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON_PATH`, `OPEN_WEBUI_BASE_URL`, `*_DIR_HOST`, `*_HOST_PORT`, `*_BIND_ADDRESS`.
- Compose-Start (Docker Compose unterstützt mehrere `--env-file`):
  - `docker compose --env-file .env --env-file .config.env --env-file <service>/.config.env -f <service>/docker-compose.yml up -d`
- **Keine neuen Host-Ports** ohne Begründung + Doku (was, warum, Risiko).
- Bevorzugt **Reverse Proxy** statt direktes Exposing; intern auf Docker-Netzwerk halten, wo möglich.
- Persistenz/Backups mitdenken: Volumes/Bind-Mounts klar benennen; Hinweis, was gesichert werden muss.
- **Upgrade Safety Gate (verpflichtend)**:
  - Vor jedem Versions-Upgrade muss der Agent pruefen und belegen:
    - Release/Tag existiert wirklich.
    - Stable vs. prerelease.
    - Migrations-/Breaking-Warnungen aus den Release Notes.
  - Vor dem Upgrade muss der Agent Risiken in 1-3 Bulletpoints nennen und den User explizit bestaetigen lassen.
  - Bei DB-Migrationen: Backup-Entscheidung immer explizit mit User klaeren (durchfuehren oder bewusst skippen).

### Docker/Compose Konventionen
- Ordnernamen sind **kebab-case** (z. B. `open-webui/`, `mcp-transcript-miner/`, `mcp-context6/`, `emb-bench/`).
- Pro Service ein Ordner (z. B. `open-webui/`, `mcp-transcript-miner/`, `qdrant/`) mit:
  - `docker-compose.yml`
  - `.config.env.example` (committen); echte Werte in `.config.env`/`<service>/.config.env` (gitignored)
  - optional `README.md`/`OPERATIONS.md` für Bedienung & Recovery
- Nach Compose-Änderungen: `docker compose config` (oder äquivalent) ausführen, soweit möglich.
- Healthchecks verwenden, wenn Services es unterstützen.

## 2) Repo-Struktur (Stand heute)
- `INDEX.md` — Reiner Link-Index (Startpunkt fuer Navigation)
- `MEMORY.md` — Snapshot + Langzeitgedaechtnis fuer den naechsten Context
- `docs/memory/daily/` — Episodische Tageslogs (append-only Verlauf)
- `open-webui/` — Open WebUI Service (Docker Compose)
- `mcp-transcript-miner/` — **Transcript Miner** MCP Server (Streamable HTTP; OpenAPI optional/legacy; Configs/Runs/Outputs + Knowledge Indexing)
- `transcript-miner/` — TranscriptMiner Pipeline-Engine (Python; Transcripts + Summaries)
- `mcp-owui-connector/` — MCP Connector (Open WebUI / Roo)
- `qdrant/` — Qdrant Service (optional)
- `docs/adr/` — Architecture Decision Records

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
