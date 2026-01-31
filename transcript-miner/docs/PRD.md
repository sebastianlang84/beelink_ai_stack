# TranscriptMiner – Product Requirements Document (PRD)

**Current Version: v2.2**
**Last updated: 2025-12-30 01:48 CET (Europe/Vienna)**

## 1) Problem & Kontext

YouTube-/Podcast-Transkripte sind lang, fehlerhaft (ASR = Automatic Speech Recognition) und verteilt über viele Channels. Du willst daraus verlässlich:

- **Coverage (Topics/Entities):** Welche Themen/Entities werden von wie vielen YouTubern erwähnt? (Stocks sind nur ein möglicher Entity-Typ)
- **Wissensextraktion:** Kernaussagen, Thesen, Katalysatoren, Risiken, Zahlen/Behauptungen (mit Unsicherheits-Flag).
- **Reports:** Wiederholbar, versioniert, nachvollziehbar.

Wichtig: Pipeline soll deterministisch auditierbar sein (so weit möglich), und LLM (Large Language Model)-Einsatz soll budgetiert und bei Bedarf skalierbar (Sharding/Multi-Agent) sein.

---

## 2) Zielbild (Was ist „done“?)

Ein CLI-Tool, das für eine Menge Transkripte (N Videos) in einem Lauf:

### MVP (Minimal nutzbares Produkt) – Phase 1

1) **Ingest (inkrementell, idempotent):** Neue Videos/Transkripte laden (**nur das Delta**), lokal cachen.
- **Zielset** = Videos, die laut Config *in diesem Run* betrachtet werden sollen (z.B. `last_n: 5`).
- **Delta** = Videos/Artefakte, die im Zielset sind, aber lokal fehlen **und** für den nächsten Verarbeitungsschritt benötigt werden.
- **TTL-Regel (Time-To-Live):** Wenn `output/data/transcripts/by_video_id/` nach TTL gelöscht wurde, wird ein Transkript **nicht automatisch** erneut geladen, **solange** `output/data/summaries/by_video_id/<video_id>.summary.md` vorhanden ist.
- Re-Download passiert nur, wenn:
  - die Summary fehlt/ungültig ist, oder
  - `force_redownload_transcripts: true` gesetzt ist, oder
  - ein Run explizit „rebuild summaries“ verlangt.
- Beispiel `last_n: 5`: erster Run lädt 5; nächster Run lädt nur neue Videos (z.B. 1). Wenn ein lokales Transkript fehlt (gelöscht), zählt es **nur dann** als Delta, wenn die Summary ebenfalls fehlt oder ein Rebuild erzwungen wird.

2) **Video-Analyse (LLM, pro Video):** Extrahiert pro Video Topics/Entities in strukturierter Form (ohne Evidence/Confidence).

3) **Aggregation (ohne LLM):** Coverage-Stats (**creator_count, video_count**) + Duplikate zusammenführen. (`creator_count` = Anzahl Channels)

4) **Reporting:** Markdown-Report + maschinenlesbare Artefakte.

### Optional später (Phase 2 / PoC)

- Segmentierung/Chunking (nur wenn Kontext/Budget es erfordert)
- Confidence-Scoring (Relevanz/Sicherheit)
- Evidence/Belege (Snippets/Spans)

---

## 3) Ziele (MUST)

- MUST: Ingest ist inkrementell und idempotent: bereits vorhandene Videos/Transkripte werden nicht erneut geladen; fehlende, **benötigte** Artefakte werden nachgeladen.
- MUST: Coverage-Metriken pro Entity/Topic: **creator_count, video_count**. (`creator_count` = Anzahl Channels)
- MUST: Pro-Video strukturierter Output: Liste von Entities/Topics + einfache Highlights/Claims (ohne Belege).
- MUST: Reproduzierbarkeit: gleiche Inputs + gleiche Config → gleicher Output (bis auf LLM-Nondeterminismus).
- MUST: Sauberer Output-Vertrag (Dateipfade/Schema-Versionierung).
- MUST: „LLM-Budgetierung“: harte Limits (Tokens/Kosten) + Policy, wann Sharding statt Single-Run.
- MUST: Fehlerrobust: einzelne Videos dürfen fehlschlagen, Run soll weiterlaufen; Fehlerbericht.

