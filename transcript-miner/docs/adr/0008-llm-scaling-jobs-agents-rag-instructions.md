# ADR 0008: LLM-Skalierung — 1 Job vs. Multi-Job, Job-Dependencies/„Agents“, RAG-Trigger, Instructions pro Config

Status: **Proposed** (Entscheidungspaket dokumentiert; Implementierung offen)

## Problem

Die aktuelle LLM-Analyse ist als **ein einzelner LLM-Job** modelliert (ein Prompt, ein Call, ein Report) und skaliert bei wachsenden Transcript-Mengen nur begrenzt.

Wir müssen entscheiden und dokumentieren:

1) Ob die LLM-Analyse als **1 Job** (Single-Prompt) oder als **Multi-Job Pipeline** (Map/Reduce) organisiert werden soll.
2) Wie ein konzeptionelles Modell für **Job-Dependencies / „Agents“** (z.B. `extract → critique → synthesize`) einzuordnen ist, ohne eine konkrete API zu behaupten.
3) Wann **RAG/Embeddings** (Retrieval statt Vollprompt) sinnvoll/erforderlich werden (Trigger-Kriterien).
4) Wie „**LLM Instructions**“ pro Config/Topic konzeptionell aussehen können und wie sie sich **in das bestehende Config-Schema** einfügen könnten, ohne Implementierungsdetails als Fakten auszugeben.

**Ziel dieses ADR-Updates:** Die offenen Punkte „Scaling-Policy“ und „LLM-Scaling TODOs“ in [`TODO.md`](../../../TODO.md:43) und ab [`TODO.md`](../../../TODO.md:438) so konkretisieren, dass daraus eine implementierbare, auditierbare Spezifikation entsteht (ohne neue Code-APIs/Flags als Ist-Zustand zu behaupten).

## Kontext / Evidenz (Ist-Zustand)

- Der Repo-Fokus ist „fetch → analysis“ (nicht mehr „correction“), siehe Zielbild in [`TODO.md`](../../../TODO.md:17).
- Der aktuelle LLM-Runner ist als **ein einzelner Job** implementiert und schreibt Artefakte in ein History-Bundle unter `output/history/<topic>/<YYYY-MM-DD>/<HISTORY_BUNDLE>/` (u.a. `report.json`, `manifest.json`, `audit.jsonl`, Prompts), siehe Doku in [`README.md`](../../README.md:480) und Implementierung in [`run_llm_analysis()`](../../src/transcript_ai_analysis/llm_runner.py:339).
  - Prompt-Building: es werden Transcript-Blöcke zusammengefügt und per Char-Limits begrenzt (z.B. „max transcripts“, „max chars per transcript“, „max total chars“), siehe Auswahl-Loop in [`run_llm_analysis()`](../../src/transcript_ai_analysis/llm_runner.py:239).
- Offene Design-Punkte für LLM-Skalierung sind im Backlog explizit notiert (Map/Reduce, Agents/Dependencies, RAG-Trigger, Instructions pro Config), siehe Abschnitt „LLM-Analyse Skalierung“ in [`TODO.md`](../../../TODO.md:436).
- Vorarbeiten/Referenzen:
  - Embeddings/Vector-DB als offene Entscheidung: [`docs/adr/0002-embeddings-vector-db.md`](0002-embeddings-vector-db.md:1)
  - Sizing/Token-Budget als messbasierte Methodik (Zahlen fehlen bewusst): [`docs/adr/0003-sizing-token-budget.md`](0003-sizing-token-budget.md:1)
  - Parallelität/„Agents“/Worker-Modell (Rate-Limits/Kosten/Retry/DLQ): [`docs/adr/0004-parallelism-agents.md`](0004-parallelism-agents.md:1)
  - Kandidaten-Architektur „Segmenter → (Heuristic/LLM extractor) → optional Embeddings/Vector Index → Aggregation“: [`docs/architecture.md`](../architecture.md:413)

## Optionen

### Option A: 1 Job (Single-Prompt, Single-Report)

**Beschreibung:**

- Ein LLM-Call verarbeitet eine (begrenzte) Menge an Transkripten/Chunks und erzeugt direkt den Ziel-Report.

**Vorteile**

- Minimaler Orchestrierungsaufwand, leichter zu testen/bedienen.
- Passt zum heutigen Runner-Modell (ein Report-Artefakt), siehe [`run_llm_analysis()`](../../src/transcript_ai_analysis/llm_runner.py:145).

