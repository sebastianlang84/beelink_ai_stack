# Changelog

## [0.3.4] – 2025-12-30

### Changed
- **Flat-First Report Structure:** Berichte landen nun standardmäßig direkt in `3_reports/` anstatt in Zeitstempel-basierten Unterordnern. Dies verbessert die Übersichtlichkeit massiv.
- **Automatisches Archiv-System:** Bei jedem neuen Run werden existierende Berichte automatisch nach `3_reports/archive/run_YYYYMMDD_HHMMSSZ/` verschoben, um Platz für die neuen Ergebnisse zu machen.
- **Verbesserte Navigation:** Der aktuellste Report ist nun immer ohne Klick-Umwege im Hauptverzeichnis des Profils zu finden.

## [0.3.3] – 2025-12-30

### Added
- **Multilingual Reports:** Automatische Generierung von Berichten in Deutsch (`report_de.md`) und Englisch (`report_en.md`) via `tools/generate_llm_report.py`.
- **Report Templates:** Unterstützung für Markdown-Templates unter `templates/` (z.B. `report_stocks_de.md`), um die Berichtsstruktur flexibel zu gestalten.
- **Config-gesteuerte Reports:** Neue Sektion `report:` in der YAML-Konfiguration zur Definition von Modellen und System-Prompts pro Topic.
- **Token-Limit-Checks:** Das Report-Tool prüft nun das Context-Window des gewählten Modells (z.B. 400k für GPT-5.2) und warnt bei Überschreitung.
- **Automatisierte Config-Discovery:** Das Report-Tool findet die passende Konfiguration automatisch anhand des Output-Pfades, falls keine `--config` angegeben wurde.

## [0.3.2] – 2025-12-28

### Added
- **Residential Proxy Support:** Erfolgreiche Umstellung auf Residential Proxies (Webshare) zur Umgehung von YouTube IP-Blocks.

### Fixed
- **Proxy-Authentifizierung:** Fix in [`src/transcript_miner/transcript_downloader.py`](src/transcript_miner/transcript_downloader.py), um zu verhindern, dass die automatische Sticky-Session-Logik die Authentifizierung bei Residential-Plänen (die strikt `-rotate` erfordern) bricht.

## [0.3.1] – 2025-12-28

### Added
- **Erweiterter Proxy-Support:** Unterstützung für Länder-Filter (`filter_ip_locations`) in der Proxy-Konfiguration (siehe [`src/common/config_models.py`](src/common/config_models.py)).
- **Sticky Sessions für Webshare:** Automatische Bindung einer Proxy-IP an eine Video-ID, um Abbrüche während des Transcript-Downloads zu verhindern (siehe [`src/transcript_miner/transcript_downloader.py`](src/transcript_miner/transcript_downloader.py)).
- **WSL-Optimierung:** Neue Beispiel-Konfiguration [`config/config_wsl_optimized.yaml`](config/config_wsl_optimized.yaml) mit konservativen Delays und Proxy-Vorlagen für private Umgebungen.
- **Diagnose-Tools:** Neue Skripte zur Fehlersuche bei IP-Blocks unter `tools/` (u.a. `repro_ip_block.py`, `final_proxy_test.py`).

### Fixed
- **Webshare Proxy-Rotation:** Korrektur der Parameter-Übergabe an `WebshareProxyConfig` (`proxy_username` statt `username`).
- **Connection-Handling:** Monkeypatch für `WebshareProxyConfig`, um `Connection: close` zu verhindern, was die IP-Stabilität innerhalb einer Session verbessert.

## [0.3.0] – 2025-12-28 (Initial v2 Release)

### Added

