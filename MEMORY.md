# MEMORY

Purpose: One-page snapshot plus reset-resilient long-term memory for the next context.

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
- `fourier-cycles` now writes `price.png` per series (raw price/level chart) so index/asset levels are directly visible next to spectral plots.
- Reconstruction plot labeling was clarified to indicate transformed signal (returns), not raw price levels.
- `fourier-cycles` cycle selection now defaults to top 3 stable cycles (presence/power thresholds + minimum period distance), with new charts: `price_cycle_overlay.png` and `cycle_components.png`.
- Validation run on 2026-02-18 UTC for `^GSPC` succeeded (`success=1`, `failure=0`); outputs include new overlay/component charts.
- Web app planning started in `fourier-cycles/PRD_webapp.md` (dockerized FE/BE split, Tailscale access strategy, Windows `.bat` SSH tunnel + browser debug workflow for MCP DevTools).
- Web app Phase A skeleton completed on 2026-02-19: FastAPI backend and Vite/React frontend running in Docker Compose with healthchecks.
- Web app Phase B & Phase C completed on 2026-02-19: Python API dropped. Interactive ECharts UI (Single Page Darkmode Dashboard) implemented directly fetching static CSV/JSON via Nginx.
- Browser-Debug tunnel workflow for Fourier UI was implemented on 2026-02-19: Windows helper `fourier-cycles/tools/open_fourier_debug.bat` plus Linux MCP runner `fourier-cycles/tools/run_chrome_devtools_mcp.sh`.
- `chrome-devtools-mcp` was installed locally on Linux at `$HOME/.local/share/chrome-devtools-mcp` (pinned `0.17.3`) for MCP-based browser debugging via SSH reverse tunnel endpoint `127.0.0.1:9223`.
- Root continuity model was migrated on 2026-02-19 from `HANDOFF.md` to `MEMORY.md` (snapshot + long-term memory unified).
- Local unstaged user change exists in `scripts/backup_all.sh` and is intentionally untouched.
- Living Docs updated for Fourier service bootstrap: `README.md`, `TODO.md`, `CHANGELOG.md`, `INDEX.md`.
- Living Docs check for build-app planning task: `README.md`, `TODO.md`, `CHANGELOG.md` reviewed; no additional changes needed.
- Living Docs updated for smoke-run/fix task: `TODO.md`, `CHANGELOG.md`; `README.md` reviewed (no change needed).
- Living Docs updated for output-path migration task: `README.md`, `CHANGELOG.md`; `TODO.md` reviewed (no change needed).
- Living Docs updated for price-chart clarity task: `CHANGELOG.md`; `README.md` and `TODO.md` reviewed (no change needed).
- Living Docs updated for top-cycle visualization task: `README.md`, `TODO.md`, `CHANGELOG.md`.
- Living Docs updated for webapp-planning task: `TODO.md`, `CHANGELOG.md`; `README.md` updated with PRD link.
- Living Docs updated for continuity-memory migration task: `README.md`, `CHANGELOG.md`; `TODO.md` reviewed (no change needed).
- Living Docs updated for Fourier browser-debug workflow task: `README.md`, `fourier-cycles/README.md`, `TODO.md`, `CHANGELOG.md`.

## Long-Term Memory
- User preference finalized on 2026-02-19: use `MEMORY.md` as the single reset-resilient continuity file instead of `HANDOFF.md`.
- `atlas` = the repository's cross-context continuity mandate.
- Practical meaning of `atlas`: plan, decide, and track state in files (`MEMORY.md`, `TODO.md`, ADRs), not in chat memory.
- Durable process decisions belong in `docs/adr/`; `MEMORY.md` stays concise and operational.
- Keep continuity entries factual and current; avoid duplicate long histories that belong in Git/ADR/CHANGELOG.

## Open Decisions
- Qdrant detail policy handling:
  - Option A: keep only ADR and drop archived detail policy
  - Option B: keep archived detail policy as background
  - Default: **Option B**

## Next Steps
1. Continue P1 Fourier deepening: define production basket and tune stability thresholds from first successful run outputs.
2. Add bounded retries/backoff for Yahoo/FRED fetch path.
3. Continue Fourier web app Phase D (optional controlled run trigger).
4. OpenClaw integration remains intentionally deferred for now.

## Known Risks / Blockers
- Long-tail links outside root docs can still reference pre-consolidation paths.
- Archive growth can become noisy without periodic pruning.
- Dirty worktree file `scripts/backup_all.sh` must not be auto-reverted.
