# mcp-transcript-miner (HTTP/MCP) — Transcript Miner (Open WebUI Tool)

Ein **einziger** Tool-Server für Open WebUI: YouTube Transcripts holen, TranscriptMiner Configs bearbeiten, Runs starten und Summaries in Knowledge Collections indexieren.

## API

### `GET /healthz`
- `200 OK` wenn der Service läuft.

### MCP (Streamable HTTP): `POST /mcp`
Tool-Discovery/Invocation für Open WebUI/RooCode. Tools:
- `capabilities.get` (optional: `{ "detail": "short|full", "max_chars": 6000 }`)
- `configs.list`, `configs.get`, `configs.write`
- `runs.start`, `runs.status`
- `sync.topic`
- `index.transcript`
- `transcript.fetch`

### `GET /configs`
Listet verfügbare TranscriptMiner Configs (YAML) aus `TRANSCRIPT_MINER_CONFIG_DIR`.
Enthält `display_name` und `aliases` zur besseren Zuordnung durch LLMs.

### `GET /configs/{config_id}`
Gibt den YAML-Inhalt einer Config zurück.

### `POST /configs/{config_id}`
Validiert YAML und schreibt (optional) die Config.
- Default: schreibt und erstellt ein Backup unter `TRANSCRIPT_MINER_CONFIG_BACKUP_DIR`.
- Dry-run: setze `validate_only=true`.

### `POST /runs/start`
Startet einen TranscriptMiner-Run asynchron (im Container) anhand einer Config aus `/configs`.
Antwort enthält eine `run_id`. Status über `GET /runs/{run_id}`.
Hinweis für LLMs: zuerst `configs.list` aufrufen und den exakten `config_id` verwenden.
Antwort enthält zusätzlich ein `summary` (kurzer Klartext für Nutzer).
Empfehlung: `summary` für Nutzertexte verwenden; `log_path` nur auf Nachfrage.
Der Server akzeptiert auch Aliases aus `configs.list` und löst sie auf `config_id` auf.

### `GET /runs/{run_id}`
Liefert Status und Log-Tail des Runs.
Empfehlung: `summary` für Nutzertexte verwenden; `log_tail` nur auf Nachfrage.
Auto‑Sync‑Statusfelder (best effort):
- `auto_sync_state` = queued|running|finished|failed
- `auto_sync_error` / `auto_sync_result` (falls vorhanden)

