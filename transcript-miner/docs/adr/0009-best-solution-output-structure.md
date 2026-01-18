# ADR 0009: Best-Solution Output-Struktur (Global Dedup + Reports/History)

Status: **Proposed**

## Problem

Die aktuelle Output-Struktur ist teilweise inkonsistent (Mischung aus nummerierten Ordnern und Channel-Ordnern) und unterstützt kein effizientes globales Deduplizieren von Transkripten und Summaries über verschiedene Runs hinweg. Zudem fehlt eine klare Trennung zwischen "aktuellen" Reports und einer auditierbaren Historie (History Bundles).

## Kontext / Evidenz

- In [`README.md`](../../README.md:280) wurde bereits ein Ziel-Layout skizziert.
- [`TODO.md`](../../../TODO.md:43) fordert eine "Best-Solution Output-Struktur" mit Global Dedup.
- [`docs/adr/0001-filesystem-vs-db.md`](0001-filesystem-vs-db.md) hat das Filesystem als Source-of-Truth bestätigt.

## Entscheidung

Wir führen eine neue, kanonische Output-Struktur ein, die auf `video_id` als globalem Schlüssel basiert.

### Ziel-Struktur (Kanonisch)

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

### Kernprinzipien

1.  **Global Dedup (Canonical Store):** Transkripte und Summaries werden genau einmal unter `output/data/transcripts/by_video_id/` bzw. `output/data/summaries/by_video_id/` gespeichert. Alle Runs (unabhängig vom Topic) nutzen diese zentrale Quelle.
2.  **Atomic Writes:** Alle Schreibvorgänge in den Canonical Store erfolgen atomar (`.tmp` -> `rename`).
3.  **Current vs. History:**
    -   **Current Reports:** Unter `output/reports/<topic>/` liegt immer der aktuellste Report eines Tages für Menschen gut auffindbar.
    -   **History Bundles:** Unter `output/history/<topic>/...` wird jeder Run mit allen Inputs, Prompts und Zwischenergebnissen vollständig archiviert.
4.  **Topic-basiert:** Reports und Historie sind nach `topic` (aus der Config) gruppiert.

## Konsequenzen

- Bestehende Miner-Logik muss auf den neuen Pfad-Resolver umgestellt werden.
- Migration: Bestehende Daten in `1_transcripts/` und `2_summaries/` müssen schrittweise in den Canonical Store überführt werden (Dual-Read/Write).
- `OutputConfig` in `src/common/config_models.py` muss erweitert werden, um die neuen Pfade zu unterstützen.

## Migration-Plan

1.  **Phase 1: Dual-Read.** Der Miner prüft zuerst den neuen Canonical Store. Wenn dort nichts gefunden wird, sucht er im Legacy-Pfad.
2.  **Phase 2: Canonical-Write.** Neue Transkripte werden immer in den Canonical Store geschrieben.
3.  **Phase 3: Report-Redirection.** Reports werden primär unter `output/reports/` und `output/history/` abgelegt.
4.  **Phase 4: Cleanup.** Sobald die Migration stabil ist, können Legacy-Ordner (`1_transcripts`, `2_summaries`, `3_reports`) nach einer Übergangsfrist entfernt werden.
