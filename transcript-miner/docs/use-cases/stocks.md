# Use-Case: Stock-Coverage & Investment Insights (Stocks) - Phase 1 (MVP)

Diese Dokumentation beschreibt den Use-Case für die Analyse von Finfluencer-Kanälen zur Extraktion von Aktien-Coverage und Makro-Insights gemäß **Phase 1 (MVP)** des [PRD](../PRD.md).

## 1. Zielsetzung (Phase 1)
Analyse einer Menge von Finfluencer-Channels, um eine **Coverage-Übersicht pro Aktie** zu erhalten.
- **Kernmetriken:** `creator_count` (Anzahl Influencer) und `video_count` (Anzahl Videos) pro Aktie.
- **Output:** Balkendiagramm und strukturierte Reports.

---

## 2. Analyse-Policy (MVP)

### Grundprinzipien
- **LLM-first für Semantik:** Das LLM entscheidet über die Relevanz von Themen/Entities.
- **Inkrementell & Idempotent:** Nur neue Videos werden verarbeitet. Bereits vorhandene Summaries werden nicht neu generiert, außer es wird explizit verlangt.
- **Kein Evidence/Confidence im MVP:** Gemäß PRD (Abschnitt 4) wird in Phase 1 auf Belege und Konfidenzwerte verzichtet, um die Komplexität gering zu halten.

### Definition „Covered“ (MVP)
Ein Video gilt als Coverage für eine Aktie, wenn diese inhaltlich Thema ist (nicht nur Name-Dropping). Das LLM liefert hierfür eine strukturierte Liste von Entities/Topics.

---

## 3. Datenfluss & Pipeline (Phase 1)

### Stage 0: Ingest (Inkrementell)
- Laden von neuen Videos/Transkripten (nur Delta).
- **TTL-Regel:** Roh-Transkripte in `output/data/transcripts/by_video_id/` werden nach 30 Tagen gelöscht. Ein Re-Download erfolgt nur, wenn die Summary in `output/data/summaries/by_video_id/` fehlt.

### Stage 1: Video-Analyse (LLM, pro Video)
- Extraktion von Topics/Entities in strukturierter Form.
- Output: `output/data/summaries/by_video_id/<video_id>.summary.md`.

### Stage 2: Aggregation (Deterministisch)
- Zusammenführung der Video-Ergebnisse.
- Berechnung von `creator_count` und `video_count`.
- Erstellung eines History-Bundles unter `output/history/<topic>/...` und aktueller Reports unter `output/reports/<topic>/`.

---

## 4. Artefakte & Retention (PRD-konform)

Die Pfade basieren auf `output.global` + `output.topic`.

| Artefakt | Pfad (Beispiel) | Retention | Zweck |
|---|---|---|---|
| **Roh-Transkripte** | `output/data/transcripts/by_video_id/<video_id>.txt` | 30 Tage | Audit & Debugging (löschbar) |
| **Video-Summaries** | `output/data/summaries/by_video_id/<video_id>.summary.md` | 1 Jahr | Verdichtetes Wissen pro Video |
| **Global Reports** | `output/reports/<topic>/report_de_<YYYY-MM-DD>.md` | Ewig | Zusammenfassende Analyse (Sprache via CLI) |
| **Ingest Index** | `output/data/indexes/<topic>/current/ingest_index.jsonl` | Ewig | Zentrales Register aller Artefakte |

---

## 5. Konfiguration (config.yaml)
- `output.topic`: z.B. `stocks`
- `output.global`: z.B. `../output`
- `retention.transcripts_days`: 30
- `retention.summaries_days`: 365
- `retention.reports_forever`: true
