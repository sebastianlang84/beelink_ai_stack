# TODO / Active Backlog

Purpose: Active work only.
Contains: Open tasks with priority and status.
Does not contain: Completed history (see Git/ADR/CHANGELOG).

## P0 (Now)
- [ ] **Open WebUI Knowledge cleanup (pending user confirm)**
  - Remove undesired collections (`bitcoin` / `crypto`) only after explicit confirmation.
  - Re-verify intended topics and sync behavior.
  - Read-only verification on 2026-02-18: only `investing_new` + `investing_archive` exist; no `bitcoin`/`crypto` collections present.

## P1 (Next)
- [ ] **Fourier analysis deepening (FRED + Yahoo)**
  - Define first target basket (symbols/series).
  - Add significance/robustness checks (beyond raw DFT ranking).
  - Document interpretation guardrails for non-forecast use.

- [ ] **OpenClaw Telegram E2E final verification**
  - Close DM/group behavior verification and record final operational path.

## P2 (Later)
- [ ] **Resource checks automation**
  - Periodic free-space + backup growth checks.
  - Alert thresholds for critical disk pressure.

## ai_stack_todo
- Active list lives in this file only.
- Completed items are removed (history in Git/ADR/CHANGELOG).
