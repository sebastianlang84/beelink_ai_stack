# Prompt Engineering Handover Report — Investing Summary (Meta) (Schema v3)

## 1) Request Context
The user considers the per-video summary for **"The META Rally Is Only Getting Started!"** too short (and too hard to audit).
They requested a handover report that includes:
- the full original transcript (verbatim)
- the current summary
- the prompt responsible for the summary

This file mirrors the existing v2 handover report (`enhance_prompt_engineering.md`) but proposes a **Schema v3** direction and concrete next improvements.

## 2) Source Transcript (Verbatim)
```text
Meta just reported earnings. The stock
is up 6 and a half% in the after hours.
Absolutely absolutely amazing report.
They pretty much crushed it. Massive
beaten earnings per share 8.88 versus
823 expected. They also beat on revenue.
Now what's really surprising to me in
the report is Meta is still growing 24%
revenues and they're expected to grow
30% in revenues in Q1 of 2026. I don't
know many companies over a trillion
dollar in market cap. They're still
growing 24% in revenues, not in earnings
per share in revenues organically. And
it really tells you that the capex that
Mark Zuckerberg is spending right now in
2026. It has nothing to do with the
metaverse hype and the metaverse dream
that he was spending on and he wasted
all this money back in 2021. This is
actually driving organic growth. It's
driving revenue growth. It's driving
efficiency and I'm going to talk about
this a little bit more and I was talking
about it in my videos many times and
that's why I started a position in Meta
and I've been buying the dips on the
stock and I thank Mr. Market for the
opportunities and rationality in
general. Earnings per share was 8.88. It
was their highest earnings per share uh
quarter ever. The company is still
growing in daily active people. Over 3.6
billion people use the app every single
day. And I always talk about how this is
extremely underrated and it goes under
the radar within the company because the
company has access to 3.6 billion
people. Meta can decide to launch an app
tomorrow or a website or a actually a
decent AI product like something as good
as Gemini or Chat GPT and they don't
have to spend any money on advertising.
They own the advertising bridge you
could say. They're like a toll bridge
for advertising and they can reach 3.6
billion people overnight. the reach and
this should be worth much more than 22
times earnings or 20 or 21 times
earnings. Yet this is where MEA is
trading at. And to me it's absolutely
absolutely uh ridiculous. Now for their
capex it was you know also ridiculous
115 to 135 billion for 2026 which is
double what they spent back in 2025. And
many people were surprised that why did
Meta guide for such for 135 and the
stock went up? People were expecting for
Meta to go down on such high capex
guidance. But there's a reason for that.
And the main reason for that is the
market is starting to realize that this
capex again it has nothing to do with
the metaverse mansion in the metaverse
and buying land online or whatever that
is and some some crazy things. This is
actually helping them. They're finding
efficiencies. they're making money from
it. And this they said it themselves.
They said we've seen a 30% increase in
output per engineer with the majority of
that growth coming from the adoption of
agentic coding and also seeing more
efficiencies in other areas. They're
also helping their ad business and they
we talked about this before they made
like 60 billion from ads related to AI.
How AI is helping them and they're using
AI to help uh to create like agents that
help businesses when they advertise.
they could ask them questions and they
pretty much help them in general. So
this is to me is absolutely crazy. And
there's another reason why the stock is
up and this is Reality Labs. Reality
Labs has been a money- losing business
for many years and it keeps losing more
and more money every single quarter and
every single year. But this is what Mark
Zuckerberg said. He said, "I expect
Reality Labs losses this year to be
similar to last year, and this will
likely be the peak as we start to
gradually reduce our losses going
forward while continuing to execute on
our vision." And that gives the market a
lot more certainty because they were
expecting the reality of the ABS
business to be a mind- losing business
forever and losses to keep are
increasing. Well, now it's speaking and
losses are about to be reduced over the
next few years. Uh the CEO is even
laying off more than 8,000 reality lab
employees and they're trying to focus
more on VR and wearable devices such as
the Meta Rayban smart glasses which have
been a massive massive success. Now I
just told you about a company that's
likely going to be leading in AI. AI is
helping them fight the efficiencies.
They own WhatsApp, they own Instagram,
they own Facebook, they own Oculus, they
own the meta smart glasses which is
doing really really well. They have
access to 3.6 6 billion people every
single day is a growing 24% and 30% in
quarterly revenues. Where do you believe
the stock is trading at? ...
```

## 3) Current Summary (Verbatim; v2 Markdown View)
The currently stored summary is a derived Markdown view, rendered from the LLM JSON output.
It is not quote-complete, which makes audits and RAG retrieval weaker than necessary.

