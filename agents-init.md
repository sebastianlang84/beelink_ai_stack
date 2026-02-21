# agents-init.md - One-shot Bootstrap fuer AGENTS + Memory + Guardrails (+ Skills)

Diese Datei ist fuer **neue Projekte** gedacht und soll die **erste Datei** sein, die einem Coding Agent gegeben wird.

Ziel: In einem frischen Repo eine belastbare Agent-Governance mit Memory-Routing, Living-Docs, Skill-Standard und Guardrails anlegen.

Wichtig: Nach erfolgreichem Bootstrap muss der Agent diese Datei loeschen (`agents-init.md`).

## 1) Ausfuehrungsvertrag (verbindlich)

1. Nur ein Ziel in diesem Task: Governance/Memory/Guardrail-Grundgeruest anlegen.
2. Erst lesen, dann schreiben.
3. Keine Secrets in Dokumente.
4. Keine Scope-Ausweitung auf Service-Code.
5. Abschluss nur mit Verifikation.
6. Danach Self-Cleanup: `agents-init.md` loeschen.

## 2) Ablauf (vom Agent in genau dieser Reihenfolge ausfuehren)

### Phase A - Preflight + Read-only Diagnose

Vor dem ersten write ausgeben:
- `Ziel`
- `Scope (in/out)`
- `Gelesene Quellen`

Dann read-only pruefen:
- `pwd`
- `git status --short`
- `rg --files`
- Falls vorhanden lesen: `AGENTS.md`, `SKILL.md`, `MEMORY.md`, `README.md`, `INDEX.md`, `TODO.md`, `CHANGELOG.md`
- Falls vorhanden lesen: `skills/*/SKILL.md` (nur die fuer den aktuellen Task relevanten)

### Phase B - Bootstrap schreiben

Falls Dateien fehlen: anlegen.
Falls Dateien schon existieren: nur minimal noetige Inhalte mergen, keine user-fremden Inhalte loeschen.

Pflichtstruktur:

```text
AGENTS.md
SKILL.md
CLAUDE.md -> AGENTS.md (symlink; wenn Claude-Modelle verwendet werden)
MEMORY.md
README.md
INDEX.md
TODO.md
CHANGELOG.md
agents/README.md
agents/adr/README.md
agents/memory/daily/.gitkeep
docs/adr/README.md
docs/policies/policy_secrets_env.md
skills/ (optional, mit `skills/<skill-name>/SKILL.md`)
```

### Phase C - Verifikation

Pflichtchecks (read-only):
- `rg -n "^# AGENTS.md" AGENTS.md`
- `rg -n "^# SKILL.md" SKILL.md`
- falls Claude im Scope: `test -L CLAUDE.md && [ "$(readlink CLAUDE.md)" = "AGENTS.md" ]`
- `rg -n "^# MEMORY" MEMORY.md`
- `rg -n "^# INDEX" INDEX.md`
- `rg -n "^# TODO" TODO.md`
- `rg -n "^# Changelog" CHANGELOG.md`
- `rg -n "^# agents/README" agents/README.md`
- `rg -n "^# Policy: Secrets" docs/policies/policy_secrets_env.md`
- falls vorhanden: `rg -n "^# SKILL.md" skills/*/SKILL.md`

### Phase D - Living Docs + Commit + Self-Delete

1. `README.md`, `TODO.md`, `CHANGELOG.md` auf Konsistenz pruefen/aktualisieren.
2. `MEMORY.md` aktualisieren oder explizit dokumentieren: `MEMORY.md geprueft: keine Aenderung noetig`.
3. Commit erstellen (`type(scope): kurze beschreibung`).
4. **Danach** `agents-init.md` loeschen.
5. Loeschung verifizieren: `test ! -f agents-init.md`.
6. Wenn noetig zweiten Commit fuer die Loeschung erstellen.

## 2.1) Claude-Kompatibilitaet (wenn Claude-Modelle im Spiel sind)

- Nach Erstellung von `AGENTS.md` einen Symlink anlegen:
  - `ln -s AGENTS.md CLAUDE.md`
- Wenn `CLAUDE.md` bereits existiert und nicht auf `AGENTS.md` zeigt:
  - nicht automatisch ueberschreiben, sondern Stop & Ask.
- Ziel: identische Regeln fuer Agent-Engines, die `CLAUDE.md` erwarten.

## 2.2) Skill-Standard (Anthropic `SKILL.md`)

- Root-`SKILL.md` anlegen, damit projektweite Skill-Regeln explizit sind.
- Optional: konkrete Skills unter `skills/<skill-name>/SKILL.md` ablegen.
- Wenn ein Skill namentlich angefordert wird oder klar passt:
  - Skill-Datei zuerst oeffnen und befolgen.
- Kontext klein halten:
  - Nur relevante Teile aus `SKILL.md` laden (keine Bulk-Reads).
