# ADR 0007: LLM Output-Formate (JSON vs. Markdown/Text) — Auditierbarkeit vs. Human Readability

Status: **Accepted**

## Problem

Der LLM-Runner schreibt die eigentliche LLM-Antwort in einen schema-stabilen Container [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450) (unter `output.content`; Writer: [`transcript_ai_analysis.llm_runner.run_llm_analysis()`](../../src/transcript_ai_analysis/llm_runner.py:236)).

In der Praxis ist der Text dadurch in vielen Editoren schwer lesbar, weil Zeilenumbrüche als `\n` innerhalb eines JSON-Strings dargestellt werden (und/oder die Editor-Ansicht den String als „Einzeiler“ rendert).

## Kontext / Evidenz (Ist-Zustand)

- Der LLM-Runner schreibt in ein History-Bundle unter `output/history/<topic>/<YYYY-MM-DD>/<HISTORY_BUNDLE>/`:
  - [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450) (LLM-Antwort unter `output.content`)
  - [`report.md`](../../src/transcript_ai_analysis/llm_runner.py:63) **oder** [`report.txt`](../../src/transcript_ai_analysis/llm_runner.py:63) (menschenlesbare, deterministisch abgeleitete View)
  - [`metadata.json`](../../src/transcript_ai_analysis/llm_runner.py:73) (Provenienz/Hashes für `report.json` + derived Report)
  - [`manifest.json`](../../src/transcript_ai_analysis/llm_runner.py:511)
  - [`audit.jsonl`](../../src/transcript_ai_analysis/llm_runner.py:253)
  - [`system_prompt.txt`](../../src/transcript_ai_analysis/llm_runner.py:384), [`user_prompt.txt`](../../src/transcript_ai_analysis/llm_runner.py:385)
  (siehe Writer/Callsite: derived + metadata werden nach `report.json` erzeugt via [`_write_derived_report_and_metadata()`](../../src/transcript_ai_analysis/llm_runner.py:73)).
- Hinweis: Ein separater Offline-Validator fuer das Artefakt-Bundle wurde entfernt (kein `validate_llm_report_artefacts()` mehr im aktuellen Code).
- Das Repo hat explizite Artefakt-/Audit-Prinzipien („keine stillen Overwrites ohne klare Policy“, Outputs sind auditierbare Artefakte) (siehe Policy in [`AGENTS.md`](../../../AGENTS.md:138)).

## Entscheidungskriterien

Wir gewichten die Kriterien entlang des Backlog-Problems (siehe [`TODO.md`](../../../TODO.md:239)):

1. **Auditierbarkeit / Traceability**: Inputs/Prompts/Outputs müssen nachvollziehbar bleiben.
2. **Schema-Stabilität / Maschinenlesbarkeit**: Tools sollen ohne „scraping“ aus Text weiterhin zuverlässig parsen können.
3. **Human Readability**: Der „primäre“ Report muss für Menschen schnell konsumierbar sein.
4. **Kompatibilität**: Bestehende Runs/Artefakte dürfen nicht „brechen“.

## Optionen

### Option A) Nur JSON (maschinenlesbar)

**Beschreibung**

- [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450) bleibt das einzige Report-Artefakt; LLM-Text bleibt unter `output.content`.

**Vorteile**

- Eindeutiger, schema-stabiler Container (ein Artefakt, ein Parser).
- Konsistent zu Manifest-/Audit-Pattern (z.B. `manifest.json`, `audit.jsonl`) aus anderen Pipelines (siehe Artefakt-Kontrakt in [`README.md`](../../README.md:340)).

**Nachteile**

- Human Readability leidet (Backlog-Problem: JSON-escaped Text ist schwer lesbar, siehe [`TODO.md`](../../../TODO.md:243)).
- „Quick read“ wird unnötig tooling-lastig (JSON Viewer / Extraktion nötig).

### Option B) JSON + zusätzlich `report.md`/`report.txt` (human-readable derived artefact)

**Beschreibung**

- [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450) bleibt der **kanonische** schema-stabile Container.
- Zusätzlich wird ein menschenlesbares Artefakt abgelegt, das **nur den Text** enthält.