- **Log-Rotation und automatischer Cleanup:** Unterstützung für `TimedRotatingFileHandler` und eine zusätzliche Bereinigungslogik für verwaiste Log-Dateien (siehe [`src/transcript_miner/logging_setup.py`](src/transcript_miner/logging_setup.py:86) und [`cleanup_old_logs()`](src/transcript_miner/logging_setup.py:155)). Konfigurierbar über `logging.rotation_enabled` etc. (siehe [`LoggingConfig`](src/common/config_models.py:157)).
- **Multi-Config CLI (Default: Multi-Run):** repeatable `--config` Flags, kanonische Config-Order und deterministische `config_set_id`/Namespace-Run-Root (siehe [`transcript_miner.main.parse_arguments()`](src/transcript_miner/main.py:334), [`transcript_miner.main._canonical_config_paths()`](src/transcript_miner/main.py:29), [`transcript_miner.main._compute_config_set_id()`](src/transcript_miner/main.py:43), [`transcript_miner.main._run_with_parsed_args()`](src/transcript_miner/main.py:422)).
- **Fail-fast Isolation für Multi-Run:** Kollisionen in Output-Roots sowie `logging.file`/`logging.error_log_file` werden vor dem Run erkannt (siehe [`transcript_miner.main._validate_multi_run_isolation()`](src/transcript_miner/main.py:81)).

- **Stock-Exports (Batch 2 → Artefakte):**
  - `by_symbol.json` / `by_channel.json` / `global.json` werden vom Aggregations-Runner geschrieben (siehe [`run_aggregation()`](src/transcript_ai_analysis/aggregation_runner.py:152)).

- **LLM Output Validation (Strict JSON + Evidence-Policy):** offline-validierbare Checks für `output.content` (siehe [`transcript_ai_analysis.llm_output_validator.validate_llm_output_content()`](src/transcript_ai_analysis/llm_output_validator.py:500)).

- **LLM derived report + metadata + artefact validator:** aus `report.json.output.content` wird deterministisch ein menschenlesbares Artefakt (`report.md` oder `report.txt`) plus `metadata.json` erzeugt, und ein Offline-Validator prüft Bundle-Konsistenz (Hashes, byte-identischer Derived Report; Rolling-Window-Guardrails nur falls in `metadata.json` repräsentiert) (siehe [`run_llm_analysis()`](src/transcript_ai_analysis/llm_runner.py:236) → [`_write_derived_report_and_metadata()`](src/transcript_ai_analysis/llm_runner.py:73) und [`validate_llm_report_artefacts()`](src/transcript_ai_analysis/llm_output_validator.py:60); Tests: [`tests/test_llm_output_validation_policy.py`](tests/test_llm_output_validation_policy.py:1)).

## 2025-12-28 – Testlauf & Robustheit

- **Testlauf-Ergebnisse:**
  - Smoke-Tests erfolgreich (offline-robust).
  - Integrationstests identifizierten `IpBlocked` Probleme in Cloud-Umgebungen (YouTube-Blocking von Datacenter-IPs).
- **Backlog:** Robustheit gegen IP-Blocks als Priorität in [`TODO.md`](../TODO.md:77) aufgenommen.

### Versioning (SemVer Policy)

- **Status:** Das Projekt ist aktuell im **0.x** Bereich (Pre-1.0). Solange 0.x gilt, können sich CLI/Config/Outputs noch ändern; wir behandeln solche Änderungen aber weiterhin als „breaking“ und dokumentieren sie explizit.
- **Bump-Regeln (SemVer-orientiert):**
  - **Patch** (`0.x.Y`): Bugfixes / Doku / interne Refactors ohne Interface-Änderung.
  - **Minor** (`0.(x+1).0`): neue Features, die rückwärtskompatibel sind (CLI-Flags/Config-Felder additiv, Output-Felder additiv).
  - **Major** (`1.0.0`): sobald CLI, Config-Schema und Output-Layouts als stabil betrachtet werden (mindestens: `python -m transcript_miner` Interface + `docs/config.md` Schema + Output-Artefakte unter `output/` inklusive `analysis/*`).
