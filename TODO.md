# TODO / Priorisiertes Backlog

## User Feedback & Kritik (Offen)

- [x] **User-Data Konzepte vollständig auswerten:** `user_data/` (Kritik, Config-Vorschläge, Report-Templates) → konkrete P0/P1 Tasks + Akzeptanzkriterien.

- [x] **P0: Prompt-Härtung & Taxonomie (Stocks/Macro/Crypto)**
  - Ziel: Striktere Extraktion gemäß `user_data/config_vorschlag.md`.
  - Umsetzung:
    - `stocks_covered` nur bei Deep-Dive (min. 2 Evidence items, thesis + risk/catalyst/etc).
    - `macro_insights` mit Tag-Taxonomie (rates, inflation, btc, eth, etc).
    - Evidence-Rollen: thesis, risk, catalyst, numbers_valuation, comparison.
  - DoD: Prompts in `config_investing.yaml` sind aktualisiert; JSON-Validatoren wurden später entfernt.

- [x] **P1: Investor-Grade Report Template**
  - Ziel: Report-Struktur gemäß `user_data/report_template_vorschlag.md`.
  - Umsetzung:
    - Sektionen: Meta, Stocks (Thesis Cards), Macro (Szenarien), Crypto (Narratives), Appendix (Evidence IDs).
    - Strikte Trennung: Fact vs. Claim vs. Interpretation.
  - DoD: `templates/report_investing_de.md` (und en) entsprechen dem neuen Standard.

- [x] **P1: Begriffs-Bereinigung (Creator vs. Channel vs. Topic)**
  - Ziel: Korrekte Terminologie in Reports und Logs gemäß `user_data/kritik...`.
  - Umsetzung: "1 Creator" durch "1 Topic" oder konkrete Channel-Namen ersetzen.
  - DoD: Reports zeigen `unique_youtube_channels` statt nur "Creator".
- [x] **Mangelnde Transparenz/Kommunikation während der Ausführung**
- [x] **Blockierende CLI-Kommandos ohne Feedback**
- [x] **Fehlende Fortschrittsanzeige (Tokens/Zeichen)**
- [x] **Unordnung in der Output-Struktur** (Mischung aus nummerierten Ordnern und Channel-Ordnern)
- [x] **Mangelhafte Qualität des generierten `report.md`** (entspricht nun dem PRD-Standard, bilingual, template-basiert)

### Kritik-Punkte (aus ChatGPT-5.2 Review)
- [x] **P0: LLM-JSON-Logging abschaltbar machen** (Default: off, via Env `ENABLE_LLM_JSON_LOG` oder Config)
- [x] **P0: Retry-Policy härten** (Cap + Jitter + `Retry-After` Support)
- [x] **P0: Per-Video-Modus via Config-Flag** (statt Magic-String im Prompt)
- [x] **P0: Retention `null disables` sauber behandeln** (in `cleanup_transcripts`)
- [x] **P1: Token-Budget (input/output) als harte Limits**
- [x] **P1: Aggregation: Dedupe-Metriken + Creator-Felder sauber trennen**
- [x] **P1: `resolve_paths` vervollständigen** (alle Pfadfelder erfassen)
- [x] **P1: Validator modularisieren + Golden-File-Tests**
  - Hinweis: Validatoren wurden später entfernt (Markdown-only Summaries).
- [x] **P2: Concurrency im Per-Video-Modus mit Rate-Limit**
- [x] **P2: Run-Manifeste / Run-level Versioning für Reports**

## TODO

- [ ] **Apache Tika als Docker-Service installieren**
  - Ziel: Tika via Docker bereitstellen (fuer OWUI/Indexing, falls noetig).
  - Bedarf: Compose-Service + Port/Netzwerk + Healthcheck; Doku/Runbook ergaenzen.

- [x] **Open WebUI Knowledge: Auto-Create Governance (klarer User-Intent)**
  - Problem: LLM/RAG-Queries können neue Collections (z. B. `bitcoin`, `crypto`) auto-anlegen, wenn `OPEN_WEBUI_CREATE_KNOWLEDGE_IF_MISSING=true`.
  - Ziel: Auto-Create nur, wenn es explizit gewollt ist.
  - Optionen:
    - A) Auto-Create nur bei explizitem Request-Flag (z. B. `create_knowledge_if_missing=true`) — Default: *kein* Auto-Create.
    - B) Allowlist-Topics (z. B. `investing`, `investing_test`, `ai_knowledge`) — alle anderen blocken.
    - C) Kombination aus A + B (Flag **und** Allowlist).
  - UX: klare Fehlermeldung, wenn Knowledge fehlt und Auto-Create blockiert ist.
  - Doku/Config: `.config.env` / `mcp-transcript-miner/.config.env` + README aktualisieren.

- [ ] **Open WebUI Knowledge: Unerwuenschte Collections aufraeumen**
  - Option: `bitcoin`/`crypto` Collections loeschen (nur falls User bestaetigt).
  - Danach: Sync/Index nur fuer erlaubte Topics.

- [ ] **Open WebUI Knowledge: Duplikate sichtbar machen**
  - CLI/Script, das pro Collection Dateinamen + Duplikate ausgibt (id/filename/count).
  - Optionaler Fix: Duplikate loeschen (nur nach Bestätigung).

- [x] **Re-Sync nach Summary-Rebuild**
  - Status: investing Run fertiggestellt; `sync/topic/investing` erfolgreich (109 processed/109 indexed).
  - Hinweis: Live-Events ohne Transkript (VideoUnplayable) bleiben Skip.

- [ ] **Markdown Linter integrieren (Repo-wide)**
  - Ziel: Konsistente Markdown-Qualitaet (MD041/MD022/MD031/MD032 etc.).
  - Optionen: markdownlint-cli2 oder markdownlint.
  - Scope: alle `*.md`, mit erlaubter `.markdownlint.json`/`.markdownlint.yaml` Konfiguration.
  - CI: optional als eigener Job (fast fail bei Lint-Fehlern).

- [x] **Watchdog: OWUI-Stop aufklaeren + Regeln schaerfen**
  - Fakt: Watchdog stoppt Container **nur** beim Temp-Stop und Default-Target ist `owui`.
  - Check: `/data/watchdog.alert.jsonl` → `2026-01-31T00:29:43Z` mit `temp_max_c=63.0` bei `threshold_c=60` (Action: `stop_containers_temp_threshold`).
  - Entscheidung: Defaults in `watchdog/.config.env.example` auf 95C/3 Messungen angehoben; Auto-Stop via `WATCHDOG_TEMP_STOP_CONTAINER_NAMES=` deaktivierbar.

- [x] **Watchdog/OWUI Stop: Lessons Learned + Knowledge sichern (Context-Erase)**
  - Lessons: zuerst `watchdog.alert.jsonl` pruefen (Temp-Stop ist der einzige Stop-Trigger).
  - Doku-Optionen (persistenter Kontext):
    - `docs/plan_watchdog_monitoring.md`: Default-Temp-Stop (95C/3) + Log-Pfad + Hinweis auf OWUI-Stop.
    - `README.md`: kurzer Warnhinweis im Watchdog-Quickstart + wie man Temp-Stop abstellt/erhoeht.
    - `CHANGELOG.md`: Eintrag fuer Doku-Update (Watchdog Temp-Stop Hinweis).
    - Optional: eigenes Runbook `docs/runbook_watchdog_temp_stop.md` (Check → Ursache → Fix).

- [x] **Investing-Test Workflow (Alpha, schneller Iterate)**
  - Ab sofort fuer Experimente/Prompt-Tuning `investing_test` nutzen (kleinere Datenmenge, weniger Kosten/Time).
  - `config_investing_test.yaml` als Standard fuer Prompt-Iterationen.
  - Production-Investing nur nach validiertem Prompt/Schema-Update laufen lassen.
  - Referenz: `docs/prompt_engineering_expert_notes.md`

- [x] **P0: Healing/Validation für Transkripte & Summaries (inkrementell, metadata‑basiert)**
  - Ziel: Gute Files wiederverwenden; nur kaputte/inkomplette Artefakte re‑fetch/re‑generate.
  - Transkripte: Validierungsregeln definieren (z.B. Datei fehlt/leer/zu kurz, Meta weist auf Fehler/Block hin, Meta↔Datei‑Mismatch).
  - Summaries: Markdown-only, Source-Block + Pflicht-Sections + `video_id`-Konsistenz; sonst neu generieren.
  - Metadaten als Signalquelle (published_at, transcript_status, error_type, etc.).
  - Defekte Artefakte sichern (rename/backup) statt still löschen.
  - DoD:
    - Inkrementelle Runs laden keine “guten” Artefakte neu.
    - Kaputte/inkomplette Transkripte werden re‑fetched; fehlerhafte Summaries neu generiert.
    - Logging zeigt Healing‑Entscheidungen nachvollziehbar pro Video.

- [x] **P1: Zeitfenster‑Selektion statt “letzte N Videos”**
  - Ziel: `letzte X Tage` + `max. Y Videos pro Channel` (Recency‑Sortierung).
  - Logik: Alle Videos im Zeitfenster sammeln → nach `published_at` sortieren → auf Limit kürzen.
  - Beispiel: 30 Tage / 10 Videos ⇒ Channel A (100 in 30 Tagen) → 10; Channel B (5 in 30 Tagen) → 5.
  - Offene Punkte: Feldnamen/Schema (z.B. `youtube.lookback_days` + `youtube.max_videos_per_channel`), Defaults, Doku/Testcases.

- [x] **P0: Best-Solution Output-Struktur (Global Dedup + Reports/History) — Kickoff/ADR**
  - Ziel: Zielbild als verbindliche Architektur-Entscheidung dokumentieren (Canonical `video_id`, Global Data Layer, Current Reports, History Bundles).
  - Deliverable: neues ADR + “Migration Plan” (Schritte/Phasen/Kompatibilität).
  - DoD:
    - ADR beschreibt: Ordnerstruktur, Namenskonventionen, Dedup-Regeln, Locking/Atomic Write, Current-vs-History-Policy.
    - Klarer “Not in scope” Abschnitt (z.B. Symlinks optional, DB optional).
  - Check: Doku-Review (kein Code).

- [x] **P0: Global Transcript Store (Canonical by `video_id`)**
  - Ziel: Transkripte (und Meta) genau einmal global speichern; alle Runs nutzen diese Quelle.
  - Struktur:
    - `output/data/transcripts/by_video_id/<video_id>.txt`
    - `output/data/transcripts/by_video_id/<video_id>.meta.json`
  - Implementierung (inkrementell):
    - Read-New: vor Download prüfen, ob Canonical existiert → Skip YouTube Request.
    - Fallback-Old: wenn Canonical fehlt → Legacy-Pfad suchen → importieren → Canonical schreiben.
    - Atomic Write: `.tmp` → rename; optional `.lock` pro `<video_id>`.
  - DoD:
    - Zwei Configs im selben Multi-Run laden überlappende Videos **nicht** erneut herunter.
    - Parallel Runs vermeiden Race-Conditions (Lock/Atomic).
   - Checks:
     - `uv run python -m transcript_miner --config config/config_investing.yaml --config config/config_ai_knowledge.yaml`
     - Logs zeigen für bereits vorhandene Canonicals “skip download”.

- [x] **P0: Global Summary Store (Canonical by `video_id`)**
  - Ziel: LLM-Summaries genau einmal pro Video speichern; Multi-Run soll Summaries nicht duplizieren.
  - Struktur:
    - `output/data/summaries/by_video_id/<video_id>.summary.md`
    - optional `output/data/summaries/by_video_id/<video_id>.md`
  - Policy (entscheidbar):
    - Recompute nur explizit (Flag/Config), sonst: wenn Summary existiert → Skip LLM Call.
    - Versionierung über Fingerprint (Config+Prompts+Model) im JSON Meta-Header.
  - DoD:
    - LLM per_video Calls werden pro `<video_id>` nicht doppelt ausgeführt, wenn canonical Summary existiert.
  - Checks:
    - Run 1 erzeugt canonical summaries; Run 2 (anderes Profil) erzeugt keine neuen LLM calls für identische video_ids.

