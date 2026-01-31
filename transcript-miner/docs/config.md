# Konfigurations-Referenz (YAML)

Diese Referenz beschreibt die **YAML-Konfiguration**, die beim Transcript Miner geladen und via Pydantic validiert wird.

Hinweis zu Code-Links in dieser Doku:

- Links im Format `pfad/datei.py:zeile` sind für VS Code (und ähnliche Editoren) optimiert und springen direkt an die referenzierte Stelle.

Quelle des Schemas: [`common.config_models.Config`](../src/common/config_models.py:179)

## Konfig-Hierarchie / Priorität (API-Key)

Priorität (höchste zuerst):

1. CLI-Argument `--api-key` (Modul-Entry, siehe [`transcript_miner.main.parse_arguments()`](../src/transcript_miner/main.py:334))
2. `api.youtube_api_key` aus YAML (siehe [`ApiConfig.youtube_api_key`](../src/common/config_models.py:147))
3. `YOUTUBE_API_KEY` aus Environment / `.env` (siehe [`transcript_miner.main.run_miner()`](../src/transcript_miner/main.py:282) und [`.env.example`](../.env.example:1))

## Global-Config (cross-topic Defaults)

Optional kann eine globale Config genutzt werden, um **topic-unabhängige Defaults** (z.B. Proxy/Rate-Limits, `output.global`, API-Attribution) zentral zu setzen.

- Default-Pfad: [`config/config_global.yaml`](../config/config_global.yaml:1)
- Merge-Policy (Ist-Verhalten): globale Config wird zuerst geladen, danach wird die Topic-Config geladen; bei Konflikten gewinnt die Topic-Config.
  - Dicts werden rekursiv gemerged.
  - Listen/Scalars werden durch die Topic-Config ersetzt.

Quelle: Loader in [`common.config.load_config()`](../src/common/config.py:23).

Wichtig:

- Das Miner-Modul liest den Key in [`run_miner()`](../src/transcript_miner/main.py:177) aus `config.api.youtube_api_key` und fällt sonst auf `YOUTUBE_API_KEY` zurück (siehe Env-Fallback in [`run_miner()`](../src/transcript_miner/main.py:192)).

## Minimalbeispiel ([PRD](PRD.md) Struktur)

```yaml
api:
  youtube_api_key: ${YOUTUBE_API_KEY}

youtube:
  channels:
    - "@CouchInvestor"
  num_videos: 2
  keywords: []
  preferred_languages: ["en", "de"]

output:
  # Empfohlen (global dedup):
  global: ../output
  topic: example
  metadata: true

logging:
  level: INFO
  file: ../logs/miner.log
  error_log_file: ../logs/error.log
```

Hinweis zu `${…}`:

- `api.youtube_api_key` kann `${YOUTUBE_API_KEY}` enthalten und wird beim Laden ersetzt (siehe [`ApiConfig.resolve_api_key_env_vars()`](../src/common/config_models.py:161)).

Wichtig:

- Wenn `${VAR}` nicht gesetzt ist, bleibt der Platzhalter in `substitute_env_vars()` unverändert; für `api.youtube_api_key` wird ein nicht aufgelöster Platzhalter anschließend als **nicht gesetzt** behandelt (→ `None`), damit die Fallback-Priorität (Config → Environment) korrekt greift (siehe [`ApiConfig.resolve_api_key_env_vars()`](../src/common/config_models.py:162) und [`common.path_utils.substitute_env_vars()`](../src/common/path_utils.py:71)).

## Multi-Config (Config Composition)

Dieser Abschnitt beschreibt (A) den **Ist-Zustand** der Multi-Config CLI (implementiert) und (B) die darüber hinausgehende **Spezifikation** (normativ; teilweise noch proposed).

Quellen:

- ADR (Design-Entscheidung/Entwurf): [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:1) *(Status dort: Proposed)*.
- Pfad-Policy (Ist-Verhalten): Relative Pfade in `output.*`/`logging.*` sind **config-dir-relativ** (Evidenz: `base_dir = config_path.parent.resolve()` in [`common.config.load_config()`](../src/common/config.py:23) und Resolver in [`common.path_utils.resolve_paths()`](../src/common/path_utils.py:12); Doku-Regel: [`docs/config.md`](config.md:216)).

Wichtig (Scope/Invariant):

- Die bestehende Priorität bleibt unverändert: **CLI > Config > Env > Defaults** (siehe [`docs/config.md`](config.md:11) und Kontext in [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:21)).
- Multi-Config umfasst zwei Ebenen:
  - **Ist (implementiert):** repeatable `--config` + deterministische Reihenfolge/ID + Default-Modus „multi-run“.
  - **Spez (proposed):** weitere Modi wie „merge“/„union“ und deren Konflikt-/Merge-Regeln.

### Ist-Zustand (implementiert): repeatable `--config` (Default: Multi-Run)

Evidenz:

- Argparse akzeptiert `--config` als repeatable Flag (`action="append"`) und verbietet das Mischen mit dem positional `config_path`: [`transcript_miner.main.parse_arguments()`](../src/transcript_miner/main.py:334) und Guard in [`transcript_miner.main._run_with_parsed_args()`](../src/transcript_miner/main.py:422).
- Kanonische Config-Order (resolve → dedupe → sort): [`transcript_miner.main._canonical_config_paths()`](../src/transcript_miner/main.py:29).
- Deterministische `config_set_id` (Basenames + SHA-256 über Config-Bytes): [`transcript_miner.main._compute_config_set_id()`](../src/transcript_miner/main.py:43).
- Namespace-Run-Root: `output/_runs/{config_set_id}` (Fail-fast wenn existiert): [`transcript_miner.main._multi_run_namespace_root()`](../src/transcript_miner/main.py:61) und Overwrite-Guard in [`transcript_miner.main._run_with_parsed_args()`](../src/transcript_miner/main.py:494).
- Fail-fast Multi-Run Isolation (Output-Root + Logfiles dürfen nicht kollidieren): [`transcript_miner.main._validate_multi_run_isolation()`](../src/transcript_miner/main.py:81).

