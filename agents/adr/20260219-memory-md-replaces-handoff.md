# ADR: Replace HANDOFF with MEMORY as continuity source
Date: 2026-02-19
Status: Accepted

## Context
- `HANDOFF.md` captured only a short snapshot and did not explicitly model durable, cross-task memory.
- The project needs reset-resilient continuity across context-window boundaries, including stable operator preferences and long-lived decisions.
- Process docs referenced `HANDOFF.md` as mandatory, which prevented a unified "snapshot + long-term memory" pattern.

## Decision
- Replace `HANDOFF.md` with `MEMORY.md` as the single continuity file at repo root.
- `MEMORY.md` now contains both:
  - current snapshot (`Current State`, `Open Decisions`, `Next Steps`, `Known Risks / Blockers`)
  - durable continuity memory (`Long-Term Memory`)
- Update all root documentation contracts and process rules (`AGENTS.md`, `README.md`, `INDEX.md`, `docs/README.md`, `agents/README.md`) to reference `MEMORY.md`.

## Consequences
- Positive:
  - Better continuity across resets: one canonical file for short-term handoff plus long-term memory.
  - Less ambiguity for agents and operators about where durable context lives.
- Negative:
  - Existing references to `HANDOFF.md` must be migrated.
  - Historical ADRs remain valid context but include superseded terminology.

## Alternatives considered
- Keep `HANDOFF.md` and add a separate `LONG_TERM_MEMORY.md`.
  - Rejected due to split-brain risk and higher maintenance overhead.
- Keep `HANDOFF.md` unchanged and rely only on ADRs/TODO.
  - Rejected because operator preferences and continuity cues are too fragmented.
