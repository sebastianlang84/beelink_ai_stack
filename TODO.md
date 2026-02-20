# TODO / Active Backlog

Purpose: Active work only.
Contains: Open tasks with priority and status.
Does not contain: Completed history (see Git/ADR/CHANGELOG).

## P0 (Now)
- None.

## P1 (Next)
- [ ] **Fingerprint-Backfill Verhalten korrigieren (Unerwünscht)** [added by Claw 🦞]
  - Problem: Jede kleinste Änderung am Prompt/Modell löst einen massiven, teuren Backfill historischer Summaries aus (Fingerprint-Mismatch).
  - Ziel: Backfill sollte optional oder "soft" sein (z.B. nur für die letzten N Tage oder via explizitem CLI-Flag).
- [ ] **Fourier analysis deepening (FRED + Yahoo)** [added by Claw 🦞]
  - Define first target basket (symbols/series).
  - Add significance/robustness checks (beyond raw DFT ranking).
  - Document interpretation guardrails for non-forecast use.

## P2 (Later)
- [ ] **Resource checks automation**
  - Periodic free-space + backup growth checks.
  - Alert thresholds for critical disk pressure.

## ai_stack_todo
- Active list lives in this file only.
- Completed items are removed (history in Git/ADR/CHANGELOG).
