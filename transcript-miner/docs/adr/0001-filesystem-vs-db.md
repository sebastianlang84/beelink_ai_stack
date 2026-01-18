# ADR 0001: Filesystem vs. Datenbank für Analyse-Artefakte

Status: **Proposed** (noch keine Entscheidung)

## Problem

Wir müssen festlegen, ob Analyse-Ergebnisse langfristig **file-basiert** (JSON/JSONL/CSV/…) bleiben oder ob wir eine **Datenbank** (SQLite/DuckDB/Postgres) als primäre Datenhaltung verwenden.

## Kontext / Evidenz

- Zielbild: „fetch → analysis“, Corrector ist nicht mehr Kernziel (siehe [`TODO.md`](../../../TODO.md:17) und Corrector-Hinweis in [`README.md`](../../README.md:455)).
- Bestehender Analysis-Output (Batch 1) ist file-basiert und deterministisch: `manifest.json`, `transcripts.jsonl`, `audit.jsonl` (siehe [`write_analysis_index()`](../../src/transcript_miner/transcript_index/runner.py:44)).
- Analysis Batch 2+ Artefakt-Layout ist als Doku-Spezifikation file-basiert definiert (siehe „Batch 2+ Artefakt-Layout“ in [`docs/architecture.md`](../architecture.md:151)).
- Backlog fordert explizit einen Decision Record (siehe [`TODO.md`](../../../TODO.md:135)).

## Entscheidungskriterien (aus Backlog / DoD)

Die relevanten Kriterien sind im Backlog explizit benannt (siehe [`TODO.md`](../../../TODO.md:138)):

- **Reproduzierbarkeit/Determinismus:** Idempotente Re-Runs, klare Overwrite-Policy, `schema_version`/Kompatibilitätsregeln (siehe Artefakt-Policy in [`docs/architecture.md`](../architecture.md:145) und Batch-1 Determinismus in [`README.md`](../../README.md:395)).
- **Query-/Aggregation-Use-Cases:** Stock-Coverage, globale Reports, Dedup/Merge über `video_id` (siehe Batch-2 Layout + Aggregates in [`docs/architecture.md`](../architecture.md:151)).
- **Deployment/Operations-Komplexität:** lokal/CI/offline ohne zusätzliche Infrastruktur.
- **Datenvolumen/Performance:** inkrementelle Updates, Indexing, Kosten/Komplexität von Joins/Aggregationen (Zahlen sind aktuell **unsicher**; Messung ist separate Aufgabe, siehe [`docs/adr/0003-sizing-token-budget.md`](0003-sizing-token-budget.md:1)).
- **Auditierbarkeit:** Evidence/Traceability (welches Transcript/Video/Channel führte zu welcher Aussage), kompatibel zu bestehenden Miner-Outputs inkl. `progress.json` (siehe Output-/Audit-Referenzen in [`README.md`](../../README.md:241)).

## Optionen

### A) File-basiert (JSON/JSONL/CSV; optional Parquet)

**Vorteile**

- Einfaches Deployment (keine DB-Operations)
- Gut für Repro/Archivierung (Artefakte sind Dateien)
- Passt zum bereits dokumentierten Artefakt-Vertrag („Batch 2+“ Layout) (siehe [`docs/architecture.md`](../architecture.md:151))

**Nachteile**

- Queries/Joins/Aggregationen werden schnell unhandlich
- Inkrementelle Updates/Dedup/Upserts sind komplizierter
- Ad-hoc Analysen benötigen meist zusätzliche Tools/Skripte (z.B. `jq`, Pandas) und saubere Konventionen

### B) Embedded DB (SQLite oder DuckDB)

**Vorteile**

- Stark für lokale Analysen/Queries; Single-File
- Besser für Incremental Updates/Indizes
- Kann als *abgeleiteter Query-Index* aus file-basierten Artefakten gebaut werden (ohne Source-of-Truth-Wechsel)

**Nachteile**

- Schema/Versionierung muss gepflegt werden
- Locking/Concurrency begrenzt
- Backup/Restore muss explizit definiert werden (auch wenn es „nur eine Datei“ ist)

### C) Server DB (z.B. Postgres)

**Vorteile**

- Concurrency/Skalierung; robuste Indizes
- Zentrale Datenhaltung für Multi-User/Service-Betrieb

**Nachteile**

- Deployment/Operations deutlich komplexer
- Bricht den „offline-first“ Charakter (CI/Local) ohne zusätzliche Infra (oder komplexe Mocks)

## Kriterienvergleich (qualitativ)