#### Nutzerorientiert: „Wie benutze ich das heute?“ (Ist-Zustand)

Die Multi-Config CLI ist im Miner-Modul (`python -m transcript_miner`) implementiert und nutzt ein **repeatable** `--config` Flag (siehe [`transcript_miner.main.parse_arguments()`](../src/transcript_miner/main.py:334)).

- Mehrere Configs werden als **Multi-Run** ausgeführt: jede YAML läuft separat (nacheinander) und verwendet ihre eigenen `output.*`/`logging.*` Einstellungen (siehe Scope-Statement in [`docs/config.md`](config.md:69)).
- `--config ...` darf nicht mit dem positional `config_path` gemischt werden (Guard in [`transcript_miner.main._run_with_parsed_args()`](../src/transcript_miner/main.py:422)).

Default-Pipeline (Ist-Zustand):

- Ein normaler Run führt standardmäßig **Mining → Index → LLM-Summaries → Aggregation/Report** aus.
- Schritte sind per CLI steuerbar: `--skip-index`, `--skip-llm`, `--skip-report` oder `--only mine|index|llm|report` (siehe [`src/transcript_miner/main.py`](../src/transcript_miner/main.py)).
- Report-Sprache (wenn `report.llm` aktiv ist): `--report-lang de|en|both` (siehe [`src/transcript_miner/main.py`](../src/transcript_miner/main.py) und [`src/transcript_ai_analysis/__main__.py`](../src/transcript_ai_analysis/__main__.py)).

Beispiele mit existierenden YAMLs:

```bash
# Multi-Run: Stocks + AI Knowledge
uv run python -m transcript_miner \
  --config config/config_investing.yaml \
  --config config/config_ai_knowledge.yaml
```

```bash
# Multi-Run: zwei Configs
uv run python -m transcript_miner \
  --config config/config_investing.yaml \
  --config config/config_ai_knowledge.yaml
```

Output-/Kollisions-Policy (Ist-Verhalten):

- deterministische `config_set_id` + Namespace unter `output/_runs/{config_set_id}` (siehe [`_compute_config_set_id()`](../src/transcript_miner/main.py:43) und [`_multi_run_namespace_root()`](../src/transcript_miner/main.py:61)); existierender Namespace → **fail-fast** (siehe [`transcript_miner.main._run_with_parsed_args()`](../src/transcript_miner/main.py:494)).
- zusätzlich: **fail-fast** wenn zwei Configs auf denselben effektiven Output-Root oder dieselben Logfiles resolven (siehe [`_validate_multi_run_isolation()`](../src/transcript_miner/main.py:81)).

### Begriffe & Determinismus

- **ConfigFile**: ein YAML-File auf Disk.
- **ConfigSet**: Menge mehrerer ConfigFiles.
- **Kanonische Config-Order (normativ):**
  1. `absolute_path = Path(path).resolve()`
  2. Duplikate (gleicher `absolute_path`) entfernen
  3. sortieren: lexikographisch nach String von `absolute_path`

Quelle der Order-Regel: Abschnitt „Kanonische Config-Order“ in [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:41).

### Modus-Katalog (Semantik) — Spezifikation (proposed)

Es gibt drei Kompositionsmodi:

1) **Multi-Run** *(mehrere Runs, gemeinsame Analyse)* — **empfohlener Default (normativ)**

- Semantik: Jede Config wird **separat** ausgeführt (eigene Outputs/Logs). Für nachgelagerte Analyse wird die **Union** der Output-Roots betrachtet.
- Begründung (Safety): geringstes Kollisionsrisiko, weil `output.*`/`logging.*` nicht vereinheitlicht werden müssen (ADR: „Multi-Run: pro Config“ in [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:65)).

2) **Merge** *(eine effektive Config, ein Miner-Run)*

- Semantik: Mehrere YAMLs werden zu **einer** effektiven Config zusammengeführt; es gibt **einen** Miner-Run.

3) **Union** *(vereinigen + konfliktauflösen, ein Miner-Run)*

- Semantik: Bestimmte Felder werden **vereinigt** (stable union), der Rest wird deterministisch konfliktauflösend behandelt oder fail-fast.

### Konfliktregeln (normativ)

Die Konfliktregeln gelten für die Auflösung *zwischen* mehreren ConfigFiles (C1..Cn in kanonischer Order). Sie gelten **zusätzlich** zur unveränderten Priorität (CLI > Config > Env > Defaults).

#### 1) Kollisionskritische Felder: `output.*` (Merge/Union: fail-fast)

Begründung: `output.*` bestimmt den Ort von `progress.json`, `transcripts/` etc. (Output-Referenz: [`README.md`](../README.md:241)). Kollisionen sind Datenverlust-/Inconsistency-Risiko.

**Regel (normativ, Merge/Union): fail-fast bei Konflikt.**

- Wenn mindestens eine Config `output.root_path` oder `output.path` setzt, müssen die *effektiven* Werte der folgenden Felder über alle Configs **identisch** sein:
  - `output.root_path` (falls gesetzt) bzw. `output.path` (Fallback)
  - `output.use_channel_subfolder`
  - `output.metadata`
  - `output.retention_days`
