# HANDOFF

Purpose: One-page snapshot for the next context.

## Current State
- Open WebUI stack is pinned to `0.8.3` and recent upgrade is complete.
- Core docs now include reset-safe handoff and context-engineering template (`goals/build_app.md`).
- Finance Fourier POC exists and is runnable (`scripts/finance_fourier_analysis.py`).
- Documentation strategy is being consolidated toward minimal, non-redundant main docs.
- Local unstaged user changes exist in `TODO.md` and `scripts/backup_all.sh`.

## Atlas Definition
- `atlas` = the repository's cross-context continuity mandate.
- Practical meaning: plan, decide, and track state in files (`HANDOFF.md`, `TODO.md`, ADRs), not in chat memory.
- If a task says "atlas", it refers to long-horizon, reset-safe continuity.

## Open Decisions
- Root navigation source:
  - Option A: `docs/README.md` as primary index
  - Option B: `INDEX.md` as primary index
  - Default: **Option B**
- TODO policy:
  - Option A: keep done+open in one file
  - Option B: active tasks only
  - Default: **Option B**

## Next Steps
1. Verify root docs for strict no-duplication and replace repeats with links.
2. Continue active engineering work from `TODO.md` P0/P1 items.

## Known Risks / Blockers
- Large docs cleanup can accidentally drop still-relevant context.
- Existing links may break during file removals/renames.
- Long changelog truncation may reduce in-file discoverability (history still in Git).
- Dirty worktree (`TODO.md`, `scripts/backup_all.sh`) must not be auto-reverted.