**Nachteile**

- Skaliert schlecht mit Transcript-Menge/Token-Budget (Context Window), siehe Problemstellung in [`docs/adr/0003-sizing-token-budget.md`](0003-sizing-token-budget.md:1).
- Höheres Risiko, dass irrelevanter Kontext das Signal „verwässert“.
- Eingeschränkte Wiederverwendbarkeit/Zwischenartefakte (z.B. „Extraktion pro Transcript“ als auditierbarer Baustein).

### Option B: Multi-Job (Map/Reduce) mit deterministischen Zwischenartefakten

**Beschreibung:**

- Pipeline in **mindestens zwei Jobs**:
  - **Map/Extract/Compress (Job A):** pro Transcript oder Chunk strukturierte Notizen/Extrakte erzeugen (z.B. JSON/JSONL), mit stabiler Identität und Audit-Bezug.
  - **Reduce/Synthesize (Job B):** nur die kompakten Notizen aggregieren (z.B. pro Channel + global) und daraus den finalen Report erzeugen.

Diese Aufteilung entspricht dem im Backlog skizzierten Vorschlag (Job A/B), siehe [`TODO.md`](../../../TODO.md:450).

**Vorteile**

- Skaliert besser: der „Reduce“-Job arbeitet mit kleineren, gezielten Inputs.
- Bessere Auditierbarkeit: Zwischenartefakte können Quellen/Chunks referenzieren (analog zum Artefakt-/Audit-Prinzip in [`docs/architecture.md`](../architecture.md:41)).
- Bessere Wiederverwendbarkeit: Map-Artefakte können für mehrere Synthesis-Varianten (unterschiedliche Reports) genutzt werden.

**Nachteile**

- Mehr Komplexität (Orchestrierung, Artefakt-Layout, Retry/DLQ, Kostenkontrolle).
- Mehr Entscheidungen nötig (Job-Grenzen, Output-Formate, Determinismus-Policy).

### Option C: Multi-Job + RAG (Embeddings/Vector-Index als Retrieval-Layer)

**Beschreibung:**

- Wie Option B, aber Job B (oder ein Query-Job) nutzt Retrieval über einen Chunk-Index.

**Vorteile**

- Gut bei sehr großen Datenmengen und „spitzen“ Fragen („finde relevante Stellen“).

**Nachteile**

- Zusätzliche Artefakte/Infra (Embedding-Model, Index, Versionierung), siehe offene Punkte in [`docs/adr/0002-embeddings-vector-db.md`](0002-embeddings-vector-db.md:1).

## Entscheidung

Wir dokumentieren als Zielbild eine **Multi-Job Map/Reduce Pipeline (Option B) als Default-Architektur für Skalierung**, behalten aber **1 Job (Option A) als bewusstes „Small-Run/Debug“-Profil**.

Begründung:

- Das Repo hat bereits starke Patterns für deterministische, auditierbare Artefakte (Batch 1 Index, Batch 2 Layout), siehe Artefakt-Definition in [`docs/architecture.md`](../architecture.md:41).
- Ein Single-Prompt-Runner existiert heute und ist nützlich, aber die Skalierungsgrenzen sind absehbar und wurden explizit als offene Entscheidung notiert, siehe Abschnitt „LLM-Analyse Skalierung“ in [`TODO.md`](../../../TODO.md:436) und Sizing-Methodik in [`docs/adr/0003-sizing-token-budget.md`](0003-sizing-token-budget.md:1).

Wichtig: Diese ADR **behauptet keine neuen CLI-Flags oder Config-Felder als Ist-Zustand**; sie beschreibt ein Zielbild/Design.

Zusätzlich treffen wir in diesem ADR eine **messbare, auditierbare Policy** für die Entscheidung

- **Single-Run (1 Job)** vs.
- **Sharding/Multi-Job**

basierend auf **Token-Budget-Heuristiken** (Sizing-Methodik in [`docs/adr/0003-sizing-token-budget.md`](0003-sizing-token-budget.md:1)), ohne konkrete Zahlenwerte festzunageln.

### Decision 1: Scaling-Policy „Single-Run vs. Sharding“ (token-budget-basiert)

**Status:** Normative Policy (implementierbar), aber **proposed** im Sinne von „noch nicht als expliziter Policy-Mechanismus im Code umgesetzt“.