- Andernfalls: **Fehler** („output.* conflict“).

Quelle der Regel: [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:94).

**Regel (normativ, Multi-Run): pro ConfigFile.**

- Keine Gleichheitsanforderung; jede Config schreibt in ihre eigenen Outputs.

#### 2) Kollisionskritische Felder: `logging.*` (Merge/Union: fail-fast)

Begründung: mehrere Runs in dieselben Logfiles führen zu schwer auditierbaren, nicht-deterministischen Log-Interleavings.

**Regel (normativ, Merge/Union): fail-fast bei Konflikt.**

- `logging.level`, `logging.file`, `logging.error_log_file` müssen über alle Configs **identisch** sein.
- Rotation-Felder (falls genutzt) sind analog zu behandeln (Schema-Felder siehe [`docs/config.md`](config.md:266)).

Quelle der Regel: [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:116).

**Regel (normativ, Multi-Run): pro ConfigFile.**

- Jede Config loggt in ihre eigenen Files.

#### 3) Additiv vs. überschreibend (normative Tabelle)

| Feld | Merge-Regel | Union-Regel | Multi-Run |
|---|---|---|---|
| `youtube.channels` | last-one-wins | stable union (dedupe) | pro Config |
| `youtube.keywords` | last-one-wins | stable union (dedupe) | pro Config |
| `youtube.preferred_languages` | last-one-wins | stable union (dedupe) | pro Config |
| `youtube.num_videos` | last-one-wins | `max(...)` | pro Config |
| `youtube.lookback_days` | last-one-wins | `max(...)` | pro Config |
| `youtube.max_videos_per_channel` | last-one-wins | `max(...)` | pro Config |

Details / Quelle: Feld-Regeln in [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:133).

Stable union (normativ): Startliste = Wert aus C1; dann C2..Cn, append nur neue Einträge (Vergleich: exact string nach `strip()`). Quelle: [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:151).

#### 4) Alle anderen Felder (Merge/Union: fail-fast)

**Regel (normativ):**

- In Merge/Union gilt: **fail-fast bei Konflikt**, wenn das Feld nicht explizit durch eine Regel oben abgedeckt ist.

Motivation: schützt gegen implizite Semantik und stille Änderungen an Analyse-Prompts/Outputs (ADR: [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:183)).

### Deterministische Run-Identität / Namespaces (normativ; Implementierung: proposed)

Ziel: Multi-Config Runs müssen eine stabile Identität haben, um Kollisionen/Overwrites zu vermeiden (Policy: „keine stillen Overwrites“ in [`AGENTS.md`](../AGENTS.md:140)).

#### 1) `config_set_id` (normativ)

Wir definieren eine deterministische `config_set_id` (String):

1. `names_part`: Basenames der ConfigFiles (ohne Extension), in kanonischer Order, join mit `+`.
2. `hash_part`: SHA-256 über die Bytes der ConfigFiles in kanonischer Order, getrennt durch `\0`; davon z.B. die ersten 12 hex chars.
3. `config_set_id = {names_part}__cs-{hash_part}`.

Quelle: [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:202).

#### 2) Namespace-Verwendung / Run-Root (normativ; proposed)

- Für Artefakte, die den Multi-Config Kontext repräsentieren (z.B. „gemeinsame Analyse“ im Multi-Run Modus), wird ein eigener Namespace-Ordner verwendet:
  - empfohlen: `<repo>/output/_runs/{config_set_id}/...` (ADR: [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:221)).
- Overwrite-Policy (normativ, proposed): existierender `{config_set_id}`-Ordner → **fail-fast**, außer es wurde explizit ein Reuse/Overwrite Mechanismus gewählt (Design-Optionen: [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:234)).

#### 3) Channel-Namespace (Ist-Zustand; relevant für Kollisionen)

Für Multi-Channel Outputs ist die empfohlene Ablage `output.global` + `output.topic` (global dedup; Policy/Quelle: [`README.md`](../README.md:155)).  
Legacy-Alternative: `output.root_path` + `output.use_channel_subfolder: true`, damit pro Channel ein eigenes Unterverzeichnis entsteht (Berechnung in [`OutputConfig.get_transcripts_path()`](../src/common/config_models.py)).

### Pfad-Resolution bei mehreren Config-Dirs (normativ)

#### 1) Grundregel: Auflösung pro ConfigFile

- Jede Config wird mit ihrer **eigenen** `base_dir = config_path.parent.resolve()` geladen.
- Relative Pfade in `output.*` und `logging.*` werden **vor** der Komposition gegen diese `base_dir` aufgelöst (Evidenz: [`common.config.load_config()`](../src/common/config.py:23) + [`common.path_utils.resolve_paths()`](../src/common/path_utils.py:12)).

#### 2) Vergleich/„Identisch“-Definition in Merge/Union

Wenn Merge/Union „identische“ Pfade fordert (fail-fast Regeln oben), meint das **nach Pfad-Resolution**:

- Wenn zwei verschiedene YAML-Strings auf denselben absoluten Pfad resolven, ist das **kein** Konflikt.
- Wenn sie auf unterschiedliche Pfade resolven, ist das ein Konflikt.

#### 3) Konsequenz für Configs unter `config/`

Da relative Pfade config-dir-relativ sind, muss ein Run-Root im Repo-Root typischerweise als `../output/...` formuliert werden (Policy-Reminder in [`docs/config.md`](config.md:216) und ADR-Hinweis: [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:230)).

### Beispiele

#### Beispiel 1 (Ist-Verhalten, ohne Multi-Config CLI): „Manual Multi-Run“ + Union-Analyse via Output-Root

