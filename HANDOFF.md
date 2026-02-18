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
1. Remove residual mentions of `AGENTDIARY.md` from active docs where no longer needed.
2. Tighten `CHANGELOG.md` further to release/user-visible items only.
3. Verify root docs for strict no-duplication and replace repeats with links.
4. Define `atlas` explicitly in `HANDOFF.md` (and ADR if architectural).
5. Continue active engineering work from `TODO.md` P0/P1 items.

## Known Risks / Blockers
- Large docs cleanup can accidentally drop still-relevant context.
- Existing links may break during file removals/renames.
- Long changelog truncation may reduce in-file discoverability (history still in Git).
- Dirty worktree (`TODO.md`, `scripts/backup_all.sh`) must not be auto-reverted.