**Ziel:** deterministische, auditable Entscheidung je Run, ob

- (A) der bestehende Single-Job Runner reicht (Small-Run/Debug), oder
- (B) ein Sharding-/Multi-Job-Modus genutzt werden soll (Skalierung).

#### Inputs (normativ)

Diese Inputs müssen für die Entscheidung herangezogen und im Audit festgehalten werden:

1) **Modell-Context-Window** `C` (Tokens)
   - Quelle: Modell-/Provider-Dokumentation (außerhalb des Repos). In diesem Repo wird `C` **nicht** als feste Zahl dokumentiert.

2) **Prompt-Overhead** `P` (Tokens)
   - `P` umfasst `system_prompt` + `user_prompt_template` + Template-Füllung ohne Transcript-Text.
   - Token-Counting-Implementierung ist im Repo grundsätzlich vorhanden (optional via `tiktoken`, Fallback vorhanden), siehe [`calculate_token_count()`](../../src/common/utils.py:165).

3) **Reserve für Output** `R` (Tokens)
   - `R` ist der reservierte Platz für die Modellantwort (z.B. für einen JSON-Report). Der konkrete Wert ist eine Policy-/Config-Entscheidung und wird hier nicht als Zahl behauptet.

4) **Safety-Margin** `m` (0..1)
   - konservative Sicherheitsmarge, um Token-Schätzfehler und Provider-Overhead abzufangen.

5) **Transkript-Menge** (die potenziellen Inputs)
   - pro Kandidat-Transkript eine geschätzte Token-Länge `t_i`.
   - `t_i` kann aus:
     - tatsächlichem Token-Count (falls verfügbar), oder
     - heuristischer Approximation (Fallback), abgeleitet aus dem bestehenden Fallback in [`calculate_token_count()`](../../src/common/utils.py:165).

#### Budget-Definition (normativ)

Wir definieren ein „Single-Run Input Budget“ (Tokens):

`B_single = floor((C - P - R) * m)`

**Wichtig:** Diese Formel ist absichtlich ohne konkrete Zahlenwerte; sie ist das auditierbare Gerüst, das später mit gemessenen/konfigurierten Werten belegt wird.

#### Entscheidungsheuristik (normativ, deterministisch)

Wir berechnen für die ausgewählte Transkript-Menge (siehe „Selektion“ unten):

- `T_in_est = sum(t_i)`
- `N = Anzahl Transkripte`
- `t_max = max(t_i)`
- `share_max = t_max / T_in_est` (falls `T_in_est > 0`, sonst `0`)

**Regel S1 (Hard Budget):**

- Wenn `T_in_est <= B_single`, ist Single-Run **zulässig**.

**Regel S2 (Coverage Guard):**

Single-Run ist nur zulässig, wenn zusätzlich beide Guards erfüllt sind:

1) `N <= N_single_max` *(Policy-Wert, Zahlen folgen aus Sizing; aktuell **proposed**)*
2) `share_max <= share_max_single` *(Policy-Wert, verhindert Dominanz eines einzelnen Transkripts; aktuell **proposed**)*

**Regel S3 (Fallback → Sharding):**

- Wenn S1 **oder** S2 verletzt ist, wird deterministisch auf **Sharding/Multi-Job** umgeschaltet.

#### Selektion/Ordering (normativ; Implementation teilweise bereits vorhanden)

Der heutige Runner selektiert Transkript-Blöcke via Char-Limits (Ist-Zustand), siehe Auswahl-Loop in [`run_llm_analysis()`](../../src/transcript_ai_analysis/llm_runner.py:239). Für die Token-basierte Policy gilt:

- **Ordering:** Kandidaten werden in einer stabilen, deterministischen Reihenfolge betrachtet.
  - Quelle/Empfehlung: nutze die deterministischen Scan-/Sortierpatterns aus dem Index/Batch-1 (siehe Sortierungen in [`README.md`](../../README.md:432)).
- **Selection-Result:** die Policy muss explizit ausweisen, welche Transkripte/Chunks **inkludiert** bzw. **ausgeschlossen** wurden und warum.

> Hinweis (Evidence Gate): Der konkrete Selection-Algorithmus (z.B. „sortiere nach published_at“ vs. „sortiere nach Relevanz“) ist im Code nicht als API dokumentiert. Diese ADR fordert nur Determinismus + Audit-Felder.