Dieses Beispiel nutzt ausschließlich bestehende Single-Config Runs und danach die Index-Analyse über einen gemeinsamen Output-Root.

1) Miner separat ausführen:

```bash
uv run python -m transcript_miner config/config_investing.yaml
uv run python -m transcript_miner config/config_ai_knowledge.yaml
```

2) Danach Index/Analysis über *einen* gemeinsamen Output-Root (Beispiel-Command in README):

```bash
uv run python -m transcript_miner.transcript_index \
  --input-root ../output \
  --output-dir ../output/_analysis
```

Quelle für den Index-Runner Aufruf: [`README.md`](../README.md:409).

#### Beispiel 2 (**proposed**): Multi-Run per „repeatable --config“

```bash
# Ist-Zustand: Multi-Run ist der Default, sobald mehrere `--config` angegeben werden.
uv run python -m transcript_miner \
  --config config/config_investing.yaml \
  --config config/config_ai_knowledge.yaml
```

Quelle des CLI-Entwurfs: [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:241).

#### Beispiel 3 (**proposed**): Union (Channels/Keywords vereinigen, ein Run)

```bash
# PROPOSED: union-Modus (Flags existieren im aktuellen Code nicht)
uv run python -m transcript_miner \
  --config config/config_investing.yaml \
  --config config/config_ai_knowledge.yaml \
  --config-mode union
```

Aktueller Ist-Zustand: Es gibt **kein** `--config-mode` Flag in [`transcript_miner.main.parse_arguments()`](../src/transcript_miner/main.py:334).

Erwartung (normativ):

- Es gibt **einen** Miner-Run.
- `youtube.channels`/`youtube.keywords` werden als stable union zusammengeführt (Regeln: [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:169)).
- `output.*` und `logging.*` müssen über alle Configs nach Resolution **identisch** sein, sonst **Fehler** (Regeln: [`docs/adr/0006-multi-config-composition.md`](adr/0006-multi-config-composition.md:94)).

## Schema-Details

### `api`

Definiert externe API-Zugänge.

- `api.youtube_api_key` *(string | null)*: YouTube Data API v3 Key. Kann `${VAR}`-Substitution nutzen (siehe [`ApiConfig.youtube_api_key`](../src/common/config_models.py:159)).
- `api.youtube_cookies` *(string | null)*: Pfad zur cookies.txt. **HINWEIS: Derzeit aufgrund von YouTube-Änderungen oft nicht funktionsfähig.**
  - Relative Pfade werden beim Laden gegen das Config-Directory aufgelöst (Quelle: [`resolve_paths()`](../src/common/path_utils.py:13)).
