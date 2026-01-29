# Expert Notes — TranscriptMiner Summaries (Investing)

Below are expert recommendations to improve summary completeness and robustness.

## 0) Zielbild
- **Maximale Informationsabdeckung** bei weiterhin strikter Nachvollziehbarkeit (jede Zahl/These mit wörtlichem Quote).
- **Stabiler Output** auch bei ASR-Fehlern (Automatic Speech Recognition), ohne “falsche Korrekturen” zu erfinden.
- **Kein Verlust durch Renderer**: Raw JSON wird gespeichert; Markdown rendert *alles Wesentliche*.

---

## 1) Hauptprobleme im aktuellen Setup (warum “thin”)
1) **`snippet_sha256` als Modellpflicht** ist ein Output-Bremser:
   - Das Modell kann den Hash nicht zuverlässig berechnen → reduziert Items, um Fehler zu vermeiden.
2) **Numbers-Extraktion ist nicht “vollständig verpflichtend”**:
   - Multiples/Guidance/Peer-Vergleiche werden im Transcript genannt, aber nicht als `numbers` erzwungen.
3) **Multi-Topic-Blöcke werden zusammengeklatscht**:
   - “AI Effizienz + CapEx Akzeptanz + Distribution + Reality Labs” wird zu 1–2 Sätzen.
4) **ASR-Zahlen** (z.B. „823 expected“ statt „8.23“) blockieren “saubere” Numbers, wenn Verbatim-Only verlangt wird.

---

## 2) Pipeline-Fixes (höchster Hebel, prompt-unabhängig)
### 2.1 Raw JSON immer speichern
- Speichere pro Video:
  - `raw_llm_json_output.json` (exakt, unverändert)
  - `rendered_summary.md` (nur Darstellung)
- Damit ist Debugging klar: **LLM extrahiert zu wenig** vs **Renderer droppt zu viel**.

### 2.2 Hashing aus dem Modell rausnehmen
- Entferne `snippet_sha256` aus dem LLM-Schema.
- Pipeline berechnet später:
  - `quote_sha256 = sha256(quote_text_utf8)`
- Optional: `quote_offsets` (start/end) wenn Preprocessing stabiles Text-Indexing hat.

### 2.3 Validator + Repair-Schleife (Quality-Gate)
- Nach dem ersten LLM-Run:
  - Prüfe: Wenn im Transcript “x times / % / billion / guidance / expected return / PEG / multiples” vorkommen
    → müssen entsprechende `numbers` existieren.
- Wenn fail:
  - “Repair prompt” laufen lassen (nur fehlende Items ergänzen, keine Umschreibung).

---

## 3) Schema-Änderungen (minimal, aber wirksam)
### 3.1 Numbers: Verbatim vs Normalized getrennt
Für jede Zahl:
- `value_verbatim`: exakt aus Quote (ASR kann schief sein)
- `value_normalized` (optional): nur wenn sehr wahrscheinlich, mit Begründung + Confidence runter

### 3.2 Comparatives explizit abbilden
- Entweder über `numbers.context="multiple_comparison"`
- oder eigener Block `comparative_valuation` (Empfehlung: **numbers reicht**, aber mit sauberem `context`)

---

## 4) Verbesserter Prompt (System Prompt) — STRICT JSON, aber informationsreich

SYSTEM PROMPT (v3):
Du bist ein Analyst für Investing (Aktien, Makro, Krypto).

OUTPUT-FORMAT:
- Gib STRICT JSON aus: genau EIN JSON-Objekt, keine Prosa, keine Codefences.
- Keine externen Fakten. Kein Web-Fact-Checking. Nur das, was im Transcript steht.

TASK: stocks_per_video_extract

ZIEL:
- Pro Transcript extrahierst du:
  (A) echte Aktien-Deep-Dives → `stocks_covered`
  (B) Makro- & Crypto-Insights → `macro_insights` (mit sauberen `tags`)
  (C) substanzielle, aber nicht Deep-Dive Aktien-Segmente → `stocks_mentioned`
  (D) sonstige relevante Learnings/Prozess/Risiko/Portfolio → `other_insights`
  (E) ALLE wörtlich belegten Zahlen/Valuation/Levels/Guidance/Comparisons/Returns → `numbers`

WICHTIG: INFORMATION > Kuerze
- Wenn transcript_quality.grade == "ok" und das Transcript zahlen-/thesenreich ist:
  - Extrahiere konsequent alle separaten These-Bloecke als eigene Items (nicht zusammenmischen).
  - Zahlen/Multiples/Peer-Vergleiche/Guidance/Return-Claims muessen vollstaendig in `numbers` landen.

