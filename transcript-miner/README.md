# Transcript Miner

Python-Tool zum automatischen Extrahieren/Strukturieren von YouTube-Transkripten (und optional Metadaten), um sie für nachgelagerte Analyse (z.B. LLMs) nutzbar zu machen.

Hinweis zu Code-Links in dieser Doku:

- Links im Format `pfad/datei.py:zeile` sind für VS Code (und ähnliche Editoren) optimiert und springen direkt an die referenzierte Stelle.

## Projektüberblick

Wichtige Ordner / Rollen:

- [`src/`](src:1): Python-Pakete
  - [`src/transcript_miner/`](src/transcript_miner:1): Mining-Pipeline (Channel → Videos → Transkripte)
  - [`src/common/`](src/common:1): gemeinsame Utilities (Config, Pfade, etc.)
- [`config/`](config:1): Beispiel-Konfigurationen (`*.yaml`)
- [`docs/`](docs:1): Projektdoku (z.B. Config-Referenz, Notizen, …)
  - Architektur/Entscheidungen (Einstieg): [`docs/architecture.md`](docs/architecture.md:1)
  - Doku-Index (alle Markdown-Dateien): [`docs/README.md`](docs/README.md:1)
- [`logs/`](logs:1): zentrale Logs (Übersicht: [`logs/README.md`](logs/README.md:1))
- [`docs/audit/`](docs/audit:1): Repo-Hygiene/Audit-Logs (z.B. Cleanup-Reports)
- `data/`: lokale, **nicht versionierte** Inputs (keine Secrets, große/volatile Dateien nicht committen)

## Quickstart

Voraussetzungen: Python (siehe [`pyproject.toml`](pyproject.toml:1)), `uv`.

Python-Constraint (Policy): `>=3.11` (siehe [`pyproject.toml`](pyproject.toml:9)).

1) Dependencies installieren

```bash
uv venv
uv sync
```

2) Secrets konfigurieren (nur lokal)

- `cp .env.example .env`
- in `.env` die Werte für `YOUTUBE_API_KEY` und `OPENROUTER_API_KEY` setzen (siehe „Secrets / .env“ unten)

3) Run

```bash
uv run python -m transcript_miner --config config/config_stocks_crypto.yaml
```

Default-Verhalten (ohne zusätzliche Flags): der Lauf führt **Mining → Index → LLM-Summaries → Aggregation/Report** aus.

Optionen (Auswahl):

- nur Mining: `uv run python -m transcript_miner --config … --skip-index --skip-llm --skip-report`
- Report-Sprache (wenn `report.llm` aktiv ist): `--report-lang de|en|both`

### Smoke-Checks (offline)

Siehe auch die UV-first Smoke-Checks in [`AGENTS.md`](AGENTS.md:176).

```bash
uv run python -m transcript_miner --help
uv run python -c "import transcript_miner"
uv run pytest -q
```

## Workflow (GitHub Flow)

Workflow-Entscheidung: GitHub Flow.

- Arbeit passiert auf Feature-Branches.
- Integration via Pull Request nach `main`.
- CI ist der Qualitäts-Gate für PRs.

## CI / Tooling

Die GitHub Actions Workflows unter [`.github/workflows/`](.github/workflows:1) verwenden `uv`.

### Optionale Dependencies (Policy)

- `google-api-python-client` / `googleapiclient`: wird **nur** für echte YouTube Data API Calls benötigt und wird bewusst lazy importiert (siehe [`transcript_miner.youtube_client._require_googleapiclient()`](src/transcript_miner/youtube_client.py:20)), damit `--help`/Imports offline nicht crashen.
- `openai`: wird für LLM-basierte Features benötigt (z.B. LLM-Analyse-Runner); ohne Paket schlägt ein tatsächlicher LLM-Call fehl; Retry-Policy nutzt cap + jitter und berücksichtigt `Retry-After` (siehe [`common.utils.call_openai_with_retry()`](src/common/utils.py:31)).
- `tiktoken`: optional für Token-Counting; ohne Paket wird ein heuristischer Fallback verwendet (siehe [`common.utils.calculate_token_count()`](src/common/utils.py:165)).

### Secret Scanning (CI)

In CI läuft ein Secret-Scan über Gitleaks (Workflow: [`.github/workflows/gitleaks.yml`](.github/workflows/gitleaks.yml:1)).

## Secrets / `.env`

Dieses Projekt verwendet eine lokale [`.env`](.env:1) für **Secrets**.

Regeln:

- Die Datei `.env` ist **nicht** im Git und wird ignoriert (siehe [`.gitignore`](.gitignore:1)).
- In `.env` stehen **ausschließlich Secrets** (keine Konfig/Flags/Paths).
- Für Variablennamen/Beispiele siehe [`.env.example`](.env.example:1).

Benötigte Variablen:

- `YOUTUBE_API_KEY`: YouTube Data API v3 Key
- `OPENROUTER_API_KEY`: OpenRouter API Key (für LLM-Analyse)

### Troubleshooting (Secrets / API-Key)

#### 1) Key fehlt / wird nicht gefunden

- Symptom: Miner beendet sich früh mit „YouTube API key not found …“.
- Evidenz: Check + Exit-Code `1` in [`run_miner()`](src/transcript_miner/main.py:177) (Key-Fallback `config.api.youtube_api_key` → `os.environ["YOUTUBE_API_KEY"]`, siehe [`run_miner()`](src/transcript_miner/main.py:190)).
- `.env` wird erst **nach** `argparse` geladen (best-effort), damit `--help` offline robust bleibt (siehe `.env`-Loading in [`main()`](src/transcript_miner/main.py:245)).

#### 2) Key ist ungültig / YouTube Data API Fehler

- Symptom: Channel-Resolution oder Videolisten schlagen fehl; es wird geloggt und das jeweilige Processing bricht ab.
- Evidenz: `HttpError` wird in [`get_channel_by_handle()`](src/transcript_miner/youtube_client.py:204) geloggt und führt zu `None`-Return; daraus folgt Abbruch in [`process_channel()`](src/transcript_miner/main.py:57) (Branch: „could not resolve channel“, siehe [`process_channel()`](src/transcript_miner/main.py:82)).

