# MEMORY
last_updated: 2026-02-21
scope: always-loaded bootstrap; max ~200 lines

Purpose: One-page snapshot plus reset-resilient long-term memory for the next context.

## 1) Current State
- Reusable bootstrap spec `agents-init.md` exists for new repositories to scaffold AGENTS/memory/guardrails, including Claude compatibility via `CLAUDE.md -> AGENTS.md`, Anthropic-style `SKILL.md` bootstrap/routing, and an explicit self-delete contract after setup.
- Open WebUI stack is pinned to `0.8.3`; upgrade status is stable.
- Root continuity model is `MEMORY.md` (snapshot + long-term memory), with rationale documented in `agents/adr/20260219-memory-md-replaces-handoff.md`.
- Documentation is split between `agents/` (governance/memory/meta) and `docs/` (service/ops/architecture), plus archive (`docs/archive/`).
- `fourier-cycles/` is operational (batch pipeline + static ECharts UI) with browser-debug tunnel workflow documented and available.
- `fourier-cycles` UI superposition uses backend-exported component vectors (`waves.csv`), preselects backend-selected cycles, and allows toggling any stable cycle because the backend now exports wave vectors for all stable cycles.
- `fourier-cycles` stability display is normalized to `0..1` (`stability_score_norm`) for clearer interpretation.
- `fourier-cycles` selection now enforces presence + period-distance thresholds strictly; presence uses a dynamic noise-floor baseline instead of a fixed 3% to properly differentiate actual cycles from wideband noise.
- `fourier-cycles` default analysis band is tuned to medium-term cycles (`FOURIER_MIN_PERIOD_DAYS=30`, `FOURIER_MAX_PERIOD_DAYS=300`) to avoid short 1-10 day dominance in default outputs.
- `fourier-cycles` cycle table (right panel) supports interactive sorting via header clicks for period/amp/snr/presence/phase/p-bandmax/rank.
- `fourier-cycles` methodology is now explicitly documented in `fourier-cycles/METHODOLOGY.md` and implemented with absolute robustness metrics (amp/snr/phase-coherence/p-bandmax) plus separate relative ranking (`rank_score_norm`) to avoid semantic mixing.
- `fourier-cycles` web app now includes an internal `fourier-cycles-api` trigger path (`POST /api/run`, `GET /api/run/status`) proxied via UI, with busy-guard and per-run logs under `output/_trigger_logs/`.
- `fourier-cycles/tools/open_fourier_debug.bat` now auto-retries SSH tunnel setup, waits for local Chrome debug-port readiness via DevTools endpoint checks (locale-independent fallback), rotates remote DevTools ports on failure, falls back to UI-only `-L` tunnel when `-R` port forwarding is occupied, uses key-only SSH, fails fast on invalid SSH key-auth, and applies explicit host-key/timeout policy (`accept-new`, configurable) to avoid silent precheck hangs.
- `fourier-cycles/tools/open_fourier_debug.bat` now also rotates local UI-forward ports (`127.0.0.1:13010+`) when occupied, so local browser access does not fail on stale/blocked forwards.
- `fourier-cycles/docker-compose.webapp.yml` healthchecks are aligned with container reality (`python` probe in API image, `127.0.0.1` probe in UI), so healthy/unhealthy reflects actual service availability.
- `fourier-cycles` production basket baseline is fixed to `SPY,BTC-USD,DGS10,CPIAUCSL`; strict selection defaults are calibrated to `selection_min_presence_ratio=0.50`, `selection_min_phase_locking_r=0.04`, `selection_min_amp_sigma=0.06` (ADR `docs/adr/20260221-fourier-production-basket-calibration.md`), with optional `windows.csv` audit (`FOURIER_EXPORT_WINDOWS_CSV=true`) and optional `wavelet.png` (`FOURIER_ENABLE_WAVELET_VIEW=true`).
- `fourier-cycles` Tailscale exposure policy is fixed to dedicated hostname/root mapping (no `/fourier` path-prefix baseline), documented in `docs/adr/20260221-fourier-tailscale-hostname-mapping.md`.
- `transcript-miner` summary regeneration now has a configurable backfill gate (`analysis.llm.summary_backfill_mode=off|soft|full`, default `soft` with `summary_backfill_days=14`) plus CLI overrides (`--summary-backfill-mode`, `--summary-backfill-days`) to avoid expensive historical auto-backfills after prompt/model tweaks.
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
1. Add bounded retries/backoff for Yahoo/FRED fetch path.
2. Optionally add `scripts/check_memory_hygiene.sh` into CI/pre-commit once routing stabilizes in daily usage.

## 5) Known Risks / Blockers
- Long-tail links outside root docs can still reference pre-consolidation paths.
- Archive growth can become noisy without periodic pruning.
- Dirty worktree file `scripts/backup_all.sh` exists and must not be auto-reverted.
