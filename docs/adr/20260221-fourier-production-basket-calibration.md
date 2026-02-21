# ADR: Fourier Production Basket and Selection Threshold Baseline
Date: 2026-02-21
Status: Accepted

## Context
- The active backlog required finalizing Fourier deepening by defining a production basket and calibrating strict selection thresholds from successful outputs.
- `fourier-cycles` uses strict absolute eligibility gates (`presence_ratio`, `phase_locking_r`, `amp_median`) plus ranking/diversification.
- A full-basket reference run (`run_20260220T234612Z`) delivered successful outputs for all four intended baseline series.

## Decision
- Define the production basket as:
  - Yahoo: `SPY`, `BTC-USD`
  - FRED: `DGS10`, `CPIAUCSL`
- Calibrate selection defaults from reference-run selected-cycle minima:
  - `FOURIER_SELECTION_MIN_PRESENCE_RATIO`: `0.60 -> 0.50`
  - `FOURIER_SELECTION_MIN_PHASE_LOCKING_R`: `0.08 -> 0.04`
  - `FOURIER_SELECTION_MIN_AMP_SIGMA`: keep `0.06`
- Keep unchanged for now:
  - `FOURIER_SELECTION_MIN_NORM_POWER_PERCENTILE=0.75`
  - `FOURIER_SELECTION_MIN_PERIOD_DISTANCE_RATIO=0.20`
  - `FOURIER_SELECTION_MAX_P_VALUE_BANDMAX=1.00`

## Consequences
- Positive:
  - The default thresholds align with observed full-basket cycle quality instead of relying on fail-open fallback for weak edge cases.
  - Baseline behavior is reproducible across operator docs, config examples, and pipeline defaults.
- Negative:
  - Slightly lower phase/presence gates may admit more candidates on noisy baskets; monitoring remains necessary.
  - If the production basket changes materially, recalibration is required.

## Alternatives considered
- Keep previous stricter defaults (`presence=0.60`, `phase_r=0.08`) and rely on fail-open fallback.
  - Rejected: this made at least one baseline series depend on fallback despite otherwise acceptable signal quality.
- Raise amplitude threshold above `0.06`.
  - Rejected: would risk suppressing legitimate macro cycles in CPI-like series.