- [x] **P0: “Current” Reports unter `/reports/` (menschenlesbar, pro Tag überschreibend)**
  - Ziel: Reports dort ablegen, wo Menschen sie erwarten; Dateiname ist datum-basiert.
  - Struktur:
    - `output/reports/<topic>/report_de_<YYYY-MM-DD>.md`
    - optional `output/reports/<topic>/report_en_<YYYY-MM-DD>.md`
  - Topic-Regel (deterministisch):
    - aus Config ableiten (z.B. basename von `output.root_path`), oder explizites Feld einführen.
  - DoD:
    - Nach einem Run existiert genau 1 “current” Report pro (topic, day, lang).
    - Header enthält Pointer auf das History-Bundle (siehe nächster Punkt).
  - Checks:
    - `ls -la output/reports/<topic>/` zeigt report_de_YYYY-MM-DD.md (und optional report_en_...).

- [x] **P0: History Bundles (`/history/`) für Repro/Forensik**
  - Ziel: Jede Report-Erzeugung bekommt ein Bundle mit allen Inputs/Artefakten; Current kann überschreiben.
  - Struktur:
    - `output/history/<topic>/<YYYY-MM-DD>/<YYYY-MM-DD>__<HHMM>__<model_slug>__<fingerprint8>/`
      - `report_de.md`, `report.json`, `manifest.json`, `inputs_resolved.json`, `audit.jsonl`, `logs/`
  - DoD:
    - Current Report verweist auf Bundle-Pfad + fingerprint8.
    - Re-Run am selben Tag erzeugt neues Bundle, überschreibt aber Current.
  - Checks:
    - `find output/history/<topic>/<YYYY-MM-DD> -maxdepth 2 -type f -name 'report_de.md'`

- [x] **P1: Views für Menschen (optional, keine zweite Wahrheit)**
  - Ziel: Menschen können nach Channel/Datum/Titel browsen; Canonical bleibt `video_id`.
  - Struktur:
    - `output/data/views/by_channel/<channel_slug>/<YYYY-MM-DD>__<video_id>__<title_slug>.txt -> ../../transcripts/by_video_id/<video_id>.txt`
    - `output/data/views/by_channel/<channel_slug>/<YYYY-MM-DD>__<video_id>__<title_slug>.md -> ../../summaries/by_video_id/<video_id>.md`
  - Implementations-Optionen:
    - Symlink (wenn stabil), Hardlink (gleiche Partition), oder Pointer-Datei (portable).
  - DoD:
    - Views sind deterministisch regenerierbar aus canonical + meta.
  - Checks:
    - `find output/data/views/by_channel -type f | head`

- [x] **P1: Migration “Dual Read/Write” (Legacy → New)**
  - Ziel: Bestehende Profile bleiben nutzbar; Canonical wird schrittweise gefüllt.
  - Schritte:
    1) Read-New (Canonical) + Fallback-Old (Import)
    2) Write Canonical immer
    3) Reports: current+history parallel zu legacy 3_reports/
    4) Deprecate legacy outputs (später)
  - DoD:
    - Keine Breaking-Changes für bestehende Configs/CLI.

- [x] **P1: Report-Source-Lesbarkeit (Channel + Video Title überall)**
  - Ziel: im Report niemals nur “(Creator, Video <id>)”, sondern “<Channel> — <Video Title>”.
  - DoD:
    - Aggregation/Report zieht `video_title` + `channel_name` aus Transcript-Meta und nutzt diese im Output.

- [x] **P2: OpenRouter Attribution (App Name)**
  - Ziel: bessere Zuordnung in OpenRouter UI/CSV.
  - Umsetzung:
    - Immer `X-Title` (App Name) und `HTTP-Referer` setzen.
    - Config-Felder: `api.openrouter_app_title`, `api.openrouter_http_referer`.
  - DoD:
    - OpenRouter Activity zeigt konsistent `app_name` für Runs (falls Provider das unterstützt).

- [x] **P0: Default Full-Pipeline Run (Mining → Index → LLM → Report)**
  - Standard-Verhalten: ein Programmlauf macht **alles** (Transkripte downloaden → Index bauen → LLM-Summaries → Aggregation/Report).
  - CLI: Schritte sollen optional überspringbar sein (Flag-Namen TBD; z.B. `--skip-index`, `--skip-llm`, `--skip-report` oder `--only <step>`).
  - Konfig-Hierarchie beibehalten (CLI > Config > Env > Defaults); kein Schema-Bruch.
  - Output/Overwrite-Policy: deterministisch, keine stillen Overwrites; Logs/Artefakte klar getrennt pro Run/Config.
  - Doku: README „Wie ausführen“ auf **1 Command** aktualisieren + Beispiele für Skip/Only.

- [x] **P1: Reports: Creator-Namespace bereinigen, Canonical-Dedupe (z.B. TSLA), fehlende Channels im Report prüfen**
  - Report zeigt `channel_namespace` mit `/1_transcripts`-Suffix (sollte nur Handle sein).
  - Duplikate in Top-Aktien (z.B. `Tesla (TSLA)` vs `Tesla, Inc. (TSLA)`).
  - Fehlende Channels im Report trotz Transkripten (z.B. `@DataCatInvest`).

- [x] **P1: Report: Verständlichkeit & Konsistenz (Inhalt/Präsentation)**
  - Abkürzungen beim ersten Auftreten erklären (z.B. mNAV, NAV, YTD, DCF, EV, FCF, P/E, P/FCF, ICE, TPU).
  - Top-Aktien: einheitliches Format `Company (TICKER) — mentions: X — videos: Y — creators: Z` + Dedupe (z.B. TSLA).
  - Mentions vs. Coverage: immer `mentions`, `video_count`, `creator_count` ausweisen (kein „Cluster“ nur aus Mentions).
  - Datenqualität operationalisieren (ok/low/truncated + Schwellen) und Confidence-Tag pro Kernaussage.
  - Behauptungen klar als Beobachtung+Unsicherheit markieren; Quellen-Qualität sichtbar machen.
  - Sentiment messbarer machen (Score + Confidence oder Bull/Bear/Open Questions pro Aktie).
  - Struktur: Actionable/Watchlist/Kontext am Ende der Key Findings trennen.
  - Traceability: pro Top-Aktie kurze Quellenzeile (Creator + Video-IDs).

- [x] **P1: Reports: Recency-Guardrails (as-of + Zeitfenster + Freshness)**
  - Report-Header + JSON: as-of Timestamp, Zeitraum (min/max `published_at`), Freshness-Metriken (z.B. Median-Alter, Anteil <30 Tage).
  - Aggregates: pro Ticker `raw` vs `recent` Counts (30/60/90 Tage) + Stale-Flag (keine Erwähnung in X Tagen).
  - Optional: recency-weighted Score mit Halbwertszeit (konfigurierbar).
  - Report-Prompt-Regeln: Neuere Quellen priorisieren, Zeitachse bei Widerspruch, Freshness-Warnung wenn letzte Quelle zu alt.
  - Konfig + Doku: Fenster/Halbwertszeit pro Report-Profil definieren.

- [x] **P2: Report: Investor‑Brief‑Erweiterungen (Gap IST → SOLL)**
  - Traceability pro These (Quelle + 1–2 Snippets/Paraphrasen) und pro Aktie (Creator/Videos).
  - Coverage-Qualität: Anteil ok vs low/truncated + Confidence mit Begründung.
  - Actionability: Bull/Bear + Katalysatoren + Widerlegungs-Kriterien pro Aktie.
  - Minimal-Factsheet: Market Cap, Wachstum, Marge, FCF, Verschuldung, Bewertungsmultiples.
  - Risiko/Portfolio-Fit: Risiko-Klasse, Positionsgröße/Tranching, Exposure (z.B. BTC-Beta).
  - Aktualität: Video-Datum + „neu seit letztem Run“ + Delta-Übersicht.

- [x] **P2: Report-Sprache per CLI-Option (en/de) wählen; nur eine Report-Datei erzeugen**
  - Beim Programmaufruf eine Sprach-Option übergeben (`--report-lang de|en|both`).
  - Standard: `--report-lang de` erzeugt **nur** `report.md` (Deutsch); `--report-lang en` erzeugt **nur** `report.md` (Englisch).
  - Optional: `--report-lang both` erzeugt `report_de.md` und `report_en.md`.

- [x] **Flat-First Report-Struktur (v0.3.4)**
  - Ziel: Aktuellster Report immer direkt in `3_reports/`.
  - Archivierung: Alte Runs wandern automatisch nach `archive/`.
  - Implementierung: `src/common/path_utils.py`, `src/common/config_models.py`, `llm_runner.py`, `aggregation_runner.py`.
- [x] **Bilinguale Report-Generierung (v0.3.3)**
  - Implementierung: [`tools/generate_llm_report.py`](tools/generate_llm_report.py)
  - Features: Deutsch/Englisch, Templates, Config-Integration, Token-Checks.
- [x] **Ordnerstruktur-Migration (PRD Sektion 8.3)**
  - Roh-Transkripte: `1_transcripts/`
  - Video-Summaries: `2_summaries/`
  - Reports & Aggregates: `3_reports/`
  - Ingest-Index: `3_reports/index/`
  - Implementierung: [`OutputConfig`](src/common/config_models.py:41), [`process_channel()`](src/transcript_miner/main.py:162), [`run_llm_analysis()`](src/transcript_ai_analysis/llm_runner.py:262), [`run_aggregation()`](src/transcript_ai_analysis/aggregation_runner.py:23).
  - Tests: [`tests/test_summary_check_ingest.py`](tests/test_summary_check_ingest.py:1), [`tests/test_llm_runner.py`](tests/test_llm_runner.py:1).
  - Evidence: Aggregation-Tests in [`tests/test_aggregation.py`](tests/test_aggregation.py:1).
- [x] **Aggregation & Reporting (ohne LLM)** (PRD Abschnitt 7):
  - Implementierung: [`run_aggregation()`](src/transcript_ai_analysis/aggregation_runner.py:23), [`aggregate_by_channel()`](src/transcript_ai_analysis/aggregation.py:45).
  - Artefakte: `3_reports/aggregates/by_channel.json`, `by_symbol.json`, `global.json`.
- [x] **Drilldown-Exports: Stock → Influencer + Evidence (Pointer + Snippet-Preview)** (Canvas Abschnitt „Optional: Stock → Influencer-Liste“: [`docs/use-cases/stocks.md`](docs/use-cases/stocks.md))
  - Output A: `stock_to_influencers.json` (Map `ticker -> [channel_namespace...]`).
  - Output B: `coverage_evidence.jsonl` (1 Zeile pro `(ticker, channel_namespace)`), mit **Evidence-Pointern** + **Snippet-Preview**:
    - Pointer-Felder angelehnt an Aggregates-Schema in [`docs/architecture.md`](docs/architecture.md:327): `video_id`, `mention_id`, `transcript_path`, `snippet_sha256`.
    - Preview-Feld angelehnt an Mentions-Schema in [`docs/architecture.md`](docs/architecture.md:265): `snippet_preview` (z.B. 200–300 Zeichen aus `evidence.snippet`).
  - DoD: deterministisch (stable sort) und ableitbar aus Aggregations-Artefakten unter `PROFILE_ROOT/3_reports/aggregates/`.
  - Implementierung: [`run_aggregation()`](src/transcript_ai_analysis/aggregation_runner.py:23).
  - Tests: [`tests/test_aggregation.py`](tests/test_aggregation.py:1).

- [x] **Hybrid-Semantik: `mentioned` vs `covered` (thematic) als zwei getrennte Metriken** (Canvas Definition „Influencer covert Stock X“: [`docs/use-cases/stocks.md`](docs/use-cases/stocks.md))
  - Ziel: Die Pipeline liefert *immer* ein stabiles Grundsignal (`mentioned`) und *optional* ein stärkeres Signal (`covered`), ohne Begriffe zu vermischen.
  - Evidence: Aggregation liest Markdown-Per-Video-Summaries (Source-Block + Sections) in [`run_aggregation()`](src/transcript_ai_analysis/aggregation_runner.py:300); JSON-Validatoren wurden entfernt.

  - **Definition 1: `mentioned` (deterministisch, Aggregation-kompatibel)**
    - Ein Influencer/Channel „mentioned“ Stock X, wenn in den letzten **N** Videos mindestens **eine** valide Mention existiert.
    - „Valide Mention“ = Ticker/ISIN/Name-Match nach Extraktor + Canonicalization (je nach Policy).
    - Counting-Regel: pro `(ticker, channel_namespace)` **maximal 1×** zählen (Set-Logik).
    - Evidence: aus Mentions (`evidence.snippet` + Pointer), siehe normatives Mention-Schema in [`docs/architecture.md`](docs/architecture.md:265).

  - **Definition 2: `covered` (thematic, Name-Dropping ausgeschlossen)**
    - Ein Influencer/Channel „covered“ Stock X, wenn mindestens ein Video existiert, in dem das Unternehmen **inhaltlich Thema** ist.
    - Nicht `covered` bei reiner Aufzählung/Name-Dropping („Magnificent 7 …“), Sponsoring/Disclaimer-Mentions, Metaphern.
    - Counting-Regel: pro `(ticker, channel_namespace)` **maximal 1×** zählen.
    - Evidence: zusätzlich zur Mention-Evidence muss eine thematische Begründung/Belegkette existieren (z.B. Quote/Snippet + Referenz `video_id`; optional Confidence).

  - **Implementation Note (Richtung, nicht DoD):**
    - `covered` wird als **zusätzliche Klassifikations-Schicht** auf Kandidaten angewandt (z.B. LLM/Classifier), nicht als Ersatz für Mentions.
    - Ziel ist auditierbares Verhalten: Entscheidungen müssen auf Transcript-Text zurückführbar bleiben.

  - **DoD:** Reports/Exports können beide Metriken ausgeben (z.B. `mentioned_by_influencers_count` und `covered_by_influencers_count`) und sind deterministisch reproduzierbar.
