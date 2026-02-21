# Changelog

All notable user-/operator-relevant changes are documented in this file.
This project follows a Keep a Changelog style.

## [Unreleased]
### Added
- `agents-init.md` bootstrap spec to initialize AGENTS/memory/guardrails in fresh repositories, including a mandatory self-delete step after successful setup.
- `INDEX.md` as root navigation entrypoint.
- `docs/adr/` decision-tracking model introduced for documentation strategy.
- `atlas` definition added to continuity memory as cross-context continuity mandate.
- `docs/adr/20260218-qdrant-indexing-boundaries.md` to lock Qdrant indexing boundaries.
- `MEMORY.md` introduced as unified continuity document (snapshot + long-term memory).
- `agents/adr/20260219-memory-md-replaces-handoff.md` to formalize `HANDOFF.md` -> `MEMORY.md`.
- New service `fourier-cycles/` with Dockerized Yahoo+FRED cycle extraction, rolling stability checks, and PNG artifact generation.
- `fourier-cycles` now writes a dedicated `price.png` per series (raw level/price chart) alongside spectral plots.
- `fourier-cycles/PRD_webapp.md` planning baseline for a dockerized frontend/backend web app, Tailscale access, and Windows SSH-tunnel debug workflow.
- `fourier-cycles` webapp Compose now deploys `fourier-cycles-ui` plus internal `fourier-cycles-api` trigger service.
- `fourier-cycles-ui` interactive frontend added (Phase C) using ECharts to display zoomable price/cycle charts and a selectable stability metrics table on a single-screen dark mode dashboard.
- Controlled Phase D run trigger implemented: `POST /api/run` (confirm-required), `GET /api/run/status`, busy guard for parallel runs, and per-run trigger logs under `fourier-cycles/output/_trigger_logs/`.
- Windows debug helper `fourier-cycles/tools/open_fourier_debug.bat` for Chrome debug mode + SSH local/reverse tunneling to Linux.
- Linux helper `fourier-cycles/tools/run_chrome_devtools_mcp.sh` to run `chrome-devtools-mcp` against tunneled browser endpoint (`127.0.0.1:9223`).
- ADR `docs/adr/20260219-fourier-debug-devtools-mcp-tunnel.md` documenting the chosen MCP DevTools runtime and tunnel convention.
- `agents/memory/daily/2026-02-20.md` as first episodic memory daily entry after slimming root continuity memory.
- `agents/adr/20260220-agent-docs-split.md` to formalize the `agents/` vs `docs/` documentation boundary.
- `scripts/check_memory_hygiene.sh` for lightweight structure/size drift checks on `MEMORY.md` (warn-first).
- `fourier-cycles/METHODOLOGY.md` as detailed, implementation-bound method specification (preprocessing, rolling harmonic fit, SNR/presence, phase coherence, surrogate p-values, ranking, selection).
- `fourier-cycles` optional audit export `windows.csv` (per-window amp/phase/snr/presence per cycle) via `FOURIER_EXPORT_WINDOWS_CSV=true`.
- `fourier-cycles` optional non-stationary wavelet activity plot `wavelet.png` via `FOURIER_ENABLE_WAVELET_VIEW=true`.