Ist-Implementierung (evidenzbasiert):

- Derived Report wird deterministisch aus dem bereits geschriebenen `report.json` erzeugt: [`_write_derived_report_and_metadata()`](../../src/transcript_ai_analysis/llm_runner.py:73).
- Der Dateiname wird konservativ gewählt: `report.md` nur bei starken Markdown-Signalen, sonst `report.txt` (Detektion: [`_is_probably_markdown()`](../../src/transcript_ai_analysis/llm_runner.py:31)).

**Vorteile**

- Beste beider Welten: Maschinen können weiter `report.json` parsen, Menschen lesen `report.md`/`report.txt` direkt.
- Auditierbarkeit bleibt intakt (JSON bleibt Source-of-Truth; Textdatei ist ein „derived view“).
- Migration/Backfill ohne Codeänderung möglich (siehe unten).

**Nachteile**

- Mehr Artefakte (Retention/Policy muss klar sein, um „Artefakt-Sprawl“ zu vermeiden).
- Potenzielles Drift-Risiko, falls JSON und Text nicht deterministisch gekoppelt werden (muss durch Policy minimiert werden).

### Option C) Nur Markdown/Text (mit minimalem JSON-Manifest)

**Beschreibung**

- Primärartefakt ist eine Text/Markdown-Datei.
- Ein minimales JSON-Manifest enthält Run-Metadaten, Fingerprints, Input-Refs.

**Vorteile**

- Maximale Lesbarkeit.

**Nachteile**

- Parser/Schema-Stabilität verschiebt sich auf „Markdown-Konventionen“.
- Risiko von unklarer Semantik bei späteren Tooling-/Aggregation-Schritten.
- Bricht bestehende Erwartung, dass [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450) den Output enthält (siehe Ist-Outputs in [`README.md`](../../README.md:448)).

## Entscheidung

Wir wählen **Option B (JSON + zusätzliches menschenlesbares Report-Artefakt)**.

### Normative Regeln (Policy)

1. [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450) bleibt **kanonisch** und schema-stabil (LLM-Output unter `output.content`, siehe Report-Build in [`run_llm_analysis()`](../../src/transcript_ai_analysis/llm_runner.py:450)).
2. Ein zusätzliches menschenlesbares Report-Artefakt ist zulässig und empfohlen, aber **abgeleitet** (kein eigener Wahrheitsanspruch).
3. Auditierbarkeit hat Vorrang vor reiner „Schönheit“: Inputs/Prompts und ein maschinenlesbarer Container bleiben Pflicht (siehe Prompt-Artefakte in [`README.md`](../../README.md:455)).

### Operationalisierung (klein, normativ, ohne neue Flags/APIs)

Ziel: die „derived“ Datei ist eine **View** auf `output.content` und kann deterministisch generiert/validiert werden.

- **Ablage:** derived Artefakt liegt neben [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:186) im History-Bundle (Ist-Layout siehe „Analysis (LLM) — optional“ in [`README.md`](../../README.md:480)).
- **Dateiname:**
  - Wenn `output.content` wahrscheinlich Markdown ist: `report.md`, sonst `report.txt` (Heuristik: [`_derived_report_filename_for_content()`](../../src/transcript_ai_analysis/llm_runner.py:63)).
  - Hinweis: diese Namen sind eine **Konvention**, keine eigene Schnittstelle; die kanonische Quelle bleibt immer [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450).
- **Inhalt/Encoding:** UTF-8; Dateiinhalt ist byte-identisch zu `report.json.output.content` (keine zusätzlichen Header/Wrapper, keine JSON-Escapes).
- **Determinismus:** die derived Datei muss bei gleicher [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450) deterministisch reproduzierbar sein.
- **Integrität:** Hashes/Kopplung sind im Metadata-File vorhanden (Hash-Erzeugung: [`_write_derived_report_and_metadata()`](../../src/transcript_ai_analysis/llm_runner.py:73)); aktuell ohne separaten Offline-Validator.

## Konsequenzen