- [x] Multi-Config Semantik definieren + CLI-Concepts (siehe „P0 — Config Composition / Multi-config Runs“).
  - Evidence: CLI Multi-Config Verarbeitung in [`transcript_miner.main.parse_arguments()`](src/transcript_miner/main.py:334) sowie Canonical Order/ID in [`transcript_miner.main._canonical_config_paths()`](src/transcript_miner/main.py:29) und [`transcript_miner.main._compute_config_set_id()`](src/transcript_miner/main.py:43).
- [x] SemVer-Policy + Version in [`pyproject.toml`](pyproject.toml:3) aktualisieren.
  - Evidence: Packaging-Version in [`pyproject.toml`](pyproject.toml:3); SemVer-Policy in [`CHANGELOG.md`](CHANGELOG.md:20).
- [x] LLM: Output-Formate (`report.json` + derived `report.md`/`report.txt` + `metadata.json`) entschieden und umgesetzt (ADR: [`docs/adr/0007-llm-output-formats-json-vs-markdown.md`](docs/adr/0007-llm-output-formats-json-vs-markdown.md:1); Writer: [`_write_derived_report_and_metadata()`](src/transcript_ai_analysis/llm_runner.py:73)).
- [x] LLM: Skalierungs-Policy Single-Run vs Sharding/Multi-Job (ADR: [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:1)).
  - Evidence: Normative Policy „Single-Run vs Sharding“ in [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:102).

- [x] **LLM Prompt-Anforderungen: maschinenlesbar + Evidence-Pflicht + strikte Regeln** (Canvas „LLM-Prompt-Anforderungen“: [`docs/use-cases/stocks.md`](docs/use-cases/stocks.md))
   - Spezifikation (normativ, implementierbar): Markdown-only Summary-Layout (Source + feste Sections).
   - Output: **Markdown-only** (keine JSON-Schemata/Validatoren).
   - Für jede Aussage (z.B. `covered`): Evidence muss wörtlich aus Transcript stammen (Snippet/Quote) + Referenz (`video_id`, optional Char-Spans).
   - Unsicherheit: `confidence` oder Status-Feld; bei Unsicherheit lieber weglassen oder als „ambiguous“ markieren.
   - Guardrails: keine erfundenen Ticker/Entities; klare Negativ-Regeln (Name-Dropping, Sponsoring, Metaphern).
   - DoD: Prompts/Inputs werden für Audit gespeichert (vgl. existierende LLM-Artefakte unter `3_reports/run_.../*`, Doku: [`README.md`](README.md:448)).
   - Implementierung/Enforcement: Prompt-/Artefakt-Schreiben in [`run_llm_analysis()`](src/transcript_ai_analysis/llm_runner.py:236); Validatoren wurden entfernt.

- [x] **Fehlerquellen/Countermeasures als Qualitäts-Policy für `covered` + Canonicalization** (Canvas „Typische Fehlerquellen“: [`docs/use-cases/stocks.md`](docs/use-cases/stocks.md))
  - „Apple“ (Wort) vs Apple (Company): Ticker-Fokus + Evidence; optional Stoplist/Context-Regeln.
  - Listen/Name-Dropping: explizite Prompt-Regel „kein covered bei reiner Liste“.
  - Schlechte ASR/Transkriptqualität: Confidence nutzen; optional `transcript_quality`/Warn-Events im Audit.
  - Ticker-Fakes: keine Regex-only Entscheidung; lieber Canonicalization + Whitelist/Blacklist + Evidence.
  - DoD: Diese Regeln sind als Tests/Fixtures oder Audit-Checks abgedeckt (Offline).
  - Evidence: Prompt-Regeln + Markdown-Summary-Layout; Offline-Validatoren wurden entfernt.

- [x] **Optimierung der Output-Ordnerstruktur (Refactoring)**
  - Ziel: Entwicklung einer besseren Strategie für die Output-Ordnerstruktur.
  - Problem: Aktuell entstehen zu viele leere Ordner, was zu Unordnung führt.
  - Aufgabe: Überarbeitung der Ordner-Erstellung, um "Chaos" zu vermeiden (z.B. Lazy Creation oder flachere Hierarchien).
  - Lösung: Lazy Creation ist bereits in `src/common/utils.py` und `src/transcript_miner/video_processor.py` implementiert. Ordner werden erst beim Speichern erstellt.

- [x] **Robustheit gegen IP-Blocks verbessern**
  - Problem: `youtube-transcript-api` läuft in Cloud-Umgebungen (Datacenter-IPs) häufig in `IpBlocked` Fehler.
  - Lösung: Implementierung von Proxy-Support (Webshare/Generic), Sticky Sessions pro Video und optimierten Delays.
  - Dokumentation: [`docs/config.md`](docs/config.md) und [`config/config_wsl_optimized.yaml`](config/config_wsl_optimized.yaml).
  - Erkenntnis: Datacenter-IPs werden von YouTube oft generell für Transkripte geblockt; Residential Proxies empfohlen.

- [x] **Report-Optimierung: Daily Reports + Skip-Logic**
  - Ziel: Vermeidung von Report-Duplikaten und unnötigen Runs.
  - Anforderung 1: Option `daily_report` (ein Ordner pro Tag, überschreiben).
  - Anforderung 2: Option `skip_on_no_new_data` (Fingerprint-Check gegen existierenden Report).
  - Implementierung: `src/common/config_models.py` (Config), `src/transcript_ai_analysis/llm_runner.py` (Logic).

- [x] **Verbesserung der Terminal-Anzeige beim Download von Transkripten**
  - Ziel: Saubere Progress-Anzeige und Status-Indikatoren.
  - Beschreibung: Implementierung eines sauberen Progress-Bars (z.B. `0% === 100%`) mit Indikatoren für Info (I), Error (E) und Warning (W). Details sollen nur in den Logs erscheinen, nicht im Terminal.
  - DoD: Terminal bleibt übersichtlich; Fortschritt ist jederzeit erkennbar; Fehler/Warnungen werden kompakt signalisiert.
  - Implementierung: Integration von `rich.progress` in `src/transcript_miner/main.py`.

## DONE

- [x] Analysis Index/Aggregation Artefakt-Layout + deterministische Aggregation inkl. Evidence (Spezifikation: [`docs/architecture.md`](docs/architecture.md:129)).
- [x] UV-first Workflow + CI + Smoke-Checks (siehe UV-first Pattern in [`AGENTS.md`](AGENTS.md:176)).

<details>
<summary>Historie (vollständig, inkl. DONE-Items)</summary>

Ziel: „funktionierendes Programm“ + „perfekte, übersichtliche Doku“.

Legende:
- **P0** = Blocker für „läuft zuverlässig“ / reproduzierbar
- **P1** = hohe Priorität (Qualität, Tests, Doku-Vollständigkeit)
- **P2** = nice-to-have / Erweiterungen

Definition of Done (für v1 „funktionierendes Programm“):
- `uv venv` + `uv sync` + `uv run python -m transcript_miner --help` funktionieren offline (ohne API-Key, ohne optionale Dependencies) — siehe UV-first Pattern in [`AGENTS.md`](AGENTS.md:176).
- `uv run python -m transcript_miner config/config_ai_knowledge.yaml --api-key ...` erzeugt Outputs gemäß [`README.md`](README.md:123).
- CI läuft grün (Format/Lint/Tests/Smoke) und ist UV-first/Lockfile-basiert (siehe [`.github/workflows/ci.yml`](.github/workflows/ci.yml:1)).

---

## Neues Zielbild / Richtung (2025-12)

**Produktziel (neu):** Pipeline ist **transcript fetch → analysis** (statt „fetch → correction“).

- Fokus ist **Analyse** auf Basis der heruntergeladenen Transkripte (Inputs/Outputs des Miners siehe [`README.md`](README.md:1)).
- Corrector/LLM-Korrektur ist **nicht mehr Zielbild** (siehe „Deprecated“ weiter unten); er kann optional bestehen bleiben, aber wird nicht mehr als Kern-Pipeline priorisiert.
- Analyse soll zwei Ebenen abdecken:
  1. **Stock-Coverage pro Aktie:** „wer (Channel) erwähnt welche Aktie wie oft“ inkl. Evidence.
  2. **Gesamtanalyse über alle heruntergeladenen Transkripte** (globaler Summary/Report).
- Zusätzlich: **Multi-Config Runs / Config Composition**: mehrere YAMLs kombinieren (z.B. [`config/config_investing.yaml`](config/config_investing.yaml:1) + [`config/config_ai_knowledge.yaml`](config/config_ai_knowledge.yaml:1)) und daraus eine **gemeinsame Analyse** erzeugen.
- Optional (Entscheidung offen): Evaluieren, ob Analyse-Artefakte langfristig in einer **Datenbank** (statt nur Files/JSON) persistiert werden sollen (siehe Backlog „Datenhaltung / Datenbank-Option“ unten).

Nicht-Ziele (für dieses Zielbild):
- Keine „Korrektur-Pipeline“ als Default.
- Keine implizite Änderung der bestehenden Konfig-Hierarchie (Pattern bleibt: CLI > Config > Env > Defaults; siehe [`AGENTS.md`](AGENTS.md:166)).

---

## P0 — Analysis Pipeline (transcript fetch → analysis)

Status-Hinweis (Ist-Zustand):

- **Der Transcript-Index ist bereits implementiert** (Offline-Scan vorhandener Miner-Outputs).
- **Artefakte (Index):** `manifest.json`, `transcripts.jsonl`, `audit.jsonl` (Details siehe „Analysis (offline) — Index“ in [`README.md`](README.md:259)).
- Offen bleiben die eigentlichen „Stock Analysis“ Schritte (Extraktion, Canonicalization, Coverage-Stats, Global Report) in den nachfolgenden TODOs.

### P0.1 Datenmodell / Artefakte (Analysis Outputs)

- [x] Definiere ein **stables Analyse-Artefakt-Layout** innerhalb des Output-Roots (pro Run + global aggregierbar).
  - **Ergebnis/Spezifikation:** siehe Abschnitt „4.3 Spezifikation (Doku): Aggregation Artefakt-Layout + globale Aggregation“ in [`docs/architecture.md`](docs/architecture.md:129).
  - **DoD:** Dokumentierte Liste der Artefakte + Felder + Versionierung/Kompatibilitätsregeln (z.B. `schema_version`).
  - **DoD:** Konkrete Artefakt-Typen sind benannt (z.B. „Mentions“ / „Aggregates“ / „Audit-Log“ als JSON/JSONL), inkl. Zweck/Owner.
  - **DoD:** „Audit Trail“ ist möglich (welches Transcript, welcher Channel, welches Video; Verlinkung zu bestehenden Transcript-Dateien gemäß [`README.md`](README.md:223)).
  - **Hinweis:** Channel-Handle-Normalisierung muss konsistent zum bestehenden Pattern sein („@ weg, `/` und `\\` → `_`“; siehe [`AGENTS.md`](AGENTS.md:169)).

