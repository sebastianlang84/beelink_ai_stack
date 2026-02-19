# ADR: Main Documentation Strategy (Minimal, Stable, Non-Redundant)
Date: 2026-02-18
Status: Superseded
Superseded by: `docs/adr/20260219-memory-md-replaces-handoff.md`

## Context
- Root main docs had high redundancy and drift risk.
- Context resets made chat-only commitments unreliable.
- Maintenance cost was high because identical text existed in multiple files.

## Decision
- Adopt this root-doc contract:
  - `AGENTS.md` = normative process rules
  - `README.md` = operator guide
  - `INDEX.md` = navigation only
  - `HANDOFF.md` = one-page current snapshot
  - `TODO.md` = active tasks only
  - `CHANGELOG.md` = short user/release-visible changes
  - `docs/adr/` = final decision records
- Enforce no text duplication across root main docs: link instead of copy.

## Consequences
- Positive:
  - Lower drift and less maintenance overhead.
  - Better reset recovery with a single snapshot source.
  - Cleaner auditability via Git + ADR + changelog.
- Negative:
  - One-time cleanup effort and link migrations.
  - Existing long-form historical notes move out of main docs.

## Alternatives considered
- Keep current mixed strategy with task-diary + long TODO + long CHANGELOG.
  - Rejected due to persistent redundancy and ambiguity.
- Keep two parallel indexes (`README` + `docs/README`) as equal entrypoints.
  - Rejected to avoid navigation drift; `INDEX.md` becomes primary navigation.