| Kriterium | A) Files | B) Embedded DB | C) Server DB |
|---|---|---|---|
| Repro/Archivierung | **sehr gut** (Artefakte sind immutable-ish) | gut (wenn DB als *abgeleitetes* Artefakt behandelt wird) | mittel (stärker „stateful“, Dump/Restore nötig) |
| Determinismus (Re-Runs) | **gut** (Policy/Schemas in Artefakten, z.B. `schema_version`) | gut, aber erfordert Schema-Migrationsdisziplin | gut, aber migrations/ops-lastiger |
| Ad-hoc Queries/Joins | mittel (Tooling nötig) | **sehr gut** | **sehr gut** |
| Inkrementelle Updates/Indexing | mittel (Upserts/Indices „manuell“) | **gut** | **sehr gut** |
| Ops/Komplexität (lokal/CI) | **sehr niedrig** | niedrig–mittel | **hoch** |
| Auditierbarkeit/Traceability | **sehr gut** (File-Refs/Evidence in JSONL) | gut (wenn File-Refs erhalten bleiben) | gut (dito) |
| Backups | einfach (Copy/Snapshot) | mittel (konsistentes Copy/Backup definieren) | komplex (DB-Backups/Retention/Restore) |

Hinweis: Performance-/Volumen-Aussagen sind ohne Messung **unsicher** (siehe Sizing-ADR [`docs/adr/0003-sizing-token-budget.md`](0003-sizing-token-budget.md:1)).

## Entscheidung

Noch offen.

### Empfehlung (Proposed)

**Empfehlung:** **Filesystem bleibt Source-of-Truth** für Analyse-Artefakte (JSON/JSONL; optional spaltenorientiert wie Parquet als *zusätzliches* Export-Format). Eine **embedded DB (SQLite/DuckDB)** ist optional als **abgeleiteter Query-Index** zulässig. Eine **Server-DB (Postgres)** ist für den aktuellen Offline-/CLI-Fokus nicht empfohlen.

**Begründung (entlang der Kriterien):**

- Der Artefakt-Vertrag ist bereits file-basiert spezifiziert (Batch 2+ Layout inkl. Manifest/Audit/Dedup) in [`docs/architecture.md`](../architecture.md:151); das reduziert Risiko und verhindert „Schema-Drift“.
- Determinismus/Idempotenz ist als Prinzip explizit gefordert und bei file-basierten Artefakten leichter auditierbar (Batch-1/Batch-2-Policy; siehe [`README.md`](../../README.md:395) und [`docs/architecture.md`](../architecture.md:145)).
- Auditierbarkeit (Evidence/Traceability bis mindestens `{video_id, channel_namespace, transcript_path}`) ist in der Artefakt-Spezifikation bereits normativ (siehe [`docs/architecture.md`](../architecture.md:145)).
- Embedded DB liefert Query-Komfort, ohne den Source-of-Truth zu verschieben (DB wird aus `*.jsonl`/`*.json` generiert und kann jederzeit neu aufgebaut werden).

### Praktische Entscheidungsregel (wenn später neu bewertet wird)

1. Source-of-Truth bleibt file-basiert (Artefakte) für Repro (kompatibel zu Batch 1).
2. SQLite/DuckDB als optionaler Query-Index, sobald die ersten Aggregations-Usecases umgesetzt sind.
3. Postgres nur, wenn ein Service/Mehrbenutzerbetrieb erzwungen wird.

## Migrationspfad (falls DB gewählt wird)

Ziel: DB-Nutzung hinzufügen, ohne bestehende Runs/Artefakte zu brechen und ohne die Auditierbarkeit zu verlieren.

### Phase 0 (Baseline): File-Artefakte sind kanonisch

- Artefakte gemäß Spezifikation unter `analysis/batch2/` sind der Vertrag (siehe [`docs/architecture.md`](../architecture.md:151)).

### Phase 1 (Minimallösung): „Import from existing outputs“ (empfohlen)

- DB wird **aus vorhandenen Artefakten** gebaut (Import):
  - `analysis/batch1/transcripts.jsonl` liefert Transcript-Refs (`video_id`, `channel_namespace`, Pfade), siehe Feldübersicht in [`README.md`](../../README.md:371).
  - `analysis/batch2/*.jsonl`/`*.json` liefert Mentions/Canonicalization/Aggregates/Duplicates/Audit (siehe Layout in [`docs/architecture.md`](../architecture.md:151)).
- Die DB gilt als **cacheable/derivable**: sie kann gelöscht und deterministisch aus Artefakten neu erzeugt werden.

### Phase 2 (Optional): „Write-through“