- [x] Definiere ein **globales Aggregationsziel** über alle bereits heruntergeladenen Transkripte in einem Output-Root.
  - **Ergebnis/Spezifikation:** Merge-Key + Dedup-/Tie-Breaking + Overwrite-Policy sind in [`docs/architecture.md`](docs/architecture.md:189) beschrieben.
  - **DoD:** Klarer Merge-Key/Identifikator für Transkripte (z.B. Video-ID aus Dateiname / Metadaten) und Policy für Duplikate.
  - **DoD:** Policy für deterministische Re-Runs (keine stillen Overwrites ohne klare Policy; siehe [`AGENTS.md`](AGENTS.md:140)).

### P0.2 Stock Mention Extraction (inkl. Evidence)

- [x] Definiere eine **Extraktions-Strategie** für Stock-Mentions aus Transcript-Texten.
  - **Ergebnis/Spezifikation:** [`docs/use-cases/stocks.md`](docs/use-cases/stocks.md:1).
  - **DoD:** Klare Definition, was als „Mention“ zählt (Ticker, Company Name, ISIN, Synonyme) und wie Evidence gespeichert wird (z.B. Textsnippet + Timestamp/Segment, falls verfügbar).
  - **DoD:** Klare Failure-Policy (unbekannte/mehrdeutige Begriffe → markieren, nicht still verwerfen).

- [x] Implementiere **Symbol-Normalisierung** (z.B. `Tesla (TSLA)` → `TSLA`) für Aggregation/Report.
  - **Code:** [`transcript_ai_analysis.aggregation_runner._canonicalize_symbol_key()`](src/transcript_ai_analysis/aggregation_runner.py:118) und [`transcript_ai_analysis.llm_report_generator._canonicalize_symbol_key()`](src/transcript_ai_analysis/llm_report_generator.py:51).
  - **Tests:** Label/Preferred-Label Verhalten in [`tests/test_aggregation.py`](tests/test_aggregation.py:186).


### P0.3 Stock-Coverage Stats (pro Aktie / pro Channel)

- [x] Erzeuge **Coverage-Statistiken**: pro Aktie und pro Channel „wie oft erwähnt“.
  - **Code (Aggregation, deterministisch):**
    - [`aggregate_by_channel()`](src/transcript_ai_analysis/aggregation.py:45)
    - [`aggregate_by_symbol()`](src/transcript_ai_analysis/aggregation.py:89)
    - [`aggregate_global()`](src/transcript_ai_analysis/aggregation.py:138)
  - **Tests:** [`tests/test_aggregation.py`](tests/test_aggregation.py:1)
  - **DoD:** Metriken sind definiert (z.B. unique-videos vs. total-mentions) und jeder Wert ist auf Evidence rückführbar.
  - **DoD:** Output enthält sowohl „Top Stocks pro Channel“ als auch „Top Channels pro Stock“.

- [x] **CSV-Export: Stock → #Influencer (Counts)** (Canvas Abschnitt „Stock → Anzahl Influencer“, vgl. [`docs/use-cases/stocks.md`](docs/use-cases/stocks.md))
  - Output: `stock_coverage_counts.csv` mit Spalten `ticker,count`.
  - `count` = Anzahl **unique Channels** (`channel_namespace`) pro `ticker` im betrachteten Sample (pro Channel max. 1× zählen).
  - Datenquelle: Aggregations-Artefakte unter `PROFILE_ROOT/3_reports/aggregates/` (Layout: [`docs/architecture.md`](docs/architecture.md:151)); *nicht* PNG/Plot in diesem Schritt.
  - DoD: Exporter ist deterministisch, deduped auf `channel_namespace` und kann aus Aggregations-Outputs neu generiert werden.
  - Code: [`run_aggregation()`](src/transcript_ai_analysis/aggregation_runner.py:23); Test: [`tests/test_aggregation.py`](tests/test_aggregation.py:1).

### P0.4 Global Summary / Report über alle Transkripte

