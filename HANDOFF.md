# HANDOFF

Purpose: One-page snapshot for the next context.

## Current State
- Open WebUI stack is pinned to `0.8.3` and recent upgrade is complete.
- Docs tree was consolidated into `docs/runbooks/`, `docs/policies/`, `docs/plans/`, `docs/archive/`.
- Historical OWUI RAG snapshots moved to `docs/archive/owui-rag/`.
- OpenClaw-specific notes moved from shared docs to `openclaw/notes/`.
- Qdrant indexing boundary is now fixed as ADR: `docs/adr/20260218-qdrant-indexing-boundaries.md`.
- Finance Fourier POC exists and is runnable (`scripts/finance_fourier_analysis.py`).
- Local unstaged user change exists in `scripts/backup_all.sh` and is intentionally untouched.

## Atlas Definition
- `atlas` = the repository's cross-context continuity mandate.
- Practical meaning: plan, decide, and track state in files (`HANDOFF.md`, `TODO.md`, ADRs), not in chat memory.
- If a task says "atlas", it refers to long-horizon, reset-safe continuity.

## Open Decisions
- Qdrant detail policy handling:
  - Option A: keep only ADR and drop archived detail policy
  - Option B: keep archived detail policy as background
  - Default: **Option B**

## Next Steps
1. User-confirmed Open WebUI Knowledge cleanup (`bitcoin`/`crypto`) and re-verify sync behavior.
2. Backup disk cleanup under `/srv/ai-stack/backups/` with before/after free-space check.
3. Continue P1 work from `TODO.md` (Fourier deepening, OpenClaw Telegram E2E verification).

## Known Risks / Blockers
- Long-tail links outside root docs can still reference pre-consolidation paths.
- Archive growth can become noisy without periodic pruning.
- Dirty worktree file `scripts/backup_all.sh` must not be auto-reverted.
