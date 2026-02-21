#!/usr/bin/env python3
"""Synthetic 5-component superposition check for fourier-cycles extraction."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent / "src"
import sys

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fourier_cycles_pipeline import (  # type: ignore  # noqa: E402
    compute_spectrum,
    discover_candidate_spectrum,
    evaluate_stability,
    select_cycles_for_output,
)


@dataclass(frozen=True)
class Component:
    fn: str
    period_days: float
    amplitude: float
    phase_rad: float


def _parse_float_csv(raw: str, name: str) -> list[float]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError(f"{name} is empty")
    return [float(value) for value in values]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=1460, help="Synthetic sample length in days.")
    parser.add_argument(
        "--periods",
        default="37,52,88,124,195",
        help="Comma-separated target periods in days (5 recommended).",
    )
    parser.add_argument(
        "--amplitudes",
        default="1.2,1.0,0.9,0.8,0.7",
        help="Comma-separated amplitudes, same length as periods.",
    )
    parser.add_argument(
        "--phases",
        default="0.2,1.0,2.1,0.7,1.6",
        help="Comma-separated phases in radians, same length as periods.",
    )
    parser.add_argument("--noise-std", type=float, default=0.25, help="Gaussian noise std.")
    parser.add_argument("--seed", type=int, default=42, help="Noise seed.")
    parser.add_argument("--min-period-days", type=float, default=20.0)
    parser.add_argument("--max-period-days", type=float, default=260.0)
    parser.add_argument("--selection-top-k", type=int, default=5)
    parser.add_argument(
        "--tolerance-ratio",
        type=float,
        default=0.08,
        help="Relative period error threshold for hit classification.",
    )
    parser.add_argument(
        "--output-dir",
        default="fourier-cycles/output/synthetic-check/latest",
        help="Write artifacts (CSV/JSON) here.",
    )
    return parser.parse_args()


def build_components(args: argparse.Namespace) -> list[Component]:
    periods = _parse_float_csv(args.periods, "periods")
    amplitudes = _parse_float_csv(args.amplitudes, "amplitudes")
    phases = _parse_float_csv(args.phases, "phases")
    if not (len(periods) == len(amplitudes) == len(phases)):
        raise ValueError("periods/amplitudes/phases lengths differ")
    functions = ["sin", "cos"]
    components: list[Component] = []
    for idx, (period, amp, phase) in enumerate(zip(periods, amplitudes, phases)):
        components.append(Component(functions[idx % 2], period, amp, phase))
    return components


def synthesize_signal(components: list[Component], days: int, noise_std: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    t = np.arange(days, dtype=np.float64)
    clean = np.zeros(days, dtype=np.float64)
    for comp in components:
        omega_t = (2.0 * np.pi * t / comp.period_days) + comp.phase_rad
        if comp.fn == "sin":
            clean += comp.amplitude * np.sin(omega_t)
        else:
            clean += comp.amplitude * np.cos(omega_t)
    rng = np.random.default_rng(seed)
    noisy = clean + rng.normal(0.0, noise_std, size=days)
    signal = noisy - float(np.mean(noisy))
    if len(signal) > 1:
        signal = signal * np.hanning(len(signal))
    return clean, signal


def build_cfg(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        top_k=max(8, args.selection_top_k),
        selection_top_k=max(1, args.selection_top_k),
        min_period_days=float(args.min_period_days),
        max_period_days=float(args.max_period_days),
        min_presence_ratio=0.30,
        min_window_power_ratio=0.03,
        rolling_windows_days=[360, 720, 1260],
        rolling_step_days=30,
        harmonic_include_trend=True,
        snr_presence_threshold=2.0,
        snr_peak_bandwidth_ratio=0.05,
        snr_background_bandwidth_ratio=0.25,
        snr_background_exclusion_ratio=0.08,
        surrogate_count=0,
        surrogate_seed=42,
        rank_weight_amp=1.0,
        rank_weight_snr=1.0,
        rank_weight_presence=1.0,
        rank_weight_phase=1.0,
        selection_min_presence_ratio=0.30,
        selection_min_norm_power_percentile=0.0,
        selection_min_period_distance_ratio=0.10,
        selection_min_phase_locking_r=0.0,
        selection_max_p_value_bandmax=1.0,
        selection_min_amp_sigma=0.0,
    )


def nearest_period(target: float, cycles: list[dict]) -> tuple[float | None, float | None]:
    if not cycles:
        return None, None
    nearest = min(cycles, key=lambda c: abs(float(c["period_days"]) - target))
    nearest_period_days = float(nearest["period_days"])
    rel_err = abs(nearest_period_days - target) / max(target, 1e-9)
    return nearest_period_days, rel_err


def write_artifacts(
    out_dir: Path,
    dates: pd.DatetimeIndex,
    clean: np.ndarray,
    signal: np.ndarray,
    stable_cycles: list[dict],
    selected_cycles: list[dict],
    summary_payload: dict,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "synthetic_series.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "clean_value", "signal_value"])
        for date, clean_value, signal_value in zip(dates, clean, signal):
            writer.writerow([date.date().isoformat(), float(clean_value), float(signal_value)])

    if stable_cycles:
        stable_df = pd.DataFrame(stable_cycles)
        stable_df.sort_values(["stable", "rank_score_norm", "presence_ratio"], ascending=False).to_csv(
            out_dir / "stable_cycles.csv", index=False
        )
    if selected_cycles:
        pd.DataFrame(selected_cycles).to_csv(out_dir / "selected_cycles.csv", index=False)

    (out_dir / "summary.json").write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    components = build_components(args)
    cfg = build_cfg(args)

    clean, signal = synthesize_signal(components, args.days, args.noise_std, args.seed)
    signal_dates = pd.date_range("2021-01-01", periods=args.days, freq="D")
    step_days = 1.0

    spectrum, full_freqs, full_power, _ = compute_spectrum(
        signal=signal,
        step_days=step_days,
        min_period_days=cfg.min_period_days,
        max_period_days=cfg.max_period_days,
    )
    candidate_pool = discover_candidate_spectrum(spectrum, cfg=cfg)
    evaluated, _, _ = evaluate_stability(
        signal=signal,
        signal_dates=signal_dates,
        step_days=step_days,
        candidate_spectrum=candidate_pool,
        full_freqs=full_freqs,
        full_power=full_power,
        cfg=cfg,
    )
    stable_cycles = [cycle for cycle in evaluated if cycle.get("stable")]
    selected_cycles = select_cycles_for_output(evaluated, cfg=cfg)

    truth_periods = [comp.period_days for comp in components]
    tolerance = float(args.tolerance_ratio)
    truth_rows = []
    hit_count_stable = 0
    hit_count_selected = 0
    for period in truth_periods:
        nearest_stable, stable_err = nearest_period(period, stable_cycles)
        nearest_selected, selected_err = nearest_period(period, selected_cycles)
        hit_stable = stable_err is not None and stable_err <= tolerance
        hit_selected = selected_err is not None and selected_err <= tolerance
        hit_count_stable += int(hit_stable)
        hit_count_selected += int(hit_selected)
        truth_rows.append(
            {
                "target_period_days": period,
                "nearest_stable_period_days": nearest_stable,
                "stable_rel_error": stable_err,
                "stable_hit": bool(hit_stable),
                "nearest_selected_period_days": nearest_selected,
                "selected_rel_error": selected_err,
                "selected_hit": bool(hit_selected),
            }
        )

    print("Synthetic Superposition Check")
    print(f"components={len(components)} days={args.days} noise_std={args.noise_std} seed={args.seed}")
    print("target_periods:", ", ".join(f"{p:.1f}" for p in truth_periods))
    print("selected_periods:", ", ".join(f"{float(c['period_days']):.1f}" for c in selected_cycles) or "none")
    print(
        f"hits_stable={hit_count_stable}/{len(truth_periods)} "
        f"hits_selected={hit_count_selected}/{len(truth_periods)} "
        f"tol={tolerance:.3f}"
    )
    print("")
    print("target\tstable_nearest\tstable_err\tselected_nearest\tselected_err")
    for row in truth_rows:
        stable_period = "-" if row["nearest_stable_period_days"] is None else f"{row['nearest_stable_period_days']:.2f}"
        stable_err = "-" if row["stable_rel_error"] is None else f"{row['stable_rel_error']:.4f}"
        selected_period = (
            "-" if row["nearest_selected_period_days"] is None else f"{row['nearest_selected_period_days']:.2f}"
        )
        selected_err = "-" if row["selected_rel_error"] is None else f"{row['selected_rel_error']:.4f}"
        print(f"{row['target_period_days']:.2f}\t{stable_period}\t{stable_err}\t{selected_period}\t{selected_err}")

    out_dir = Path(args.output_dir).expanduser().resolve()
    payload = {
        "components": [comp.__dict__ for comp in components],
        "days": int(args.days),
        "noise_std": float(args.noise_std),
        "seed": int(args.seed),
        "tolerance_ratio": tolerance,
        "hit_count_stable": int(hit_count_stable),
        "hit_count_selected": int(hit_count_selected),
        "truth_vs_detected": truth_rows,
        "selected_periods": [float(c["period_days"]) for c in selected_cycles],
    }
    write_artifacts(
        out_dir=out_dir,
        dates=signal_dates,
        clean=clean,
        signal=signal,
        stable_cycles=stable_cycles,
        selected_cycles=selected_cycles,
        summary_payload=payload,
    )
    print("")
    print(f"artifacts: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