- [x] Definiere einen **globalen Analyse-Report** (aggregiert über alle Channels/Configs in einem Run).
  - **Implementierung (Aggregation Runner + Artefakte):** [`transcript_ai_analysis.aggregation_runner.run_aggregation()`](src/transcript_ai_analysis/aggregation_runner.py:23)
  - **Artefakte:** `3_reports/aggregates/by_channel.json`, `by_symbol.json`, `global.json` (Layout-Spezifikation: [`docs/architecture.md`](docs/architecture.md:151))
  - **Test:** [`tests/test_aggregation.py`](tests/test_aggregation.py:1)
  - **DoD:** Report-Format ist festgelegt (z.B. JSON + optional Markdown) und enthält mindestens: Zeitraum/Run-Metadaten, Coverage-Highlights, Datenqualitäts-Stats (z.B. #Transkripte, #Skips).
  - **DoD:** Report kann aus vorhandenen Artefakten neu berechnet werden (idempotent).

## P1 — Analysis Qualität / Robustheit

- [x] Ergänze Validierung/Checks für Analyse-Inputs (fehlende Transkripte, Orphans, Encoding-Probleme).
  - **Implementierung:** zusätzliche Input-Validierung + Audit-Events + Telemetry in [`transcript_ai_analysis.aggregation_runner.run_aggregation()`](src/transcript_ai_analysis/aggregation_runner.py:23).
  - **Tests:** [`tests/test_aggregation.py`](tests/test_aggregation.py:1).
  - **DoD:** Klare Fehlermeldungen + Zähler (Telemetry) statt stiller Drops.

- [x] Ergänze Tests (Unit/Integration) für Extraktion + Canonicalization + Aggregation.
- [x] **CI-Integration für Doku-Governance:** `tools/md_link_audit.py` als verpflichtenden Check in CI aufnehmen.
  - **DoD:** Tests laufen offline ohne externe APIs; repräsentative Sample-Transkripte/Fixtures.
  - Evidence: Aggregation-Tests in [`tests/test_aggregation.py`](tests/test_aggregation.py:1); Validator-/Fixture-Tests wurden entfernt.

---

## P0 — Config Composition / Multi-config Runs (gemeinsame Analyse)

### P0.1 Semantik definieren (Merge vs. Multi-Run vs. Union)

- [x] Definiere die Semantik für „mehrere Config-Files kombinieren“.
  - **Design-Spezifikation (Proposed ADR):** [`docs/adr/0006-multi-config-composition.md`](docs/adr/0006-multi-config-composition.md:1)
  - **Normative Spezifikation (Doku; Implementation: proposed):** [`docs/config.md`](docs/config.md:60) (Abschnitt „Multi-Config (Config Composition) — Spezifikation“)
  - **DoD:** Klarer Modus-Katalog:
    - **Merge:** YAMLs zu einer effektiven Config zusammenführen.
    - **Multi-Run:** YAMLs getrennt ausführen, aber **gemeinsam analysieren**.
    - **Union:** Channels/Keywords vereinigen, sonstige Felder konfliktauflösend.
  - **DoD:** Konfliktregeln sind dokumentiert (z.B. `output.*`, `logging.*`, `youtube.num_videos`, `youtube.preferred_languages`).
  - **DoD:** Konfig-Hierarchie bleibt konsistent (CLI > Config > Env > Defaults; siehe [`docs/config.md`](docs/config.md:11)).

### P0.2 CLI/Entry-Point Anpassungen (nur TODO, keine Implementierung hier)

- [x] Erweitere CLI-Konzept, um **mehrere `--config`** oder eine **Config-Liste** zu akzeptieren.
  - **Design-Spezifikation (Proposed ADR):** [`docs/adr/0006-multi-config-composition.md`](docs/adr/0006-multi-config-composition.md:1)
  - **DoD:** Entwurf ist in Doku/TODO beschrieben und referenziert den primären Einstiegspunkt (Modul-CLI: [`transcript_miner.main.parse_arguments()`](src/transcript_miner/main.py:210)).
  - **DoD:** Output-Path-Policy für Multi-Config ist festgelegt (verhindert Kollisionen wie bei Multi-Channel; siehe Empfehlung in [`docs/config.md`](docs/config.md:130)).

- [x] Definiere Run-Identität/Namespaces für Multi-Config (z.B. „config-set name“) zur sauberen Ablage von Analyse-Artefakten.
  - **Design-Spezifikation (Proposed ADR):** [`docs/adr/0006-multi-config-composition.md`](docs/adr/0006-multi-config-composition.md:1)
  - **DoD:** Deterministische Benennung (keine zufälligen IDs), nachvollziehbar aus Config-Files.
  - Evidence: deterministische ID via [`transcript_miner.main._compute_config_set_id()`](src/transcript_miner/main.py:43).

### P1 — UX / Doku

- [x] Dokumentiere Multi-Config Nutzung inkl. Beispiele mit realen Beispielconfigs.
  - **DoD:** Beispiele referenzieren vorhandene YAMLs unter [`config/`](config:1), z.B. [`config/config_investing.yaml`](config/config_investing.yaml:1) und [`config/config_ai_knowledge.yaml`](config/config_ai_knowledge.yaml:1).
  - Evidence: „Wie benutze ich das heute?“ + Beispiele in [`docs/config.md`](docs/config.md:86).

---

## P1 — Datenhaltung / Datenbank-Option (Decision Record)

> Ziel: fundierte Entscheidung, ob Analyse/Artefakte weiterhin file-basiert bleiben (JSON/CSV/Parquet) oder in eine echte DB wandern sollen.

- [x] Erarbeite einen **Decision Record** „Filesystem vs. Datenbank“ für Analyse-Artefakte. (siehe [`docs/adr/0001-filesystem-vs-db.md`](docs/adr/0001-filesystem-vs-db.md:1))
  - **DoD:** Mindestens zwei Alternativen sind sauber verglichen:
    - file-basiert (JSON/CSV; optional spaltenorientiert wie Parquet)
    - embedded DB (z.B. SQLite oder DuckDB)
    - server DB (z.B. Postgres)
  - **DoD:** Vorteile/Nachteile sind entlang der relevanten Kriterien dokumentiert:
    - Reproduzierbarkeit/Determinismus (Re-Runs, Overwrite-Policy)
    - Query-/Aggregation-Use-Cases (Stock-Coverage, globale Reports)
    - Deployment/Operations-Komplexität (lokal vs. CI)
    - Datenvolumen/Performance (inkrementelle Updates, Indexing)
    - Auditierbarkeit (Evidence, Traceability)
  - **DoD:** Klare Empfehlung + Migrationspfad (falls „DB“): minimale Schema-Skizze, Export/Import-Strategie, Backups.

- [x] Definiere eine **Minimallösung** für den Übergang (falls DB gewählt wird): „write-through“ oder „import from existing outputs“. (siehe Migration/Minimallösung in [`docs/adr/0001-filesystem-vs-db.md`](docs/adr/0001-filesystem-vs-db.md:1))
  - **DoD:** Das Konzept respektiert bestehende Output-Struktur aus dem Miner (Transkripte + [`progress.json`](README.md:223), siehe [`README.md`](README.md:223)) und bricht keine bestehenden Runs.

---

## P0 — Setup / Packaging / Runtime

- [x] Migration auf UV: Quickstart in [`README.md`](README.md:18) von Poetry auf `uv` umstellen (Install/Sync/Run), inkl. `uv venv`, `uv sync`, `uv run ...`.
- [x] Migration auf UV: CI Workflows unter [`.github/workflows/`](.github/workflows:1) von Poetry auf `uv` umstellen (Dependencies + `uv run ...`).
- [x] Migration auf UV: Lockfile-Strategie entscheiden und umsetzen (`poetry.lock` entfernen vs. Übergangsphase mit beiden Lockfiles; aktuell sind `poetry.lock` und `uv.lock` im Repo vorhanden).
- [x] Migration auf UV: `uv.lock` generieren und committen; CI auf reproduzierbare Sync-Strategie umstellen (CI nutzt `uv sync --frozen`, siehe [`.github/workflows/ci.yml`](.github/workflows/ci.yml:27)).
- [x] Migration auf UV: Entwickler-Workflow dokumentieren (`uv venv`, `uv sync`, `uv run python -m transcript_miner --help`, `uv run pytest`) — siehe Quickstart/Smoke-Checks in [`README.md`](README.md:18) und UV-first Pattern in [`AGENTS.md`](AGENTS.md:176).
- [x] Migration auf UV: Optional `pyproject.toml` beibehalten, aber Poetry-spezifische Sektionen entfernen/aufräumen, falls nicht mehr benötigt (aktuell keine Poetry-spezifischen Sektionen im Manifest sichtbar; siehe [`pyproject.toml`](pyproject.toml:1)).
- [x] Entscheide und dokumentiere unterstützte Python-Version(en) und passe `requires-python` in [`pyproject.toml`](pyproject.toml:9) so an, dass lokale Standard-Umgebungen (mindestens `python3`) realistisch unterstützt werden.
- [x] Ergänze einen „One-liner Smoke“-Check in der Doku und im CI: `uv run python -c "import transcript_miner"` (Import muss ohne Netz und ohne API-Key funktionieren; Doku: [`README.md`](README.md:46), CI: [`.github/workflows/ci.yml`](.github/workflows/ci.yml:39), Test: [`tests/test_smoke.py`](tests/test_smoke.py:5)).
- [x] Standardisiere die Entry-Points und mache das Verhalten konsistent zwischen Modul-Entry [`transcript_miner.main.main()`](src/transcript_miner/main.py:211) und Top-Level [`src/__main__.py`](src/__main__.py:1) (klar: welcher Pfad ist „empfohlen“).
- [x] Stelle sicher, dass `--help` robust ist (keine Env-/Network-/optional-dep Checks vor Argument-Parsing) und verifiziere das explizit für [`transcript_miner.main.main()`](src/transcript_miner/main.py:226) (Fix: Argument-Parsing vor `.env`/Config/Runtime; Regression-Test: [`tests.test_smoke.test_cli_help_does_not_crash()`](tests/test_smoke.py:10) + [`tests.test_smoke.test_cli_help_with_positional_config_does_not_crash()`](tests/test_smoke.py:23)).
- [x] Definiere eine klare Policy für optionale Dependencies (mindestens `google-api-python-client`, `openai`, `tiktoken`) und dokumentiere, welche Features ohne diese Pakete funktionieren (siehe Lazy-Import in [`transcript_miner.youtube_client._require_googleapiclient()`](src/transcript_miner/youtube_client.py:21) und Fallback in [`common.utils.calculate_token_count()`](src/common/utils.py:165)).
- [x] Entferne/ersetze veraltete CI-Installationswege, die ein requirements-/Poetry-basiertes Setup voraussetzen; Workflows nutzen `uv` + Sync über Lockfile (siehe [`ci.yml`](.github/workflows/ci.yml:24)).

## P0 — CI / Smoke / Quality Gate

- [x] Konsolidiere Workflows unter [`.github/workflows/`](.github/workflows:1) zu einem klaren Set (z.B. „quality“, „tests“, „secret-scan“) und entferne doppelte/obsolete Jobs.
- [x] Aktualisiere [`ci.yml`](.github/workflows/ci.yml:1) so, dass Dependencies UV-first installiert werden und alle Schritte auf Repo-Tools verweisen (Setup/Sync: [`.github/workflows/ci.yml`](.github/workflows/ci.yml:24)).
- [x] Lege einen CI-Smoke-Step an, der `uv run python -m transcript_miner --help` ausführt (Regression: Offline/Help darf nicht crashen; siehe [`.github/workflows/ci.yml`](.github/workflows/ci.yml:39) und Smoke-Test [`tests/test_smoke.py`](tests/test_smoke.py:10)).
- [x] Lege eine Python-Matrix fest, die zur `requires-python`-Policy passt (>=3.11, siehe [`pyproject.toml`](pyproject.toml:9)).
- [x] Definiere eine minimale, stabile Toolchain im CI (Black + Ruff + Pytest) und führe sie auf `src/` aus; vermeide doppelte Install-Schritte (siehe Black/Ruff/Pytest Steps in [`ci.yml`](.github/workflows/ci.yml:30)).
- [x] Ergänze einen CI-Check, der `uv run python -m transcript_miner config/config_ai_knowledge.yaml --help` bzw. `--help` mit positional arg prüft (Argument-Parsing in [`transcript_miner.main.parse_arguments()`](src/transcript_miner/main.py:193)).
- [x] Ergänze Secret-Scan als verpflichtenden PR-Check (Workflows vorhanden: [`gitleaks.yml`](.github/workflows/gitleaks.yml:1)); dokumentiere, wie man lokal scannt.

## P0 — Konfig & Kompatibilität

- [x] Harmonisiere Konfig-Schema vs. Beispielkonfigs: entferne oder migriere `youtube.filter.*` Felder in YAMLs, sodass sie dem Pydantic-Schema [`common.config_models.YoutubeConfig`](src/common/config_models.py:11) entsprechen (Konflikt beschrieben in [`docs/config.md`](docs/config.md:79)).
- [x] Definiere eine eindeutige Output-Pfad-Policy („legacy“ `output.path` vs. neue `root_path`+`use_channel_subfolder`) und stelle sicher, dass Doku und Implementierung synchron sind (siehe [`OutputConfig.get_path()`](src/common/config_models.py:56) und Beispiel in [`docs/config.md`](docs/config.md:20)).
- [x] Ergänze Validierungs-/Fehlermeldungen für häufige Konfig-Fehler (z.B. leere `youtube.channels`) und verifiziere die Ausgabe in [`transcript_miner.main.main()`](src/transcript_miner/main.py:245) (Guard: [`transcript_miner.main.main()`](src/transcript_miner/main.py:303), Test: [`tests/test_config.test_empty_youtube_channels_fails_fast_with_clear_message()`](tests/test_config.py:20)).
- [x] Definiere eine konsistente Behandlung von `${VAR}`-Substitutionen für Pfade und API-Key (Pfad-Resolver: [`common.path_utils.resolve_paths()`](src/common/path_utils.py:12), API-Key-Resolver: [`ApiConfig.resolve_api_key_env_vars()`](src/common/config_models.py:151)).

## P0 — Robustheit / Fehlerhandling (Mining-Pipeline)

- [x] Ergänze Retry/Backoff/Timeout-Handling für YouTube Data API Requests (Quota/`HttpError`) und dokumentiere die Policy; Wrapper: [`transcript_miner.youtube_client._execute_with_retries()`](src/transcript_miner/youtube_client.py:107) (Defaults: [`DEFAULT_YOUTUBE_API_TIMEOUT_SEC`](src/transcript_miner/youtube_client.py:27)).
- [x] Ergänze differenziertes Handling für „kein Transkript“ vs. „TranscriptsDisabled“ vs. echte Fehler und schreibe diese Gründe in Metadaten/Logs (Result-Typ: [`TranscriptDownloadResult`](src/transcript_miner/transcript_models.py:16), Download: [`download_transcript_result()`](src/transcript_miner/transcript_downloader.py:105), Persistenz: [`process_single_video()`](src/transcript_miner/video_processor.py:436)).
- [x] Stelle sicher, dass „kein Transkript“ nicht zu endlosen Retries führt (persistierter Skip-State in `skipped.json`, siehe [`process_single_video()`](src/transcript_miner/video_processor.py:484)), aber auch nicht stillschweigend als Erfolg gezählt wird (Return `True` = „handled“, separate Skip-Liste).
- [x] Prüfe Progress-Logik auf Konsistenz: Dateinamen-Pattern vs. „already processed“ File-Check (Regex in [`sync_progress_with_filesystem()`](src/transcript_miner/video_processor.py:81) vs. Pfadcheck in [`is_video_already_processed()`](src/transcript_miner/video_processor.py:154)).
- [x] Definiere und implementiere eine Policy für „progress.json corruption“ (Backup/Restore/Corrupted-Move in [`load_processed_videos()`](src/transcript_miner/video_processor.py:77), Atomic Write in [`atomic_save_processed_videos()`](src/transcript_miner/video_processor.py:128); Doku: „Policy: progress.json Corruption / Recovery“ in [`README.md`](README.md:238)).
- [x] Definiere und implementiere eine Retention-/Cleanup-Policy für Output-Dateien (Transkripte + optionale `_meta.json`) (Implementierung: [`cleanup_old_outputs()`](src/transcript_miner/video_processor.py:182), Aufruf: [`process_channel()`](src/transcript_miner/main.py:57); Doku: [`README.md`](README.md:249)).
- [x] Ergänze robuste Fehlerzähler/Telemetry-Nutzung (stable API: [`common.telemetry.record_pipeline_error()`](src/common/telemetry.py:95); Callsites u.a. in [`process_channel()`](src/transcript_miner/main.py:57), [`process_single_video()`](src/transcript_miner/video_processor.py:436), [`transcript_miner.youtube_client._execute_with_retries()`](src/transcript_miner/youtube_client.py:107)).

---

## P1 — Tests (Unit + Integration)

- [x] Richte eine minimale Test-Suite ein, die ohne echte YouTube/OpenAI Calls läuft (Startpunkt: [`tests/conftest.py`](tests/conftest.py:1); Offline-Guard als `autouse`-Fixture umgesetzt).
- [x] Globale Import-Monkeypatches bereinigt (kein `patch_imports` im Repo); stattdessen gezielte `monkeypatch`/Fixtures pro Test + zentraler Offline-Guard in [`tests/conftest.py`](tests/conftest.py:1).
- [x] Schreibe Unit-Tests für Output-Dateinamengenerierung und Sanitizing (Funktion: [`common.utils.generate_filename_base()`](src/common/utils.py:138)). (done 2025-12-25; Tests: [`tests/test_generate_filename_base.py`](tests/test_generate_filename_base.py:1))
- [x] Schreibe Unit-Tests für `${VAR}`-Substitution und Pfadauflösung (Funktionen: [`common.path_utils.resolve_paths()`](src/common/path_utils.py:12), [`common.path_utils._resolve_path()`](src/common/path_utils.py:90)). (done 2025-12-25; Tests: [`tests/test_config.py`](tests/test_config.py:100)).
- [x] Schreibe Unit-Tests für Progress-Handling inkl. Corruption-Backup + Atomic Write (Funktionen: [`load_processed_videos()`](src/transcript_miner/video_processor.py:212), [`atomic_save_processed_videos()`](src/transcript_miner/video_processor.py:269)). (done 2025-12-25; Tests: [`tests/test_progress_handling.py`](tests/test_progress_handling.py:22))
- [x] Schreibe Unit-Tests für Filesystem↔progress Sync (Funktion: [`sync_progress_with_filesystem()`](src/transcript_miner/video_processor.py:483)) mit tempdir-fixtures. (done 2025-12-25; Tests: [`tests/test_progress_handling.py`](tests/test_progress_handling.py:123))
- [x] Schreibe Unit-Tests für Keyword-Suche (Funktion: [`search_keywords()`](src/transcript_miner/transcript_downloader.py:103)) inkl. Whole-Word/Case-Insensitive. (done 2025-12-25; Tests: [`tests/test_search_keywords.py`](tests/test_search_keywords.py:1))
- [x] Schreibe Integration-Tests für Channel-Processing mit gemocktem Resolver + Downloader (Einstieg: [`transcript_miner.main.process_channel()`](src/transcript_miner/main.py:57)). (done 2025-12-25; Tests: [`tests/test_process_channel_integration.py`](tests/test_process_channel_integration.py:1))
- [x] Schreibe Smoke-Tests für CLI `--help` und Importpfade (Einstieg: [`transcript_miner.main.parse_arguments()`](src/transcript_miner/main.py:229)). (done 2025-12-25; Tests: [`tests/test_smoke.py`](tests/test_smoke.py:1))

## P1 — Doku (perfekt, übersichtlich, konsistent)

- [x] Ergänze im Quickstart in [`README.md`](README.md:18) einen Abschnitt „Systemvoraussetzungen“ inkl. expliziter Python-Version, `uv` und „optional deps“.
- [x] Ergänze in [`README.md`](README.md:50) eine klare Empfehlung, welcher Entry-Point genutzt werden soll (`python -m transcript_miner`) und wann.
- [x] Ergänze in [`README.md`](README.md:83) eine vollständige „Output Reference“ (Dateitypen, Metadatenfelder, Progress-Datei) und verlinke auf die erzeugenden Stellen (z.B. [`process_single_video()`](src/transcript_miner/video_processor.py:185), [`_create_metadata()`](src/transcript_miner/video_processor.py:642)).
- [x] Ergänze in [`docs/config.md`](docs/config.md:1) eine „Kompatibilitätsmatrix“: unterstützte/ignorierte Felder; markiere `youtube.filter.*` als deprecated mit Migrationsempfehlung.
- [x] Ergänze in [`README.md`](README.md:1) im Abschnitt „Secrets / `.env`“ eine Troubleshooting-Sektion („Key fehlt“, „Key ungültig“, „keine Transkripte“) mit Verweisen auf Fehlerstellen (z.B. [`run_miner()`](src/transcript_miner/main.py:158)).
- [x] (Cleanup) Entferne verbleibende Legacy-Referenzen auf den entfernten Corrector in Doku/Backlog.
  - Hinweis: Das Legacy-Tooling für Korrektur-Artefakte (`tools/quality_check.py corrections`) ist deaktiviert (siehe [`tools/quality_check.main()`](tools/quality_check.py:261)); der Fokus ist „fetch → analysis“ (siehe [`README.md`](README.md:458)).
- [x] Entferne oder archiviere `Temp`-Inhalte sauber: `docs/temp.md` entfernt (inkl. Link-Fixes in [`CHANGELOG.md`](CHANGELOG.md:5)).
- [x] Ergänze eine „Troubleshooting & Logs“-Sektion, die Logfiles systematisch erklärt (Startpunkt: [`logs/README.md`](logs/README.md:1)).

- [x] **Secrets / `.env` Konsistenz:** Form/Keys in `.env` einheitlich halten und `.env` ↔ `.env.example` synchronisieren.
  - DoD: `.env.example` enthält alle erwarteten Variablen (ohne Werte) und entspricht den in Code/Doku verwendeten Namen.
  - DoD: `.env` bleibt lokal/ungetracked und folgt dem gleichen Format (eine Variable pro Zeile, keine „Konfig“ außer Secrets).

---

## P1 — UX / CLI

- [x] **Verbesserung der Terminal-Anzeige beim Download von Transkripten**
  - Ziel: Saubere Progress-Anzeige und Status-Indikatoren.
  - Beschreibung: Implementierung eines sauberen Progress-Bars (z.B. `0% === 100%`) mit Indikatoren für Info (I), Error (E) und Warning (W). Details sollen nur in den Logs erscheinen, nicht im Terminal.
  - DoD: Terminal bleibt übersichtlich; Fortschritt ist jederzeit erkennbar; Fehler/Warnungen werden kompakt signalisiert.
  - Implementierung: Integration von `rich.progress` in `src/transcript_miner/main.py`.

---

## P2 — Release / Versioning

- [x] Definiere eine Release-Checkliste (Version bump, changelog update, tag) und pflege sie in [`CHANGELOG.md`](CHANGELOG.md:1) unter „Unreleased“. (done 2025-12-25)
- [x] Setze eine Policy für SemVer und aktualisiere `version` in [`pyproject.toml`](pyproject.toml:3) passend zum Funktionsumfang.
  - Evidence: Packaging-Version in [`pyproject.toml`](pyproject.toml:3); SemVer-Policy/Bump-Regeln in [`CHANGELOG.md`](CHANGELOG.md:20).
- [x] Ergänze eine „Support“-Sektion in [`README.md`](README.md:1) (z.B. „Experimental Corrector“, „API quota limits“, „Known issues“). (done 2025-12-25)


---

## Diskussion / Design-Entscheidungen (LLM als Kernfeature)

Kontext: Aktuell ist die Offline-Analyse heuristisch/deterministisch (Index/Aggregation). Für das gewünschte Kernfeature („Intelligenz“: komplexe, themengetriebene Auswertung über viele Transkripte) braucht es eine skalierende LLM-Pipeline.

- [x] **Entscheidung: LLM Output-Formate (JSON vs. Markdown/Text) & Readability**
  - Ist-Zustand: `3_reports/run_.../report.json` speichert den LLM-Output als String unter `output.content`.
  - Umsetzung: zusätzlich wird deterministisch ein derived Report (`report.md` oder `report.txt`) plus `metadata.json` geschrieben (Writer: [`_write_derived_report_and_metadata()`](src/transcript_ai_analysis/llm_runner.py:73); Validator entfernt).
  - Decision Record: [`docs/adr/0007-llm-output-formats-json-vs-markdown.md`](docs/adr/0007-llm-output-formats-json-vs-markdown.md:1)
  - Zu klären:
    - Wann/warum ist `report.json` (maschinenlesbar, stabiler Schema-Container) nötig?
    - Wann/warum zusätzlich `report.md` oder `report.txt` als menschenlesbares Artefakt?
  - Ziel: First-class „Human-readable“ Output ohne die Auditierbarkeit/Schema-Stabilität der JSON-Artefakte zu verlieren.

### LLM Report: Rolling Window (Short-term Transkripte + Long-term Analysen)

- [x] **Spezifiziere die Rolling-Window-Semantik für den LLM-Report** (Short-term vs. Long-term).
  - Evidence: Doku/Spezifikation in [`docs/analysis/llm_report_rolling_window_semantics.md`](docs/analysis/llm_report_rolling_window_semantics.md:1).
  - Kontext: Transkripte werden per Retention-Policy typischerweise nach ~30 Tagen gelöscht (siehe `output.retention_days`, Doku: [`README.md`](README.md:317)).
  - **Begriffe (normativ, für Implementierung & Tests):**
    - **Run-Zeitpunkt**: `analysis_run_at_utc` als UTC ISO-8601 String (z.B. `2025-12-26T00:00:00Z`) wird als expliziter Parameter/Metadatum geführt.
      - Hinweis: *keine* implizite Systemzeit in der Semantik; ein Re-Run mit gleicher `analysis_run_at_utc` und gleichen Inputs muss identischen Output erzeugen.
    - **Short-term Window**: `short_term_window_days` (Default/Richtwert aus Retention: i.d.R. 30 Tage; Quelle: [`README.md`](README.md:317)).
    - **Long-term Window**: `long_term_window_days` (Lookback bis max. 365 Tage; keine älteren Analysen berücksichtigen).
  - **Inputs (normativ):**
    - **Short-term Inputs**: aktuelle Transkript-Artefakte, die zum Run verfügbar sind (Transkript-Dateien + Metadaten) und innerhalb des Short-term Cutoffs liegen.
    - **Long-term Inputs**: frühere LLM-Analyse-Artefakte unter `3_reports/run_.../` (Ist-Artefakte: [`docs/adr/0007-llm-output-formats-json-vs-markdown.md`](docs/adr/0007-llm-output-formats-json-vs-markdown.md:1) + Outputs in [`README.md`](README.md:448)).
  - **Zeit- & Cutoff-Regeln (normativ):**
    - Alle Cutoffs werden in **UTC** berechnet.
    - Short-term Cutoff: `analysis_run_at_utc - short_term_window_days`.
    - Long-term Cutoff (nur für historische Analysen): `analysis_run_at_utc - long_term_window_days`.
    - **Grenzfall-Definition:** Items mit Zeitstempel exakt auf dem Cutoff sind **inkludiert** (`>= cutoff`).
  - **Sortierung (normativ, stabil):**
    - Short-term Transkripte: aufsteigend nach `(transcript_published_at_utc, video_id)`.
    - Historische Analysen: aufsteigend nach `(source_analysis_date_utc, source_analysis_id)`.
  - **Dedupe (normativ):**
    - Short-term Transkripte werden auf `video_id` dedupliziert.
      - Tie-break: wenn dasselbe `video_id` mehrfach vorkommt, gewinnt deterministisch das Element mit lexikografisch kleinstem `transcript_path` (oder falls kein Pfad vorhanden: kleinstes `source`-Feld; sonst: stabile Input-Reihenfolge).
    - Historische Analysen werden auf `source_analysis_id` dedupliziert.
  - **DoD (Akzeptanzkriterien):**
    - Eine schriftlich eindeutige Auswahlfunktion ist dokumentiert (Inputs → gefilterte Short-term Transkripte + gefilterte Long-term Analysen), inkl. Cutoff, Sort, Dedupe und Tie-break.
    - Semantik ist testbar ohne Systemzeit (Tests können `analysis_run_at_utc` fixieren).
    - Es ist explizit dokumentiert, welche Zeitstempel-Felder für Transkripte/Analysen herangezogen werden (und was passiert, wenn ein Zeitstempel fehlt: deterministische Default/Skip-Regel, nicht still).

- [x] **Definiere das menschenlesbare Report-Markdown-Layout** (z.B. `report.md` zusätzlich zu `report.json`; siehe Output-Format-ADR).
  - Evidence: Layout-/Section-Kontrakt in [`docs/analysis/llm_report_markdown_layout_provenance_guardrails.md`](docs/analysis/llm_report_markdown_layout_provenance_guardrails.md:1).
  - Kontext: Output-Format-ADR ist **Accepted** (Option B: JSON + derived human-readable Artefakt; siehe [`docs/adr/0007-llm-output-formats-json-vs-markdown.md`](docs/adr/0007-llm-output-formats-json-vs-markdown.md:49)).
  - **Dateiname/Artefakt-Policy (normativ, ohne neue APIs):**
    - `report.json` bleibt kanonisch (ADR), zusätzlich *optional* ein derived human-readable Report (ADR).
    - **Vorschlag (kontextualisiert durch ADR):** derived Artefakt heißt `report.md` wenn `output.content` Markdown ist, sonst `report.txt` (beides liegt neben `report.json` unter `3_reports/run_.../`).
    - DoD: pro Run existiert **maximal ein** derived human-readable Artefakt (entweder `report.md` oder `report.txt`), das diffbar ist (UTF-8, `\n` line endings).
  - **Minimaler Layout-Kontrakt (normativ):**
    - Report ist Markdown (falls `report.md`) und beginnt mit genau **einem** H1-Titel.
    - Der Report enthält direkt danach eine **YAML Frontmatter-ähnliche Header-Sektion** (oder eine Markdown-Tabelle) mit Pflichtfeldern:
      - `analysis_run_at_utc`
      - `short_term_window_days`
      - `long_term_window_days`
      - `short_term_inputs_count`
      - `long_term_sources_included_count`
      - `long_term_sources_date_range_utc` (min/max)
      - `generator` (mindestens: Pipeline-Komponente/Name; keine neuen Felder außerhalb von Text erfinden, aber im Reporttext ist das zulässig)
    - DoD: Die Pflichtfelder sind so platziert, dass ein einfacher Parser (regex/line-based) sie zuverlässig extrahieren kann.
  - **Sections (normativ, Reihenfolge fix):**
    1. `## Executive Summary` (max. N Bulletpoints; N als Prompt-/Policy-Wert dokumentieren)
    2. `## Short-term Findings` (neu aus Transkripten)
    3. `## Long-term Findings` (übernommen/fortgeschrieben)
    4. `## Evidence Index` (nur Short-term Evidence)
    5. `## Sources` (Long-term Quellenliste)
    6. `## Method Notes` (Definitionen, Cutoffs, Dedupe)
    - DoD: Die Section-Titel sind stabil und werden als Akzeptanzkriterium getestet (exact match).

- [x] **Trenne im Report strikt nach Provenienz:**
  - Sektion A: „Neu aus aktuellen Transkripten abgeleitet“ (jede Aussage rückführbar auf Transcript-Evidence).
  - Sektion B: „Aus früheren Analysen übernommen/fortgeschrieben“ (jede Aussage markiert als *inherited* inkl. Quelle).
  - **Provenienz-Regeln (normativ):**
    - Jede einzelne Aussage/These im Report trägt exakt eine Provenienz-Klasse: `new` oder `inherited`.
    - **new**:
      - Muss mindestens einen Evidence-Pointer auf Transcript-Text enthalten (Snippet/Quote + Referenz; Evidence-Pattern siehe Prompt-Spezifikation: [`docs/analysis/llm_prompt_spec_strict_json_evidence.md`](docs/analysis/llm_prompt_spec_strict_json_evidence.md:1)).
      - Darf optional einen Confidence/Status tragen.
    - **inherited**:
      - Muss sichtbar gekennzeichnet sein (z.B. Prefix `[inherited]` pro Bullet/Absatz) und eine Quellenreferenz tragen.
      - Quellenreferenz enthält mindestens `source_analysis_date_utc` und einen stabilen Source-Identifier.
        - Identifier ist **nicht** zwingend ein neuer JSON-Feldname; erlaubt ist z.B. ein relativer Pfad unter `3_reports/run_.../` als String im Markdown.
  - **DoD (Akzeptanzkriterien):**
    - Kein Statement ohne Provenienz-Markierung.
    - Jede `inherited`-Aussage hat genau eine Source-Referenz und diese Source liegt innerhalb des Long-term Fensters.
  - Evidence: Provenienz-Regeln + Prefix-Konvention in [`docs/analysis/llm_report_markdown_layout_provenance_guardrails.md`](docs/analysis/llm_report_markdown_layout_provenance_guardrails.md:101).

- [x] **Drift-/Kaskadenfehler-Kontrollen für Long-term-Übernahmen definieren** (Guardrails).
  - **Guardrails (normativ):**
    - `inherited` Inhalte sind **nie Evidence** für `new` Inhalte.
      - Konkret: Evidence Index referenziert ausschließlich Short-term Transcript-Snippets; niemals Text aus früheren Reports.
    - Keine self-referential loops:
      - Eine `inherited` Aussage darf nicht auf eine Quelle referenzieren, die aus dem aktuellen Run stammt.
      - Quellenkette darf max. 1 Hop haben (keine „A übernimmt von B übernimmt von C“ im gleichen Artefakt).
    - Jede `inherited` Aussage trägt einen Status (normativ, Enum): `confirmed`, `stale`, `needs_revalidation`, `ambiguous`.
    - **Downgrade/Removal Policy (normativ):**
      - Wenn eine `inherited` Aussage im aktuellen Short-term Fenster **nicht** bestätigt werden kann, muss sie mindestens auf `needs_revalidation` oder `stale` gesetzt werden (Regel im Text dokumentieren).
      - Wenn eine `inherited` Aussage im Long-term Fenster liegt, aber Source fehlt/unlesbar ist: Status zwingend `ambiguous` und Aussage muss im Report in eine separate „Invalid inherited items“ Liste.
  - **DoD (Akzeptanzkriterien):**
    - Status-Enum wird im Report konsistent verwendet (case-sensitive, exact match).
    - Für mindestens 3 exemplarische Fälle ist dokumentiert, wie sich Status über Runs entwickeln kann (reine Doku; keine neue Implementierung).
  - Evidence: Guardrails+Status-Enum in [`docs/analysis/llm_report_markdown_layout_provenance_guardrails.md`](docs/analysis/llm_report_markdown_layout_provenance_guardrails.md:144); Offline-Checks sind heute prompt-/layout-basiert (Validator entfernt).

- [x] **Evidenz-/Transparenz-Checks als Offline-Validierung definieren** (Report-Lint/Validator).
  - Legacy-DoD (Validator entfernt): hätte mindestens erkennen sollen:
    - unmarkierte (fehlende Provenienz) Aussagen,
    - Long-term Aussagen ohne Source-Referenz,
    - „neue“ Aussagen ohne Transcript-Evidence-Pointer.
  - **Zusätzliche Checks (normativ, minimal):**
    - `inherited` Aussagen, deren `source_analysis_date_utc` außerhalb des Long-term Fensters liegt.
    - Evidence-Pointer, die auf nicht existente Dateien zeigen (Pfad existiert nicht) oder auf das falsche PROFILE_ROOT zeigen.
    - Duplicate Statements (identischer Text nach Normalisierung), getrennt nach `new` und `inherited`.
  - Output (Vorschlag, als solcher markieren): ein maschinenlesbarer Report (z.B. JSON) mit `counts` + `findings[]`, damit Regressionen in CI auffallen.
  - Evidence: Legacy-Validatoren wurden entfernt; Checks sind konzeptuell dokumentiert, aber nicht mehr enforced.

- [x] **Visualisierung im Report: Mermaid als Default, Plots optional (Artefakt-Policy festlegen)**.
  - DoD: Mermaid-Diagramme sind im Markdown eingebettet (diffbar, keine Binary-Artefakte als Default).
  - **Mermaid Default (normativ):**
    - Der Report enthält standardmäßig genau ein Mermaid-Diagramm unter `## Method Notes`.
    - Template (Beispiel, ohne Quotes/ohne Parentheses in `[]`):
      - Diagrammtyp: `flowchart TD`
      - Knoten: `ShortTerm`, `LongTerm`, `Synthesis`, `Report`
    - DoD: Diagramm ist syntaktisch valide Mermaid und zeigt die Datenflüsse (Short-term Inputs + Long-term Sources → Synthesis → Report).
  - Optional (Vorschlag, explizit optional): Wenn Plots genutzt werden, müssen Pfad/Layout/Namenskonventionen festgelegt werden (stabile Dateinamen, keine stillen Overwrites; Ablage z.B. unter dem PROFILE_ROOT).
  - Evidence: Mermaid-Default-Kontrakt in [`docs/analysis/llm_report_markdown_layout_provenance_guardrails.md`](docs/analysis/llm_report_markdown_layout_provenance_guardrails.md:248).

### LLM-Analyse Skalierung (Chunking / Multi-Job / Agents / RAG)

- [x] **Policy: Entscheidung Single-Run vs. Sharding/Multi-Job (messbar + auditierbar)**
  - Ziel: deterministische Entscheidung, wann wir einen LLM-Run über viele Transkripte machen vs. Map/Reduce sharden.
  - Primärmetrik: **Token-Budget (geschätzt)** statt Zeichen (Kontextfenster ist token-basiert).
    - Umsetzungsidee: `T_in_est = sum(t_i)` mit `t_i = ceil(chars_i / chars_per_token) + overhead`.
    - `chars_per_token` pro Modell einmal kalibrieren (Stichprobe) und als „estimator_version“ versionieren.
    - Vorhandene Basis im Repo: Zeichenbudgetierung/Selektion in [`run_llm_analysis()`](src/transcript_ai_analysis/llm_runner.py:239) und Token-Count Fallback in [`common.utils.calculate_token_count()`](src/common/utils.py:165).
  - Policy (2 Regeln):
    - **Hard Budget**: `T_in_est <= B_single` wobei `B_single = floor((C - P - R) * m)`.
    - **Coverage Guard**: zusätzlich Limits für `N` und Dominanz eines einzelnen Transkripts (z.B. `share_max = max(t_i)/T_in_est`).
  - Audit/Logs (DoD): Entscheidung + Inputs loggen (`model`, `C,P,R,m`, `T_in_est`, `N`, Längenstatistiken, `share_max`, trigger).
  - Doku/ADR-Anker: Token-Sizing [`docs/adr/0003-sizing-token-budget.md`](docs/adr/0003-sizing-token-budget.md:1), Skalierungs-ADR [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:1).
  - Evidence: Vollständige Policy (Inputs/Formel/Guards/Audit-Felder) in [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:102).

- [x] **Entscheidung: 1 Job vs. Multi-Job Pipeline** (Map/Reduce).
    - Decision Record: [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:1)
    - Vorschlag (Diskussionsgrundlage):
      - Job A (*Compression/Extraction*): pro Transcript/Chunk strukturierte Notizen (JSON) erzeugen, irrelevantes wegkürzen.
      - Job B (*Synthesis*): nur die kompakten Notizen aggregieren (pro Channel + global) und „eigentliche Analyse“ machen.
    - Ziel: nicht „alles in einen Prompt“, sondern deterministisch chunked Inputs + kleinere Prompts.
    - Evidence: Decision „Default Multi-Job, Single-Job als Small-Run“ in [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:192).

- [x] **Entscheidung: Agents/Abhängigkeiten** (mehrere Jobs mit `depends_on`, z.B. Extract → Critique → Synthesize).
    - Decision Record: [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:1)
    - Referenz-Konzept (Architektur-Skizze): „LLM extractor“ / Embeddings optional in [`docs/architecture.md`](docs/architecture.md:413).
    - Evidence: Job-DAG/`depends_on` Konzept + Regeln in [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:214).

- [x] **Entscheidung: Embeddings/Vector Store** (RAG) ab welcher Datenmenge.
    - Decision Record (Trigger-Kriterien): [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:1)
    - Separater ADR (Embeddings/Index-Optionen): [`docs/adr/0002-embeddings-vector-db.md`](docs/adr/0002-embeddings-vector-db.md:1)
    - Trigger: wenn Transcript-Mengen/Token-Budget zu groß werden, Retrieval über Chunk-Index statt Vollprompt.
    - Referenz (bestehende ADRs): [`docs/adr/0002-embeddings-vector-db.md`](docs/adr/0002-embeddings-vector-db.md:1), Token-Sizing: [`docs/adr/0003-sizing-token-budget.md`](docs/adr/0003-sizing-token-budget.md:1).
    - Evidence: RAG-Trigger-Kriterien + Audit-Felder in [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:228).

- [x] **Konfig-Semantik: „LLM Instructions“ pro Config/Topic**.
    - Decision Record: [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:1)
    - Idee: pro Config definieren, *was* analysiert werden soll (Stocks vs. Elektroautos vs. US-Politik), inkl. Prompt(s) / Job-Definitionen.
    - Wichtig: nicht „Investment-Thesen“ als festes Schema; Prompt steuert Output-Format.
    - Evidence: Instructions-pro-Config Semantik in [`docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md`](docs/adr/0008-llm-scaling-jobs-agents-rag-instructions.md:253) und Ist-Schema-Doku in [`docs/config.md`](docs/config.md:426).


---

## P0 — Outputs/Logs: Pfad-Policy + Cleanup (Fix + self-healing)

### P0.1 Fix: Logs/Outputs nicht unter `config/` ablegen

Problem: Wenn Configs unter [`config/`](config:1) liegen und YAML relative Pfade nutzt (`logs/...`, `./output/...`), werden diese Pfade **relativ zur Config-Datei** aufgelöst (Policy in [`docs/config.md`](docs/config.md:127), Code: [`common.config.load_config()`](src/common/config.py:23) + Resolver [`common.path_utils.resolve_paths()`](src/common/path_utils.py:12)). Das führt zu unbeabsichtigten Artefakten unter `config/logs/` oder `config/output/`.

- [x] **Fix**: Beispiel-Configs und Doku so anpassen, dass Logs/Outputs im Repo-Root landen (z.B. `../logs/...` und `../output/...` statt `logs/...` und `./output/...`).
  - DoD: Alle Beispiel-YAMLs unter [`config/`](config:1) sind konsistent.
  - DoD: Erklärung/Policy ist in [`docs/config.md`](docs/config.md:127) klar.

### P0.2 Cleanup-Policy (always-on, 30 Tage) + „tote Dateien“

Richtlinie: Dieser bisherige Pfad war ein Fehler; Artefakte dürfen verschoben/gelöscht werden:
- Wenn aktuell → verschieben an den korrekten Ort.
- Wenn älter als 30 Tage → löschen.

- [x] **Always-on Cleanup**: Jeder Programmdurchlauf soll Daten >30 Tage löschen.
  - Scope mindestens:
    - Outputs unter `1_transcripts/` (derzeit schon konfigurierbar via `output.retention_days`, Policy in [`README.md`](README.md:317) und Implementierung in [`cleanup_old_outputs()`](src/transcript_miner/video_processor.py:182)).
   - Logs unter `logs/` (aktuell keine zentrale Retention-Policy im Code).
    - DoD: Policy ist dokumentiert + Tests decken das Verhalten ab.

- [x] **Repo-Hygiene / Artefakt-Audit**: Unklare/ungenutzte Ordner und „Altlasten“ sichtbar machen und bereinigen.
  - Scope-Beispiele:
    - leere/ungenutzte Top-Level-Ordner (z.B. [`data/`](data:1)) entfernen **oder** mit kurzer README dokumentieren (Zweck, Ownership).
    - alte Logfiles im Repo-Root (`logs/`) nach der 30-Tage-Policy löschen.
  - DoD: Audit-Report (z.B. in `docs/audit/`) + klare Delete-Policy (keine stillen Deletes ohne Report).

- [x] **Self-healing / „Dead files“ Finder**: Tool/Runner, der unbeabsichtigte Artefakt-Orte findet (z.B. `config/**/logs/*`, `config/**/output/*`, verwaiste `_meta.json`, etc.) und nach Policy bewertet:
  - verschieben (wenn „aktuell“ und eindeutig zuordenbar)
  - löschen (wenn >30 Tage)
  - reporten (wenn unklar)
  - DoD: erzeugt Report-Audit (z.B. `docs/audit/cleanup_report.json`) und ist offline/risikoarm.

- [x] **Cleanup: Build-/Packaging-Artefakte nicht im Workspace liegen lassen**
  - Problem/Beispiel: `src/youtubetranscriptminer_v2.egg-info/` (typisches Setuptools/Build-Artefakt) taucht nach lokalen Builds/`uv`-Runs auf.
  - DoD: Artefakte werden gelöscht (lokal) und via `.gitignore` verhindert, dass sie jemals committed werden.

</details>


---

<a id="ai_stack_todo"></a>
# TODO — ai_stack (Home-Server)

Kontext (fix): **VPN-only Zugriff**, ohne Port-Forwarding, via **Tailscale**. Services sollen localhost-only gebunden sein (`127.0.0.1:<port>`) und im Tailnet bevorzugt via **Tailscale Serve (HTTPS)** genutzt werden.

SSOT (Projektzielbild): `docs/prd-tool-owui-transcript-miner-sync.md:1` und `docs/workflow_openwebui_hole_neueste_videos.md:1`.

## P0 — Muss als Nächstes (VPN-only)
- [x] Tailscale ist installiert + Service aktiv (`tailscaled` läuft)
- [x] `sudo tailscale up` durchgeführt und geprüft: `tailscale status`, `tailscale ip -4`
- [x] **SSOT Naming-Konvention (Repo + Docker + Host) + Migrationsplan (Zero-Confusion)**
  - Ziel: **keine `_`-Namen** mehr für Docker-Objekte/Host-Pfade; Repo-Filenames bleiben **kebab-case** (keine neuen `_`), Python bleibt **snake_case** (PEP8).
  - Repo (Dateien/Ordner):
    - Ordner/Services: `kebab-case/` (z. B. `open-webui/`, `mcp-transcript-miner/`)
    - Docs/Scripts: `kebab-case.md`, `kebab-case.sh` (keine neuen `_` in Filenames)
    - Code: Python-Packages/Module weiterhin `snake_case` (kein Refactor/Import-Bruch)
- Docker Compose (Project/Stack):
  - Pro Stack `name:` ist kurz & eindeutig: `owui`, `tm`, `context6`, `qdrant`, `emb-bench`
  - Keine `container_name` (default), stattdessen eindeutige Service-Namen/Network-Aliases
    - Ausnahme: `watchdog` setzt `container_name: watchdog` (explizit gewuenscht)
  - Docker Network (shared):
    - Externes Netzwerk: `ai-stack` (bewusst als einziges “ai-stack” erlaubt)
    - DNS-Kollisionen vermeiden (verbindlich):
      - Option A (empfohlen): Service-Namen global eindeutig (z. B. `owui`, `tm`, `context6`, `qdrant`)
      - Option B: `networks: aliases:` mit Stack-Prefix (z. B. `owui-svc`, `context6-svc`)
  - Docker Volumes (state):
    - Schema: `<service>-<purpose>` (z. B. `owui-data`, `tm-data`, `context6-cache`, `qdrant-data`, `emb-bench-cache`)
    - Migration: old→new Copy, danach alte Volumes löschen; keine “Legacy-Namen” in Doku verewigen
  - Docker Images (lokal gebaut):
    - Schema: `<service>:<tag>` (z. B. `tm:latest`, `context6:latest`)
  - Host-Pfade (Bind Mounts; keine Secrets):
    - Root: `/srv/ai-stack/`
    - Struktur: `/srv/ai-stack/<stack>/{data,cache,logs}` + `/srv/ai-stack/backups`
    - Beispiele: `/srv/ai-stack/tm/data`, `/srv/ai-stack/owui/data`, `/srv/ai-stack/context6/cache`
  - Secrets/Config (Host):
    - Repo: `.env` (secrets-only) + `.config.env`/`<service>/.config.env` (non-secrets) (alles gitignored; niemals committen)
  - DoD (Abnahme):
    - Repo-Audit: `rg` findet keine verbotenen Namen mehr (z. B. `_` in Docker-Objekt-Namen, `*_default` Networks, doppelte Token)
    - Host-Audit: `docker volume ls`/`docker network ls`/`docker images` zeigen nur noch Schema-konforme Namen
    - Smoke-Test läuft grün: `./scripts/smoke_test_ai_stack.sh --up --build`
- [ ] Tailnet-HTTPS aktivieren + Open WebUI via Tailscale Serve bereitstellen:
  - [x] Tailnet hat Serve aktiviert (Admin-Konsole)
  - [x] `sudo tailscale serve --bg --https=443 http://127.0.0.1:3000`
  - [x] URL prüfen: `sudo tailscale serve status`
  - [x] Test im VPN am Client: Open WebUI lädt über die `https://<node>.<tailnet>.ts.net/` URL
  - [x] Zugriff von extern verifizieren (Handy LTE + Tailscale): Browser im VPN erreicht die URL ohne Tunnel-Probleme

## P0 — TranscriptMiner × Open WebUI Sync Tool (v0, core-first)
Ziel: Runs aus Open WebUI starten (non-blocking) und **Summary-`.md` pro Video** in eine Knowledge Collection indexieren (keine Raw-Transkripte, keine Reports).

- [x] Tool-Server „Transcript Miner“ implementiert: `mcp-transcript-miner/` (ein Tool in Open WebUI)
  - [x] `POST /runs/start` + `GET /runs/{run_id}` (Run trigger + Status)
  - [x] `GET /configs` / `GET|POST /configs/{config_id}` (Configs discover + edit)
  - [x] `POST /index/transcript` (Upload → Processing-Poll → Add-to-Knowledge, idempotent via SQLite)
  - [x] `POST /sync/topic/{topic}` (indexiert per-video Summaries eines Topics)
  - [x] Repo: Secrets/Env finalisieren (SSOT: `docs/policy_secrets_environment_variables_ai_stack.md:1`)
  - [x] Compose lädt keine Repo-`.env` mehr; Start nur via expliziten `--env-file` (pro Stack config+secrets)
  - [x] Doku/Runbook + `.env.example` decken alle benötigten Keys ab
  - [x] Repo: `.env` mit echten Werten befüllt (und niemals committen):
    - [x] `YOUTUBE_API_KEY` + `OPENROUTER_API_KEY` (für Runs mit LLM-Analyse)
    - [x] `OPEN_WEBUI_API_KEY` (JWT Bearer; `OWUI_API_KEY` ist deprecated Alias)
    - [x] `OPEN_WEBUI_API_KEY` Rotation nicht nötig (nie im Repo/Logs/Chat sichtbar)
  - [x] Secrets vs Config sauber trennen (nur Secrets in `.env`)
    - [x] `.env` darf nur enthalten: Tokens/Keys/Passwörter/private Keys (keine Pfade/Hosts/IDs/Mappings)
    - [x] Nicht-Secrets in `.config.env` bzw. `<service>/.config.env` (Policy + Doku)
  - [x] `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON`/`OPEN_WEBUI_KNOWLEDGE_ID` optional; Default ist Knowledge-Name = Topic (OWUI API Resolution)
  - [ ] Betriebs-Workflow: Mapping ändern ohne “Gefummel” (klarer Runbook-Schritt; ggf. Tool-Reload/Restart dokumentieren)
- [x] YouTube Transcript Block (HTTP 429) entschärfen: stabile Fetch-Strategie (IP/Proxy/Cookies), Runbook + Tests
  - [x] Runbook + Tests dokumentiert (`docs/runbook_youtube_429_mitigation.md`)
  - [x] Webshare‑Proxy getestet (OK)
- [ ] Smoke-Test Runbook:
  - [x] Repo: Runbook + Script vorhanden (`docs/runbook_smoke_test.md:1`, `scripts/smoke_test_ai_stack.sh:1`)
  - [x] Services laufen (Compose `ps` zeigt `healthy`)
  - [x] Host: `curl http://127.0.0.1:3000/` → `200`
  - [x] Tool→OWUI API erreichbar (Auth OK; `/api/v1/files/` → `200`)
  - [x] 1 Topic (z. B. `investing`), 2–3 Videos: Summaries in Knowledge indexed (verifiziert via `/api/v1/knowledge/<id>/files`)
  - [x] Chat-Retrieval in Open WebUI manuell prüfen (Collection aktivieren, Frage stellen, Sources prüfen)
  - [x] Falls YouTube 429/Block: `youtube_cookies.txt` unter Repo-Root hinterlegen (gitignored) + `YOUTUBE_COOKIES_FILE=/host_secrets/youtube_cookies.txt` in `mcp-transcript-miner/.config.env` setzen

## P1 — Betrieb & Sicherheit
- [x] Open WebUI localhost-only + Healthcheck/Log-Rotation in Compose
- [x] Geplante Runs: investing alle 3h via systemd Timer (Auto-Sync aktiviert)
- [ ] OpenWebUI + OpenRouter + Tavily + Jupyter Code Interpreter (Tool-Loop) Setup/Plan
- [ ] Backup-Ziel definieren (Volumes):
  - [x] Repo: Runbook + Scripts für Backup/Restore vorhanden (`docs/runbook_backup_restore.md:1`, `scripts/README.md:1`)
  - [x] Repo: systemd Timer Templates vorhanden (`scripts/systemd/ai_stack_backup.timer`, `scripts/systemd/ai_stack_backup.service`)
  - [x] Host: Backup-Verzeichnis festlegen (z. B. `/srv/ai-stack/backups`, chmod `700`) + systemd Timer installieren/aktivieren
  - [x] `owui-data` sichern (Open WebUI Data)
  - [x] `tm-data` sichern (Runs/State/SQLite/Backups)
  - [x] TranscriptMiner Output Root sichern (bind-mount; Zielpfad: `/home/wasti/ai_stack_data/transcript-miner/output`)
- [ ] Offene Entscheidung: “Schöne URL” für Open WebUI im VPN-only Setup
  - [ ] Option A (einfach): Tailscale Serve URL so lassen (ts.net) + Bookmark-Titel/Shortcut am Client
  - [ ] Option B (Client-Alias): Hosts/DNS am Client setzen (Merknamen wie `openwebui` → zeigt auf Server/Tailscale), weiterhin Zugriff via Serve-URL (TLS Hostname bleibt ts.net)
  - [x] Option C (Tailscale Custom Domain/Hostname): eigene Domain/Hostname in der Tailscale Admin Console für Serve konfigurieren (merknamen.ts.net)
  - [ ] Option D (Reverse Proxy): Caddy/Traefik + eigene Domain + TLS (mehr Setup/Wartung; später)
  - [ ] Option E (ohne Serve): Open WebUI direkt an Tailscale-IP binden und per `http://<tailscale-ip>:3000` nutzen (kein HTTPS; öffnet Port im Tailnet)

## P2 — Observability / Wartung
- [ ] Ressourcen-/Disk-Checks: freier Speicher, Docker-Volume-Wachstum, Backup-Größe
- [x] Watchdog-Plan dokumentiert (CPU/Temperatur/Disk): `docs/plan_watchdog_monitoring.md`
- [x] Watchdog-Container implementiert (CPU/Temperatur/Disk + Docker-Hygiene)
- [ ] Docker Housekeeping Policy: `docker system prune` (vorsichtig) / Image-Retention
- [ ] Repo-Hygiene (lokal): unversionierte Artefakte aufräumen (z. B. `transcript-miner/.venv`, `emb-bench/.cache_out`, `emb-bench/runs*`, alte `open-webui/tool-imports/backup_*.json`)
- [ ] (Optional) automatische Security Updates fürs OS (Unattended-Upgrades)

## P3 — Phase 2 / Erweiterungen (später)
- [ ] Traefik/Caddy + HTTPS + Domain (nur wenn gewünscht; nicht nötig für VPN-only)
- [ ] Qdrant Setup planen (Compose + `.env.example` + PRD) und in Gesamtarchitektur einhängen
  - [x] Standalone Qdrant Stack (localhost-only) vorhanden: `qdrant/docker-compose.yml:1` (`http://127.0.0.1:6333`)
- [x] Open WebUI Setup (Compose + Doku), Image-Tag gepinnt (0.7.2)
- [x] Neues Tool: `context6` (PoC) — „persönliches Context7“ (Fetch → Normalize → Chunk → Search/Get)
  - [x] PRD: `docs/prd_context6_poc_working_draft.md:1`
  - [x] MCP Server PoC: `mcp-context6/` (`POST /mcp`)
  - [ ] Fokus: reproduzierbare „Doc-Snapshots“ (Version/Commit/URL) + idempotentes Re-Indexing (Dedupe per `source_id`)
  - [ ] Export/Indexing in Open WebUI Knowledge Collections (PoC optional, später)
- [ ] Open WebUI Tool UX (optional, wenn sinnvoll):
  - [ ] Open WebUI Function (Action) „Sync“ Button + Status/Toasts via `__event_emitter__` evaluieren
  - [ ] Fallback Polling UX: `GET /runs/{run_id}` alle X Sekunden
- [ ] Open WebUI RAG Setup (Collections):
  - [ ] Collection Mapping klären: Name vs ID als Referenz im Tool
  - [ ] Collections anlegen (IDs notieren), Topic/Config → Collection zuordnen
- [ ] Transcript Pull/Push Strategie für YouTube definieren (Proxy/Rate-Limits, falls Datacenter blockt)
