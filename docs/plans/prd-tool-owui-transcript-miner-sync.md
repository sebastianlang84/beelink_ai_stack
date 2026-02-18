# PRD v0 — TranscriptMiner Sync Tool für Open WebUI

## 1) Begriffsklärung / SSOT

- Open WebUI „Knowledge Base“ = **Knowledge Collections** (Bereich „Knowledge“).
- Collections sind **passiv**: sie halten Dokumente + Embeddings/Index für Retrieval im Chat.
- Die Automatisierung passiert **außerhalb** der Collection:
  - Ein Tool (OpenAPI/Tool-Server oder Open WebUI Function) startet/steuert Runs.
  - Worker/Scripts führen die Pipeline aus und schreiben Ergebnisse in die Collection.

## 2) Core-Ziel (1 Satz)
Aus Open WebUI heraus (via Tool) einen Run starten, der **YouTube → Transcript → Summary → Index in Open WebUI Knowledge Collection** ausführt, sodass danach mit einer Collection voller **Summaries** gechattet werden kann.

## 3) User-Workflow (Schritt-für-Schritt)

### Schritt 1 — Konfiguration (SSOT)
User verwaltet die Run-Konfiguration (YAML) über UI oder Tool-Parameters.

Minimal-Inhalte:
- Quellen: Channels/Playlists/Suchbegriffe
- Sprachen/Fallback-Regel (z. B. `de,en`)
- Grenzen: max. neue Videos pro Run, Zeitraum
- Ziel: welche Open-WebUI-Collection wird befüllt (Name oder ID)

### Schritt 2 — Run starten
User klickt „Sync/Run“ in Open WebUI.
Open WebUI ruft das Tool auf (z. B. `POST /runs/start`).

### Schritt 3 — Tool startet Worker/Scripts
- Variante A (simple): Tool erledigt alles inline.
- Variante B (robuster): Tool startet Job/Worker und liefert `run_id` zurück (non-blocking).

### Schritt 4 — Discovery: neue Videos finden
Worker nutzt die Quellen-Konfiguration und findet neue Videos.
Intern entstehen/nutzt der Worker: `video_id` (Primärschlüssel), URL, Titel, Kanal, Datum, etc.
Niemand gibt `video_id` manuell ein.

### Schritt 5 — Transcript + Metadaten laden
Worker lädt das „beste“ Transcript (Sprachpriorität + Fallback) und normalisiert Metadaten.

### Schritt 6 — Summaries erzeugen
Worker erstellt Summaries aus Transcript + Meta (optional Kapitel/Keypoints).

### Schritt 7 — Indexieren in Open WebUI Collection
Worker schreibt Summaries als Dokumente in die Ziel-Collection.
Metadaten werden als Felder/Tags gespeichert (inkl. URL, Datum, Kanal; `video_id` als interner Key).

### Schritt 8 — Chat mit Collection
In Open WebUI wird die Collection im Chat verwendet (Retrieval über Summaries).

## 4) Architektur-Rollen (logisch)
- Config-Storage/UI: YAML-SSOT, über Open WebUI editierbar (oder Tool-Overrides)
- Run-Trigger Tool (OpenAPI): startet Runs, liefert `run_id`, Status
- Worker/Runner: Discovery → Transcript → Summary → Index
- State/Dedupe: verhindert Doppelverarbeitung (`video_id`/URL/sha256)
- Open WebUI Collections: passiver Ziel-Speicher

## 5) Wichtigste Korrektur
Nicht „Knowledge macht das automatisch“, sondern:
- Tool/Worker macht die Automatisierung.
- Collection speichert Ergebnisse.

## 6) Vorhandene Komponenten / Realität (ai_stack)
- Open WebUI läuft (LLM via OpenRouter; Modelle sind austauschbar).
- TranscriptMiner (Python) ist die Pipeline-Engine (Transcripts, Summaries, File-Handling, Recovery).
- Vorhanden: `mcp-transcript-miner/` als **einziges** Open WebUI Tool (Indexer ist integriert).

Implikation:
- Nicht alles neu bauen.
- Ziel: Open WebUI Tool/Glue + Indexierung in Collections + (optional) UI-Konfig.

## 7) Festgelegt (aktueller Stand)
- Integrations-Strategie: **Option 1 (Thin Tool)**.
  - Tool = Trigger + Glue + Indexierung nach Open WebUI.
  - TranscriptMiner bleibt Pipeline-Engine.
- Artefaktformat: **Summary pro Video als `.md`** (human- und LLM-lesbar).
- Ziel-Collection: **nur Summaries** embedden (keine Reports, keine Raw-Transkripte).
- Anpassungen: Tool + TranscriptMiner dürfen angepasst werden, wenn nötig.
- Auth: API-Keys in Open WebUI sind „buggy“; bevorzugt JWT/Bearer Flow über `WEBUI_SECRET_KEY`/Login (genauer Mechanismus als Discovery-Task).

