# HANDOFF

Purpose: One-page snapshot for the next context.

## Current State
- Open WebUI stack is pinned to `0.8.3` and recent upgrade is complete.
- Docs tree was consolidated into `docs/runbooks/`, `docs/policies/`, `docs/plans/`, `docs/archive/`.
- Historical OWUI RAG snapshots moved to `docs/archive/owui-rag/`.
- OpenClaw-specific notes moved from shared docs to `openclaw/notes/`.
- Qdrant indexing boundary is now fixed as ADR: `docs/adr/20260218-qdrant-indexing-boundaries.md`.
- Finance Fourier POC exists and is runnable (`scripts/finance_fourier_analysis.py`).
- Backup cleanup executed on 2026-02-18: `/srv/ai-stack/backups/owui-data__*.tar.gz` removed (12 files, ~48G). Free space on `/` improved from 344G to 392G.
- Open WebUI Knowledge cleanup closed on 2026-02-18 after verification: only `investing_new` + `investing_archive` present; no `bitcoin`/`crypto` collections found.
- OpenClaw Telegram E2E final verification closed on 2026-02-18 (user-confirmed working behavior).
- `fourier-cycles/` service scaffold added on 2026-02-18 (Docker batch job for Yahoo+FRED, rolling cycle stability checks, PNG outputs + `latest` symlink).
- `goals/build_app.md` was filled for `fourier-cycles` on 2026-02-18 (5+2 planning baseline with DoD, gates, and open risks).
- `fourier-cycles` smoke run succeeded on 2026-02-18 UTC with defaults (`SPY`, `BTC-USD`, `DGS10`, `CPIAUCSL`): `success=4`, `failure=0`, artifacts under `/home/wasti/ai_stack/fourier-cycles/output/latest`.
- Runtime bug fixed in `fourier-cycles`: `summary.json` writing no longer crashes on non-JSON date types.
- `fourier-cycles` output location was moved on 2026-02-18 to workspace path `/home/wasti/ai_stack/fourier-cycles/output` (default host mount and docs aligned).
- Existing Fourier run artifacts were migrated into workspace output; legacy external folder `/home/wasti/ai_stack_data/fourier-cycles/output` was removed.
- Local unstaged user change exists in `scripts/backup_all.sh` and is intentionally untouched.
- Living Docs updated for Fourier service bootstrap: `README.md`, `TODO.md`, `CHANGELOG.md`, `INDEX.md`.
- Living Docs check for build-app planning task: `README.md`, `TODO.md`, `CHANGELOG.md` reviewed; no additional changes needed.
- Living Docs updated for smoke-run/fix task: `TODO.md`, `CHANGELOG.md`; `README.md` reviewed (no change needed).
- Living Docs updated for output-path migration task: `README.md`, `CHANGELOG.md`; `TODO.md` reviewed (no change needed).

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
1. Continue P1 Fourier deepening: define production basket and tune stability thresholds from first successful run outputs.
2. Add bounded retries/backoff for Yahoo/FRED fetch path.
3. OpenClaw integration remains intentionally deferred for now.

## Known Risks / Blockers
- Long-tail links outside root docs can still reference pre-consolidation paths.
- Archive growth can become noisy without periodic pruning.
- Dirty worktree file `scripts/backup_all.sh` must not be auto-reverted.