#### 3) Quota / Rate-Limit / temporäre HTTP-Fehler

- Symptom: wiederholte Warnungen/Retry-Logs bei Data-API Requests.
- Evidenz: Retry-Policy + Backoff/Jitter in [`_execute_with_retries()`](src/transcript_miner/youtube_client.py:107); die Retrybarkeit hängt u.a. von Status-Codes (`429`, `5xx`) und bestimmten `403`-Reasons ab (siehe [`_is_retryable_google_http_error()`](src/transcript_miner/youtube_client.py:87)).

#### 4) „Keine Transkripte“ / IP-Blocks

- **Symptom:** Miner bricht mit `IpBlocked` oder `RequestBlocked` ab.
- **Ursache:** YouTube blockiert Datacenter-IPs (Cloud) und IPs mit geringer Reputation (VPN, WSL-Hosts) für den Transcript-Endpunkt.
- **Diagnose:** Nutze `uv run python tools/repro_ip_block.py <video_id>`, um zu prüfen, ob ein isolierter Request funktioniert.
- **Diagnose (Matrix):** Nutze `uv run python tools/youtube_block_probe.py --config config/config_stocks_crypto.yaml --videos <video_id>` um Rate-Limit-Parameter systematisch zu testen.
- **Lösung:** 
  - Nutze **Residential Proxies** (z.B. Webshare.io Residential Plan). Datacenter-Proxies funktionieren oft nicht.
  - Nutze das konservative, cookie-freie Profil in [`config/config_wsl_optimized.yaml`](config/config_wsl_optimized.yaml:1) oder erhöhe `min_delay_s`/`jitter_s` entsprechend.
  - Teste einen Handy-Hotspot, um ISP-seitige Blocks auszuschließen.

Hinweis zu Logs:

- Überblick über relevante Logfiles: [`logs/README.md`](logs/README.md:1).
- Fehler-History (JSONL, append-only): `output/data/diagnostics/errors.jsonl` (ERROR+ aus der Pipeline; bei globalem Output-Layout).

## Konfiguration

Konfigurationsdateien liegen unter [`config/`](config:1).

Eine detaillierte Schema-Referenz (inkl. Minimalbeispiel) ist in [`docs/config.md`](docs/config.md:1) dokumentiert.

Wenn du verstehen willst, **wie die Pipeline und die Analyse-Schritte zusammenspielen** (inkl. Mermaid-Übersichten und offenen Architektur-Entscheidungen), lies zusätzlich [`docs/architecture.md`](docs/architecture.md:1).

### Minimal-YAML (für Parsing/Validation, nicht als „läuft ohne Key“ zu verstehen)

Beispiel (10–15 Zeilen):

```yaml
api:
  youtube_api_key: ${YOUTUBE_API_KEY}
youtube:
  channels: ["@CouchInvestor"]
  num_videos: 1
  preferred_languages: ["en", "de"]
  keywords: ["inflation"]
output:
  global: ../output/example
  topic: example
  metadata: false
logging:
  level: INFO
```

Offline/ohne Netz kannst du damit z.B. **nur** das Laden/Validieren testen:

- `load_config()` liest YAML, löst Pfade auf und legt nötige Verzeichnisse an (siehe [`common.config.load_config()`](src/common/config.py:23) und [`common.path_utils.ensure_directories_exist()`](src/common/path_utils.py:123)).

Wichtig für echte Runs:

- Für echte Channel/Video-Metadaten wird die YouTube Data API verwendet; ohne API-Key bricht der Miner mit Exit-Code `1` ab (siehe Key-Check in [`run_miner()`](src/transcript_miner/main.py:158)).

### Output-Pfad-Policy (empfohlen vs. Legacy)

- **Empfohlen (neu, global dedup):** `output.global` + `output.topic`
  - Globales Root via [`OutputConfig.get_global_root()`](src/common/config_models.py:164), Reports unter [`OutputConfig.get_reports_path()`](src/common/config_models.py:274).
  - Alias: `output.global_root` (legacy key, wird auf `output.global` gemappt).
- **Legacy (per-profile, multi-channel-safe):** `output.root_path` + `output.use_channel_subfolder: true`
  - Effektiver Pfad pro Channel wird in [`OutputConfig.get_transcripts_path()`](src/common/config_models.py:222) berechnet.
- **Legacy-Fallback:** `output.path`
  - Wird **nur** genutzt, wenn `output.root_path` nicht gesetzt ist (siehe Fallback in [`OutputConfig.get_path()`](src/common/config_models.py:203)).

### `${VAR}`-Substitution (YAML)

- `${VAR}` wird für Pfade beim Laden ersetzt (siehe [`common.path_utils.substitute_env_vars()`](src/common/path_utils.py:71) und [`common.path_utils.resolve_paths()`](src/common/path_utils.py:12)).
- `${VAR}` wird auch für `api.youtube_api_key` unterstützt (siehe [`ApiConfig.resolve_api_key_env_vars()`](src/common/config_models.py:162)).

Hinweis:

- Falls ein Platzhalter `${VAR}` nicht aufgelöst werden kann, wird `api.youtube_api_key` als **nicht gesetzt** behandelt (intern `None`), damit korrekt auf Environment/CLI-Fallbacks zurückgefallen wird (siehe [`ApiConfig.resolve_api_key_env_vars()`](src/common/config_models.py:162)).

API-Key-Priorität (höchste zuerst):
1. `--api-key` CLI argument
2. `config.api.youtube_api_key`
3. `YOUTUBE_API_KEY` Environment Variable (aus `.env`)

## Wie ausführen (Entry-Points)

Es existieren mehrere Entry-Points, je nach Use-Case:

### Entry-Points im Vergleich (Ist-Zustand)