### Changed
- `transcript-miner` summary regeneration now uses a configurable backfill policy (`off|soft|full`, default `soft` with day window), plus CLI overrides (`--summary-backfill-mode`, `--summary-backfill-days`) to avoid expensive historical auto-backfills after prompt/model changes.
- `fourier-cycles` pipeline now computes absolute cycle metrics (`amp_*`, `snr_*`, `fit_score_phase_free`, `phase_locking_r`, `best_lag_days_median`, `lag_iqr`, `margin_median`, `p_value_bandmax`) and keeps relative metrics (`rank_score_norm`, `stability_score_norm`) explicitly separated.
- `fourier-cycles` candidate discovery now uses local peak detection in period space (with distance guard) instead of plain top-power slicing.
- `fourier-cycles` rolling robustness now supports multi-scale windows via `FOURIER_ROLLING_WINDOWS_DAYS` + `FOURIER_ROLLING_STEP_DAYS`, plus phase-invariant harmonic regression per window.
- `fourier-cycles` strict absolute selection defaults were calibrated against the first production basket: `FOURIER_SELECTION_MIN_PHASE_LOCKING_R` `0.40 -> 0.08` and `FOURIER_SELECTION_MIN_AMP_SIGMA` `0.20 -> 0.06` (p-value threshold remains `1.00` until surrogate significance is more discriminative on the basket).
- `fourier-cycles` selection logic now supports strict absolute filters (presence, phase coherence, amplitude, p-value) with fail-open fallback to keep default overlays/PNGs usable when strict gates are too restrictive.
- `fourier-cycles-ui` cycle table now displays absolute metrics (`Amp`, `SNR`, `Presence`, `Phase-R`, `p-bandmax`) and a clearly labeled relative sort metric (`Rank (rel)`).
- `fourier-cycles/.config.env.example` now documents advanced analysis controls (signal mode, detrending, SNR bands/thresholds, surrogate settings, ranking weights, strict selection thresholds).
- `fourier-cycles` default analysis period band is now `30..300` days (`FOURIER_MIN_PERIOD_DAYS=30`, `FOURIER_MAX_PERIOD_DAYS=300`) to prioritize medium-term cycles over very short 1-10 day components.
- `fourier-cycles` presence calculation now uses a dynamically scaled statistical noise floor (based on band width relative to the full frequency range) instead of a hardcoded 3% threshold, making cycle selection more physically meaningful.
- `AGENTS.md` Arbeitsstil now includes an explicit mandatory helpfulness rule: solution-first delivery plus concrete, verifiable workarounds on blockers.
- Main documentation strategy consolidated toward minimal, non-redundant root docs.
- Continuity doc migrated from `HANDOFF.md` to `MEMORY.md` (snapshot + long-term memory in one file).
- `TODO.md` reduced to active tasks only.
- `CHANGELOG.md` rebaselined to keep only concise, user/operator-relevant entries.
- `docs/` reorganized into active sets (`runbooks/`, `policies/`, `plans/`) plus `archive/`.
- Agent governance/memory/meta docs moved out of `docs/` into dedicated `agents/` (`agents/adr/`, `agents/memory/daily/`, `agents/plans/`).
- OpenClaw notes moved from shared docs to `openclaw/notes/`.
- Workflow and YouTube 429 report content consolidated into active PRD/runbook paths.
- Root docs (`README.md`, `INDEX.md`, `TODO.md`) now include the `fourier-cycles` service entrypoint and operator quickstart.
- `fourier-cycles` default host output path moved into workspace (`/home/wasti/ai_stack/fourier-cycles/output`).
- `fourier-cycles` output selection now defaults to top 3 stable cycles using stricter presence/power thresholds and minimum period-distance filtering.
- Script cleanup: removed obsolete shell helpers `scripts/secrets_env_doctor.sh` (deprecated) and `scripts/purge_all_summaries_everywhere.sh` (unused).
- Memory routing/hygiene policy tightened across root docs: `AGENTS.md` now defines mandatory routing targets and precedence; `README.md` and `INDEX.md` include a concise routing map.
- Root `MEMORY.md` was refactored to a strict 5-block, status-first structure; historical timeline content moved to `agents/memory/daily/`.
- Episodic memory location standardized to `agents/memory/daily/` (replacing earlier `docs/*` paths) for cleaner active-memory routing.
- `fourier-cycles` UI charts now use mouse-wheel zoom on the X-axis only; Y-axis auto-scales dynamically to the visible window for tighter readability.
- Secrets policy filename shortened to `docs/policies/policy_secrets_env.md` and root references updated.
- `fourier-cycles` now exports `waves.csv` per series, and the UI uses these real component vectors for individual overlays and superposition (no mock overlay values).
- `fourier-cycles` cycles now include `stability_score_norm` (0..1 per series) and the UI displays normalized stability instead of raw tiny score values.
- `fourier-cycles` cycle selection now enforces configured presence and minimum-period-distance constraints strictly (no rule-breaking backfill), so selection can return fewer than `selection_top_k`.
- `fourier-cycles` `cycles.csv` now exports all stable cycles for UI exploration, while `summary.json` keeps the final selected subset for default overlays.
- `fourier-cycles-ui` right-hand cycle table now supports click-to-sort on `Period`, `Power`, `Presence`, and `Stability (0-1)` headers (toggle asc/desc).
- `fourier-cycles-ui` now shows a `Run now` control and run-state badge backed by `/api/run/status` polling.
- `fourier-cycles/ui/nginx.conf` now proxies `/api/*` to the internal `fourier-cycles-api` service without exposing a new host port.
- `fourier-cycles/tools/open_fourier_debug.bat` now auto-retries SSH tunnel establishment and waits briefly for local Chrome debug-port readiness before each attempt.
- `fourier-cycles/tools/open_fourier_debug.bat` now rotates remote DevTools ports on repeated SSH failures (default span `9223..9233`) to avoid getting stuck on a single occupied reverse-forward port.
- `fourier-cycles/tools/open_fourier_debug.bat` now enforces key-only SSH (`BatchMode=yes`, `IdentitiesOnly=yes`, configurable `SSH_KEY_PATH`) to prevent password prompts during tunnel retries.
- `fourier-cycles/tools/open_fourier_debug.bat` now performs a fast SSH key-auth precheck and fails closed when auth is invalid, instead of retrying with unusable credentials.
- `fourier-cycles/tools/open_fourier_debug.bat` now uses explicit host-key policy + connect timeout (`SSH_STRICT_HOST_KEY_CHECKING=accept-new`, `SSH_CONNECT_TIMEOUT_SEC`) and shows auth-check progress to avoid silent hangs before the first tunnel attempt.
- `fourier-cycles/tools/open_fourier_debug.bat` now verifies local Chrome readiness via DevTools endpoint (`/json/version`) with a locale-independent fallback, preventing false negatives on non-English Windows `netstat` output.
- `fourier-cycles/tools/open_fourier_debug.bat` now falls back to a UI-only SSH tunnel (`-L`) when reverse DevTools forwarding (`-R`) fails due occupied remote ports, reducing UI/API flapping during retries.
- `fourier-cycles/tools/open_fourier_debug.bat` now auto-rotates local UI forward ports when the default (`127.0.0.1:13010`) is already occupied, preventing immediate `connection refused` on stale/blocked local forwards.
- `fourier-cycles/docker-compose.webapp.yml` healthchecks were hardened: API now uses a Python-based local HTTP probe (`127.0.0.1:8080`) and UI checks use `127.0.0.1:80` to avoid localhost/IPv6 false negatives.

### Fixed
- `fourier-cycles` waves export now writes components for all stable cycles (instead of just the top selected few), unblocking the UI from displaying individually toggled non-default cycles.
- `fourier-cycles` run summary serialization now handles date fields correctly; batch run no longer fails at `summary.json` write.
- `fourier-cycles` reconstruction chart labeling now clearly indicates transformed signal values (returns), avoiding confusion with raw price charts.
- `fourier-cycles` superposition visibility: UI now preselects backend-selected cycles and shows an explicit warning when `waves.csv` is missing/unreadable.
- `fourier-cycles` rolling stability now uses local band-power around candidate frequencies instead of single nearest-bin power, reducing leakage-driven false positives in short windows.
- `fourier-cycles/tools/open_fourier_debug.bat` now correctly handles the `ErrorLevel` during port-availability checks, preventing silent instant crashes when ports are available.
- `fourier-cycles/tools/open_fourier_debug.bat` now bypasses local Windows port-forwarding restrictions by loading the UI directly via LAN IP, keeping only the secure `-R` reverse tunnel for the MCP DevTools connection.
