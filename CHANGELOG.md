# Changelog

All notable user-/operator-relevant changes are documented in this file.
This project follows a Keep a Changelog style.

## [Unreleased]
### Added
- `INDEX.md` as root navigation entrypoint.
- `docs/adr/` decision-tracking model introduced for documentation strategy.
- `atlas` definition added to `HANDOFF.md` as cross-context continuity mandate.
- `docs/adr/20260218-qdrant-indexing-boundaries.md` to lock Qdrant indexing boundaries.
- New service `fourier-cycles/` with Dockerized Yahoo+FRED cycle extraction, rolling stability checks, and PNG artifact generation.
- `fourier-cycles` now writes a dedicated `price.png` per series (raw level/price chart) alongside spectral plots.
- `fourier-cycles/PRD_webapp.md` planning baseline for a dockerized frontend/backend web app, Tailscale access, and Windows SSH-tunnel debug workflow.

### Changed
- Main documentation strategy consolidated toward minimal, non-redundant root docs.
- `HANDOFF.md` reduced to a strict snapshot format (state/decisions/next steps/risks).
- `TODO.md` reduced to active tasks only.
- `CHANGELOG.md` rebaselined to keep only concise, user/operator-relevant entries.
- `docs/` reorganized into active sets (`runbooks/`, `policies/`, `plans/`) plus `archive/`.
- OpenClaw notes moved from shared docs to `openclaw/notes/`.
- Workflow and YouTube 429 report content consolidated into active PRD/runbook paths.
- Root docs (`README.md`, `INDEX.md`, `TODO.md`) now include the `fourier-cycles` service entrypoint and operator quickstart.
- `fourier-cycles` default host output path moved into workspace (`/home/wasti/ai_stack/fourier-cycles/output`).
- `fourier-cycles` output selection now defaults to top 3 stable cycles using stricter presence/power thresholds and minimum period-distance filtering.

### Fixed
- `fourier-cycles` run summary serialization now handles date fields correctly; batch run no longer fails at `summary.json` write.
- `fourier-cycles` reconstruction chart labeling now clearly indicates transformed signal values (returns), avoiding confusion with raw price charts.