- **Breaking Change (Definition, auch in 0.x):**
  - CLI: Flag entfernt/umbenannt oder Semantik inkompatibel geändert.
  - Config: Feld entfernt/umbenannt oder Semantik inkompatibel geändert (Priorität CLI > Config > Env > Defaults bleibt).
  - Outputs: Dateien/Ordner umbenannt/verschoben oder JSON-Schemata inkompatibel geändert (Feld entfernt/umbenannt oder Bedeutung geändert).

### Changed

- **Ordnerstruktur-Migration (PRD Sektion 8.3):**
  - Roh-Transkripte verschoben nach `1_transcripts/` (vorher `transcripts/`).
  - LLM-Reports/Summaries verschoben nach `2_summaries/` (vorher `analysis/llm/`).
  - Batch 2 Artefakte verschoben nach `3_reports/` (vorher `analysis/batch2/`).
  - Ingest-Index verschoben nach `3_reports/index/` (vorher `analysis/batch1/`).
  - `OutputConfig` bietet nun zentrale Methoden für diese Pfade (`get_transcripts_path()`, `get_summaries_path()`, etc.).
  - Abwärtskompatibilität für den Index-Scanner implementiert (findet weiterhin alte `transcripts/` Ordner).

- LLM-Analyse: OpenAI Python SDK v1+ kompatibel gemacht (Client API statt `openai.ChatCompletion.create`), inkl. Retry-Exceptions ohne `openai.error.*` (siehe [`transcript_ai_analysis.llm_runner.run_llm_analysis()`](src/transcript_ai_analysis/llm_runner.py:145) und [`common.utils.call_openai_with_retry()`](src/common/utils.py:31)).

### Release

### Dev

- Dev-Dependency: `openai` Python SDK ergänzt (siehe [`pyproject.toml`](pyproject.toml:21)).

### Release-Checkliste (Repo-spezifisch)

- [ ] **Changelog finalisieren:** relevante Änderungen aus „Unreleased“ konsolidieren und den Release als datierten Abschnitt ablegen (diese Datei: [`CHANGELOG.md`](CHANGELOG.md:1)).
- [ ] **Version bump:** `version` in [`pyproject.toml`](pyproject.toml:3) aktualisieren (Packaging-Version).
- [ ] **Offline-Smoke-Checks ausführen (UV-first):** die Befehle aus „Smoke-Checks (offline)“ in [`README.md`](README.md:46) laufen lassen.
- [ ] **Tests laufen lassen:** `uv run pytest -q` (siehe ebenfalls „Smoke-Checks (offline)“ in [`README.md`](README.md:46)).
- [ ] **Secrets/Logs prüfen:** sicherstellen, dass keine Secrets committed werden (Regeln + Gitleaks-Workflow sind in [`README.md`](README.md:75) dokumentiert).

