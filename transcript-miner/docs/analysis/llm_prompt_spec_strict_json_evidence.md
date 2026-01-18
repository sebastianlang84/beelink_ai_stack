# LLM Prompt Spec — Strict JSON + Evidence (Policy)

## Status

- **Policy-Dokument** (Doku/Guardrails), kein API-/Schema-Contract.
- Ziel: reproduzierbare, offline-validierbare LLM-Outputs mit klarer Evidence-Traceability.

Diese Datei existiert, weil mehrere Stellen im Repo auf sie verweisen (z.B. [`docs/config.md`](../config.md:519)) und die Referenz zuvor ins Leere lief.

---

## Grundprinzipien

1) **Kein Raten / keine externen Fakten**

- Aussagen müssen aus dem bereitgestellten Material ableitbar sein.
- Wenn etwas nicht aus dem Material ableitbar ist: `unknown` / weglassen.

2) **Strict JSON (maschinenlesbar)**

- Ausgabe ist **ein** JSON-Objekt (keine Prosa außerhalb des JSON).
- Output soll deterministisch validierbar sein (Schema-Versionierung empfohlen).

3) **Evidence-Pflicht (Traceability)**

- Jede „harte“ Aussage sollte mit einem Evidence-Pointer auf Transcript-Text belegt sein.
- Evidence soll mindestens enthalten:
  - `video_id`
  - `channel_namespace`
  - `transcript_path` (wenn verfügbar)
  - `quote` oder `snippet` (kurz, wörtlich)

---

## Minimal-Output-Shape (empfohlen)

> Hinweis: Das ist ein **Doku-Vorschlag** zur Konsistenz, kein zwingendes Runtime-Schema.

```json
{
  "schema_version": 1,
  "topic": "<topic>",
  "as_of": "<utc-iso>",
  "items": [
    {
      "kind": "claim",
      "entity": "<ticker|topic>",
      "text": "<claim text>",
      "confidence": 0.0,
      "evidence": [
        {
          "video_id": "<id>",
          "channel_namespace": "<channel>",
          "transcript_path": "<path or null>",
          "quote": "<short verbatim quote>"
        }
      ]
    }
  ]
}
```

---

## Abgrenzung zu Markdown-Reports

- Für menschenlesbare Reports (Markdown) siehe Report-Layout/Guardrails in [`docs/analysis/llm_report_markdown_layout_provenance_guardrails.md`](llm_report_markdown_layout_provenance_guardrails.md:1).

