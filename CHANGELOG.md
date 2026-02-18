# Changelog

All notable user-/operator-relevant changes are documented in this file.
This project follows a Keep a Changelog style.

## [Unreleased]
### Added
- `INDEX.md` as root navigation entrypoint.
- `docs/adr/` decision-tracking model introduced for documentation strategy.

### Changed
- Main documentation strategy consolidated toward minimal, non-redundant root docs.
- `HANDOFF.md` reduced to a strict snapshot format (state/decisions/next steps/risks).
- `TODO.md` reduced to active tasks only.

### Removed
- `AGENTDIARY.md` removed in favor of Git + ADR + changelog.

## [2026-02-18]
### Added
- Finance Fourier analysis workflow:
  - `scripts/finance_fourier_analysis.py`
  - `docs/runbook_finance_fourier.md`
- Context-engineering framework docs:
  - `docs/framework_context_engineering_5plus2.md`
  - `goals/build_app.md`
- Reset-safe handoff baseline:
  - `HANDOFF.md`

### Changed
- Open WebUI image baseline updated to `0.8.3`.
- Agent process hardened for reset-resilient handoff checks.
