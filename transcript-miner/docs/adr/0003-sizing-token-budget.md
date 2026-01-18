# ADR 0003: Sizing/Token Budget, Chunking und Context-Window

Status: **Proposed** (Methodik definiert, Zahlen folgen aus Messung)

## Problem

Wir müssen abschätzen, wie groß die Transcript-Mengen (Tokens) bei 10–15 Channels über 1–2 Wochen werden, um eine robuste Chunking-/Aggregation-Strategie festzulegen.

## Kontext / Evidenz

- Der Miner schreibt pro Video `output/data/transcripts/by_video_id/*.txt` und optional `.meta.json` (siehe Output-Übersicht in [`README.md`](../../README.md:300)).
- Token-Counting ist im Code vorhanden (optional via `tiktoken` mit Fallback): [`common.utils.calculate_token_count()`](../../src/common/utils.py:165).

## Methodik (messbasiert)

1. Stichprobe N Transkripte (z.B. 20–50 Dateien unter `output/data/transcripts/by_video_id/*.txt`).
2. Pro Datei messen:
   - `chars`, `words`, `tokens` (falls `tiktoken` installiert; sonst Fallback-Approximation).
3. Extrapolation:
   - `videos_total = channels * videos_per_week_per_channel * weeks`
   - `total_tokens ≈ videos_total * avg_tokens_per_video`
4. Entscheidung:
   - Chunk-Größe + Overlap so wählen, dass ein LLM-Call sicher innerhalb des Context-Windows bleibt.

## Optionen

- A) Chunking + deterministische Aggregation (Standard)
- B) Chunking + Retrieval (falls Embeddings/Vector-Index gewählt; siehe [`docs/adr/0002-embeddings-vector-db.md`](0002-embeddings-vector-db.md:1))

## Entscheidung

Noch offen (Zahlen fehlen). Chunking wird als Default angenommen.

## Offene Punkte / ToDo

- Mess-Skript/Workflow festlegen (z.B. kleiner CLI/Tooling-Command) und Ergebnisse als Report-Artefakt ablegen.