```markdown
---
schema_version: 2
task: stocks_per_video_extract
topic: investing
video_id: hHR4Bt2OCY4
url: https://www.youtube.com/watch?v=hHR4Bt2OCY4
title: The META Rally Is Only Getting Started!
channel_namespace: thepatientinvestorr
channel_id: UCowj3bHIz47dMIe8n37qTlw
published_at: 2026-01-29T15:26:46
transcript_path: /transcript_miner_output/data/transcripts/by_video_id/hHR4Bt2OCY4.txt
raw_hash: sha256:faa7135389effbe55a6c7c2131e4ea9050a368ddb44d9be2afe34314954259c3
transcript_quality_grade: ok
transcript_quality_reasons: Kohärenter Text; Leichte ASR-Fehler bei Zahlen (823 statt 8.23) und Fachbegriffen (mind-losing statt money-losing), aber Kontext bleibt klar.
generated_at_utc: 2026-01-29T22:43:14.442904Z
---

# The META Rally Is Only Getting Started!

## Source
- topic: `investing`
- video_id: `hHR4Bt2OCY4`
- url: https://www.youtube.com/watch?v=hHR4Bt2OCY4
- channel_namespace: `thepatientinvestorr`
- published_at: `2026-01-29T15:26:46`

## Stocks Covered
- Meta Platforms Inc.: Der Host führt einen Deep-Dive zu Meta nach den Earnings durch und begründet seine bullische Haltung mit dem starken Umsatzwachstum, der Effizienzsteigerung durch KI und der prognostizierten Stabilisierung der Verluste in der Reality-Labs-Sparte.

## Numbers / Levels
- 8.88 USD: valuation — Meta Earnings Per Share (EPS)
- 24 %: growth — Meta Revenue Growth
- 115 to 135: guidance — Meta Capex 2026 in Billion USD
- 60: growth — Ad revenue related to AI in Billion USD
- 3.6: other — Daily active people in Billions

## Other Insights
- company_process: KI-Tools steigern die Effizienz der Meta-Ingenieure massiv durch agentenbasiertes Coding.
- sentiment: Der Markt akzeptiert nun hohe CapEx-Ausgaben, da diese direktes Umsatzwachstum und Effizienz treiben statt spekulativer Metaverse-Projekte.
```

## 4) Proposed Prompt (Schema v3)
Note: This is a proposed Schema v3 prompt. Current configs and validators are still Schema v2.

### 4.1 System Prompt (v3 direction)
```text
Du bist ein Analyst fuer Investing (Aktien, Makro, Krypto).

OUTPUT-FORMAT:
- Gib STRICT JSON aus: genau EIN JSON-Objekt, keine Prosa, keine Codefences.
- Keine externen Fakten. Kein Web-Fact-Checking. Nur das, was im Transcript steht.

TASK: stocks_per_video_extract

ZIEL:
- Pro Transcript extrahierst du:
  (A) echte Aktien-Deep-Dives -> stocks_covered
  (B) Makro- & Crypto-Insights -> macro_insights (mit sauberer tags Taxonomie)
  (C) substanzielle, aber nicht Deep-Dive Aktien-Segmente -> stocks_mentioned
  (D) sonstige relevante Learnings/Prozess/Risiko/Portfolio -> other_insights
  (E) ALLE woertlich belegten Zahlen/Valuation/Levels/Guidance/Comparisons/Returns -> numbers

DEEP-DIVE-KRITERIUM:
- stocks_covered nur, wenn:
  * >= 2 evidence items
  * >= 1x role="thesis"
  * >= 1x role in {"risk","catalyst","numbers_valuation","comparison"}

NUMBERS-COMPLETENESS (hart):
- Wenn im Transcript Zahlen vorkommen (Multiples, Growth, CapEx, Guidance, Peer-Vergleiche, Returns):
  * pro explizit genannter Zahl mindestens ein numbers-Item.
  * Peer-Vergleiche: jede Peer-Zahl als eigenes Item.

EVIDENCE:
- Jede evidence.quote muss woertlich im Transcript stehen (verbatim).
- Nutze den kuerzesten zusammenhaengenden Ausschnitt.
- Keine erfundenen Zahlen/Details.

ASR-NORMALISIERUNG (optional, aber gekennzeichnet):
- numbers.value_verbatim ist immer das Quote-Fragment (ASR kann schief sein).
- numbers.value_normalized nur wenn Kontext klar; dann normalization_reason angeben und confidence senken.
```

### 4.2 User Prompt Template (Schema v3)
Key change vs v2: `numbers.value_verbatim` + optional `numbers.value_normalized` (instead of one `value_raw`),
and explicit contexts for comparisons/returns.