| Entry-Point | Konfig-Übergabe | `.env`-Loading (wann?) | API-Key-Resolution | Quelle |
|---|---|---|---|---|
| `uv run python -m transcript_miner` | `--config <yaml>` (repeatable) oder positional `config_path` + optional `--api-key` | best-effort in Paket-Entry [`src/transcript_miner/__main__.py`](src/transcript_miner/__main__.py:1) via [`dotenv.load_dotenv()`](src/transcript_miner/__main__.py:15) **und** zusätzlich best-effort nach Argparse in [`src/transcript_miner/main.py`](src/transcript_miner/main.py) | `--api-key` wird in Environment + Config gespiegelt; danach nutzt der Miner `config.api.youtube_api_key` → `YOUTUBE_API_KEY` | [`src/transcript_miner/main.py`](src/transcript_miner/main.py) |
| `uv run python -m src` | wie `python -m transcript_miner` (delegiert an `main()`) | lädt `.env` in [`src/__main__.py`](src/__main__.py:1) via [`dotenv.load_dotenv()`](src/__main__.py:15) | identisch zu `python -m transcript_miner`, da am Ende [`transcript_miner.main.main()`](src/transcript_miner/main.py:226) ausgeführt wird | [`src.__main__`](src/__main__.py:1), [`transcript_miner.main.main()`](src/transcript_miner/main.py:226) |

Empfehlung:

- Primärer CLI-Einstieg ist `python -m transcript_miner`.

### 1) Modul-Entry: `python -m transcript_miner`

- Zweck: direkter CLI-Einstieg in das Miner-Paket (bietet `--api-key` Override).
- Implementierung: [`transcript_miner.main.main()`](src/transcript_miner/main.py:226) und Paket-Entry [`src/transcript_miner/__main__.py`](src/transcript_miner/__main__.py:1).

Beispiele:

```bash
uv run python -m transcript_miner config/config_ai_knowledge.yaml
uv run python -m transcript_miner config/config_ai_knowledge.yaml --api-key "$YOUTUBE_API_KEY"
```

#### Multi-Config Nutzung (Default: Multi-Run)

Das Modul-CLI unterstützt mehrere Config-Dateien über ein **repeatable** `--config` Flag (argparse `action="append"`, siehe [`transcript_miner.main.parse_arguments()`](src/transcript_miner/main.py:334)).

Wichtig (Ist-Verhalten):

- **Syntax:** mehrere `--config <path>` angeben.
- **Nicht mischen:** `--config ...` darf **nicht** zusammen mit dem positional `config_path` verwendet werden (Guard in [`transcript_miner.main._run_with_parsed_args()`](src/transcript_miner/main.py:422)).
- **Semantik:** sobald mehr als eine Config angegeben wird, ist der Modus **Multi-Run**: jede YAML wird separat ausgeführt (nacheinander) (Scope-/Ist-Doku in [`docs/config.md`](docs/config.md:60)).

Kollisions-/Output-Policy (Kernidee: keine stillen Overwrites):

- Es wird eine deterministische `config_set_id` aus den Config-Dateien gebildet (siehe [`_compute_config_set_id()`](src/transcript_miner/main.py:43)) und ein Namespace-Ordner unter `output/_runs/{config_set_id}` angelegt (siehe [`_multi_run_namespace_root()`](src/transcript_miner/main.py:61)).
- Existiert dieser Ordner bereits, bricht der Run **fail-fast** ab (Overwrite-Guard in [`transcript_miner.main._run_with_parsed_args()`](src/transcript_miner/main.py:494)).
- Zusätzlich wird **fail-fast** geprüft, dass sich die einzelnen Runs nicht in `output.*` bzw. `logging.*` in die Quere kommen (Collision-Check in [`_validate_multi_run_isolation()`](src/transcript_miner/main.py:81)).

Beispiele (reale YAMLs unter [`config/`](config:1)):

```bash
# Beispiel 1: Stocks + AI Knowledge als Multi-Run
uv run python -m transcript_miner \
  --config config/config_stocks.yaml \
  --config config/config_ai_knowledge.yaml
```

Hinweis: In Multi-Run schreibt **jede** Config in ihren eigenen Output-Pfad gemäß `output.*` (Policy/Empfehlung siehe „Output-Pfad-Policy“ oben in [`README.md`](README.md:155) und Details in [`docs/config.md`](docs/config.md:344)).

### 2) Top-Level Modul-Entry: `python -m src`

Nur relevant, wenn direkt aus dem `src/`-Layout heraus gestartet wird:

- [`src/__main__.py`](src/__main__.py:1) lädt `.env` und ruft [`transcript_miner.main.main()`](src/transcript_miner/main.py:226) auf.

## Wie Transkripte bezogen werden (Mechanik)

Dieses Projekt nutzt **zwei unterschiedliche Mechaniken**, die oft verwechselt werden:

### 1) YouTube Data API v3 (Kanal-/Video-Metadaten)

- Client-Erstellung über `google-api-python-client` via [`build(... developerKey=api_key)`](src/transcript_miner/youtube_client.py:105) in [`get_youtube_client()`](src/transcript_miner/youtube_client.py:85).
- Kanalauflösung / Videolisten passieren über Data-API-Aufrufe in [`get_channel_by_handle()`](src/transcript_miner/youtube_client.py:108) und [`get_channel_videos()`](src/transcript_miner/youtube_client.py:149).
- Requests laufen durch den Retry/Timeout-Wrapper [`_execute_with_retries()`](src/transcript_miner/youtube_client.py:48) (Defaults: [`DEFAULT_YOUTUBE_API_NUM_RETRIES`](src/transcript_miner/youtube_client.py:23), [`DEFAULT_YOUTUBE_API_TIMEOUT_SEC`](src/transcript_miner/youtube_client.py:24)).

### 2) Transcript-Download (YouTubeTranscriptApi)

- Der eigentliche Transcript-Download passiert über `youtube-transcript-api` in [`download_transcript()`](src/transcript_miner/transcript_downloader.py:26).
- Sprach-Selektor (Ist-Verhalten):
  - zuerst „manually created transcript“ in `preferred_languages` (siehe [`download_transcript()`](src/transcript_miner/transcript_downloader.py:50))
  - dann „generated transcript“ in `preferred_languages` (siehe [`download_transcript()`](src/transcript_miner/transcript_downloader.py:61))
  - sonst Fallback: „erstes verfügbares Transkript“ aus der Liste (Iteration) (siehe [`download_transcript()`](src/transcript_miner/transcript_downloader.py:72)).