- Robustness/CLI: `--help` ist side-effect-arm (Argument-Parsing vor `.env`/Config/Runtime), plus zusätzlicher Smoke-Test (siehe [`tests/test_smoke.py`](tests/test_smoke.py:10)).
- Config: Output-Pfad-Policy (`output.root_path`/`use_channel_subfolder` vs Legacy `output.path`) dokumentiert und `root_path` wird beim Config-Load als Pfad behandelt (siehe [`common.path_utils.resolve_paths()`](src/common/path_utils.py:12)).
- Config: `${VAR}`-Substitution zentralisiert für Pfade und `api.youtube_api_key` (siehe [`common.path_utils.substitute_env_vars()`](src/common/path_utils.py:71) und [`ApiConfig.resolve_api_key_env_vars()`](src/common/config_models.py:162)).
- Config: nicht aufgelöste `${VAR}`-Platzhalter in `api.youtube_api_key` werden als "nicht gesetzt" behandelt (→ Env/CLI-Fallback greift) (siehe [`ApiConfig.resolve_api_key_env_vars()`](src/common/config_models.py:160)).
- Robustness: Progress-Dedup checkt Dateinamen konsistent (Filesystem-Check nutzt jetzt `*_{video_id}.txt`) (siehe [`is_video_already_processed()`](src/transcript_miner/video_processor.py:567) und Regression-Test [`tests/test_progress_handling.py`](tests/test_progress_handling.py:100)).
- Packaging: interne Imports korrigiert (`src.common.*` → `common.*`) für installierbares Paket-Layout (siehe [`src/transcript_miner/video_processor.py`](src/transcript_miner/video_processor.py:1) und [`src/transcript_miner/logging_setup.py`](src/transcript_miner/logging_setup.py:1)).
- Robustness: YouTube Data API Requests nutzen Retries/Timeout-Wrapper (siehe [`transcript_miner.youtube_client._execute_with_retries()`](src/transcript_miner/youtube_client.py:48)).
- Analysis (Batch 1): Offline-Runner zum Scannen vorhandener Transcript-Outputs und Schreiben deterministischer Artefakte (`manifest.json`, `transcripts.jsonl`, `audit.jsonl`) (siehe [`transcript_miner.transcript_index.runner.write_analysis_index()`](src/transcript_miner/transcript_index/runner.py:55)).
- Tests: transcript-index Runner-Tests erweitert (Determinismus über Input-Root-Reihenfolge, Fehlerfälle für ungültige Dateinamen) (siehe [`tests/test_analysis_runner.py`](tests/test_analysis_runner.py:1)).
- Docs: Analysis-Backlog klarer abgegrenzt („Batch 1“ als Transcript-Index umgesetzt; Stock-Analysis Schritte weiterhin offen) (siehe [`TODO.md`](../TODO.md:35) und „Analysis (offline) — Batch 1“ in [`README.md`](README.md:259)).
- Docs: „Output Reference“ erweitert (Miner-Artefakte inkl. `_meta.json` Feldliste mit Quellen aus [`_create_metadata()`](src/transcript_miner/video_processor.py:642) und [`TranscriptDownloadResult.to_metadata_fields()`](src/transcript_miner/transcript_models.py:26)).
- Docs: „Secrets / .env“ Troubleshooting ergänzt (Key fehlt/ungültig, Quota/Retry, keine Transkripte) mit evidenzbasierten Verweisen (u.a. [`run_miner()`](src/transcript_miner/main.py:177), `.env`-Loading in [`main()`](src/transcript_miner/main.py:245)).
- Docs: Legacy Corrector/`llm_correction` entfernt (Zielbild „fetch → analysis“).
- Docs: Logs-Doku konsolidiert/ausgebaut und in README verlinkt (siehe [`logs/README.md`](logs/README.md:1)).
- Docs: `progress.json` Sync/Ordering und Skip-State (`skipped.json`) an aktuellen Code angepasst (Sorting deterministisch, Reihenfolge nicht semantisch) (siehe [`sync_progress_with_filesystem()`](src/transcript_miner/video_processor.py:332) und Skip-Persistenz in [`process_single_video()`](src/transcript_miner/video_processor.py:514)).

- Analysis: optionaler LLM-Analyse-Runner (ein Job pro Run) schreibt `analysis/llm/*` Artefakte (Runner: [`transcript_ai_analysis.llm_runner.run_llm_analysis()`](src/transcript_ai_analysis/llm_runner.py:166)).


## 2025-12-23 – Repo cleanup / migration

- Struktur-Migration: Inhalte aus `transcript-miner/` ins Repo-Root verschoben (Poetry/`src/`/`tests/`/`tools/`/`config/`/`data/`/`.github/`).
- Doku-Konsolidierung: Memory-Bank wird entfernt; relevante Inhalte wurden in Root-Dokus übernommen.
- Security: geleakte API-Keys in Logs wurden redacted; `.env`/`logs/` werden ignoriert.

## Historisch (aus ehemaliger Memory-Bank, grob)

- 2025-05-25: Bidirektionaler Progress-Sync (self-healing) und Channel-Subfolder-Feature eingeführt (Details siehe [`README.md`](README.md:1)).