```text
Aufgabe: Analysiere GENAU EIN Transcript (der Block unten).
Gib STRICT JSON gemaess Schema aus.

{
  "schema_version": 3,
  "task": "stocks_per_video_extract",
  "source": {
    "channel_namespace": "...",
    "video_id": "...",
    "transcript_path": "..."
  },
  "raw_hash": "sha256:<64hex>",

  "transcript_quality": {
    "grade": "ok|low|unknown",
    "reasons": [],
    "confidence": 0.0
  },

  "macro_insights": [
    {
      "claim": "...",
      "confidence": 0.0,
      "tags": ["crypto","btc"],
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
        { "quote": "...", "role": "risk|catalyst|numbers_valuation|comparison" }
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

Anzahl Transkripte: {transcript_count}

{transcripts}
```

## 5) Why the Summary Feels Thin (Root Causes)
Observed gaps vs transcript richness:
- Multiple valuation comparisons are mentioned (Meta ~22-23x vs MSFT/Apple/Google/Amazon/AVGO) but are missing.
- Forward-looking growth guidance (30% revenue growth expected in Q1 2026) is missing.
- Reality Labs block is compressed: peak losses framing + layoffs (~8,000) + VR/wearables shift should become separate, explicit insights.
- Distribution moat (WhatsApp/IG/FB reach) is mentioned but not represented as its own insight.
- The current Markdown view does not show quotes/evidence, so even correct extraction feels less trustworthy.

This looks like a combination of (a) incomplete number-capture rules and (b) rendering/persistence choices that drop audit value.

## 6) Recommendations (Schema v3 + Pipeline)
Concrete changes to improve coverage and auditability:

1) Enforce numbers completeness with explicit triggers
   - If transcript_quality.grade="ok" and the transcript contains multiple numeric claims, require a minimum `numbers` count.
   - Force `multiple_comparison` and `return_expectation` contexts for common investing content.

2) Split multi-topic blocks into separate insights
   - Require that distinct topics become separate `other_insights` items (AI efficiency, CapEx acceptance, Reality Labs, distribution moat).
   - This prevents "everything in one sentence" summaries.

3) Fix the evidence friction point (do not ask the LLM to compute hashes)
   - Current v2 schema requires `evidence[].snippet_sha256` and validators enforce it.
   - Proposed v3: remove hash-from-LLM requirements; instead compute `quote_sha256 = sha256(quote_text)` in the pipeline.
   - Result: more evidence items, fewer "model plays it safe" failures.

4) Persist raw JSON per video (debugging + future re-render)
   - Store `raw_llm_json_output.json` (exact model output) next to the markdown summary.
   - Make the markdown view strictly derivable from the JSON (and keep both).

5) Improve the Markdown renderer for RAG
   - Append a short quote snippet (1 line) per bullet or at least per section.
   - For `numbers`, always show `unit` + `what_it_refers_to`.
   - For ambiguous numbers (e.g. "75 exposure"), require `what_it_refers_to` or skip.

6) Add a repair pass for missing numbers (optional)
   - If the first output fails completeness checks, run a "repair prompt" that only appends missing numbers/insights.
   - This is cheaper than rerunning the whole pipeline and avoids rewriting existing items.

## 7) Candidate Output Expansion (Example Targets)
(For guidance only; not a regenerated summary.)

Numbers (each should be a separate item with quote evidence):
- EPS: 8.88 (and "823 expected" with optional normalization to 8.23 if justified)
- Revenue growth: 24%
- Q1 2026 revenue growth expected: 30%
- CapEx 2026: 115-135B USD
- AI ads revenue: 60B USD
- Daily active people: 3.6B
- Meta multiple: 22x/23x
- Peer multiples: MSFT 28x, Apple 31x, Google 31x, Amazon 32x, AVGO 35x
- Layoffs: 8,000 (Reality Labs)
- Return expectations: 18-20% annual return; EPS growth 18-20%; PEG 1.1-1.2

Other insights (split into separate blocks):
- AI efficiency uplift: 30% output per engineer via agentic coding
- Market narrative shift: high CapEx accepted because it drives efficiency/revenue (not metaverse hype)
- Reality Labs: losses peak + plan to reduce; focus on VR/wearables; smart glasses adoption
- Distribution moat: can launch products to 3.6B users without paid ads

## 8) Additional Notes
- ASR errors are real here ("823 expected"). v3 should separate verbatim vs normalized numeric values.
- The current summary markdown is not quote-complete; even with a better prompt, we should not discard evidence in the rendered view.

## 9) Next Actions (Implementation Plan)
Minimal stepwise plan (lowest risk first):
1) Add raw JSON persistence per video (keep existing Markdown).
2) Update the Markdown renderer to include a short quote/evidence snippet per section.
3) Introduce Schema v3 in configs + validators (value_verbatim/value_normalized; new number contexts).
4) Remove LLM-hash requirements; compute quote hashes in the pipeline (validator update).
