# MEMORY
last_updated: 2026-02-20
scope: always-loaded bootstrap; max ~200 lines

Purpose: One-page snapshot plus reset-resilient long-term memory for the next context.

## 1) Current State
- Open WebUI stack is pinned to `0.8.3`; upgrade status is stable.
- Root continuity model is `MEMORY.md` (snapshot + long-term memory), with rationale documented in `docs/adr/20260219-memory-md-replaces-handoff.md`.
- Documentation is organized into active sets (`docs/runbooks/`, `docs/policies/`, `docs/plans/`) plus archive (`docs/archive/`).
- `fourier-cycles/` is operational (batch pipeline + static ECharts UI) with browser-debug tunnel workflow documented and available.
- Historical timeline entries were moved out of this file to `docs/memory/daily/`.

## 2) Long-Term Memory
- Continuity is file-based, not chat-based: durable state must live in repo docs.
- `atlas` means cross-context continuity mandate for this repository.
- Durable process/architecture decisions belong in `docs/adr/`; `MEMORY.md` remains concise and operational.
- Memory routing policy:
  - Semantisch/stabil -> `MEMORY.md`
  - Prozedural -> `docs/runbooks/*`
  - Episodisch -> `docs/memory/daily/*`
  - Entscheidungs-Why -> `docs/adr/*`
- Secrets policy is strict: `.env` contains secrets only; non-secrets belong in `.config.env` and service `.config.env` files.

## 3) Open Decisions
- Qdrant detail policy handling:
  - Option A: keep only ADR and drop archived detail policy
  - Option B: keep archived detail policy as background
  - Default: **Option B**

## 4) Next Steps
1. Continue P1 Fourier deepening: define production basket and tune stability thresholds from first successful run outputs.
2. Add bounded retries/backoff for Yahoo/FRED fetch path.
3. Continue Fourier web app Phase D (optional controlled run trigger).
4. Optionally add `scripts/check_memory_hygiene.sh` into CI/pre-commit once routing stabilizes in daily usage.

## 5) Known Risks / Blockers
- Long-tail links outside root docs can still reference pre-consolidation paths.
- Archive growth can become noisy without periodic pruning.
- Dirty worktree file `scripts/backup_all.sh` exists and must not be auto-reverted.