- Bei Konflikt zwischen `AGENTS.md` und `SKILL.md`:
  - Stop & Ask vor der Umsetzung.

## 3) Template: `AGENTS.md`

```md
# AGENTS.md - <PROJECT_NAME>

Dieses Dokument ist die hoechste Agent-Policy in diesem Repository.

## 0) Prioritaet
- `AGENTS.md` (dieses File) ist die oberste Regelquelle.
- Bei Claude-Engines: `CLAUDE.md` soll als Symlink auf `AGENTS.md` zeigen.
- `SKILL.md` ist gleichrangig zu `AGENTS.md` (Anthropic Standard).
- Wenn Skill namentlich angefordert wird oder klar passt: Skill zuerst.
- Projekt-spezifische Skills liegen unter `skills/<skill-name>/SKILL.md`.
- Bei Widerspruch zwischen `AGENTS.md` und `SKILL.md`: Stop & Ask.
- `AGENT.md` (falls vorhanden) ist nachrangig.

## 1) Non-Negotiables
- Keine Action-first Ausfuehrung: erst verifizieren, dann handeln.
- Kein Raten bei Unklarheit: Annahmen klar markieren.
- Kein Scope-Mix: pro Task genau ein technisches Ziel.
- Keine Secrets committen.

## 2) Ausfuehrungsprotokoll

### Gate A: Preflight
Vor dem ersten write kurz ausgeben:
- Ziel
- Scope (in/out)
- Gelesene Quellen

### Gate B: Read-only Diagnose
Nur lesen/pruefen (Status, Files, Logs, Config-Validierung).
Keine mutierenden Schritte.

### Gate C: Umsetzung
Nach Diagnose und User-Freigabe (`go`/`mach`) umsetzen.
Ausnahme: User verlangt explizit sofortige Umsetzung.

### Gate D: Verifikation
Nach jeder Aenderung Erfolg pruefen.
Ohne Verifikation ist ein Task nicht abgeschlossen.

## 3) Doku-Vertrag
- `README.md`: Operator-Guide (Setup/Run/Recover)
- `INDEX.md`: Link-Navigation
- `MEMORY.md`: Snapshot + Langzeitgedaechtnis (kurz, statusorientiert)
- `TODO.md`: aktive Arbeit
- `CHANGELOG.md`: user-/operator-relevante Aenderungen
- `agents/adr/`: Agent-/Prozessentscheidungen
- `docs/adr/`: Architektur-/Serviceentscheidungen

## 4) Living Docs Pflicht
- Bei jeder relevanten Aenderung `README.md`, `TODO.md`, `CHANGELOG.md` pruefen/aktualisieren.
- Wenn keine Aenderung noetig ist, explizit festhalten.

## 5) Memory Routing
- Stabil/semantisch -> `MEMORY.md`
- Prozedural -> `docs/runbooks/*`
- Episodisch -> `agents/memory/daily/*`
- Agent-/Prozess-Why -> `agents/adr/*`
- Architektur-/Service-Why -> `docs/adr/*`

## 6) Sicherheits-Guardrails
- `.env` nur Secrets.
- Non-Secrets in `.config.env` und `<service>/.config.env`.
- Keine neuen Host-Ports ohne Begruendung + Doku.
- Reverse Proxy/VPN-only bevorzugen statt direktem Exposing.

## 7) Abschlusspflicht pro Task
1. Ergebnis verifizieren.
2. `MEMORY.md` pruefen/aktualisieren.
3. Living Docs pruefen/aktualisieren.
4. Commit erstellen (wenn User nichts anderes sagt).

## 8) Commit-Format
`type(scope): kurze beschreibung`

`type` in `{docs, fix, feat, chore, ops, refactor, test}`
```

## 4) Template: `MEMORY.md`

```md
# MEMORY
last_updated: <YYYY-MM-DD>
scope: always-loaded bootstrap; max ~200 lines

Purpose: One-page snapshot plus reset-resilient long-term memory for the next context.

## 1) Current State
- <3-10 knappe bullets zum Ist-Zustand>

## 2) Long-Term Memory
- Kontinuitaet ist dateibasiert, nicht chatbasiert.
- Verbindliche Absprachen muessen in Repo-Dateien stehen.
- Keine Secrets in Memory-Dateien.

## 3) Open Decisions
- <offene Entscheidungen + Default>

## 4) Next Steps
1. <naechster sinnvoller Schritt>
2. <optional>

## 5) Known Risks / Blockers
- <Risiko oder "None">
```

## 5) Template: `README.md`

```md
# <PROJECT_NAME>

Purpose: Operator guide.
Contains: Setup, Run, Test, Deploy, Troubleshooting.
Does not contain: laufende Entscheidungen/Historie.

Startpunkt fuer Navigation: `INDEX.md`.

## Quickstart
1. <Setup>
2. <Run>
3. <Healthcheck>

## Memory Routing (kurz)
- `AGENTS.md` -> `MEMORY.md` zuerst laden.
- Stabil/semantisch -> `MEMORY.md`
- Prozedural -> `docs/runbooks/*`
- Episodisch -> `agents/memory/daily/*`
- Entscheidungs-Why -> `agents/adr/*`, `docs/adr/*`

## Repo-Struktur
- `AGENTS.md`
- `SKILL.md`
- `CLAUDE.md` (Symlink auf `AGENTS.md`, falls Claude-Modelle genutzt werden)
- `INDEX.md`
- `MEMORY.md`
- `TODO.md`
- `CHANGELOG.md`
- `agents/`
- `docs/`
- `skills/` (optional, projekt-spezifische Skills)
```

## 5.1) Template: `SKILL.md`

```md
# SKILL.md - <PROJECT_NAME> Skills

Purpose: Projektweite Skill-Regeln und Routing.

## Prioritaet
- `SKILL.md` ist gleichrangig zu `AGENTS.md`.
- Bei Widerspruch: Stop & Ask.

## Verwendung
- Wenn ein Skill namentlich angefordert wird oder klar passt:
  - Skill zuerst oeffnen und befolgen.
- Projekt-Skills liegen unter `skills/<skill-name>/SKILL.md`.
- Nur relevante Teile lesen; keine unnoetigen Bulk-Reads.

## Skill-Struktur (optional)
- `skills/<skill-name>/SKILL.md`
- `skills/<skill-name>/scripts/`
- `skills/<skill-name>/assets/`
- `skills/<skill-name>/references/`
```

## 6) Template: `INDEX.md`

```md
# INDEX

Purpose: Navigation-only entrypoint.

## Core Docs
- `AGENTS.md` - normative agent/process rules
- `SKILL.md` - skill rules (Anthropic standard)
- `README.md` - operator guide
- `MEMORY.md` - current snapshot + long-term memory
- `TODO.md` - active work only
- `CHANGELOG.md` - release/user-facing changes
- `agents/README.md` - agent docs catalog

## Memory Routing
- `MEMORY.md` - status + stable defaults
- `docs/runbooks/` - procedural SOP/how-to
- `agents/memory/daily/` - episodic day logs
- `agents/adr/` - agent/process decision rationale
- `docs/adr/` - architecture/service decision rationale
```

## 7) Template: `TODO.md`

```md
# TODO / Active Backlog

Purpose: Active work only.
Contains: Open tasks with priority and status.
Does not contain: Completed history.

## P0 (Now)
- None.

## P1 (Next)
- None.

## P2 (Later)
- None.
```

## 8) Template: `CHANGELOG.md`

```md
# Changelog

All notable user-/operator-relevant changes are documented in this file.
This project follows a Keep a Changelog style.

## [Unreleased]
### Added
- Initial governance/bootstrap docs.

### Changed
- None.

### Fixed
- None.

### Breaking
- None.
```

## 9) Template: `agents/README.md`

```md
# agents/README

Purpose: Catalog for agent-governance and continuity documents.

## Scope
- Agent process and policy decisions: `agents/adr/`
- Episodic continuity logs: `agents/memory/daily/`

## Root Main Docs
- `AGENTS.md`
- `MEMORY.md`
- `INDEX.md`
- `README.md`
```

## 10) Template: `agents/adr/README.md`

```md
# agents/adr

Purpose: Agent/process/documentation governance decisions.

ADR format:
- Context
- Decision
- Consequences
- Alternatives
```

## 11) Template: `docs/adr/README.md`

```md
# docs/adr

Purpose: Architecture/service decisions.

ADR format:
- Context
- Decision
- Consequences
- Alternatives
```

## 12) Template: `docs/policies/policy_secrets_env.md`

```md
# Policy: Secrets and Env Files

## Grundsatz
- `.env` enthaelt nur Secrets (API keys, tokens, passwords, private keys).
- Non-Secrets gehoeren in `.config.env` oder `<service>/.config.env`.

## Compose-Start
`docker compose --env-file .env --env-file .config.env --env-file <service>/.config.env -f <service>/docker-compose.yml up -d`

## Guardrails
- Keine Secrets committen.
- `.env*` und service `.config.env` gitignoren.
- Beispielwerte nur in `*.example` Dateien committen.
```

## 13) Abschlussmeldung (vom Agent nach Bootstrap)

Die Abschlussmeldung muss enthalten:
1. Ist-Zustand
2. Naechster Schritt
3. Risiko/Blocker (nur wenn vorhanden)
4. Liste der angelegten/aktualisierten Dateien
5. Verifikationschecks
6. Hinweis, dass `agents-init.md` geloescht wurde

---

Wenn du diese Datei als Agent liest: Fuehre jetzt den Bootstrap aus, verifiziere, committe, loesche diese Datei, und melde knapp mit Dateiliste + Checks.