DEEP-DIVE-KRITERIUM fuer `stocks_covered` (wie bisher):
- mindestens 2 Evidence-Items
- davon mindestens 1x role="thesis"
- plus mindestens 1x role in {"risk","catalyst","numbers_valuation","comparison"}

NUMBERS-COMPLETENESS (NEU, kritisch):
- Wenn im Transcript irgendeines vorkommt:
  - Multiples: "x times", "P/E", "trading at", "PEG"
  - Guidance: "expected", "guide", "forecast", "next quarter", "Q1 2026"
  - Growth / Percent: "%", "billion", "million"
  - Return Claims: "annual return", "worth over", "price target"
  DANN:
  - Erzeuge fuer JEDE explizit genannte Zahl mindestens einen `numbers`-Eintrag.
  - Peer-Vergleiche: jede Peer-Zahl als eigenes `numbers`-Item (nicht zusammenfassen).
  - `numbers` sollen nicht duplizieren, aber duerfen aehnlich sein, wenn Kontext anders.

EVIDENCE-REGELN:
- Jede Evidence `quote` muss woertlich im Transcript stehen (verbatim).
- Nutze den kuerzesten zusammenhaengenden Ausschnitt, der den Claim belegt.
- Keine erfundenen Zahlen/Details.

ASR-NORMALISIERUNG (NEU, erlaubt aber gekennzeichnet):
- Zusaetzlich zu `value_verbatim` optional `value_normalized`, wenn Kontext klar.
- Dann:
  - `normalization_reason` kurz angeben
  - `confidence` senken (z.B. -0.15 bis -0.30)
  - Quote bleibt unveraendert (verbatim).

COVERAGE-ZIELE (HART als MUST, NEU):
- Wenn transcript_quality.grade == "ok" UND transcript_length_chars >= 1200:
  - numbers >= 10
  - other_insights >= 4
  - (stocks_covered >= 1 ODER stocks_mentioned >= 1)
- Wenn transcript_length_chars >= 2500:
  - numbers >= 14
  - other_insights >= 6
- Wenn grade == "low": weniger ok, aber nichts Wichtiges droppen.

ABBREVIATIONS (immer beim ersten Auftreten aufloesen):
- EPS = Earnings Per Share
- DAU = Daily Active Users
- CapEx = Capital Expenditures
- PEG = Price/Earnings to Growth
- ASR = Automatic Speech Recognition

---

## 5) Verbesserter User Prompt Template (Schema v3)

USER PROMPT TEMPLATE (v3):
Aufgabe: Analysiere GENAU EIN Transcript (der Block unten).
Gib STRICT JSON gemaess Schema aus.

{
  "schema_version": 3,
  "task": "stocks_per_video_extract",
  "source": {
    "channel_namespace": "...",
    "video_id": "...",
    "transcript_path": "...",
    "url": "..."
  },
  "raw_hash": "sha256:<64hex>",

  "transcript_meta": {
    "published_at": "...",
    "title": "...",
    "transcript_length_chars": 0
  },

  "transcript_quality": {
    "grade": "ok|low|unknown",
    "reasons": [],
    "confidence": 0.0
  },

  "macro_insights": [
    {
      "claim": "...",
      "confidence": 0.0,
      "tags": ["macro","rates"],
      "evidence": [
        { "quote": "...", "role": "other" }
      ]
    }
  ],

  "stocks_covered": [
    {
      "canonical": "...",
      "why_covered": "...",
      "confidence": 0.0,
      "evidence": [
        { "quote": "...", "role": "thesis" },
        { "quote": "...", "role": "numbers_valuation|comparison|risk|catalyst" }
      ]
    }
  ],

  "stocks_mentioned": [
    {
      "canonical": "...",
      "mention_type": "quick_take|setup|news|valuation|levels",
      "summary": "...",
      "confidence": 0.0,
      "evidence": [
        { "quote": "...", "role": "other|numbers_valuation" }
      ]
    }
  ],

  "other_insights": [
    {
      "topic": "portfolio|risk_management|trading_process|sentiment|sector|company_process|other",
      "claim": "...",
      "confidence": 0.0,
      "evidence": [
        { "quote": "...", "role": "other" }
      ]
    }
  ],

  "numbers": [
    {
      "context": "valuation|multiple|multiple_comparison|growth|margin|buy_level|sell_level|stop|guidance|return_expectation|other",
      "value_verbatim": "...",
      "value_normalized": "...",
      "normalization_reason": "...",
      "unit": "%|USD|EUR|x|bps|people|other",
      "what_it_refers_to": "...",
      "confidence": 0.0,
      "evidence": [
        { "quote": "...", "role": "numbers_valuation" }
      ]
    }
  ],

  "errors": []
}