#### Audit-Felder (normativ; in Artefakten/Logs zu führen)

Damit die Entscheidung „Single vs Sharding“ messbar/auditierbar ist, müssen pro Run mindestens folgende Felder (als Log-Event und/oder als Teil eines `manifest.json`) erfasst werden:

- `scaling_policy_version` *(string, z.B. `"adr-0008@v1"`)*
- `decision_mode` *(enum: `single_job` | `multi_job` | `rag`)*
- `model` *(string; existiert heute als Konfigfeld, siehe LLM-Anforderungen in [`README.md`](../../README.md:467))*
- `C_tokens`, `P_tokens`, `R_tokens`, `m`
- `B_single_tokens`, `T_in_est_tokens`
- `N_inputs`, `t_max_tokens`, `share_max`
- `guards`: `N_single_max`, `share_max_single`, sowie ob sie erfüllt sind
- `token_estimator`: `method` *(enum: `tiktoken` | `fallback`)* und `estimator_version`
- `selection_summary`: `included_count`, `excluded_count`, `excluded_reasons[]`

Alle Felder sind **proposed** als Audit-Kontrakt (nicht als bestehende JSON-Schema-Fakten).

### Decision 2: „1 Job vs Multi-Job“ (Map/Reduce Rollen)

**Entscheidung (normativ):**

- **Default (Skalierung):** Multi-Job Pipeline (Map/Reduce) wie Option B.
- **Small-Run/Debug:** Single Job (Option A) bleibt erlaubt, wenn die Scaling-Policy (Decision 1) „single_job“ ergibt.

**Job-Rollen (Konzept; normativ, aber Artefakt-Details sind proposed):**

- **Job A — Extract/Compress (Map):**
  - Input: einzelne Transkripte oder deterministische Chunks.
  - Output: strukturierte „Notes/Extracts“ pro Input (bevorzugt JSON/JSONL), die **Evidence-Pointer** enthalten (Policy/Format-Prinzip siehe [`docs/analysis/llm_prompt_spec_strict_json_evidence.md`](../analysis/llm_prompt_spec_strict_json_evidence.md:1)).
  - Ziel: Kontext komprimieren, irrelevantes entfernen, Evidence stabil verlinken.

- **Job B — Synthesize/Report (Reduce):**
  - Input: die kompakten Notes/Extracts aus Job A (nicht die Rohtranskripte).
  - Output: finaler Report im bestehenden LLM-Report-Format (kanonisch [`report.json`](../../README.md:487) + derived view), siehe Artefakt-ADR [`docs/adr/0007-llm-output-formats-json-vs-markdown.md`](0007-llm-output-formats-json-vs-markdown.md:1) und Output-Liste in [`README.md`](../../README.md:485).

**Policy:**

- Job A und Job B müssen jeweils einen eigenen Audit-Trail haben (Manifest + Audit-Events), analog zum bestehenden Pattern im Single-Job Runner (Artefakte unter `output/history/<topic>/.../`, siehe [`manifest.json`](../../README.md:480) + [`audit.jsonl`](../../README.md:480)).

### Decision 3: Agents/`depends_on` (nur konzeptuell)

**Entscheidung:** Wir modellieren die Pipeline als **Job-DAG**, deren Kanten per `depends_on` beschrieben werden.

- `depends_on` ist ein **konzeptuelles** Feld/Attribut für Job-Definitionen (proposed).
- Ein „Agent“ ist ein Ausführungsmodell (Worker), nicht die fachliche Semantik.

Normative Regeln:

1) **DAG, keine Zyklen**: `depends_on` darf keine Zyklen erzeugen.
2) **Artefakt-basierte Abhängigkeiten**: Abhängigkeiten gelten als erfüllt, wenn die referenzierten Artefakte vorhanden sind und deren Input-Fingerprint zum aktuellen Run passt.
   - Evidenz/Pattern: Fingerprint-Mechanik existiert heute im LLM-Runner, siehe [`_compute_run_fingerprint()`](../../src/transcript_ai_analysis/llm_runner.py:111).
3) **Retry-Isolation**: Failures in Job A dürfen Job B blockieren, aber müssen als „partial coverage“ auditierbar sein (welche Inputs fehlen?).

### Decision 4: Embeddings/RAG Trigger (entscheidbar + auditierbar)