### `POST /transcript`
Request JSON:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "preferred_languages": ["de", "en"],
  "include_timestamps": false,
  "max_chars": 20000
}
```

Response JSON (Beispiele):
- Success:
```json
{ "status": "success", "text": "...", "meta": { "language": "en", "is_generated": true, "sha256": "..." } }
```
- No transcript:
```json
{ "status": "no_transcript", "reason": "no_transcript_found" }
```
- Error:
```json
{ "status": "error", "error_type": "CouldNotRetrieveTranscript", "error_message": "..." }
```

### Outputs (global layout)
Wenn `TRANSCRIPT_MINER_OUTPUT_DIR` gemountet ist:
- `GET /outputs/topics` — Topics aus `output/data/indexes/*/current/manifest.json`
- `GET /outputs/topics/{topic}/videos?limit=50&offset=0` — Einträge aus `transcripts.jsonl`
- `GET /outputs/videos/{video_id}/transcript?max_chars=20000` — `output/data/transcripts/by_video_id/<video_id>.txt` (+ optional `*.meta.json`)
- `GET /outputs/videos/{video_id}/summary?max_chars=30000` — `output/data/summaries/by_video_id/<video_id>.summary.md`

### Indexing (Open WebUI Knowledge)
- `POST /index/transcript` — upload/poll/add (idempotent via SQLite, keyed by `source_id`)
- `POST /sync/topic/{topic}` — indexiert per-video Summaries für ein Topic via globaler Lifecycle-Routing-Logik:
  - Targets: `<topic>_new` (pro Channel max. `newest_per_channel`, optional nur bis `new_max_age_days`) und `<topic>_archive` (Rest bis `archive_max_age_days`)
  - Regeln kommen aus `transcript-miner/config/config_global.yaml` (`owui_collections.*`)
  - Excluded Topics (z.B. `company_dossiers`) werden **nicht** geroutet und behalten Direct-Sync nach `<topic>`.
  - Missing Summaries: optionaler LLM‑Healing‑Run (nur LLM) für das passende Config‑Topic, dann Sync
  - Optional im Request: `heal_missing_summaries` (default `true`), `heal_timeout_s` (default `900`), `heal_poll_s` (default `5`)
  - Hinweis: OWUI‑Duplicate‑Content wird als `skipped` behandelt (kein harter Fehler)
- `POST /sync/lifecycle/{topic}` — expliziter Lifecycle Sync (gleiche Logik wie `sync.topic`)
  - Backwards-compatible alias: `POST /sync/investing/lifecycle`

No-Fuss Workflow:
1. Run starten (`POST /runs/start`) für ein Config-Topic (z.B. `investing`).
2. `sync.topic` aufrufen: `POST /sync/topic/investing`
3. Ergebnis ist immer `<topic>_new` + `<topic>_archive` (ausser Excluded Topics wie `company_dossiers`).

Hinweis:
- `POST /sync/topic/<topic>_new` oder `POST /sync/topic/<topic>_archive` ist **nicht** erlaubt; verwende immer das Base-Topic ohne Suffix.

Optional:
- Auto-Create ist nur aktiv, wenn **beides** gesetzt ist:
  - Env: `OPEN_WEBUI_CREATE_KNOWLEDGE_IF_MISSING=true`
  - Request: `create_knowledge_if_missing=true`
  - Optional: Allowlist via `OPEN_WEBUI_CREATE_KNOWLEDGE_ALLOWLIST=investing,investing_test,...` (leer = alle)
- Upload-Dateinamen werden aus Datum/Channel/Title/Video-ID gebildet (lesbar).
- Dedupe-Precheck gegen OWUI (Hash/Dateiname) ist standardmaessig aktiv:
  - `OPEN_WEBUI_KNOWLEDGE_DEDUP_PRECHECK=true` (Default)
  - Cache: `OPEN_WEBUI_KNOWLEDGE_DEDUP_CACHE_TTL_SECONDS=900`
- Parallel-Guard: gleichzeitige `POST /sync/topic/{topic}`-Laufe fuer dasselbe Topic werden mit `status=busy` abgewiesen (verhindert Race-Condition-Duplikate).
- Lifecycle-Parameter:
  - Source: `transcript-miner/config/config_global.yaml` -> `owui_collections.*`
  - Optional Override: `OPEN_WEBUI_COLLECTIONS_CONFIG_PATH=/transcript_miner_config/config_global.yaml`

## Betrieb
- Standalone (vom Repo-Root): `docker compose --env-file .env --env-file .config.env --env-file mcp-transcript-miner/.config.env -f mcp-transcript-miner/docker-compose.yml up -d --build` (Compose-Service: `tm`)

Persistenz/Backup: `docs/runbook_backup_restore.md:1`

## LLM Backend (Gemini CLI)
- Der TM-Container unterstuetzt jetzt zwei LLM-Backends fuer Summary-Generierung:
  - `TM_LLM_BACKEND=openrouter` (bisherig, mit `OPENROUTER_API_KEY`)
  - `TM_LLM_BACKEND=gemini_cli` (neu, ohne OpenRouter API-Calls)
- Einmalige Auth fuer `gemini_cli` im Container:
  - `docker exec -it tm gemini`
- Modell-Policy:
  - nutze `google/gemini-3-flash-preview` in der Config (wird intern auf `gemini-3-flash-preview` normalisiert)
  - Pro-Modelle sind im Runner geblockt.
- Optional:
  - `TM_GEMINI_CLI_MODEL` ueberschreibt das Modell aus der Config
  - `TM_GEMINI_CLI_TIMEOUT_SECONDS` setzt das CLI-Timeout (Default `900`)
- Betriebsdetail Scheduler:
  - `scripts/run-tm-investing.sh` und `scripts/run-tm-investing-companies.sh` starten ohne erzwungenes `skip_report`; der Report-Pfad nutzt dasselbe Backend wie `TM_LLM_BACKEND` (z. B. `gemini_cli`).

## Troubleshooting

### Sync teilweise fehlgeschlagen (`status=partial`, `step=process`)
Typisches Symptom: `auto_sync_state=failed` und in Open WebUI Logs steht ein Embedding/Proxy-Fehler (z. B. `ClientHttpProxyError: 502`).

Mitigation:
- Ab jetzt retryt der Indexer transient fehlgeschlagene Upload/Process/Add-Schritte automatisch.
- Steuerung per Env:
  - `OPEN_WEBUI_INDEX_MAX_ATTEMPTS` (Default `3`)
  - `OPEN_WEBUI_INDEX_RETRY_BACKOFF_SECONDS` (Default `5`)
- Danach kann ein manueller Re-Sync die Lücke schließen: `POST /sync/topic/{topic}`.

### Run schlägt fehl: `Read-only file system` (z. B. `/transcript_miner_repo/logs`)
Ursache: Der TranscriptMiner-Code-Ordner ist im Tool-Container absichtlich **read-only** gemountet (`/transcript_miner_repo:ro`).

Fix:
- Stelle sicher, dass du den aktuellen Stand nutzt (Logging schreibt dann nach `TRANSCRIPT_MINER_OUTPUT_DIR/logs`).
- Falls du eigene Configs verwendest: setze `logging.file`/`logging.error_log_file` auf einen **schreibbaren** Pfad (z. B. unter `TRANSCRIPT_MINER_OUTPUT_DIR`).

### Fehler-History landet nicht auf dem Host
Wenn `output.global` in der Config auf `/home/wasti/ai_stack_data/...` zeigt, muss dieser Pfad im Container gemountet sein.
Stelle sicher, dass `AI_STACK_DATA_DIR_HOST=/home/wasti/ai_stack_data` gesetzt ist (siehe `.config.env.example`).

### YouTube 429 / Block (Too Many Requests)
Wenn `POST /transcript` oder ein Run häufig mit `429`/`Too Many Requests` fehlschlägt, hilft oft ein `cookies.txt`.

- Lege die Datei auf dem Host ab: `/home/wasti/ai_stack/youtube_cookies.txt` (nicht committen)
- Setze in `mcp-transcript-miner/.config.env`:
  - `YOUTUBE_COOKIES_FILE=/host_secrets/youtube_cookies.txt`
- Stelle sicher, dass deine Config `api.youtube_cookies: ${YOUTUBE_COOKIES_FILE}` enthält (z. B. `transcript-miner/config/config_investing.yaml`)