Regeln (kurz):
- Keine Name-Drops ohne Substanz.
- `stocks_covered` nur bei Deep-Dive.
- Makro+Crypto in `macro_insights` mit Tag-Taxonomie.
- Alles sonst Wichtige → `other_insights` (niemals droppen).
- Zahlen/Multiples/Levels/Guidance/Comparisons/Returns → `numbers` (vollstaendig).
- Jede Evidence `quote` muss woertlich im Transcript vorkommen.
- Nutze `transcript_path` und `raw_hash` exakt wie im Input-Block.

{transcripts}

---

## 6) Repair Prompt (nur Ergänzung fehlender Zahlen/Blöcke)
Ziel: Nur fehlende Items ergänzen, vorhandenes NICHT umschreiben.

REPAIR SYSTEM:
Du bist ein Repair-Validator. Du bekommst:
(1) Transcript
(2) bisheriges JSON
Aufgabe: Ergänze ausschliesslich fehlende `numbers` und fehlende getrennte `other_insights`-Bloecke.
Output: STRICT JSON mit exakt gleichem schema_version=3.

REPAIR LOGIK:
- Wenn Transcript Peer-Multiples nennt (z.B. "Apple 31 times") und das JSON hat keinen passenden `numbers.context=\"multiple_comparison\"`,
  dann fuege EIN `numbers` Item pro Peer hinzu.
- Wenn Transcript Forward Guidance (z.B. "expected to grow 30% in Q1 2026") nennt und fehlt → ergänzen.
- Wenn Transcript Return/PEG Claims nennt und fehlt → ergänzen (confidence niedrig, “Host claims …”).
- Wenn Transcript Reality Labs layoffs/peak losses/Smart glasses nennt und es fehlt als eigener other_insights Block → ergänzen.

---

## 7) Renderer-Fix (damit Markdown nicht “droppt”)
- Markdown soll mindestens rendern:
  - `stocks_covered` + Evidence Rollen (thesis/comparison/numbers_valuation)
  - `numbers` gruppiert nach context (multiple_comparison, guidance, growth, return_expectation)
  - `other_insights` als Liste (je 1 Satz + Quote optional)
- Optional: “Numbers Table” im Markdown (Value, Unit, Context, RefersTo)

---

## 8) Konkrete Anwendung auf META-Transcript (was künftig NICHT fehlen darf)
Numbers (Beispiele, jeweils eigenes Item):
- EPS (Earnings Per Share): 8.88
- EPS expected: 823 (verbatim) + optional normalized 8.23 (mit reason)
- Revenue growth: 24%
- Q1 2026 revenue growth expected: 30%
- CapEx (Capital Expenditures) 2026: 115–135B USD
- “AI ads revenue”: 60B USD
- DAU (Daily Active Users): 3.6B people
- Meta multiple: 22x / 23x (je nach Quote)
- MSFT multiple: 28x
- Apple multiple: 31x
- Google multiple: 31x
- Amazon multiple: 32x
- AVGO multiple: 35x
- Layoffs: 8,000 (Reality Labs)
- Return expectation: 18–20% annual
- EPS growth expectation: 18–20%
- PEG: 1.1–1.2

Other insights (je Block separat):
- “Market accepts high CapEx because it drives efficiency & revenue (not metaverse hype)”
- “30% output per engineer uplift via agentic coding”
- “Reality Labs losses peak; expected to reduce going forward; layoffs; focus on wearables/VR”
- “Distribution moat: 3.6B reach; can launch AI products without ads”
- “AI traffic share call option: currently weak product; integration into WhatsApp/IG/FB/glasses could re-rate”

---

## 9) Minimaler Quick-Win ohne Schemawechsel
Wenn schema_version nicht sofort geändert wird:
- Entferne nur `snippet_sha256` als Pflicht.
- Mach `numbers` verpflichtend bei jeder Zahl.
- Setze harte Mindestanzahl: numbers>=12 bei grade=ok & Laenge>1200.
- Fuege Repair-Schleife hinzu.
