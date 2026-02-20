# Framework - Context Engineering 5+2 (Architect, Trace, Link, Assemble, Stress Test, Validate, Monitor)

Zweck: Dieses Framework reduziert Zufall in KI-gestuetzter Entwicklung, indem vor dem Coden klare Ziele, technische Grenzen und Pruefschritte festgelegt werden.

Hinweis: "Deterministisch" ist in der Praxis nicht absolut erreichbar, aber mit diesem Prozess wird das Ergebnis deutlich reproduzierbarer und stabiler.

Template im Repo:
- `goals/build_app.md`

## Ueberblick
1. Architect
2. Trace
3. Link
4. Assemble
5. Stress Test
6. Validate (Production)
7. Monitor (Production)

## 1) Architect (Bauplan)
Ziel: Klar definieren, wie Erfolg aussieht, bevor implementiert wird.

Pflichtinhalte:
- Problem: Welches konkrete Problem wird geloest?
- User: Fuer wen wird gebaut?
- Success: Woran messen wir "fertig" (Definition of Done)?
- Constraints: Budget, Zeit, Compliance, Tech-Limits.

Output:
- Ein kurzes PRD/Goal-Dokument mit messbaren Abnahmekriterien.

## 2) Trace (Technische Blaupause)
Ziel: Front-loading der technischen Entscheidungen, statt spaeterem Tool-Hopping.

Pflichtinhalte:
- Data Schema: Tabellen/Modelle/Objekte inkl. Felder und Verantwortlichkeit.
- Integrations Map: Externe Systeme, Endpunkte, Auth-Flows.
- Tech Stack: Frameworks, Build/Deploy-Pfad, Runtime.

Output:
- Architekturblatt mit Datenfluss und festen Integrationsentscheidungen.

## 3) Link (Verbindungspruefung)
Ziel: Vor dem Build sicherstellen, dass Integrationen real funktionieren.

Pflichtinhalte:
- API Reachability (Endpoint lebt wirklich)
- Auth-Pruefung (Token/Scopes korrekt)
- Minimaler Request/Response-Smoke-Test pro Integration

Output:
- Kurzes Link-Protokoll: "Verbindung ok/nicht ok + Grund".

## 4) Assemble (Schichtweiser Zusammenbau)
Ziel: In stabilen Layers liefern, nicht als One-Shot-Block.

Empfohlene Reihenfolge:
1. Basis: Datenzugriff/Storage.
2. Logik: Backend/Worker/Edge.
3. Interface: UI und Interaktion.

Output:
- Kleine, testbare Inkremente statt grosser Yolo-Generierung.

## 5) Stress Test (Belastungsprobe)
Ziel: Vor Deploy Robustheit gegen reale und unguenstige Nutzung pruefen.

Pflichtinhalte:
- Functional Tests (Happy Path)
- Edge Cases (ungewoehnliche Inputs, leere Daten, Timeouts)
- Error Handling (saubere Fehler statt Crash)

Output:
- Testprotokoll mit bestanden/nicht bestanden und Rest-Risiken.

## 6) Validate (Production-Level)
Ziel: Security und Korrektheit als feste Gate-Stufe.

Pflichtinhalte:
- Zugriffskontrolle und Rollen
- Datenisolation (z. B. tenant/read/write boundaries)
- Input Validation, sichere Defaults, Secrets-Handling

Output:
- Security/Correctness-Checklist mit expliziter Freigabeentscheidung.

## 7) Monitor (Production-Level)
Ziel: Laufzeit-Transparenz fuer Stabilitaet, Kosten und Qualitaet.

Pflichtinhalte:
- Laufzeitmetriken (Latenz, Fehlerquote, Queue-Dauer)
- Business-nahe Signale (Drop-offs, Erfolgsrate)
- Strukturierte Logs/Tracing fuer Debug und Postmortems

Output:
- Minimales Monitoring-Dashboard + Alert-Trigger.

## Praktische Arbeitsregel
- Keine Phase ueberspringen.
- Bei roten Checks wird nicht "weitercodiert", sondern auf die letzte gruenen Phase zurueckgesprungen.
- Jede Phase erzeugt ein explizites Artefakt (Doc, Test, Report), damit der Prozess reproduzierbar bleibt.

## Meine Einschaetzung
Stark:
- Sehr guter Schutz gegen KI-Raten und Scope-Drift.
- Besonders wirksam in Teams und bei laengeren Projekten.
- Erzwingt klare Akzeptanzkriterien und bessere Debugbarkeit.

Schwachstelle:
- Mehr Overhead bei sehr kleinen Wegwerf-Prototypen.
- "Determinismus" sollte als Zielrichtung verstanden werden, nicht als Garantie.

Empfehlung:
- Fuer alles ab "mehr als 1-2 Integrationen" klar anwenden.
- Fuer Mini-MVPs als Light-Version nutzen (Architect/Trace/Link/Stress Test mindestens).