---

## 4) Nicht-Ziele (NON-GOALS)

- Keine Kursprognosen/Trading-Signale.
- Keine Echtzeit-Feeds.
- Kein UI (vorerst). CLI + Dateien.
- Kein perfektes Fact-Checking im Web (optional später).
- Kein Evidence/Confidence im MVP (kommt optional später).

---

## 5) Use-Case

Einziger Kern-Use-Case: Aus einer großen Menge Transkripte Wissen generieren und so ablegen, dass es später wiederauffindbar, vergleichbar und über Zeiträume nutzbar ist.

### Was „Wissen“ hier bedeutet (MVP)

- **Knowledge Items (Wissenseinheiten) pro Video:** kurze, strukturierte Punkte.
- z.B. These, Argument, Risiko, Katalysator, Zahl/Statistik, Definition, Handlungsschritt (als Paraphrase).

**Einordnung (optional):** Items können später mit Scope (Art des Inhalts) und Domain (Themenbereich) getaggt werden; im MVP nicht nötig.

### Schwierigkeit (explizit)

Videos unterscheiden sich stark:

- Deep Dive: wenige Entities/Topics, viel Detail.
- Mention/News: vieles kurz.
- Makro/Allgemein: Tipps/Strategien, Regime, Politik/US, Tech/AI etc.

Im MVP: keine Klassifikation nötig. Optional später: Video-Kategorie + Scope-Kategorie.

---

## 6) Optional: Klassifikation (Phase 2)

### 6.1 Video-Kategorien (optional; Phase 2)

- deep_dive (wenige Topics/Entities, viel Detail)
- mixed (Mix aus Detail + kurzen Erwähnungen)
- broad (Makro/Allgemein, viele kurze Themen)

### 6.2 Scope-Kategorien pro Knowledge Item (optional; Phase 2)

- entity_focus (klar zu einer Entity/Topic)
- macro (Regime, Zinsen, Liquidität, Politik, Rahmenbedingungen)
- how_to (Tipps/Strategien/Prozesse)
- news (Ereignis/Update)

### 6.3 Domains (nur Filter; kein Stock-Bias)

- investing/stocks, investing/crypto, tech/ai, politics/us, macro, other

---

## 7) Scope & Pipeline (High-Level)

### Input

- Quellen-Definition (z.B. YouTube-Kanäle, Playlists) + Regeln (z.B. „letzte N Videos“)
- Transkripttext
- Metadaten: video_id, channel_id/namespace, title, date, url, language, duration

### Processing Stages

**Ingest (LLM-frei)**

- Inkrementeller Sync pro Quelle: Zielmenge bestimmen (z.B. „letzte 5 Videos“), nur das Delta nachladen (siehe Definition oben).
- Cache/Index aktualisieren, gelöschte Artefakte erkennen und **bei Bedarf** nachladen (abhängig davon, was für den nächsten Schritt fehlt).

**LLM Analysis (pro Video, policy-gesteuert)**

- Pro Video ein strukturierter JSON-Output (Entities/Topics + Highlights/Claims).

**Deterministic Aggregation (ohne LLM)**

- Coverage-Stats + Regeln zum Zusammenführen von Duplikaten.
- Optional: Cross-Report Vergleich (Delta).

**Reporting**

- Markdown + report.json.

**Optional später (Phase 2 / PoC)**

- Segmentierung/Chunking (nur wenn Kontext/Budget es erfordert)
- Confidence
- Evidence

---

## 8) Output-Vertrag (Artefakte & Ordner)

### 8.1 Output-Root pro Config (wichtig)

Globales Output-Root + Topic (empfohlen):

- `output.global`: `project_root/output/`
- `output.topic`: `investing`, `ai_knowledge`, …

