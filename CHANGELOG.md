# Changelog

All notable user-/operator-relevant changes are documented in this file.
This project follows a Keep a Changelog style.

## [Unreleased]
### Added
- `INDEX.md` as root navigation entrypoint.
- `docs/adr/` decision-tracking model introduced for documentation strategy.
- `atlas` definition added to continuity memory as cross-context continuity mandate.
- `docs/adr/20260218-qdrant-indexing-boundaries.md` to lock Qdrant indexing boundaries.
- `MEMORY.md` introduced as unified continuity document (snapshot + long-term memory).
- `agents/adr/20260219-memory-md-replaces-handoff.md` to formalize `HANDOFF.md` -> `MEMORY.md`.
- New service `fourier-cycles/` with Dockerized Yahoo+FRED cycle extraction, rolling stability checks, and PNG artifact generation.
- `fourier-cycles` now writes a dedicated `price.png` per series (raw level/price chart) alongside spectral plots.
- `fourier-cycles/PRD_webapp.md` planning baseline for a dockerized frontend/backend web app, Tailscale access, and Windows SSH-tunnel debug workflow.
- `fourier-cycles-ui` Docker Compose deployed. Note: Python API was dropped in favor of static Nginx JSON serving.
- `fourier-cycles-ui` interactive frontend added (Phase C) using ECharts to display zoomable price/cycle charts and a selectable stability metrics table on a single-screen dark mode dashboard.
- Windows debug helper `fourier-cycles/tools/open_fourier_debug.bat` for Chrome debug mode + SSH local/reverse tunneling to Linux.
- Linux helper `fourier-cycles/tools/run_chrome_devtools_mcp.sh` to run `chrome-devtools-mcp` against tunneled browser endpoint (`127.0.0.1:9223`).
- ADR `docs/adr/20260219-fourier-debug-devtools-mcp-tunnel.md` documenting the chosen MCP DevTools runtime and tunnel convention.
- `agents/memory/daily/2026-02-20.md` as first episodic memory daily entry after slimming root continuity memory.
- `agents/adr/20260220-agent-docs-split.md` to formalize the `agents/` vs `docs/` documentation boundary.
- `scripts/check_memory_hygiene.sh` for lightweight structure/size drift checks on `MEMORY.md` (warn-first).

### Changed
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

### Fixed
- `fourier-cycles` run summary serialization now handles date fields correctly; batch run no longer fails at `summary.json` write.
- `fourier-cycles` reconstruction chart labeling now clearly indicates transformed signal values (returns), avoiding confusion with raw price charts.
- `fourier-cycles` superposition visibility: UI now preselects backend-selected cycles and shows an explicit warning when `waves.csv` is missing/unreadable.
