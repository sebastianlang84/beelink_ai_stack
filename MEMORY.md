# MEMORY
last_updated: 2026-02-20
scope: always-loaded bootstrap; max ~200 lines

Purpose: One-page snapshot plus reset-resilient long-term memory for the next context.

## 1) Current State
- Open WebUI stack is pinned to `0.8.3`; upgrade status is stable.
- Root continuity model is `MEMORY.md` (snapshot + long-term memory), with rationale documented in `agents/adr/20260219-memory-md-replaces-handoff.md`.
- Documentation is split between `agents/` (governance/memory/meta) and `docs/` (service/ops/architecture), plus archive (`docs/archive/`).
- `fourier-cycles/` is operational (batch pipeline + static ECharts UI) with browser-debug tunnel workflow documented and available.
- `fourier-cycles` UI superposition uses backend-exported component vectors (`waves.csv`), preselects backend-selected cycles, and warns explicitly if wave data is missing.
- `fourier-cycles` stability display is normalized to `0..1` (`stability_score_norm`) for clearer interpretation.
- `fourier-cycles` selection now enforces presence + period-distance thresholds strictly (no rule-breaking backfill); `cycles.csv` contains all stable cycles, while default overlays remain driven by `summary.json` selected cycles.
- `fourier-cycles` cycle table (right panel) supports interactive sorting via header clicks for period/power/presence/stability.
- Historical timeline entries were moved out of this file to `agents/memory/daily/`.

## 2) Long-Term Memory
- Continuity is file-based, not chat-based: durable state must live in repo docs.
- `atlas` means cross-context continuity mandate for this repository.
- Durable decisions are split: process/gov in `agents/adr/`, architecture in `docs/adr/`; `MEMORY.md` remains concise and operational.
- Memory routing policy:
  - Semantisch/stabil -> `MEMORY.md`
  - Prozedural -> `docs/runbooks/*`
  - Episodisch -> `agents/memory/daily/*`
  - Entscheidungs-Why -> `agents/adr/*`, `docs/adr/*`
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
