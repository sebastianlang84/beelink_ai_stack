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

### `GET /configs/{config_id}`
Gibt den YAML-Inhalt einer Config zurück.

### `POST /configs/{config_id}`
Validiert YAML und schreibt (optional) die Config.
- Default: schreibt und erstellt ein Backup unter `TRANSCRIPT_MINER_CONFIG_BACKUP_DIR`.
- Dry-run: setze `validate_only=true`.

### `POST /runs/start`
Startet einen TranscriptMiner-Run asynchron (im Container) anhand einer Config aus `/configs`.
Antwort enthält eine `run_id`. Status über `GET /runs/{run_id}`.

### `GET /runs/{run_id}`
Liefert Status und Log-Tail des Runs.

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
- `POST /sync/topic/{topic}` — indexiert per-video Summaries für ein Topic (benötigt `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON`)

## Betrieb
- Standalone: `cd mcp-transcript-miner && docker compose --env-file /etc/ai-stack/secrets.env up -d --build` (Compose-Service: `tm`)

Persistenz/Backup: `docs/runbook_backup_restore.md:1`

## Troubleshooting

### YouTube 429 / Block (Too Many Requests)
Wenn `POST /transcript` oder ein Run häufig mit `429`/`Too Many Requests` fehlschlägt, hilft oft ein `cookies.txt`.

- Lege die Datei auf dem Host ab: `/etc/ai-stack/youtube_cookies.txt` (nicht ins Repo committen)
- Setze in `/etc/ai-stack/secrets.env`:
  - `YOUTUBE_COOKIES_FILE=/host_secrets/youtube_cookies.txt`
- Stelle sicher, dass deine Config `api.youtube_cookies: ${YOUTUBE_COOKIES_FILE}` enthält (z. B. `transcript-miner/config/config_stocks_crypto.yaml`)