Diese ADR trifft keine Entscheidung „Embeddings ja/nein“ (siehe separaten ADR [`docs/adr/0002-embeddings-vector-db.md`](0002-embeddings-vector-db.md:1)), sondern definiert Trigger-Kriterien, wann RAG als Modus sinnvoll/erforderlich ist.

**Entscheidung (normativ):**

- RAG wird **getriggert**, wenn entweder
  1) die Scaling-Policy (Decision 1) auch nach Map/Compression regelmäßig Budget-Überschreitungen zeigt, **oder**
  2) die Fragestellung primär „Retrieval“ ist (Belege/Zitate finden), **oder**
  3) die Relevanz-Dichte sehr gering ist (viel Rauschen, wenige relevante Chunks), **oder**
  4) wiederholte Queries auf demselben Datenbestand laufen (Retrieval amortisiert sich).

Damit „RAG Trigger“ auditierbar ist, definieren wir (proposed) messbare Observables (ohne Zahlen):

- `budget_exceeded_rate`: Anteil Runs, in denen `T_in_est > B_single` (oder in Multi-Job ein analoges Budget überschritten wird)
- `relevance_density_est`: Anteil als relevant markierter Chunks/Notes (z.B. via Heuristik oder Output-Counts aus Job A)
- `query_profile`: Klassifikation `retrieval_heavy` vs `synthesis_heavy` (Heuristik, proposed)
- `repeat_queries_over_same_corpus`: boolean/Counter (proposed)

**Audit-Felder (normativ, proposed):**

- `rag_triggered` *(bool)*
- `rag_trigger_reasons[]` *(enum-liste: `budget_exceeded`, `retrieval_heavy`, `low_relevance_density`, `repeat_queries`)*
- `rag_corpus_fingerprint` *(string; stabiler Hash über Chunk-/Notes-Korpus)*

### Decision 5: „LLM Instructions“ pro Config/Topic (Semantik)

Ziel: pro Config/Topic klar festhalten, *was* analysiert werden soll, ohne ein neues, starres Report-Schema zu erzwingen.

#### Ist-Zustand (implementiert)

Heute „leben“ die Instructions bereits in den vorhandenen Prompt-Feldern unter `analysis.llm.*`:

- `analysis.llm.system_prompt`
- `analysis.llm.user_prompt_template`

Diese Felder werden als required validiert, wenn `analysis.llm.enabled=true` (siehe Doku in [`README.md`](../../README.md:467)).

#### Normative Struktur (ohne neue Config-Felder zu behaupten)

Wir definieren die Semantik „pro Topic“ so:

1) **Topic = Config-Intent**
   - Eine YAML-Config repräsentiert ein Topic/Intent („stocks“, „us-politics“, …) durch ihren Inhalt und ihre Benennung.
   - Konsequenz: Topic-spezifische Instructions werden in **dieser** Config gepflegt.

2) **Trennung: stabile Guardrails vs. topic-spezifischer Auftrag**
   - `system_prompt` enthält stabile, wiederverwendbare Regeln (Output-Format, Evidence-Pflicht, Verbote wie „keine erfundenen Fakten“), idealerweise referenzierend auf die Prompt-Spezifikation [`docs/analysis/llm_prompt_spec_strict_json_evidence.md`](../analysis/llm_prompt_spec_strict_json_evidence.md:1).
   - `user_prompt_template` enthält den Topic-spezifischen Auftrag (z.B. „Stock-Coverage + thematisches Covered“, „US-Politik Narrative“, …) und ggf. parameterisierte Slots.

3) **Auditierbarkeit**
   - Der Runner schreibt (Ist-Zustand) die effektiven Prompts als Artefakte, siehe [`system_prompt.txt`](../../README.md:492) und [`user_prompt.txt`](../../README.md:492).
   - Für Topic-Tracking wird empfohlen, im Report/Manifest ein Topic-Label zu führen.
      - **proposed:** ein Feld wie `topic` oder `instruction_set_id` im Manifest.

#### Proposed Erweiterung (optional, nicht implementiert)

Wenn Multi-Job/Multiple Topics pro Run benötigt werden, ist eine datengetriebene Struktur wie „Jobs-Liste“ sinnvoll.

- **proposed:** `analysis.llm.jobs[]` (Job-Definitionen inkl. `name`, `depends_on`, Prompt-Templates, Output-Kontrakt)
- Alternativ (ebenfalls proposed): ein `analysis.topics[]` Block.