### 8.2 Speicher-Schichten (Retention)

Die Schichten sind semantisch benannt (nicht short/long/persistent):

- **transcripts:** Roh-Transkripte (TTL = Time-To-Live) 30 Tage → werden gelöscht.
- **summaries:** pro Video verdichtetes Wissen (TTL 1 Jahr).
- **reports:** Reports/Aggregate über alle Summaries der Config (TTL ewig).

### 8.3 Ordnerlayout (global)

```
output/
├── data/
│   ├── transcripts/by_video_id/
│   ├── summaries/by_video_id/
│   └── indexes/<topic>/current/
├── reports/<topic>/
└── history/<topic>/<YYYY-MM-DD>/<HISTORY_BUNDLE>/
```

### 8.4 Current vs. History

- **History-Bundle:** Jede Report-Generierung landet in einem stabilen Bundle unter `output/history/<topic>/.../`.
- **Current Reports:** Für die schnelle Sicht werden Reports als Tagesdatei nach `output/reports/<topic>/report_de_<YYYY-MM-DD>.md` (bzw. `report_en_...`) kopiert.

### 8.5 Mindest-Artefakte (global layout)

- `output/data/indexes/<topic>/current/ingest_index.jsonl` (ewig)
- `output/data/summaries/by_video_id/<video_id>.summary.md` (Pro Video)
- `output/history/<topic>/<YYYY-MM-DD>/<HISTORY_BUNDLE>/aggregates/` (Aktuelle Aggregat-Daten pro Run)
- `output/reports/<topic>/report_de_<YYYY-MM-DD>.md` (Current)
- `output/reports/<topic>/run_manifest.json` (Current)

---

## 9) Datenmodelle (Schemas)

### 9.1 Canonical Entities

`CanonicalEntity: { type, canonical_id, display_name, aliases[], attributes{} }`

- type Beispiele: stock, crypto, person, product, topic
- `attributes{}` ist typ-spezifisch (optional)

### 9.2 VideoResult (LLM Output) – MVP

Minimal (MUST):

- `video_id, channel_id, title, published_at`
- `knowledge_items[]`:
  - `{ text, entities? }`

Optional (Phase 2 / PoC):

- `video_category?: deep_dive|mixed|broad`
- `knowledge_items[].scope?: entity_focus|macro|how_to|news`
- `knowledge_items[].domain?`

Hinweis: Klassifikation ist nützlich für Filter/QA, aber nicht nötig fürs MVP.

### 9.3 Aggregates

- Coverage per Entity/Topic
- Coverage per Channel
- Trend: Delta zu vorherigem Report (falls vorhanden)

Phase 2 (optional): Felder `confidence` und `evidence_*` können später ergänzt werden, ohne MVP-Schema zu brechen.

---

## 10) LLM-Policy (Single-Run vs Sharding)

Ziel: operational, messbar, deterministisch.

### Inputs für Entscheidung

- total_tokens_estimate
- num_videos
- max_context_tokens (Modell)
- expected_entity_density (heuristisch: Entity-Cues/1k chars; je nach Extractor-Pack)
- budget_limit (Tokens/€)

### Policy (MVP)

**Single-Run, wenn:**

- `total_tokens_estimate <= 0.6 * max_context_tokens` und
- `num_videos <= V_SINGLE_MAX` (Default 5–10) und
- entity_density nicht „hoch“

**Sharded pro Video, wenn:**

- `num_videos > V_SINGLE_MAX` oder
- einzelne Videos sehr lang (Token-Schätzer > threshold)

**Sharded pro Batch, wenn:**

- viele kurze Videos, aber Gesamtsumme zu groß

### Aggregation nach Sharding

Ausschließlich deterministisch (keine zweite LLM-Runde im MVP)

Konflikte via Regeln:

- gleiche canonical_id (bei gleichem type) → Vorkommen zusammenführen
- highlights/claims: Duplikate zusammenführen (z.B. hashing + fuzzy-match; ohne LLM)

