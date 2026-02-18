# Policy — Was in Qdrant indexiert wird (ai_stack)

Status: superseded by `docs/adr/20260218-qdrant-indexing-boundaries.md` (detail background retained here).

Ziel: Klar definieren, **welche Texte** als Vektoren in Qdrant landen, welche Metadaten als Payload gespeichert werden, und wie wir Collection-Namen/Versionierung handhaben.

Grundsatz: **Qdrant speichert nur Vektoren + Filter-Metadaten**, der „Source of Truth“ für den Volltext bleibt im jeweiligen Service (Files/SQLite).

---

## 1) Einheit der Indexierung: „Chunk“

Wir indexieren **Chunks** (nicht ganze Repos / ganze Webseiten / komplette Reports).

Warum:
- bessere Retrieval-Qualität (granular)
- weniger Kontext-Müll
- stabile IDs/Dedupe pro Chunk möglich

---

## 2) Collection-Strategie

### 2.1 Pro Embedding-Modell / Dimension eine Collection

Qdrant Collections haben eine feste `vector.size` (Dim). Deshalb:
- **eine Collection pro (embedding_model, dim)** oder
- **bewusst** nur ein Modell/dim im gesamten Stack.

Empfohlene Namenskonvention:
- `context6_chunks__qwen3_8b__4096` (Beispiel)

Minimal (PoC):
- `context6_chunks` solange wir genau **ein** Modell/dim nutzen.

---

## 3) Point-ID / Dedupe

Point-ID soll stabil und idempotent sein:
- `point_id = chunk_id` (hash-basiert, stabil über Re-Indexing)

Damit kann „Upsert“ Duplikate vermeiden und Updates ersetzen.

---

## 4) Payload-Schema (Filter + Traceability)

Payload-Felder (Keyword/Filter):
- `source_id` (z. B. `sha256(type:canonical_uri)` bei context6)
- `snapshot_id` (Version/Snapshot für reproducible runs)
- `doc_id` (stabile Dokument-ID)
- `chunk_id` (redundant, aber praktisch)

Payload-Felder (Debug/Traceability, optional):
- `url` (oder `url_or_path`)
- `title`
- `heading_path`

Wichtig:
- Volltext **nicht** in Qdrant-Payload speichern (zu groß, schlechtere Performance, doppelte SSOT).
- Volltext bleibt in Files/SQLite; Qdrant liefert `chunk_id` + Score.

Indexing-Optimierung:
- Für häufige Filterfelder `source_id`, `snapshot_id`, `doc_id` Payload-Index anlegen (Schema: `keyword`).

Quelle: Qdrant Docs (Payload Index / Tenant Index / Multitenancy).

---

## 5) Was indexieren wir konkret (ai_stack)

### 5.1 context6 (PoC)
- Index: normalisierte Doku-Chunks (Markdown/Text) aus GitHub/Crawl/Local.
- Collection: `context6_chunks` (PoC), später ggf. `context6_chunks__<model>__<dim>`.
- Lookup: `search` liefert Treffer → `get_chunk` holt Volltext aus SQLite.

### 5.2 emb-bench
- Für Benchmarks optional: temporäre Collections pro Run (z. B. `emb_bench_<ts>`), oder In-Memory Backend.
- Payload minimal: `doc_id` (für Mapping).

### 5.3 transcript-miner (optional später)
- Falls wir Retrieval über Summaries/Reports wollen: indexiere **Summary-Chunks** pro Video (nicht Raw-Transkripte), Payload mit `video_id`, `topic`, `published_at`.
- Aktuell: Open WebUI Knowledge wird als RAG-Store genutzt; Qdrant ist dafür nicht zwingend.

---

## 6) Index-Scope: Wer entscheidet „was rein darf“?

Wichtig: Qdrant entscheidet **nicht**, welche Inhalte indexiert werden. Qdrant speichert nur das, was ein Indexer ihm als (Chunk → Vektor + Payload) schickt.

### 6.1 context6 (PoC)
- Scope wird über **Source-Konfiguration** bestimmt (z. B. GitHub include/exclude, Crawl-Allowlist, Local include/exclude).
- Ergebnis: Der Indexer fetched/normalisiert/chunkt nur das, was die Source-Regeln zulassen.

### 6.2 RooCode (Codebase Indexing, externes Tool)
Laut RooCode Docs (Feature „Codebase Indexing“):
- Scope wird über **Ignore-Patterns** gesteuert: `.gitignore` + zusätzlich `.rooignore`.
- Zusätzlich gelten feste Filter: Binary/Images werden übersprungen, Dateien > ~1MB werden nicht indexiert.
- Chunking ist intern (Tree-sitter/Markdown-Header/Fallback) und ist in der UI typischerweise nicht fein parametrisierbar.

Praxis:
- Wenn du nicht willst, dass “alle Files” in einem Repo indexiert werden: `.rooignore` (oder `.gitignore`) entsprechend pflegen.
- Template: `.rooignore.example` (nach `.rooignore` kopieren und anpassen).
