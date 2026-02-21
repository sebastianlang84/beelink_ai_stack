# ADR: agents-init Bootstrap Contract

Date: 2026-02-21
Status: Accepted

## Context
- New repositories repeatedly need the same governance baseline: `AGENTS.md`, `MEMORY.md`, Living Docs, and secrets guardrails.
- Chat-only setup instructions are not reset-resilient and are easy to apply inconsistently.
- We need one portable entry document that can be handed to a coding agent as the first file in a fresh project.

## Decision
- Introduce a root-level `agents-init.md` as a one-shot bootstrap specification.
- `agents-init.md` defines:
  - mandatory execution gates (preflight, read-only diagnose, write, verification),
  - required file tree for governance/memory/guardrails,
  - concrete templates for core docs and policies,
  - completion contract (Living Docs + Memory check + commit),
  - mandatory self-delete of `agents-init.md` after successful bootstrap.

## Consequences
- Bootstrap process is reproducible and reset-resilient across repositories.
- Governance quality is higher from day zero, with explicit memory routing and secrets boundaries.
- Slight upfront maintenance cost: template updates in `agents-init.md` must track evolving standards.

## Alternatives
- Keep bootstrap instructions only in chat:
  - Rejected due to poor reset resilience and lower reproducibility.
- Keep separate snippets/scripts without one contract document:
  - Rejected due to fragmentation and higher setup drift risk.