Evidence Gate: Diese Felder existieren aktuell nicht als dokumentierte Ist-Schema-Felder in [`docs/config.md`](../config.md:1); sie sind hier explizit als **proposed** markiert.

## Einordnung: „Agents“ und Job-Dependencies (konzeptionell)

Begriffsdefinition (für dieses Repo):

- Ein **Job** ist ein deterministischer Pipeline-Schritt, der aus definierten Inputs Artefakte erzeugt.
- Ein **Agent** ist (konzeptionell) ein Worker, der Jobs ausführt (seriell oder parallel). Er ist **keine** Produktfunktion an sich, sondern ein Ausführungsmodell.
- **Job-Dependencies** (`depends_on`) beschreiben eine DAG-Reihenfolge („welche Artefakte müssen existieren, bevor Job X starten darf“).

Konzeptuell passt das zur bestehenden Diskussion „Parallelität/Agents/Worker“ (Rate-Limits/Kosten/Retry), siehe [`docs/adr/0004-parallelism-agents.md`](0004-parallelism-agents.md:1).

Beispiel-DAG (nur Konzept, keine API):

```text
batch1_index
  -> segment
     -> extract_notes (LLM)
        -> critique_notes (LLM, optional)
           -> synthesize_report (LLM)
```

Policy-Vorschlag (Design, nicht implementiert):

- Dependencies werden über Artefakt-Existenz/Fingerprints entschieden (analog zum Input-Fingerprint-Pattern im heutigen LLM-Runner, siehe [`_compute_run_fingerprint()`](../../src/transcript_ai_analysis/llm_runner.py:111)).
- Jeder Job schreibt ein `manifest.json` + `audit.jsonl`, damit Re-Runs, Retry und Debugging standardisiert sind (Pattern existiert bereits im Ist-Zustand, siehe Artefakte in [`README.md`](../../README.md:450)).

## RAG/Embeddings: Trigger-Kriterien (qualitativ)

RAG ist hier ein **Skalierungs- und Relevanz-Werkzeug**: statt „alles in den Prompt“, werden **relevante Chunks** retrieved.

Trigger-Kriterien (qualitativ; konkrete Schwellenwerte sind **unsicher**, weil Sizing-Zahlen explizit fehlen, siehe Methodik in [`docs/adr/0003-sizing-token-budget.md`](0003-sizing-token-budget.md:14)):

1) **Token-/Kontextbudget wird regelmäßig überschritten**
   - Symptom: selbst nach Chunking/Map-Compression passt der Input nicht stabil in das gewünschte Modell-Context-Window.
   - Mess-/Sizing-Grundlage: siehe Methodik in [`docs/adr/0003-sizing-token-budget.md`](0003-sizing-token-budget.md:14).

2) **Die Fragestellung ist retrieval-lastig** („suche relevante Evidenzstellen“)
   - Beispiele: „Finde alle Stellen zu Topic X“, „zeige Gegenbeispiele“, „gib Quellen für Claim Y“.
   - Heuristik: wenn „Finden“/„Belege“/„Zitate“ dominieren, ist Retrieval häufig effektiver als Vollprompt.

3) **Hohe Heterogenität / viele irrelevante Transkripte**
   - Wenn nur ein kleiner Anteil der Transkripte relevant ist, verbessert Retrieval das Signal-Rausch-Verhältnis.

4) **Wiederholte Queries über denselben Datenbestand**
   - RAG amortisiert sich eher, wenn mehrere Analysen/Reports auf denselben Chunks laufen.

Hinweis: Die Entscheidung „Embeddings ja/nein“ und die Wahl des Index-Typs (lokal vs. Vector-DB) bleibt separat (siehe [`docs/adr/0002-embeddings-vector-db.md`](0002-embeddings-vector-db.md:1)). Diese ADR definiert nur, **wann** RAG konzeptionell getriggert wird.

## „LLM Instructions“ pro Config/Topic (Konzept)

Ziel: Eine Config soll nicht nur „LLM enabled + Prompt“ enthalten, sondern **das Analyse-Intent eines Topics** beschreiben (z.B. „Stocks“, „US-Politik“, „E-Autos“) und die dafür nötigen Jobs/Prompts definieren.

### Ist-Zustand (heute)

