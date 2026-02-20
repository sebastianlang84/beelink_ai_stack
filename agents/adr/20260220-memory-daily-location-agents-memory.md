# ADR: Place episodic memory under agents/memory/daily
Date: 2026-02-20
Status: Accepted

## Context
- The initial routing move introduced `docs/archive/memory-daily/` as location for episodic memory logs.
- This mixed active memory operations with archive semantics.
- The project needs a clear, stable path for active episodic memory that is distinct from service folders and from historical archive-only docs.

## Decision
- Standardize episodic memory path to `agents/memory/daily/`.
- Keep `MEMORY.md` in repo root as always-loaded snapshot/long-term memory.
- Keep `docs/archive/` for historical snapshots and superseded documents only.

## Consequences
- Positive:
  - Cleaner routing semantics: active memory is separate from archive storage.
  - Better discoverability than hidden or tool-specific dot folders.
  - Aligns with existing docs-centric repository organization while keeping services unaffected.
- Negative:
  - Existing references and scripts needed path updates.
  - Historical commit history contains old path references (`docs/archive/memory-daily/`).

## Alternatives considered
- `memory/daily/` at repo root.
  - Not chosen because this repo keeps continuity and governance docs under `agents/`.
- `.memory/` hidden folder.
  - Not chosen due lower discoverability and higher risk of being skipped in routine navigation.