- `api.openrouter_api_key` *(string | null)*: OpenRouter API Key für LLM-Analyse. Kann `${VAR}`-Substitution nutzen (siehe [`ApiConfig.openrouter_api_key`](../src/common/config_models.py:151)).
- `api.openrouter_app_title` *(string | null)*: Optionaler App-Name für OpenRouter-Attribution (`X-Title` Header; Quelle: https://openrouter.ai/docs/quickstart). Wenn nicht gesetzt, wird `"TranscriptMiner"` gesendet (Quelle: [`run_llm_analysis()`](../src/transcript_ai_analysis/llm_runner.py) und [`generate_reports()`](../src/transcript_ai_analysis/llm_report_generator.py)).
- `api.openrouter_http_referer` *(string | null)*: Optionaler Site/Repo-URL für OpenRouter-Attribution (`HTTP-Referer` Header; Quelle: https://openrouter.ai/docs/quickstart).

Hinweis (LLM-Key):

- Der LLM-Runner nutzt **OpenRouter** als Standard (erwartet Env `OPENROUTER_API_KEY` oder `api.openrouter_api_key`).
- Es existieren Legacy-Fallbacks (z.B. `openrouter_key` in `.env`, sowie `OPENAI_API_KEY`/`api.openai_api_key`) zur Abwärtskompatibilität (siehe [`run_llm_analysis()`](../src/transcript_ai_analysis/llm_runner.py:262)).

### `youtube`

YouTube-Kanäle und Filter-/Download-Parameter (siehe [`YoutubeConfig`](../src/common/config_models.py:11)).

- `youtube.channels` *(list[string])*: Kanal-Handles (z.B. `@handle`) oder URLs.
- `youtube.num_videos` *(int, default 10, min 1)*: Anzahl neuester Videos pro Kanal.
- `youtube.lookback_days` *(int, optional, min 1)*: Zeitfenster in Tagen; wenn gesetzt, werden nur Videos der letzten N Tage beruecksichtigt.
- `youtube.max_videos_per_channel` *(int, optional, min 1)*: Limit pro Kanal innerhalb `lookback_days` (Fallback: `num_videos`).
- `youtube.keywords` *(list[string])*: Suchbegriffe für Titel/Transkript-Filterung.
- `youtube.preferred_languages` *(list[string], default `["en", "de"]`)*: Bevorzugte Transkriptsprachen.

#### IP-Block Prevention (Rate Limiting & Backoff)

- `youtube.min_delay_s` *(float, default 2.0)*: Minimale Pause vor jedem Transcript-Download.
- `youtube.jitter_s` *(float, default 1.0)*: Zufälliger Jitter für die Pause.
- `youtube.max_retries` *(int, default 5)*: Maximale Anzahl an Retries bei 429 Fehlern.
- `youtube.backoff_base_s` *(float, default 2.0)*: Basis für exponentiellen Backoff.
- `youtube.backoff_cap_s` *(float, default 120.0)*: Maximum für exponentiellen Backoff.
- `youtube.cooldown_on_block_s` *(int, default 900)*: Cooldown-Zeit nach einem IP-Block (Sekunden).

Hinweis (cookie-frei):
- Für private/WSL/VPN-Umgebungen ohne Cookies gibt es ein konservatives Profil: [`config/config_wsl_optimized.yaml`](../config/config_wsl_optimized.yaml:1).

#### Proxy-Konfiguration (`youtube.proxy`)

- `youtube.proxy.mode` *("none"|"generic"|"webshare", default "none")*: Proxy-Modus.
- `youtube.proxy.http_url` *(string, optional)*: HTTP Proxy URL (für `generic`).
- `youtube.proxy.https_url` *(string, optional)*: HTTPS Proxy URL (für `generic`).
- `youtube.proxy.webshare_username` *(string, optional)*: Webshare.io Username.
- `youtube.proxy.webshare_password" *(string, optional)*: Webshare.io Password.
- `youtube.proxy.filter_ip_locations` *(list[string], optional)*: Liste von Länder-Codes (z.B. `["us", "de"]`), um den IP-Pool einzuschränken.
- Hinweis: Proxy-Credentials sollten via `${VAR}` aus der Env geladen werden (Secrets-only).

**Globaler Proxy-Default (alle Configs):**
- `config/config_global.yaml` setzt `youtube.proxy.*` per Env-Substitution (z. B. `${YOUTUBE_PROXY_MODE}`).
- CLI lädt `.env` (secrets) und `.config.env` (non-secrets) automatisch.
- Wenn `YOUTUBE_PROXY_MODE` gesetzt ist, überschreibt es proxy-Einstellungen in Topic-Configs.

**Besonderheit Webshare & Sticky Sessions:**
Das Tool implementiert eine automatische **Sticky Session** Logik für Webshare-Proxies. Wenn der Username `-rotate` enthält, wird dieser intern pro Video-ID durch eine Session-ID ersetzt. Dies stellt sicher, dass die IP-Adresse während des gesamten Abrufs eines Videos (von der Video-Seite bis zum Transcript-Download) stabil bleibt, was die Erfolgsrate bei YouTube massiv erhöht.

#### Semantik: `youtube.preferred_languages` (Ist-Verhalten)

Die Liste wird an den Transcript-Downloader übergeben (Callsite: [`process_single_video()`](../src/transcript_miner/video_processor.py:185) → [`download_transcript()`](../src/transcript_miner/transcript_downloader.py:26)).

Auswahlreihenfolge in [`download_transcript()`](../src/transcript_miner/transcript_downloader.py:26):

1. Manuell erstelltes Transkript in einer der bevorzugten Sprachen (siehe [`download_transcript()`](../src/transcript_miner/transcript_downloader.py:50)).
2. Generiertes Transkript in einer der bevorzugten Sprachen (siehe [`download_transcript()`](../src/transcript_miner/transcript_downloader.py:61)).
3. Fallback: erstes verfügbares Transkript aus `transcript_list` (Iteration) (siehe [`download_transcript()`](../src/transcript_miner/transcript_downloader.py:72)).

Default-Wert im Schema: `[
"en", "de"
]` (siehe [`YoutubeConfig.preferred_languages`](../src/common/config_models.py:31)).

#### Semantik: `youtube.lookback_days` + `youtube.max_videos_per_channel` (Ist-Verhalten)

- Wenn `youtube.lookback_days` gesetzt ist, nutzt der Miner ein Zeitfenster und ueberschreibt die Video-Auswahllogik (Quelle: [`process_channel()`](../src/transcript_miner/main.py)).
- Das per-Channel-Limit ist `youtube.max_videos_per_channel`; falls nicht gesetzt, wird `youtube.num_videos` als Fallback verwendet (Quelle: [`process_channel()`](../src/transcript_miner/main.py)).
- Die Filterung nach Zeitfenster erfolgt anhand von `published_at` beim Video-Fetching (Quelle: [`get_channel_videos()`](../src/transcript_miner/youtube_client.py)).

#### Healing / Reuse (Ist-Verhalten)

- Transcript-Downloads werden uebersprungen, wenn eine **gueltige Summary** fuer das Video existiert (PRD-Policy), sofern `youtube.force_redownload_transcripts=false` ist (Quelle: [`process_single_video()`](../src/transcript_miner/video_processor.py)).
- Defekte/inkonsistente Summary-Dateien werden als fehlend behandelt und zur Neuverarbeitung markiert (Quelle: [`process_single_video()`](../src/transcript_miner/video_processor.py)).
- Korrupte/leerbare Transkriptdateien werden als ungesund erkannt und neu geladen (Quelle: [`is_video_already_processed()`](../src/transcript_miner/video_processor.py)).

#### Semantik: `youtube.keywords` (Ist-Verhalten)

Die Keywords werden im Video-Processing gegen den **Transkripttext** gematcht (siehe Keyword-Callsite in [`process_single_video()`](../src/transcript_miner/video_processor.py:185)). Das Matching selbst passiert in [`search_keywords()`](../src/transcript_miner/transcript_downloader.py:103).

Matching-Regeln in [`search_keywords()`](../src/transcript_miner/transcript_downloader.py:103):

- **case-insensitive** (`re.IGNORECASE`) (siehe [`search_keywords()`](../src/transcript_miner/transcript_downloader.py:127)).
- **whole-word** Matching über Wortgrenzen `\\b` (Regex `\\b{keyword}\\b`) (siehe Pattern-Build in [`search_keywords()`](../src/transcript_miner/transcript_downloader.py:126)).
- Zusätzlich werden alle Zeilen gesammelt, die den Treffer enthalten (Split nach `\\n`) (siehe [`search_keywords()`](../src/transcript_miner/transcript_downloader.py:131)).

Hinweis: Wenn `keywords` leer ist, wird nichts gesucht und es werden `([], [])` zurückgegeben (siehe Guard in [`search_keywords()`](../src/transcript_miner/transcript_downloader.py:118)).

Kompatibilitätshinweis:

- Das Schema unterstützt `youtube.num_videos`, `youtube.lookback_days`, `youtube.max_videos_per_channel` und `youtube.keywords` direkt in `youtube` (siehe [`YoutubeConfig`](../src/common/config_models.py:11)).
- Ältere `youtube.filter.*` Felder waren nicht schema-konform und wurden in den Beispiel-Konfigs unter [`config/`](../config:1) migriert.

### `output`

Steuert, wo Dateien abgelegt werden (siehe [`OutputConfig`](../src/common/config_models.py:34)).

- `output.global` *(string | path | null)*: Globales Output-Root (empfohlen).
- `output.global_root` *(string | path | null)*: Legacy-Alias für `output.global`.
- `output.topic` *(string | null)*: Topic/Namespace für Reports/History/Index (erforderlich bei `output.global`).
- `output.path` *(string | path, default `./output`)*: Basispfad (legacy). In der Beschreibung als „deprecated“ markiert.
- `output.root_path` *(string | path | null)*: Legacy-Root für per-Profile Layouts.
- `output.use_channel_subfolder` *(bool, default `false`)*: Legacy: wenn `true`, wird ein Unterordner pro Channel erzeugt.
- `output.metadata` *(bool, default `true`)*: Wenn `true`, wird eine `_meta.json` pro Transkript geschrieben.
- `output.daily_report` *(bool, default `false`)*: Wenn `true`, werden Reports in tagesbasierten Ordnern (YYYY-MM-DD) abgelegt (überschreibend).
- `output.skip_on_no_new_data` *(bool, default `false`)*: Wenn `true`, wird der Run übersprungen, wenn sich der Input-Fingerprint nicht geändert hat.
- `output.write_timeout_report` *(bool, default `false`)*: Wenn `true`, wird ein Timeout-Report unter `output/reports/<topic>/timeout_budget.md` (global) bzw. `3_reports/timeout_budget.md` (Legacy) geschrieben (siehe [`OutputConfig.get_timeout_report_path()`](../src/common/config_models.py:279)).
- `output.retention_days` *(int | null, default `30`, min `0`)*: Retention/Cleanup für Dateien unter `output/data/transcripts/by_video_id/` (global) bzw. `1_transcripts/` (Legacy).
  - Wenn gesetzt: löscht Dateien, deren mtime älter als `N` Tage ist (siehe Policy in [`cleanup_old_outputs()`](../src/transcript_miner/video_processor.py:177)).
  - Wenn `null`: Cleanup deaktiviert.

#### Policy (Empfehlung)

- **Empfohlen (global dedup):** `output.global` + `output.topic`
  - Daten liegen zentral unter `output/data/`, Reports/History unter `output/reports/<topic>` bzw. `output/history/<topic>`.
- **Legacy (per-profile):** `output.root_path` + `output.use_channel_subfolder: true`
  - Ergebnis: `{root_path}/{clean_handle}/1_transcripts/`, `2_summaries/`, `3_reports/`.
- **Legacy/Kompatibilität:** `output.path`
  - Wird als Fallback genutzt, wenn `root_path` nicht gesetzt ist.

#### Pfad-Auflösung & Ablage-Policy (wichtig)

**Normative Doku-Regel:** Relative Pfade in `output.*` sind **relativ zur Config-Datei**.

Evidenz (Ist-Verhalten): `base_dir = config_path.parent.resolve()` in [`common.config.load_config()`](../src/common/config.py:23) und Auflösung in [`common.path_utils.resolve_paths()`](../src/common/path_utils.py:12) → [`common.path_utils._resolve_path()`](../src/common/path_utils.py:90).

Konsequenz:

- Wenn eine Config unter [`config/`](../config:1) liegt, dann schreibt `output.root_path: ../output/stocks` unter `<repo>/output/stocks/...`.

Hinweis (gleiches Prinzip): `logging.file` und `logging.error_log_file` werden beim Laden ebenfalls relativ zur Config-Datei aufgelöst (siehe Path-Resolution in [`common.path_utils.resolve_paths()`](../src/common/path_utils.py:12)). Wenn Configs unter [`config/`](../config:1) liegen und Logs unter `<repo>/logs/...` landen sollen, nutze in YAML `../logs/...`.

**Policy:** [`config/`](../config:1) ist ein reiner Config-Ordner (keine Outputs). Wenn Outputs unter `<repo>/output/...` landen sollen, nutze in YAML explizit `../output/<namespace>` (oder einen absoluten Pfad), z.B.:

```yaml
output:
  global: ../output
  topic: stocks
```

#### Präzedenz / FAQ

- Wenn `output.global` gesetzt ist, wird `output.root_path`/`output.path` für die Ablage ignoriert; `output.topic` ist verpflichtend.
- Im Legacy-Layout überschreibt `output.root_path` den `output.path`‑Fallback; `output.use_channel_subfolder` steuert die per‑Channel‑Unterordner.
- Für Multi‑Channel‑Configs ist entweder `output.global`+`output.topic` **oder** `output.root_path` + `output.use_channel_subfolder: true` verpflichtend (Validierung in [`transcript_miner.main.main()`](../src/transcript_miner/main.py:226)).

## Known limitations / Ist-Verhalten: „kein Transkript“ & Progress-/Skip-State

Aktuelles Verhalten (bewusst als Ist-Zustand formuliert):

- Wenn ein Video **kein Transkript** hat (Status `no_transcript` / `transcripts_disabled`), wird dieser Skip-State **persistiert** in `output/data/transcripts/skipped.json` (global) bzw. `1_transcripts/skipped.json` (Legacy), damit der Status nicht durch Filesystem↔progress Sync wieder „verloren“ geht. Evidenz: Persistenz in [`process_single_video()`](../src/transcript_miner/video_processor.py:514).
- `ingest_index.jsonl` wird zu Beginn eines Channel-Runs mit dem Dateisystem synchronisiert (siehe [`process_channel()`](../src/transcript_miner/main.py:57) → [`sync_progress_with_filesystem()`](../src/transcript_miner/video_processor.py:332)). Dabei werden IDs ohne passende `*_VIDEOID.txt` Datei entfernt.
- Ordering/Determinismus: die Reihenfolge der IDs in `progress.json` ist **nicht semantisch**; beim Sync wird deterministisch nach `video_id` sortiert (siehe Sortierung in [`sync_progress_with_filesystem()`](../src/transcript_miner/video_processor.py:388)).

#### Pfad-Auflösung (`output.get_path`)

Die effektive Ausgabebasis wird in [`OutputConfig.get_path()`](../src/common/config_models.py:50) bestimmt:

- **Neue Logik**: wenn `root_path` gesetzt und `use_channel_subfolder: true` and `channel_handle` vorhanden:
  - Unterordnername = normalisiertes Handle (`@` weg, `/` und `\\` → `_`) (siehe [`OutputConfig.get_path()`](../src/common/config_models.py:63)).
  - Ergebnis: `{root_path}/{clean_handle}`.
- **Fallback / Legacy**: sonst wird `root_path` oder `path` als Zielpfad verwendet (siehe [`OutputConfig.get_path()`](../src/common/config_models.py:78)).

### `logging`

Logging-Konfiguration (siehe [`LoggingConfig`](../src/common/config_models.py:88)).

- `logging.level` *("DEBUG"|"INFO"|"WARNING"|"ERROR"|"CRITICAL", default "INFO")*
- `logging.file` *(string, default `logs/miner.log`)*: Haupt-Logfile.
- `logging.error_log_file" *(string, default `logs/error.log`)*: Error-Logfile (WARNING+).
- `logging.llm_request_json` *(bool, default false)*: Wenn true, schreibt LLM-Request-Metadaten nach `logs/llm_requests.json` (Quelle: [`LoggingConfig`](../src/common/config_models.py:212), Logger in [`common.utils`](../src/common/utils.py:1)). Alternativ via Env `ENABLE_LLM_JSON_LOG=true` aktivierbar (Quelle: [`common.utils`](../src/common/utils.py:1)).
- Rotation (derzeit als Felder im Schema vorhanden):
  - `logging.rotation_enabled` *(bool, default false)*
  - `logging.rotation_when` *(string, default "D")*
  - `logging.rotation_interval` *(int, default 1)*
  - `logging.rotation_backup_count` *(int, default 7)*

### `analysis.llm` — „LLM Instructions“ pro Config/Topic (Ist-Zustand + Semantik)

Diese Sektion dokumentiert, wie „LLM Instructions“ **heute** im bestehenden Config-Schema abgebildet sind.

Quelle des Schemas: [`common.config_models.LlmAnalysisConfig`](../src/common/config_models.py:186)

#### Zweck

- Die YAML-Config repräsentiert in der Praxis ein **Topic/Intent** (z.B. „stocks“, „us-politics“).
- Die topic-spezifischen Instructions sind die beiden Prompt-Felder:
  - `analysis.llm.system_prompt`
  - `analysis.llm.user_prompt_template`

Diese Semantik ist konsistent mit dem Scaling-ADR, das „Instructions pro Config/Topic“ als Design-Ziel beschreibt: [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](adr/0008-llm-scaling-jobs-agents-rag-instructions.md:1).

#### Felder (Ist-Schema)

- `analysis.llm.enabled` *(bool, default `false`)*
  - Wenn `true`, wird LLM-Analyse ausgeführt (Guard im Runner; Doku: [`README.md`](../README.md:450)).

- `analysis.llm.mode` *("aggregate"|"per_video", default "aggregate")*
  - Steuert den Ausführungsmodus: `aggregate` = ein Report über alle selektierten Transkripte; `per_video` = ein Call pro Transcript.
  - Fallback/Legacy: Wenn `mode=aggregate`, kann der Runner weiterhin per-video aktivieren, wenn das Task‑Marker‑String im Prompt vorhanden ist (Quelle: [`_wants_stocks_per_video_extract()`](../src/transcript_ai_analysis/llm_runner.py:39)).
  - Exit-Code (Ist-Verhalten): Im `per_video` Modus wird `exit=0` zurückgegeben, sobald **mindestens ein** per-video Summary geschrieben wurde; fehlerhafte Einzelsummaries werden als `llm_partial_success` im Audit erfasst (Quelle: [`run_llm_analysis()`](../src/transcript_ai_analysis/llm_runner.py:281)).

- `analysis.llm.model` *(string | null)*
  - Muss gesetzt sein, wenn `enabled=true` (Validierung: [`LlmAnalysisConfig._validate_required_fields_when_enabled()`](../src/common/config_models.py:228)).

- `analysis.llm.system_prompt` *(string | null)*
  - Muss gesetzt sein, wenn `enabled=true` (Validierung: [`LlmAnalysisConfig._validate_required_fields_when_enabled()`](../src/common/config_models.py:228)).

- `analysis.llm.user_prompt_template` *(string | null)*
  - Muss gesetzt sein, wenn `enabled=true` (Validierung: [`LlmAnalysisConfig._validate_required_fields_when_enabled()`](../src/common/config_models.py:228)).
  - Unterstützte Platzhalter (Ist-Zustand, schema-docstring): `{transcripts}`, `{transcript_count}` (siehe Feldbeschreibung in [`LlmAnalysisConfig.user_prompt_template`](../src/common/config_models.py:198)).

Weitere Felder zur Größenbegrenzung (Ist-Schema): `max_transcripts`, `max_chars_per_transcript`, `max_total_chars`, `max_input_tokens`, `max_output_tokens` (siehe [`common.config_models.LlmAnalysisConfig`](../src/common/config_models.py:186)).
  - `max_input_tokens`: hartes Token-Limit für `system_prompt` + `user_prompt` (bei Überschreitung wird der Run abgebrochen bzw. per-video Transcript übersprungen).
  - `max_output_tokens`: hartes Token-Limit für die LLM-Antwort (bei Überschreitung wird der Run als Fehler markiert bzw. per-video Output übersprungen).
  - `per_video_concurrency`: Max. parallele LLM Calls im `per_video` Modus (Default `1`).
  - `per_video_min_delay_s`: Globales Mindest-Delay zwischen per-video Calls (Sekunden).
  - `per_video_jitter_s`: Maximaler Jitter (Sekunden) für das per-video Rate-Limit.
  - `reasoning_effort`: Reasoning‑Stufe für kompatible Provider (`low|medium|high`, Default `high`).
  - `stream_summaries`: Wenn `true`, werden per-video Summaries **parallel** zum Transcript-Download erzeugt (Streaming/Queue).
  - `stream_worker_concurrency`: Anzahl paralleler Streaming-Worker (Default `1`).
  - `stream_queue_size`: Queue-Größe für Streaming-Jobs (Backpressure, Default `100`).

#### Normative Semantik: wie man Instructions pro Topic strukturiert

Diese Regeln sind **Doku-/Policy-Semantik** (kein neues Schema):

1) **`system_prompt` = stabile Guardrails**
   - Enthält wiederverwendbare Regeln, die unabhängig vom Topic gelten (Output-Format, Evidence-Pflicht, Verbote wie „keine erfundenen Fakten“).
   - Referenz für strikte Output-/Evidence-Anforderungen: [`docs/analysis/llm_prompt_spec_strict_json_evidence.md`](analysis/llm_prompt_spec_strict_json_evidence.md:1).

2) **`user_prompt_template` = topic-spezifischer Auftrag**
   - Enthält das eigentliche Analyseziel für das Topic (z.B. „Stock-Coverage“, „US-Politik Narrative“).
   - Nutzt `{transcripts}` als den vom Runner eingebetteten Textkorpus und `{transcript_count}` als Meta-Info.

