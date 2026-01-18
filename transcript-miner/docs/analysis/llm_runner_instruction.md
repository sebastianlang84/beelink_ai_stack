# LLM Runner Instructions: PRD Compliant Reporting

Diese Anweisung definiert die Anforderungen an den LLM-Runner, um einen PRD-konformen Report zu generieren.

## 1. Output-Artefakte

Der LLM-Runner MUSS folgende Artefakte im History-Bundle erzeugen:
`output/history/<topic>/<YYYY-MM-DD>/<YYYY-MM-DD>__<HHMM>__<model>__<fingerprint>/`

1.  **`report.json`** (Maschinenlesbar):
    *   Enthält den vollständigen strukturierten Inhalt des Reports.
    *   Muss valides JSON sein.
    *   Darf keine Markdown-Formatierung im JSON-String enthalten, es sei denn, es handelt sich um Textfelder.

2.  **`report.md`** (Menschenlesbar):
    *   Abgeleitet aus `report.json`.
    *   Muss valides Markdown sein.
    *   Muss die unten definierte Struktur einhalten.

3.  **`metadata.json`**:
    *   Enthält Provenienz-Informationen (Hashes der Inputs, verwendetes Modell, Zeitstempel).

## 2. Report-Struktur (`report.md`)

Der Report MUSS folgende Sektionen in dieser Reihenfolge enthalten:

1.  **Header (YAML Frontmatter-ähnlich)**:
    ```markdown
    ---
    analysis_run_at_utc: <ISO-8601 Timestamp>
    short_term_window_days: <int>
    long_term_window_days: <int>
    short_term_inputs_count: <int>
    generator: TranscriptMiner LLM Runner
    ---
    ```

2.  **`## Executive Summary`**:
    *   Maximal 5 Bulletpoints mit den wichtigsten Erkenntnissen.

3.  **`## Short-term Findings`**:
    *   Erkenntnisse aus den aktuellen Transkripten.
    *   Jede Behauptung MUSS referenziert sein (siehe Evidence).

4.  **`## Long-term Findings`**:
    *   Erkenntnisse aus historischen Analysen (falls vorhanden).
    *   Muss als `[inherited]` markiert sein.

5.  **`## Evidence Index`**:
    *   Liste aller verwendeten Zitate/Snippets aus den Transkripten.
    *   Format: `[<Ref-ID>] "<Zitat>" (Video: <Video-ID>, Time: <Timestamp>)`

## 3. Evidence-Pflicht

*   **Jede** Aussage in `Short-term Findings` MUSS durch mindestens ein Zitat aus den Transkripten belegt sein.
*   Erfundene Fakten oder Halluzinationen sind streng verboten.
*   Wenn eine Information unsicher ist, muss dies explizit gekennzeichnet werden (z.B. "Confidence: Low").

## 4. Ordnerstruktur-Konformität

Der Runner muss sicherstellen, dass er Inputs aus der korrekten Struktur liest:
*   Transkripte: `output/data/transcripts/by_video_id/`
*   Summaries: `output/data/summaries/by_video_id/`

Und Outputs in die korrekte Struktur schreibt:
*   History-Bundle: `output/history/<topic>/<YYYY-MM-DD>/<HISTORY_BUNDLE>/`
