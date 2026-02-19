# TODO / Active Backlog

Purpose: Active work only.
Contains: Open tasks with priority and status.
Does not contain: Completed history (see Git/ADR/CHANGELOG).

## P0 (Now)
- None.

## P1 (Next)
- [ ] **Fourier analysis deepening (FRED + Yahoo)**
  - Docker service scaffold landed: `fourier-cycles/` (batch run + rolling stability plots + output artifacts).
  - Smoke run passed on 2026-02-18 UTC (`success=4`, `failure=0`) with default basket (`SPY`, `BTC-USD`, `DGS10`, `CPIAUCSL`).
  - Visual selection policy implemented: default top 3 cycles with stricter presence/power/distance filters + price overlay charts.
  - Define first target basket (symbols/series).
  - Add significance/robustness checks (beyond raw DFT ranking).
  - Document interpretation guardrails for non-forecast use.

- [ ] **Fourier web app (dockerized frontend/backend)**
  - Planning baseline created: `fourier-cycles/PRD_webapp.md`.
  - Stack decisions confirmed (React/Vite + FastAPI).
  - Phase A skeleton implemented (UI and API containers running with healthchecks).
  - Phase B implemented (Interactive UI with charts and stability data table).
  - Windows `.bat` workflow created (`fourier-cycles/tools/open_fourier_debug.bat`).

## P2 (Later)
- [ ] **Resource checks automation**
  - Periodic free-space + backup growth checks.
  - Alert thresholds for critical disk pressure.

## ai_stack_todo
- Active list lives in this file only.
- Completed items are removed (history in Git/ADR/CHANGELOG).
