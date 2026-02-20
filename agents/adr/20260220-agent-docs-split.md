# ADR: Split agent-governance docs from docs/
Date: 2026-02-20
Status: Accepted

## Context
- `docs/` mixed service/architecture docs with agent-governance and episodic memory files.
- This blurred ownership and made navigation harder: operator docs and agent continuity lived in the same tree.
- The project treats documentation topology as explicitly changeable when a clearer structure is available.

## Decision
- Introduce `agents/` as first-class documentation area for agent-related artifacts.
- Move agent-governance and continuity files out of `docs/`:
  - ADRs about agent/process/doc-governance -> `agents/adr/`
  - Episodic memory logs -> `agents/memory/daily/`
  - Agent/meta method notes -> `agents/plans/`
- Keep `docs/` focused on service/operations/architecture:
  - `docs/runbooks/`, `docs/policies/`, `docs/plans/`, `docs/adr/`, `docs/archive/`

## Consequences
- Positive:
  - Clear ownership boundary: agent continuity/governance separated from service operations.
  - Better navigation and lower cognitive load for both operators and coding agents.
  - Future agent-doc growth no longer crowds `docs/`.
- Negative:
  - Cross-file links require migration and maintenance.
  - Historical commit history contains now-obsolete paths.

## Alternatives considered
- Keep everything under `docs/` with subfolders like `docs/agents/*`.
  - Rejected because ownership boundary remains implicit and `docs/` keeps mixed semantics.
- Move all docs (including service runbooks/policies) under `agents/`.
  - Rejected because operator/service docs must stay neutral and independent from agent workflows.