- Es gibt eine LLM-Analyse-Konfiguration, die mindestens `analysis.llm.enabled`, `analysis.llm.model`, `analysis.llm.system_prompt`, `analysis.llm.user_prompt_template` verlangt (Doku: [`README.md`](../../README.md:467)).
- Der Runner erzeugt genau **einen** Job-Report („llm_v1“), siehe `batch: "llm_v1"` in [`run_llm_analysis()`](../../src/transcript_ai_analysis/llm_runner.py:343).

### Vorschlag (Design, ohne Implementation): „Instructions“ als Topic-/Job-Definition

Wir schlagen vor, „LLM Instructions“ als **datengetriebenes** Konzept zu definieren:

- **Topic/Intent**: Ein Name/Label („stocks“, „us-politics“, …), der die Analyse beschreibt.
- **Jobs**: Eine Liste von Job-Definitionen (z.B. `extract_notes`, `synthesize_report`) inkl. Prompt-Templates.
- **Artefakt-Verträge**: pro Job ein definierter Output (z.B. JSONL Notizen, finaler Report), kompatibel zu den ADRs zu Output-Formaten, siehe [`docs/adr/0007-llm-output-formats-json-vs-markdown.md`](0007-llm-output-formats-json-vs-markdown.md:1).

Wie das ins Config-Schema passen könnte (nur Optionen, keine Faktenbehauptung):

1) **Option 1: `analysis.llm` erweitert um `jobs`**
   - Vorteil: „LLM“ bleibt unter `analysis` und ist konsistent zum heutigen Ort.
   - Risiko: Schema wird komplexer; Validierung muss sauber zwischen „single job“ und „multi job“ unterscheiden.

2) **Option 2: neuer Block `analysis.topics[]` mit `llm_instructions`**
   - Vorteil: mehrere Topics/Reports pro Run möglich.
   - Risiko: erfordert Orchestrierung/Job-Scheduling.

3) **Option 3: Instructions als externe Dateien** (z.B. `prompts/*.md` oder `prompts/*.jinja`)
   - Vorteil: Prompts versionierbar/lesbar; Wiederverwendung.
   - Risiko: Pfad-Auflösung/Policy muss zur bestehenden Config-Path-Resolution passen (siehe Pfad-Policy in [`docs/config.md`](../config.md:216)).

Empfehlung (Design): **Option 1** als kleinster Schritt, solange der Runner ohnehin in `analysis.llm` verankert ist.

## Konsequenzen

Wenn Option B (Multi-Job) umgesetzt wird, folgt daraus:

- Es braucht ein **Artefakt-Layout** für Zwischenoutputs (z.B. „notes.jsonl“) analog zu Batch 1/2: Manifest + Audit + versionierbares Schema.
- Es braucht eine deterministische **Job-Identität** (Input-Fingerprint pro Job), damit Re-Runs und Caching möglich sind (Pattern existiert bereits im Ist-Zustand, siehe [`_compute_run_fingerprint()`](../../src/transcript_ai_analysis/llm_runner.py:111)).
- „Agents/Parallelität“ wird zu einer separaten Durchsatz-Entscheidung (bounded parallelism), siehe offene Punkte in [`docs/adr/0004-parallelism-agents.md`](0004-parallelism-agents.md:20).
- RAG/Embeddings wird nicht automatisch „Default“, sondern ein optionaler Layer mit klaren Triggern (oben) und separater ADR-Entscheidung (0002).

## Offene Punkte / ToDo

- Messung/Report der Transcript-Token-Verteilung (Sizing) als Input für Schwellenwerte, siehe Methodik in [`docs/adr/0003-sizing-token-budget.md`](0003-sizing-token-budget.md:14).
- Festlegen (und später umsetzen) der Policy-Werte `N_single_max`, `share_max_single`, `R`, `m` pro Modell/Profil auf Basis der Sizing-Messung.
- Festlegen eines minimalen Job-Sets (A/B) und der Output-Formate (JSON vs. Markdown/Text) pro Job, siehe [`docs/adr/0007-llm-output-formats-json-vs-markdown.md`](0007-llm-output-formats-json-vs-markdown.md:1).
- Entscheidung, ob Retrieval „lokal“ oder via Vector-DB erfolgt (oder gar nicht), siehe [`docs/adr/0002-embeddings-vector-db.md`](0002-embeddings-vector-db.md:1).
