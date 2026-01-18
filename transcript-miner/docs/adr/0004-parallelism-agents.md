# ADR 0004: Parallelität/„Agents“/Worker-Modell

Status: **Proposed** (noch keine Entscheidung)

## Problem

Wir müssen definieren, wie viele parallele Worker/„Agents“ die Analyse nutzt, wie Rate-Limits/Kosten kontrolliert werden und wie Fehler/DLQ gehandhabt werden.

## Kontext / Evidenz

- Zielbild verschiebt den Fokus auf Analysis (siehe [`TODO.md`](../../../TODO.md:17)).

## Optionen

### A) Single-Worker (N=1)

- Einfach zu debuggen, minimale Risiken
- Durchsatz ggf. zu gering

### B) Bounded Parallelism (N=2–K)

- Gute Balance (Kosten/Rate-Limits/Throughput)
- Erfordert saubere Retry/DLQ/Idempotenz

### C) Distributed/Queue-basiert

- Skaliert stark, aber hohe Komplexität

## Entscheidung

Noch offen.

## Konsequenzen

- Für B/C müssen Run-Namespaces und deterministische Re-Runs klar geregelt sein (siehe [`TODO.md`](../../../TODO.md:51)).

## Offene Punkte / ToDo

- Rate-Limits/Provider-Limits sammeln.
- Ziel-Durchsatz definieren (SLA: „X Videos in Y Minuten“).
