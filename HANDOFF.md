# HANDOFF

Purpose: One-page snapshot for the next context.

## Current State
- Open WebUI stack is pinned to `0.8.3` and recent upgrade is complete.
- Core docs now include reset-safe handoff and context-engineering template (`goals/build_app.md`).
- Finance Fourier POC exists and is runnable (`scripts/finance_fourier_analysis.py`).
- Documentation strategy is being consolidated toward minimal, non-redundant main docs.
- `AGENTDIARY.md` was removed; trace now relies on Git + ADR + changelog.
- Local unstaged user changes exist in `TODO.md` and `scripts/backup_all.sh`.

## Open Decisions
- Root navigation source:
  - Option A: `docs/README.md` as primary index
  - Option B: `INDEX.md` as primary index
  - Default: **Option B**
- Changelog depth:
  - Option A: keep long operational history in file
  - Option B: keep short release/user-relevant entries only
  - Default: **Option B**
- TODO policy:
  - Option A: keep done+open in one file
  - Option B: active tasks only
  - Default: **Option B**

## Next Steps
1. Verify no remaining references to removed `AGENTDIARY.md`.
2. Reduce `TODO.md` to active tasks only.
3. Rebaseline `CHANGELOG.md` to short Keep-a-Changelog format.
4. Add `docs/adr/README.md` and first ADR for documentation strategy.
5. Keep `README.md` operator-focused and move navigation to `INDEX.md`.
6. Verify no cross-file text duplication remains in root main docs.

## Known Risks / Blockers
- Large docs cleanup can accidentally drop still-relevant context.
- Existing links may break during file removals/renames.
- Long changelog truncation may reduce in-file discoverability (history still in Git).
- Dirty worktree (`TODO.md`, `scripts/backup_all.sh`) must not be auto-reverted.
