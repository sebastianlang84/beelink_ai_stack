# HANDOFF

Purpose: Fast context rehydration after session/context reset.

## Context-Window Reality (Mandatory)
- Chat memory is session-local and can be lost after context reset.
- Therefore, promises made only in chat are non-binding across resets.
- Any commitment that must survive resets must be written to repo files.
- Minimum persistence targets: `HANDOFF.md` + relevant living docs (`README.md`, `TODO.md`, `CHANGELOG.md`).
- End-of-task rule: update/check `HANDOFF.md` every task; if no change is needed, record explicitly: `HANDOFF.md geprueft: keine Aenderung noetig`.

## Read Order After Reset
1. `AGENTS.md`
2. `HANDOFF.md`
3. `README.md`
4. `docs/README.md`
5. `TODO.md`

## Current Repo State (2026-02-18)
- Open WebUI baseline is pinned to `0.8.3`.
- Context-engineering framework docs exist:
  - `docs/framework_context_engineering_5plus2.md`
  - `goals/build_app.md` (fillable template)
- Finance Fourier POC exists:
  - script: `scripts/finance_fourier_analysis.py`
  - runbook: `docs/runbook_finance_fourier.md`

## Active Local Working State
- There are local unstaged changes intentionally present:
  - `TODO.md`
  - `scripts/backup_all.sh`
- Do not auto-revert these without explicit user instruction.

## About "atlas"
- No `atlas` reference currently exists in tracked repo docs/code.
- If "atlas" is an external concept/service, define it here in this file to survive context resets.

## Quick Resume Commands
```bash
git status --short
git log --oneline -n 8
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
```

## Operational Fast Paths
- Open WebUI status/fix:
  - `./scripts/ensure-owui-up.sh status`
  - `./scripts/ensure-owui-up.sh ensure`
- Fourier quick run:
  - `./scripts/finance_fourier_analysis.py --source yahoo --symbol SPY --yahoo-range 5y --max-points 512 --top-k 8`
  - `./scripts/finance_fourier_analysis.py --source fred --series-id DGS10 --max-points 512 --top-k 8`

## Preferred Project Kickoff Pattern
- Create/fill one project file from:
  - `goals/build_app.md`
- Execute in phase order:
  - Architect -> Trace -> Link -> Assemble -> Stress Test -> Validate -> Monitor

## Update Rule
- Whenever major intent/state changes, update this file in the same task.
