# ADR 0002: Embeddings + Vector-DB (z.B. Qdrant) ja/nein?

Status: **Proposed** (noch keine Entscheidung)

## Problem

Wir müssen festlegen, ob die Analyse eine semantische Retrieval-Komponente braucht (Embeddings + Vector-Index), oder ob strukturierte Extraktion (Regeln/LLM) ohne Vector-DB ausreicht.

## Kontext / Evidenz

- Context-Window kann bei vielen Transkripten eng werden; daher ist „alles in einen Prompt“ nicht skalierbar (Sizing wird separat behandelt: [`docs/adr/0003-sizing-token-budget.md`](0003-sizing-token-budget.md:1)).
- Zielbild der Analyse: Stock-Coverage + globaler Report (siehe [`TODO.md`](../../../TODO.md:17)).

## Optionen

### A) Keine Embeddings, nur strukturierte Extraktion

**Vorteile**

- Weniger Infrastruktur/Komplexität
- Gut für deterministische Pipelines

**Nachteile**

- Semantische Suche/Topic-Clustering schwierig
- RAG-Workflows nur eingeschränkt möglich

### B) Embeddings + lokaler Index (leichtgewichtig)

**Vorteile**

- Retrieval für LLMs/Clustering möglich ohne Serverbetrieb

**Nachteile**

- Trotzdem zusätzliche Pipeline-Schritte + Versionierung nötig

### C) Embeddings + Vector-DB (z.B. Qdrant)

**Vorteile**

- Skalierbares Retrieval, Filter/Metadata, gute Basis für RAG

**Nachteile**

- Zusätzliche Operations/Deployment-Komplexität

## Entscheidung

Noch offen.

## Konsequenzen

- Wenn B/C gewählt wird, müssen Chunking/Segmentation + Embedding-Schema als Artefakte definiert werden (siehe [`TODO.md`](../../../TODO.md:43)).

## Offene Punkte / ToDo

- Klären, ob semantische Suche als Produktfeature gewünscht ist.
- Messung: Retrieval-Bedarf anhand realer Queries/Prompts.