### Nondeterminismus (ehrlich handhaben)

- Option `temperature=0` wo möglich
- Trotzdem: LLM kann variieren → speichere raw responses + prompt_hash

---

## 11) Konfiguration (config.yaml) – MUST Felder

### Output / Retention

- output.topic: z.B. stocks, ai, tech_ai, politics_us
- output.global: Default `project_root/output/`
- retention:
  - transcripts_days: 30 (Roh-Transkripte werden gelöscht)
  - summaries_days: 365 (verdichtete Video-Summaries)
  - reports_forever: true

### Sources / Ingest

- sources:
  - Liste von Quellen, z.B. `{ type: youtube_channel, channel_id, last_n: 5 }`
  - Sync-Regeln: last_n, optional since_date, optional include_shorts
- ingest:
  - cache_index_path: Default `output/data/indexes/<topic>/current/ingest_index.jsonl`
  - redownload_if_missing: true
  - skip_if_present: true
  - force_redownload_transcripts: false (Default)

### Extraction / LLM

- extractors (optional): z.B. stocks, crypto, people, products, topics
- llm:
  - provider, model, api_key_ref
  - max_tokens, temperature
  - budget: max_total_tokens, max_total_cost
  - policy: single_run_thresholds, shard_strategy

### Storage / Reporting

- reporting: templates, top_n, include_deltas

Optional später:

- preprocess (Chunking thresholds/size/overlap)
- confidence: on|off
- evidence: none|snippet|spans

---

## 12) Storage-Entscheidungen (MVP)

### MVP Default

- **Keine Datenbank im MVP.** Alle Artefakte sind Dateien (JSON/JSONL/CSV/Parquet + Markdown).
- Index/Manifest sind file-basiert (z.B. `output/data/indexes/<topic>/current/ingest_index.jsonl`).

### Optional später

- SQLite (z.B. für Indizes/FTS = Full-Text Search)
- Qdrant Vector-Store für semantische Suche und RAG (Retrieval-Augmented Generation)

**Rationale (praktisch):** Dateien sind im MVP am simpelsten und gut zu versionieren. Datenbanken/Vector-Stores bringen zusätzliche Komplexität (Schema/Migration, Embeddings/Drift, Kosten).

---

## 13) Qualität & Guardrails

### ASR-Fehler-Toleranz

Prompt: Transkripte können falsch sein → konservativ formulieren, keine Details erfinden.

### Keine Halluzinationen

MVP: Wenn unklar, lieber weglassen oder als „unsicher“ in highlights/claims formulieren.

### Bias-Hinweis

Channel-Bias: Clickbait, Confirmation Bias (Bestätigungsfehler) etc.

---

## 14) Observability (Metriken & Logs)

MUST:

- runtime pro stage
- tokens in/out pro LLM call
- cost estimate
- error counts pro stage
- coverage counts (#entities/#topics, #channels, #videos processed)

---

## 15) Akzeptanzkriterien (Definition of Done)

### MVP

- CLI run verarbeitet mindestens 50 Videos in einem Batch (mit Sharding).
- Erzeugt alle Mindest-Artefakte (Manifest, VideoResults, Coverage, Report, Errors).
- Coverage-Stats korrekt:
  - Für einen bekannten Testsatz ist creator_count (Channels) und video_count deterministisch reproduzierbar.
- LLM Budget wird eingehalten (Run bricht ab oder degradiert sauber, wenn Budget erreicht).
- Fehlertoleranz: einzelne kaputte Inputs stoppen nicht den ganzen Run.

---

## 16) Risiken / offene Punkte

- Entity-Parsing ist fehleranfällig (z.B. kurze Tokens, Homonyme). → Alias/Whitelist/Blacklist pro Extractor-Pack.
- Mehrsprachigkeit (DE/EN gemischt) → Sprache pro Video erkennen.
- Entity-Collision: gleiche Firma unterschiedliche Ticker/Region → Canonical-Entity-Regeln.
- LLM-Provider-Änderungen (Models/limits) → config-driven, keine hardcodes.

---

## 17) Referenz: Stock-Coverage Pack (aus dem früheren Canvas)

Dieses Pack ist ein Beispiel-Extractor für den Spezialfall „Finfluencer/Stocks“. Es ist optional und kann später als eigenes Pack aktiviert werden.

### Definition „Channel covert Stock X“

Ein Channel covert Stock X, wenn in den letzten N Videos mindestens ein Video existiert, in dem Stock X inhaltlich Thema ist.

„Inhaltlich Thema“ = mehr als Name-Dropping (z.B. Zahlen/News/Produkte/Bewertung/Strategie/Wettbewerb).

Ein Channel zählt pro Stock maximal 1× (Set-Logik).

### LLM Output (Beispiel-Schema; JSONL)

Dateiidee: `analysis/video_analysis.jsonl` (1 JSON pro Video)

Minimal:

- channel_id, video_id
- covered_stocks[] mit `{ ticker }`

Optional später (PoC): evidence (Belegsatz) und confidence (0..1)

### Aggregation / Outputs (Beispiel)

- ticker -> set(channel_id) → daraus ticker,count
- `aggregates/stock_coverage_counts.csv` (für Diagramm)
- `aggregates/stock_coverage_bar.png` (Balkendiagramm, z.B. matplotlib)
- Optional: `aggregates/stock_to_influencers.json`
- Optional später (PoC): `aggregates/coverage_evidence.jsonl`

### Prompt-Regeln (wichtig für Robustheit)

- Ausgabe nur JSON (keine Zusatztexte).
- Nenne nur Dinge, die wirklich Thema sind (keine Listen/Name-Dropping).
- Keine erfundenen Ticker.

### Typische Fehlerquellen (Stock-Pack)

- Homonyme („Apple“ als Frucht) → Ticker-Fokus + strenge Thema-Regel.
- Listen/Name-Dropping → Prompt-Regel „nicht zählen“.
- Schlechte Transkripte (ASR) → optional transcript_quality Feld.
- Ticker-Fakes → optional Whitelist/Blacklist.

---

## 18) Roadmap (kurz)

### MVP

- Deterministic pipeline + LLM extraction + coverage + report

### Next

- Cross-run trend/delta reports
- SQLite FTS Query CLI (entity/topic X → alle Trefferstellen im Transkript)

### Later

- Optional Vector-Store (Qdrant) + semantische Suche
- Fact-check module (optional web verify) mit klarer Kostenkontrolle

---

## 19) Glossar (Begriffe)

- MVP (Minimal nutzbares Produkt): kleinste Version, die schon nützlich ist.
- TTL (Time To Live): Aufbewahrungsdauer; danach wird gelöscht.
- LLM (Large Language Model): Sprachmodell für Extraktion/Zusammenfassung.
- FTS (Full-Text Search): Volltextsuche (z.B. in SQLite).
- Ingest: Quellen + Transkripte + Metadaten einlesen, validieren und cachen.
- Inkrementeller Sync: Bei jeder Ausführung Zielmenge (z.B. „letzte 5 Videos“) berechnen und nur das Delta nachladen.
- Delta: Videos/Artefakte, die im Zielset sind, aber lokal fehlen **und** für den nächsten Schritt benötigt werden.
- Idempotent: Mehrfaches Ausführen erzeugt keine doppelten Downloads/Artefakte.
- Extractor-Pack: Konfigurierbares Modul für einen Entity/Topic-Typ (Regeln + Alias + Output-Schema). Beispiele: stocks, crypto, people, products, topics.
- Entity/Topic: Ein „Ding“, das im Video vorkommt (z.B. Aktie, Coin, Person, Produkt, Thema).
- Chunking/Segmentierung (optional später): Text in mehrere Teile splitten, wenn Kontext/Budget es erzwingt.
- Confidence (optional später): Relevanz-/Sicherheitswert.
- Evidence (optional später): Beleg-Snippets/Spans aus dem Transkript.