## 8) Run-Start-Contract (Tool-API) — minimal

### Endpunkte
- `POST /runs/start` → `{ "run_id": "..." }`
- `GET /runs/{run_id}` → `{ state, stage, progress, counts, last_error? }`

### Minimal-States
- `queued`
- `running`
- `success`
- `failed`

### Fortschritt / Counts (Minimalfelder)
- `progress_pct` (0–100) **oder** `stage` + `stage_progress`
- `counts`: `videos_found`, `videos_new`, `summaries_written`, `uploaded`, `indexed`
- `last_error` (kurz) + optional `error_ref`

## 9) Statusanzeige: OpenRouter vs Pipeline
- OpenRouter Telemetrie (Streaming/Usage/Costs) ist **kein** Run-Status für TranscriptMiner-Jobs.
- Run-Status muss Tool-seitig über `GET /runs/{run_id}` (Polling) oder Events bereitgestellt werden.

## 10) Open WebUI Functions (Pipes/Filters/Actions) — optional (UX)
Potenzial:
- Action Button „Sync“ in der UI
- Status/Toasts via `__event_emitter__`
Tradeoffs:
- Läuft im Open WebUI Container (Deploy/Isolation/Deps anders als externes Tool)
- Emitter-Verhalten kann je nach Function-Calling-Mode eingeschränkt sein („native“)

## 11) Konfiguration (SSOT) — Minimal ohne UI-Editor
Tool akzeptiert Overrides beim Start:
- `max_new_videos`
- `since_days` / `date_range`
- `language_priority` (z. B. `["de","en"]`)
- `target_collection` (Name/ID)

## 12) Indexierung in Knowledge Collections (Thin Tool)
High-level:
1. Summary-`.md` Dateien aus TranscriptMiner Output ermitteln.
2. Upload zu Open WebUI.
3. Warten bis File-Processing/Embedding abgeschlossen.
4. Dateien der Ziel-Collection hinzufügen.

Minimal-Metadaten:
- `video_id` (internal key)
- `url`, `title`, `channel`, `published_at`
- optional `language`, `run_id`

## 13) RooCode Aufgabenliste (konkret)
1. TranscriptMiner Output prüfen:
   - Wo liegen per-video Summary `.md`?
   - Wie erkennt man zuverlässig „nur Summaries“?
2. Tool-Service implementieren/erweitern (Thin Tool):
   - `POST /runs/start` + `GET /runs/{run_id}`
   - Job-Management (`run_id`, `state`, `counts`)
   - optional Events/Emitter
3. Open WebUI Ingest integrieren:
   - Upload + Processing Wait + Add-to-Collection
   - JWT/Bearer Auth nutzen
4. Collection Mapping:
   - Name vs ID
   - Wo wird es konfiguriert (Tool-Config vs Overrides)
5. Dedupe/State:
   - `video_id` als Primärschlüssel
   - minimaler Persistenzlayer (z. B. SQLite)

## 14) Nächster Arbeitsblock (core-first)
1. Tool-Contract finalisieren
2. TranscriptMiner Output-Discovery (Summary-only)
3. Open WebUI Ingest-Flow implementieren
4. Config-SSOT + Overrides klären/umsetzen

## 15) Natural-Language Trigger: "hole die neuesten videos"
Minimaler Interaction-Contract fuer die Chat-Trigger-Variante:

### Parameter-Aufloesung + Defaults
- `topic`: aus Tool-Konfiguration (empfohlen `ai_knowledge`)
- `x`: `num_videos_per_channel` (Default aus Topic-Config)
- `y`: `max_total_videos` (Tool-Sicherheitslimit, z. B. `25`)
- `lookback_days`: aus Topic-/Global-Config
- `force_redownload_transcripts`: default `false`

Bei fehlenden Parametern fragt das Tool einmal kurz zur Bestaetigung nach, bevor ein kostenrelevanter Run startet.

### Ausfuehrungsreihenfolge
1. TranscriptMiner-Run starten (Topics/Kanaele aus Config).
2. Pro Channel gilt `x`; global limitiert der Orchestrator auf `y`.
3. Danach genau ein Sync-Zyklus nach Open WebUI Knowledge (`POST /sync/topic/{topic}` oder `POST /index/transcript`).

### Ergebnis-Reporting (kompakt)
- Channels gefunden
- Videos verarbeitet (inkl. Hinweis auf `y`-Kappung)
- Summaries erzeugt
- Knowledge Uploads: `indexed` vs `skipped`

## 16) Guardrails
- Keine neuen Host-Ports (Service bleibt im Docker-Netzwerk).
- Fail-fast bei fehlendem Topic->Knowledge Mapping.
- Secrets bleiben in `.env`; non-secrets in `.config.env`/`<service>/.config.env` (siehe Policy).