- **Kurzfristig:** Lesbarkeit ist durch den derived Report im Ist-Code verbessert (Writer: [`_write_derived_report_and_metadata()`](../../src/transcript_ai_analysis/llm_runner.py:73)); Backfill für alte Runs bleibt möglich (siehe Migration).
- **Langfristig:** Falls der Report-Text künftig ein stabiles Markdown-Layout erfüllen soll, muss das über Prompt-/Schema-Policy abgesichert werden (und ggf. zusätzliche Validator-Regeln) — unabhängig davon bleibt `report.json` kanonisch.
- Bestehende Consumer bleiben kompatibel, weil [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450) das kanonische Artefakt bleibt (Ist-Schema: `output.content` in [`run_llm_analysis()`](../../src/transcript_ai_analysis/llm_runner.py:450)).

## Migration / Backfill (ohne Codeänderungen)

Ziel: vorhandene Runs bleiben unverändert gültig; zusätzlich kann ein human-readable Report erzeugt werden.

### Phase 0 (Ist-Zustand akzeptieren)

- [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450) bleibt der Source-of-Truth.
- Leser nutzen bei Bedarf JSON-Viewer oder extrahieren den String.

### Phase 1 (Empfohlen): Derived Report neben [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450) erzeugen

Manuell aus einem bestehenden [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450):

- **Python (Beispiel):** extrahiert `output.content` und schreibt eine Textdatei.

```bash
# Pfade setzen (Beispiel; Werte sind lokal abhängig)
REPORT_JSON="..."
REPORT_TXT="..."

python -c 'import json,sys; p=sys.argv[1]; o=sys.argv[2]; d=json.load(open(p,encoding="utf-8")); open(o,"w",encoding="utf-8").write(d["output"]["content"])' \
  "$REPORT_JSON" \
  "$REPORT_TXT"
```

**Kompatibilität:**

- [`report.json`](../../src/transcript_ai_analysis/llm_runner.py:450) bleibt unverändert.
- Neue Datei ist rein additiv.

### Phase 2 (optional, zukünftige Policy): Koppelung/Integritätscheck

Wenn künftig zusätzliche Rolling-Window-/Provenienz-Felder in `metadata.json` ergänzt werden, muss die Kopplung zwischen JSON und derived View weiterhin deterministisch bleiben. Der Basis-Integritätscheck über Hashes ist bereits implementiert (siehe `metadata.derived.output_content_sha256` in [`_write_derived_report_and_metadata()`](../../src/transcript_ai_analysis/llm_runner.py:73)).

## Offene Punkte

- Namensentscheidung (`report.txt` vs. `report.md`): im Code ist die Heuristik konservativ (siehe [`_derived_report_filename_for_content()`](../../src/transcript_ai_analysis/llm_runner.py:63)); offen bleibt, ob Prompts künftig Markdown *garantieren* sollen.

## Ergänzende Spezifikation (Rolling-Window Semantik) — Referenz

Die Rolling-Window Semantik für den LLM-Report (Short-term Transkripte + Long-term Analysen) ist **nicht** Teil dieser ADR-Entscheidung (Format/Artefakte), wird aber als **normative, testbare Doku** separat geführt.

- Spezifikation: [`docs/analysis/llm_report_rolling_window_semantics.md`](../analysis/llm_report_rolling_window_semantics.md:1)
- Primärquelle (Backlog/Normativtext): [`TODO.md`](../../../TODO.md:328)

## Ergänzende Spezifikation (Report-Markdown Layout/Provenienz/Guardrails) — Referenz

Diese ADR entscheidet **nur** über Artefakt-Container/Format-Strategie (JSON + derived View). Das **Layout** des derived `report.md` sowie Provenienz-/Guardrail-Regeln werden separat als Spezifikation geführt.

- Spezifikation: [`docs/analysis/llm_report_markdown_layout_provenance_guardrails.md`](../analysis/llm_report_markdown_layout_provenance_guardrails.md:1)
- Primärquelle (Backlog/Normativtext): [`TODO.md`](../../../TODO.md:357)