3) **Ein Topic pro Config (empfohlen)**
   - Wenn mehrere Topics gebraucht werden, nutze mehrere YAMLs und (heute) Multi-Run (jede Config separat) — siehe Multi-Run-Semantik in [`docs/config.md`](config.md:60).

4) **Auditierbarkeit (Ist-Outputs)**
   - Der LLM-Runner schreibt die effektiven Prompts als Artefakte (`system_prompt.txt`, `user_prompt.txt`) zusammen mit `report.json` und `audit.jsonl` im History-Bundle (global): `output/history/<topic>/<YYYY-MM-DD>/<bundle>/` (Writer: [`run_llm_analysis()`](../src/transcript_ai_analysis/llm_runner.py) und Pfad via [`OutputConfig.get_run_reports_path()`](../src/common/config_models.py)).  
     Legacy bleibt unter `{PROFILE_ROOT}/3_reports/`.

### `report` (Neu in v0.3.3)

Konfiguration für die finale Report-Generierung via Aggregation (automatisch, wenn gesetzt) oder manuell via `tools/generate_llm_report.py`.

- `report.llm.model` *(string)*: Das zu verwendende Modell (z.B. `openai/gpt-5.2`).
- `report.llm.system_prompt` *(dict)*: System-Prompts pro Sprache.
  - `de`: Deutscher Prompt.
  - `en`: Englischer Prompt.

Beispiel:
```yaml
report:
  llm:
    model: openai/gpt-5.2
    system_prompt:
      de: "Du bist ein Analyst für Investment/Stocks..."
      en: "You are an investment/stock analyst..."
```

#### Proposed (nicht implementiert): Multi-Job Instructions

Wenn die Pipeline später als Multi-Job (Map/Reduce) umgesetzt wird, ist eine datengetriebene „Jobs“-Definition sinnvoll.

- **proposed:** eine Struktur wie `analysis.llm.jobs[]` mit `depends_on` (Konzept in [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](adr/0008-llm-scaling-jobs-agents-rag-instructions.md:1)).

Evidence Gate: Dieses Feld existiert **nicht** im Ist-Schema von [`common.config_models.LlmAnalysisConfig`](../src/common/config_models.py:186) und ist daher ausdrücklich als **proposed** markiert.

## Hinweis: entfernte Legacy-Felder

Das Feld `llm_correction` (sowie der Legacy-„Transcript Corrector“) wurde entfernt, weil das Zielbild „fetch → analysis“ ist (siehe [`TODO.md`](../../TODO.md:17)).