- In der Pipeline wird `preferred_languages` aus der YAML/Config an [`download_transcript()`](src/transcript_miner/transcript_downloader.py:26) übergeben (Callsite: [`process_single_video()`](src/transcript_miner/video_processor.py:185)).

## Outputs

Empfohlenes Layout (global dedup): siehe Output-Struktur unten sowie die Output-Pfad-Policy ("empfohlen vs. Legacy") in [`docs/config.md`](docs/config.md:170).

- Output-Basisverzeichnis: [`OutputConfig.get_global_root()`](src/common/config_models.py:164)
- Topic-Reports/History: [`OutputConfig.get_reports_path()`](src/common/config_models.py:274) und [`OutputConfig.get_run_reports_path()`](src/common/config_models.py:298)

### Ordnerstruktur (empfohlen: `output.global` + `output.topic`)

```text
output/
├── data/
│   ├── transcripts/
│   │   ├── by_video_id/
│   │   │   ├── <video_id>.txt
│   │   │   └── <video_id>.meta.json
│   │   └── skipped.json
│   ├── summaries/
│   │   └── by_video_id/
│   │       └── <video_id>.summary.md
│   └── indexes/
│       └── <topic>/current/
│           ├── manifest.json
│           ├── transcripts.jsonl
│           ├── audit.jsonl
│           └── ingest_index.jsonl
├── reports/
│   └── <topic>/
│       ├── report_de_<YYYY-MM-DD>.md
│       └── report_en_<YYYY-MM-DD>.md
└── history/
    └── <topic>/
        └── <YYYY-MM-DD>/
            └── <YYYY-MM-DD>__<HHMM>__<model>__<fingerprint>/
                ├── report.md / report_de.md / report_en.md
                ├── aggregates/
                ├── manifest.json
                ├── run_manifest.json
                ├── audit.jsonl
                ├── system_prompt.txt
                └── user_prompt.txt
```

Legacy-Layout (weiterhin unterstützt):

```text
{output_dir}/
├── 1_transcripts/
├── 2_summaries/
└── 3_reports/
```

### Report-Generierung (LLM-basiert)

Wenn `report.llm` in der Config gesetzt ist, erzeugt die Aggregation einen Report im History-Bundle und legt eine „Current“-Kopie unter `output/reports/<topic>/report_de_<YYYY-MM-DD>.md` bzw. `report_en_<YYYY-MM-DD>.md` ab.
Der Generator kann weiterhin manuell genutzt werden (z.B. für Re-Runs):

```bash
uv run python tools/generate_llm_report.py --config config/config_stocks.yaml
```

**Features:**
- **Sprache:** Standard ist `--report-lang de` → `report_de_<YYYY-MM-DD>.md`; optional `--report-lang both` → `report_de_...` + `report_en_...`.
- **Template-basiert:** Nutzt Strukturen aus `templates/` (z.B. `templates/report_stocks_de.md`).
- **Config-Aware:** Liest Prompts und Modell-Einstellungen aus der YAML-Config (`report:` Sektion).
- **Robust:** Prüft Token-Limits gegen das Context-Window des Modells (z.B. GPT-5.2, Gemini 3, Claude 4.5).

### Output Reference (Miner-Artefakte)

Quelle der Ablage pro Channel/Topic: [`OutputConfig`](src/common/config_models.py:93) und [`process_channel()`](src/transcript_miner/main.py:57).