- Pipeline schreibt weiterhin File-Artefakte als Source-of-Truth und schreibt *zusätzlich* in die DB.
- Risiko: doppelte Write-Paths; daher nur sinnvoll, wenn die DB als „erste Klasse“ Query-Schicht benötigt wird.

## Minimales DB-Schema (Skizze, für Import/Export)

Hinweis: Dies ist eine **konzeptionelle** Skizze (keine implementierte Migration im Repo).

```sql
-- Runs / Manifeste (Batch 1/2)
CREATE TABLE runs (
  run_fingerprint TEXT PRIMARY KEY,
  batch TEXT NOT NULL,                 -- z.B. "batch1" | "batch2"
  schema_version INTEGER NOT NULL,
  created_at_utc TEXT,                 -- Audit-Metadatum
  source_batch1_run_fingerprint TEXT   -- für batch2: Referenz auf batch1
);

-- Transcript-Refs (aus batch1 transcripts.jsonl)
CREATE TABLE transcript_refs (
  video_id TEXT NOT NULL,
  channel_namespace TEXT NOT NULL,
  transcript_path TEXT NOT NULL,
  metadata_path TEXT,
  output_root TEXT,
  published_date TEXT,
  PRIMARY KEY (video_id, channel_namespace, transcript_path)
);

-- Mentions (aus batch2 mentions.jsonl)
CREATE TABLE mentions (
  mention_id TEXT PRIMARY KEY,
  video_id TEXT NOT NULL,
  channel_namespace TEXT NOT NULL,
  raw TEXT NOT NULL,
  kind TEXT,
  confidence REAL,
  snippet_sha256 TEXT,
  char_start INTEGER,
  char_end INTEGER
);

-- Canonicalization (aus batch2 canonicalization.jsonl)
CREATE TABLE canonicalization (
  mention_id TEXT PRIMARY KEY,
  symbol TEXT,
  name TEXT,
  provider TEXT,
  status TEXT,
  candidates_json TEXT,
  notes TEXT
);

-- Audit-Events (aus batch1/batch2 audit.jsonl)
CREATE TABLE audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  video_id TEXT,
  channel_namespace TEXT,
  message TEXT,
  details_json TEXT
);
```

**Schema-Quelle/Mapping:** die Felder sind direkt aus den in der Architektur-Doku beschriebenen Artefakten ableitbar (siehe JSON-Schemas in [`docs/architecture.md`](../architecture.md:221)).

## Export/Import-Strategie

- **Import (Files → DB):** Parser liest `*.jsonl` zeilenweise und schreibt Tabellen (Mentions/Canonicalization/Audit/Refs). Das ist robust gegen große Datenmengen (streaming) und passt zum JSONL-Format.
- **Export (DB → Files):**
  - Minimal: Export als die gleichen JSONL/JSON Artefakte (damit bestehende Consumer/Tests weiter funktionieren).
  - Optional: zusätzliche Exporte (z.B. CSV/Parquet) als *derived artefacts* für Data-Science-Workflows (konkret ist im Repo noch **nicht** festgelegt).

## Backups / Restore

- **A) Files:** Backup via Copy/Snapshot des Run-Roots inkl. `analysis/` und Referenzen auf Miner-Outputs; deterministic rebuild bleibt möglich, solange Inputs vorhanden sind.
- **B) Embedded DB:** Backup-Policy muss explizit festlegen, *wann* ein konsistenter Snapshot gezogen wird (z.B. nur wenn kein Writer läuft). Details sind tool-/engine-spezifisch und daher aktuell **unsicher**.
- **C) Server DB:** benötigt eigene Backup-/Retention-/Restore-Prozeduren; das ist zusätzliche Operations-Komplexität.

## Konsequenzen

- Artefakt-Vertrag für Batch 2+ ist ein Blocker (siehe [`TODO.md`](../../../TODO.md:43)), unabhängig von DB-Option.
- Wenn eine DB eingeführt wird, darf sie die Auditierbarkeit nicht verschlechtern: Transcript-Refs und Evidence-Hashes müssen erhalten bleiben (siehe Audit-Invariante in [`docs/architecture.md`](../architecture.md:145)).

## Offene Punkte / ToDo

- Konkrete Query-Usecases sammeln (z.B. „Mentions pro Zeitraum/Channel/Ticker“).
- Datenvolumen + Laufzeit messen (siehe Token-/Sizing-ADR: [`docs/adr/0003-sizing-token-budget.md`](0003-sizing-token-budget.md:1)).
- (Optional) Auswahl embedded Engine (SQLite vs. DuckDB) anhand konkreter Query-Patterns; ohne Messung/Use-Cases ist die Wahl **unsicher**.