| Artefakt | Ort (global layout) | Zweck | Quelle |
|---|---|---|---|
| `ingest_index.jsonl` | `output/data/indexes/<topic>/current/ingest_index.jsonl` | Persistenter „processed“-State; dient u.a. zur Duplikat-Vermeidung (Nachfolger von `progress.json`). | Writer: [`atomic_save_processed_videos()`](src/transcript_miner/video_processor.py:128) |
| `run_summary.md` | `output/reports/<topic>/run_summary.md` | Run-Überblick (Transkripte/Summaries: erstellt/geskippt/geheilt). | Writer: [`write_run_summary_md()`](src/common/run_summary.py:39) |
| `skipped.json` | `output/data/transcripts/skipped.json` | Persistenter Skip-State („kein Transkript“) zur Vermeidung endloser Retries. | Writer: [`atomic_save_skipped_videos()`](src/transcript_miner/video_processor.py:318) |
| `transcripts/*.txt` | `output/data/transcripts/by_video_id/` | Das gespeicherte Transkript (Plain-Text). | Writer: [`save_transcript()`](src/common/utils.py:386) |
| `transcripts/*.meta.json` | `output/data/transcripts/by_video_id/` | Metadaten pro Transkript. | Builder: [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `summaries/*.summary.md` | `output/data/summaries/by_video_id/` | Pro-Video LLM-Analyse (Knowledge Items). | LLM-Runner |

Hinweis: Im Legacy-Layout liegen die Artefakte weiterhin unter `{output_dir}/1_transcripts`, `{output_dir}/2_summaries`, `{output_dir}/3_reports`.

#### `_meta.json`: Feldliste (Ist-Schema)

Die Metadaten bestehen aus (A) Video-/Datei-Feldern aus [`_create_metadata()`](src/transcript_miner/video_processor.py:891) und (B) Download-Status-Feldern aus [`TranscriptDownloadResult.to_metadata_fields()`](src/transcript_miner/transcript_models.py:26).

Wichtig:

- Im „Skip“-Fall (Status `no_transcript` / `transcripts_disabled`) wird `_meta.json` optional ebenfalls geschrieben, enthält dann aber nur ein Teilset (separate Dict-Erzeugung in [`process_single_video()`](src/transcript_miner/video_processor.py:523)).

| Feld | Typ | Bedeutung | Quelle |
|---|---|---|---|
| `video_id` | string | YouTube Video-ID. | [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `video_title` | string | Videotitel. | [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `channel_id` | string | YouTube Channel-ID (resolved). | [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `channel_name` | string | Kanalname (Display-Name). | [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `published_at` | string | Veröffentlichungszeitpunkt (ISO-String / best-effort). | [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `downloaded_at` | string | Download-Zeitpunkt (UTC ISO-String). | [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `keywords_found` | list[string] | Liste gefundener Keywords (aus `youtube.keywords`). | [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `found_lines` | list[string] | Zeilen/Snippets, die ein Keyword-Match enthalten. | [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `transcript_token_count` | int | Token-Count (tiktoken oder heuristischer Fallback). | [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `transcript_filename` | string | Dateiname der `*.txt` Datei. | [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `transcript_filepath` | string | Pfad zur `*.txt` Datei (als String serialisiert). | [`_create_metadata()`](src/transcript_miner/video_processor.py:891) |
| `transcript_status` | string | Download-Status (`success`, `no_transcript`, `transcripts_disabled`, `error`). | [`TranscriptDownloadResult.to_metadata_fields()`](src/transcript_miner/transcript_models.py:26) |
| `transcript_reason` | string \| null | Best-effort Reason-Code (z.B. `no_transcript_found`). | [`TranscriptDownloadResult.to_metadata_fields()`](src/transcript_miner/transcript_models.py:26) |
| `transcript_error_type` | string \| null | Exception-Klassenname bei `error`. | [`TranscriptDownloadResult.to_metadata_fields()`](src/transcript_miner/transcript_models.py:26) |
| `transcript_error_message` | string \| null | Exception-Message bei `error`. | [`TranscriptDownloadResult.to_metadata_fields()`](src/transcript_miner/transcript_models.py:26) |

Details:

- `progress.json` ist pro Channel und speichert verarbeitete Video-IDs; es wird zusätzlich bidirektional mit dem Dateisystem synchronisiert (siehe [`sync_progress_with_filesystem()`](src/transcript_miner/video_processor.py:332)).
- Der Dateiname basiert auf Datum/Kanalname/Video-ID (siehe [`generate_filename_base()`](src/common/utils.py:138)).

### Policy: `progress.json` Corruption / Recovery

Quelle: Loader/Writer in [`load_processed_videos()`](src/transcript_miner/video_processor.py:28) und [`atomic_save_processed_videos()`](src/transcript_miner/video_processor.py:59).

- Bei jedem erfolgreichen Save wird die vorherige `progress.json` nach `progress.bak` verschoben ("last known good").
- Wenn `progress.json` fehlt, aber `progress.bak` existiert, wird automatisch aus dem Backup wiederhergestellt.
- Wenn `progress.json` nicht parsebar ist oder eine ungültige Struktur hat:
  - best-effort Restore aus `progress.bak`,
  - die korrupte Datei wird nach `progress.corrupted.<timestamp>.json` verschoben,
  - der Run läuft mit dem wiederhergestellten (oder leeren) State weiter.

### Policy: Output Retention / Cleanup

Quelle: Cleanup in [`cleanup_old_outputs()`](src/transcript_miner/video_processor.py:177) (aufgerufen in [`process_channel()`](src/transcript_miner/main.py:57) vor dem Sync).

- Konfig: `output.retention_days` (Default: 30, `null` deaktiviert Cleanup) (Schema: [`OutputConfig`](src/common/config_models.py:37)).
- Es werden deterministisch Dateien in `output/data/transcripts/by_video_id/` (global layout) bzw. `1_transcripts/` (Legacy) gelöscht, deren mtime älter als `N` Tage ist:
  - `*.txt` werden gelöscht; dazugehörige `*_meta.json` werden immer mitgelöscht (auch wenn deren mtime neuer ist), um Orphans zu vermeiden.
  - Zusätzlich werden alte standalone `*_meta.json` gelöscht (z.B. bei Skips ohne `.txt`).
- Danach sorgt der bestehende Sync dafür, dass `ingest_index.jsonl` keine IDs ohne `*_VIDEOID.txt` mehr enthält (siehe [`sync_progress_with_filesystem()`](src/transcript_miner/video_processor.py:332)).

## Analysis (offline) — Transcript Index

Die Analysis-Pipeline kann **offline** auf Basis bereits vorhandener Transcript-Outputs laufen.

Runner: [`transcript_miner.transcript_index.__main__.main()`](src/transcript_miner/transcript_index/__main__.py:33)

### Input

- Erwartetes Pattern: `output/data/transcripts/by_video_id/*.txt` (global) **oder** `{output_root}/**/1_transcripts/*.txt` (Legacy) (siehe Scanner in [`scan_output_roots()`](src/transcript_miner/transcript_index/scanner.py:55)).
- Das ist kompatibel zu sowohl
  - legacy `output.path` (Single-Channel) als auch
  - `output.root_path` + `output.use_channel_subfolder: true` (Multi-Channel), wobei der Ordner **oberhalb** von `1_transcripts/` als `channel_namespace` verwendet wird (siehe [`_channel_namespace_for_transcripts_dir()`](src/transcript_miner/transcript_index/scanner.py:28)).

### Artefakt-Layout (Transcript Index)

Bei einem Lauf schreibt der Runner in ein frei wählbares Output-Verzeichnis `output_dir` (z.B. `./output/_analysis`) **genau drei Artefakte** (Layout ist im Docstring festgehalten): [`write_analysis_index()`](src/transcript_miner/transcript_index/runner.py:44).

```text
{output_dir}/
├── manifest.json
├── transcripts.jsonl
└── audit.jsonl
```

#### `schema_version`: Bedeutung & (Dokumentations-)Policy

- `manifest.json` enthält `schema_version` als Integer-Feld im Modell [`AnalysisManifest`](src/transcript_miner/transcript_index/models.py:33) und wird beim Erzeugen aus der zentralen Konstante [`SCHEMA_VERSION`](src/transcript_miner/transcript_index/models.py:7) gesetzt (siehe [`AnalysisManifest.create()`](src/transcript_miner/transcript_index/models.py:40)).
- Aktueller Wert: `1` (siehe [`SCHEMA_VERSION`](src/transcript_miner/transcript_index/models.py:7)).
- **Policy (Doku; nicht vom Code erzwungen):** Bei **Breaking Changes** am Artefakt-Schema (Feld entfernt/umbenannt oder Semantik inkompatibel geändert) wird `SCHEMA_VERSION` inkrementiert; additive Felder sollten kompatibel bleiben und die `schema_version` nicht erhöhen. (Evidenz: es gibt genau eine zentrale Versionsquelle und sie wird in jedes Manifest geschrieben, siehe [`SCHEMA_VERSION`](src/transcript_miner/transcript_index/models.py:7) + [`AnalysisManifest.create()`](src/transcript_miner/transcript_index/models.py:40)).

### Schema-/Feldübersicht pro Artefakt

#### 1) `manifest.json` (Run-Metadaten)

Quelle des Modells: [`AnalysisManifest`](src/transcript_miner/transcript_index/models.py:33), Serialisierung: [`AnalysisManifest.to_json()`](src/transcript_miner/transcript_index/models.py:56).

Wichtigste Felder:

- `schema_version` *(int)*: siehe oben (gesetzt in [`AnalysisManifest.create()`](src/transcript_miner/transcript_index/models.py:40)).
- `input_roots` *(list[string])*: absolute, resolvte Input-Roots; deterministisch sortiert (siehe Manifest-Erzeugung in [`write_analysis_index()`](src/transcript_miner/transcript_index/runner.py:105)).
- `transcript_count` *(int)*: Anzahl gefundener Transkripte (`len(scan.transcripts)`) (siehe [`write_analysis_index()`](src/transcript_miner/transcript_index/runner.py:105)).
- `unique_video_count` *(int)*: Anzahl eindeutiger `video_id` Values (über `set`, siehe [`write_analysis_index()`](src/transcript_miner/transcript_index/runner.py:60)).
- `run_fingerprint` *(string)*: SHA-256 Hash über `transcripts.jsonl` Lines + Scan-Errors; bewusst ohne Timestamp, damit identische Inputs identische Manifest-Bytes ergeben (siehe [`_compute_run_fingerprint()`](src/transcript_miner/transcript_index/runner.py:27)).

#### 2) `transcripts.jsonl` (Index der Transkriptreferenzen)

Format: JSONL (eine JSON-Map pro Zeile). Quelle der Felder: [`TranscriptRef`](src/transcript_miner/transcript_index/models.py:11) + [`TranscriptRef.to_json()`](src/transcript_miner/transcript_index/models.py:21).

Felder pro Zeile:

- `output_root` *(string)*: Root-Verzeichnis, aus dem der Transcript-File entdeckt wurde (siehe [`TranscriptRef.to_json()`](src/transcript_miner/transcript_index/models.py:21)).
- `channel_namespace` *(string)*: stabiler Namespace, abgeleitet vom Ordner oberhalb `1_transcripts/` (Multi-Channel) oder `default` (Legacy) (siehe [`_channel_namespace_for_transcripts_dir()`](src/transcript_miner/transcript_index/scanner.py:28)).
- `video_id` *(string)*: Merge-Key/Identität (siehe „Merge-Key“ unten).
- `transcript_path` *(string)*: Pfad zur `*.txt` Datei (siehe [`TranscriptRef.to_json()`](src/transcript_miner/transcript_index/models.py:21)).
- `metadata_path` *(string|null)*: Pfad zur `*_meta.json` falls vorhanden (siehe Metadata-Detection in [`scan_output_roots()`](src/transcript_miner/transcript_index/scanner.py:45)).
- `published_date` *(string|null)*: `YYYY-MM-DD` aus dem Dateiprefix, falls parsebar (Regex: [`_PUBLISHED_DATE_RE`](src/transcript_miner/transcript_index/scanner.py:13)).

#### 3) `audit.jsonl` (Audit Trail: Discovery + Scan-Fehler)

Format: JSONL (eine JSON-Map pro Zeile). Writer/Events: [`write_analysis_index()`](src/transcript_miner/transcript_index/runner.py:44).

Event-Typen (`kind`):

- `kind = "transcript_discovered"`: wird pro gefundenem Transcript geschrieben (Felder siehe Event-Build in [`write_analysis_index()`](src/transcript_miner/transcript_index/runner.py:68)).
  - Kernfelder: `video_id`, `channel_namespace`, `transcript_path`, `metadata_path`, `published_date` (siehe [`write_analysis_index()`](src/transcript_miner/transcript_index/runner.py:68)).
  - Best-effort Metadata-Subset aus `*_meta.json` (nur wenn vorhanden): `channel_id`, `channel_name`, `video_title`, `published_at`, `transcript_status`, `transcript_reason` (Whitelist in [`write_analysis_index()`](src/transcript_miner/transcript_index/runner.py:80)).
- `kind = "scan_error"`: wird pro Scan-Fehler geschrieben (Feld `error`) (siehe [`write_analysis_index()`](src/transcript_miner/transcript_index/runner.py:93)).

### Determinismus & Overwrite-/Write-Policy (Ist-Zustand)

- **Deterministische Scan-Reihenfolge** unabhängig von CLI-Argument-Reihenfolge: Input-Roots werden sortiert, ebenso alle gefundenen Transcript-Dateien; zusätzlich werden die Output-Refs am Ende stabil sortiert (siehe Sortierungen in [`scan_output_roots()`](src/transcript_miner/transcript_index/scanner.py:45)).
- **Deterministisches Manifest** (kein Timestamp): `run_fingerprint` wird über die (deterministisch geordnete) `transcripts.jsonl`-Repräsentation + Errors gehasht; Docstring erklärt explizit die Motivation „identische Inputs → identische manifest.json bytes“ (siehe [`_compute_run_fingerprint()`](src/transcript_miner/transcript_index/runner.py:27)).
- **Overwrite-Policy:** die drei Artefakt-Dateien werden bei jedem Run neu geschrieben und via `*.tmp` + `replace()` atomar ersetzt (siehe [`_atomic_write_text()`](src/transcript_miner/transcript_index/runner.py:11) und [`_atomic_write_json()`](src/transcript_miner/transcript_index/runner.py:20)).

### Merge-Key / Transkript-Identität (`video_id`)

- Der Index verwendet `video_id` als stabilen Identifikator.
- Der `video_id` wird aus dem Transcript-Dateinamen per Regex extrahiert:
  - `by_video_id/<video_id>.txt` via [`_VIDEO_ID_PLAIN_RE`](src/transcript_miner/transcript_index/scanner.py:13)
  - `..._{video_id}.txt` via [`_VIDEO_ID_SUFFIX_RE`](src/transcript_miner/transcript_index/scanner.py:12)
- Wenn das Pattern nicht matcht, wird ein Scan-Error erzeugt und das File wird nicht in den Index aufgenommen (siehe Error-Branch in [`scan_output_roots()`](src/transcript_miner/transcript_index/scanner.py:93)).

### Beispiel

```bash
uv run python -m transcript_miner.transcript_index \
  --input-root ../output \
  --output-dir ../output/data/indexes/stocks_crypto/current
```

## Analysis (LLM) — optional (Chat Completions)

Dieser Schritt ist **optional** und läuft nur, wenn `analysis.llm.enabled: true` in der YAML gesetzt ist (siehe Guard in [`transcript_ai_analysis.llm_runner.run_llm_analysis()`](src/transcript_ai_analysis/llm_runner.py:203)).

Runner:

- [`transcript_ai_analysis.llm.__main__.main()`](src/transcript_ai_analysis/llm/__main__.py:37)

### Voraussetzungen

- Transcript Index Artefakte existieren (siehe „Analysis (offline) — Transcript Index“ oben): `manifest.json`, `transcripts.jsonl`, `audit.jsonl`.
 - API-Key ist gesetzt:
   - Env `OPENROUTER_API_KEY` (Fallback in [`run_llm_analysis()`](src/transcript_ai_analysis/llm_runner.py:259)).

### Konfiguration

Wenn `analysis.llm.enabled=true`, müssen diese Felder gesetzt sein (Validierung in [`LlmAnalysisConfig._validate_required_fields_when_enabled()`](src/common/config_models.py:228)):

- `analysis.llm.model`
- `analysis.llm.system_prompt`
- `analysis.llm.user_prompt_template`

### Optimierung: Daily Reports & Skip-Logic

Um unnötige Runs zu vermeiden und Reports besser zu organisieren, können folgende Optionen in `config.yaml` gesetzt werden:

- `output.daily_report: true`: **Legacy-Layout** — Reports werden in `3_reports/YYYY-MM-DD/` abgelegt (überschreibt existierende Reports des gleichen Tages).
- `output.skip_on_no_new_data: true`: Der Run wird übersprungen, wenn sich die Eingabedaten (Transkripte + Prompts) seit dem letzten Run nicht geändert haben.

### Ausführen

Beispiel:

```bash
ANALYSIS_ROOT=../output/_analysis_stocks
# 1. Index erstellen
uv run python -m transcript_miner.transcript_index \
  --input-root ../output \
  --output-dir "$ANALYSIS_ROOT/data/indexes/stocks_crypto/current"

# 2. LLM-Analyse ausführen
uv run python -m transcript_ai_analysis.llm \
  --config config/config_stocks.yaml \
  --profile-root "$ANALYSIS_ROOT"
```

### Outputs

Die Artefakte werden gemäß Output-Layout abgelegt (Writer: [`transcript_ai_analysis.llm_runner.run_llm_analysis()`](src/transcript_ai_analysis/llm_runner.py:339)):

- **Summaries (global):** `output/data/summaries/by_video_id/{video_id}.summary.md`
- **LLM-History-Bundle (global):** `output/history/<topic>/<YYYY-MM-DD>/<YYYY-MM-DD>__<HHMM>__<model>__<fingerprint>/`
  - `report.json` (enthält die LLM-Antwort unter `output.content`)
  - `report.md` **oder** `report.txt` (menschenlesbare View; Writer: [`_write_derived_report_and_metadata()`](src/transcript_ai_analysis/llm_runner.py:186))
  - `metadata.json`, `manifest.json`, `audit.jsonl`
  - `system_prompt.txt`, `user_prompt.txt`
  - `raw_transcripts/` (per-video raw transcript snapshots for audit)
- **Run-Manifest (Current):** `output/reports/<topic>/run_manifest.json`

Legacy bleibt unter `{PROFILE_ROOT}/2_summaries/` und `{PROFILE_ROOT}/3_reports/`.

Hinweis (Naming): `report.md` wird nur gewählt, wenn der Output wahrscheinlich Markdown ist (konservative Heuristik: [`_is_probably_markdown()`](src/transcript_ai_analysis/llm_runner.py:31)); sonst wird `report.txt` geschrieben.

## Aggregation (offline)

Nach der LLM-Analyse können die Ergebnisse aggregiert werden (z.B. Ticker-Coverage über alle Videos).

Runner: [`transcript_ai_analysis.__main__.main()`](src/transcript_ai_analysis/__main__.py:47)

### Ausführen

```bash
# 3. Aggregation ausführen
uv run python -m transcript_ai_analysis \
  --profile-root "$ANALYSIS_ROOT"
```

### Outputs

- **History-Bundle (global):** `output/history/<topic>/<YYYY-MM-DD>/<YYYY-MM-DD>__<HHMM>__aggregate__<fingerprint>/aggregates/`
- **Current Reports (global):** `output/reports/<topic>/report_de_<YYYY-MM-DD>.md` / `report_en_<YYYY-MM-DD>.md`

Legacy: `{PROFILE_ROOT}/3_reports/aggregates/` + `report.md`.

## Troubleshooting & Logs

- Log-Übersicht: [`logs/README.md`](logs/README.md:1)
- Häufige Ursachen:
  - fehlender API-Key (`YOUTUBE_API_KEY` oder `--api-key`) → siehe Key-Handling in [`run_miner()`](src/transcript_miner/main.py:158)
  - ungültige Config-Werte → Pydantic-Fehlerausgabe in [`transcript_miner.main.main()`](src/transcript_miner/main.py:226)

### Failure Modes / Verhalten (Ist-Zustand)

Dieser Abschnitt beschreibt explizit den **aktuellen Ist-Zustand** (ohne normative Bewertung).

#### Fehlender API-Key (Data API)

- Miner (`python -m transcript_miner`): wenn weder `config.api.youtube_api_key` noch `YOUTUBE_API_KEY` gesetzt ist, loggt [`run_miner()`](src/transcript_miner/main.py:158) einen Fehler und beendet mit Exit-Code `1` (siehe [`run_miner()`](src/transcript_miner/main.py:171)).

#### Data API Fehler (`HttpError`) → „leer/None“ + Logging

- Handle/Channel Lookup: bei `HttpError` loggt [`get_channel_by_handle()`](src/transcript_miner/youtube_client.py:108) und gibt `None` zurück (siehe [`get_channel_by_handle()`](src/transcript_miner/youtube_client.py:144)).
  - Konsequenz: [`process_channel()`](src/transcript_miner/main.py:57) bricht ab, wenn die Auflösung `None` liefert (siehe [`process_channel()`](src/transcript_miner/main.py:78)).
- Videoliste: bei `HttpError` loggt [`get_channel_videos()`](src/transcript_miner/youtube_client.py:149) und gibt `[]` zurück (siehe [`get_channel_videos()`](src/transcript_miner/youtube_client.py:234)).
  - Konsequenz: wenn `videos` leer ist, loggt [`process_channel()`](src/transcript_miner/main.py:57) „No videos found …“ und gibt `True` zurück (siehe [`process_channel()`](src/transcript_miner/main.py:123)).

#### „Kein Transkript verfügbar“ (Ist-Verhalten inkl. Progress-/Skip-State)

- Downloader: das Video-Processing nutzt [`download_transcript_result()`](src/transcript_miner/video_processor.py:503) und unterscheidet Status-Fälle (z.B. `no_transcript`, `transcripts_disabled`, `error`).
- Video-Processing: wenn **kein** Transkript verfügbar ist (Status `no_transcript` / `transcripts_disabled`), dann
  - werden **keine** Transcript-Dateien geschrieben,
  - die Skip-Entscheidung wird **persistiert** in `skipped.json` (damit der Skip-State nicht durch Filesystem-Sync „weggeräumt“ wird), siehe Persistenz in [`process_single_video()`](src/transcript_miner/video_processor.py:514),
  - optional wird `_meta.json` im Skip-Fall geschrieben, wenn `output.metadata=true` (siehe Skip-Metadata-Branch in [`process_single_video()`](src/transcript_miner/video_processor.py:523)),
  - und [`process_single_video()`](src/transcript_miner/video_processor.py:437) gibt `True` zurück ("handled", kein Retry-Spam), siehe Return in [`process_single_video()`](src/transcript_miner/video_processor.py:554).
- Progress-Sync: zu Beginn eines Channel-Runs wird `progress.json` mit dem Dateisystem abgeglichen (siehe [`process_channel()`](src/transcript_miner/main.py:57) → [`sync_progress_with_filesystem()`](src/transcript_miner/video_processor.py:332)). Dabei werden IDs ohne passende `*_VIDEOID.txt` Datei entfernt.
  - Hinweis zum Ordering: die Reihenfolge der IDs in `progress.json` ist **nicht semantisch** (membership-only) und wird beim Sync deterministisch nach `video_id` sortiert (siehe Sortierung in [`sync_progress_with_filesystem()`](src/transcript_miner/video_processor.py:388)).

### Robustheit: Retry/Timeout (YouTube Data API)

- YouTube Data API Requests nutzen eine kleine Retry-Policy mit **Timeout + Exponential Backoff + Jitter** (Wrapper: [`transcript_miner.youtube_client._execute_with_retries()`](src/transcript_miner/youtube_client.py:48)).
  - Retryable: Timeouts, HTTP `429`, `5xx`, sowie bestimmte `403`-Reasons (Quota / Rate-Limit).
  - Zusätzlich wird pro Call ein Socket-Default-Timeout gesetzt und danach wiederhergestellt.

## Support

### Scope (was „supported“ ist)

- **Dokumentierte Workflows** aus dieser README (Quickstart + Entry-Points): [`README.md`](README.md:22).
- **Konfigurationsschema** und seine Prioritäten (CLI > YAML > Env) gemäß [`docs/config.md`](docs/config.md:1).
- **Offline-Smoke/Qualität**: `--help`, Import, Tests (UV-first) gemäß „Smoke-Checks (offline)“: [`README.md`](README.md:46).

### Bugs melden (minimaler, reproduzierbarer Report)

Wenn ein Run fehlschlägt, liefere (falls möglich) diese Infos mit:

1) **Befehl/Entry-Point**, den du ausgeführt hast (z.B. `uv run python -m transcript_miner ...`, siehe Entry-Point-Übersicht: [`README.md`](README.md:177)).
2) **Config-Datei** (ohne Secrets): YAML soll `${YOUTUBE_API_KEY}` referenzieren statt den Key zu enthalten (Secrets-Regeln: [`README.md`](README.md:79)).
3) **Logs (redacted)**: relevante Ausschnitte aus `logs/` (Startpunkt: [`logs/README.md`](logs/README.md:1)); keine Keys/Tokens posten (Secret-Scan in CI: [`README.md`](README.md:75)).
4) **Version/Stand**: `version` aus [`pyproject.toml`](pyproject.toml:3) und idealerweise der Commit-Hash.
5) **Offline-Checks**: Output der Smoke-Checks (mindestens `--help` + Import), siehe [`README.md`](README.md:46).

### Bekannte Limits / häufige Ursachen

- **API-Key/Secrets:** ein fehlender Key führt zu frühem Abbruch (Miner: Exit-Code `1`), siehe Evidenz in [`run_miner()`](src/transcript_miner/main.py:158) und die Regeln in „Secrets / `.env`“: [`README.md`](README.md:79).
- **Quota/Rate-Limits:** Data-API Requests können durch Quota/HTTP-Fehler scheitern; es gibt eine Retry-Policy, siehe [`_execute_with_retries()`](src/transcript_miner/youtube_client.py:48) und Troubleshooting-Hinweise: [`README.md`](README.md:106).
- **Optionale Dependencies:** bestimmte Features benötigen optionale Pakete und werden bewusst lazy-importiert (Policy + Quellen: [`README.md`](README.md:69)).


Hinweis: Der Legacy „Transcript Corrector“ (LLM-Korrektur) wurde entfernt; das Zielbild ist „fetch → analysis“ (siehe [`TODO.md`](../TODO.md:17)).
