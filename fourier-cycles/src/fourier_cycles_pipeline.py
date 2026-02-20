#!/usr/bin/env python3
"""Batch Fourier cycle extraction with rolling stability checks for Yahoo/FRED."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
import requests

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class AnalysisConfig:
    output_dir: Path
    timeframe_days: int
    resample_rule: str
    yahoo_symbols: list[str]
    fred_series: list[str]
    top_k: int
    min_presence_ratio: float
    min_window_power_ratio: float
    rolling_window_ratio: float
    rolling_step_ratio: float
    min_period_days: float
    max_period_days: float
    selection_top_k: int
    selection_min_presence_ratio: float
    selection_min_norm_power_percentile: float
    selection_min_period_distance_ratio: float
    min_points: int
    timeout_seconds: int
    end_date: dt.date


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _slug(value: str) -> str:
    chars = [ch.lower() if ch.isalnum() else "-" for ch in value]
    return "".join(chars).strip("-") or "series"


def parse_iso_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date '{value}', expected YYYY-MM-DD") from exc


def parse_args() -> AnalysisConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=_env_str("FOURIER_OUTPUT_DIR", "/data/output"))
    parser.add_argument("--timeframe-days", type=int, default=_env_int("FOURIER_TIMEFRAME_DAYS", 1095))
    parser.add_argument("--resample-rule", default=_env_str("FOURIER_RESAMPLE_RULE", "1D"))
    parser.add_argument(
        "--yahoo-symbols",
        default=_env_str("FOURIER_YAHOO_SYMBOLS", "SPY,BTC-USD"),
        help="Comma-separated Yahoo symbols",
    )
    parser.add_argument(
        "--fred-series",
        default=_env_str("FOURIER_FRED_SERIES", "DGS10,CPIAUCSL"),
        help="Comma-separated FRED series ids",
    )
    parser.add_argument("--top-k", type=int, default=_env_int("FOURIER_TOP_K", 8))
    parser.add_argument(
        "--min-presence-ratio",
        type=float,
        default=_env_float("FOURIER_MIN_PRESENCE_RATIO", 0.30),
    )
    parser.add_argument(
        "--min-window-power-ratio",
        type=float,
        default=_env_float("FOURIER_MIN_WINDOW_POWER_RATIO", 0.03),
    )
    parser.add_argument(
        "--rolling-window-ratio",
        type=float,
        default=_env_float("FOURIER_ROLLING_WINDOW_RATIO", 0.35),
    )
    parser.add_argument(
        "--rolling-step-ratio",
        type=float,
        default=_env_float("FOURIER_ROLLING_STEP_RATIO", 0.25),
    )
    parser.add_argument(
        "--min-period-days", type=float, default=_env_float("FOURIER_MIN_PERIOD_DAYS", 7.0)
    )
    parser.add_argument(
        "--max-period-days", type=float, default=_env_float("FOURIER_MAX_PERIOD_DAYS", 365.0)
    )
    parser.add_argument(
        "--selection-top-k", type=int, default=_env_int("FOURIER_SELECTION_TOP_K", 3)
    )
    parser.add_argument(
        "--selection-min-presence-ratio",
        type=float,
        default=_env_float("FOURIER_SELECTION_MIN_PRESENCE_RATIO", 0.60),
    )
    parser.add_argument(
        "--selection-min-norm-power-percentile",
        type=float,
        default=_env_float("FOURIER_SELECTION_MIN_NORM_POWER_PERCENTILE", 0.75),
    )
    parser.add_argument(
        "--selection-min-period-distance-ratio",
        type=float,
        default=_env_float("FOURIER_SELECTION_MIN_PERIOD_DISTANCE_RATIO", 0.20),
    )
    parser.add_argument("--min-points", type=int, default=_env_int("FOURIER_MIN_POINTS", 180))
    parser.add_argument("--timeout-seconds", type=int, default=_env_int("FOURIER_TIMEOUT_SECONDS", 30))
    parser.add_argument("--end-date", type=parse_iso_date, default=dt.date.today())
    args = parser.parse_args()

    min_period_days = max(1.0, args.min_period_days)
    max_period_days = max(min_period_days, args.max_period_days)

    return AnalysisConfig(
        output_dir=Path(args.output_dir),
        timeframe_days=args.timeframe_days,
        resample_rule=args.resample_rule,
        yahoo_symbols=_split_csv(args.yahoo_symbols),
        fred_series=_split_csv(args.fred_series),
        top_k=max(1, args.top_k),
        min_presence_ratio=max(0.0, min(1.0, args.min_presence_ratio)),
        min_window_power_ratio=max(0.0, args.min_window_power_ratio),
        rolling_window_ratio=max(0.1, min(0.95, args.rolling_window_ratio)),
        rolling_step_ratio=max(0.05, min(1.0, args.rolling_step_ratio)),
        min_period_days=min_period_days,
        max_period_days=max_period_days,
        selection_top_k=max(1, args.selection_top_k),
        selection_min_presence_ratio=max(0.0, min(1.0, args.selection_min_presence_ratio)),
        selection_min_norm_power_percentile=max(
            0.0, min(1.0, args.selection_min_norm_power_percentile)
        ),
        selection_min_period_distance_ratio=max(
            0.0, min(1.0, args.selection_min_period_distance_ratio)
        ),
        min_points=max(32, args.min_points),
        timeout_seconds=max(5, args.timeout_seconds),
        end_date=args.end_date,
    )


def fetch_yahoo_series(
    symbol: str,
    start_date: dt.date,
    end_date: dt.date,
    timeout_seconds: int,
) -> tuple[pd.Series, str]:
    period1 = int(dt.datetime.combine(start_date, dt.time.min, tzinfo=dt.timezone.utc).timestamp())
    period2 = int(
        dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time.min, tzinfo=dt.timezone.utc).timestamp()
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "period1": str(period1),
        "period2": str(period2),
        "interval": "1d",
        "events": "div,splits",
        "includePrePost": "false",
    }
    headers = {
        "User-Agent": "ai-stack-fourier-cycles/0.1",
        "Accept": "application/json",
    }
    response = requests.get(url, params=params, headers=headers, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()

    result = ((payload.get("chart") or {}).get("result")) or []
    if not result:
        error_info = ((payload.get("chart") or {}).get("error")) or {}
        raise RuntimeError(f"Yahoo response has no result for {symbol}: {error_info!r}")

    first = result[0]
    timestamps = first.get("timestamp") or []
    quote = (((first.get("indicators") or {}).get("quote")) or [{}])[0]
    closes = quote.get("close") or []
    if not timestamps or not closes:
        raise RuntimeError(f"Yahoo response is missing timestamp/close for {symbol}")

    rows: list[tuple[dt.datetime, float]] = []
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        try:
            numeric = float(close)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric):
            continue
        date_value = dt.datetime.fromtimestamp(int(ts), tz=dt.timezone.utc).replace(tzinfo=None)
        rows.append((date_value, numeric))

    if not rows:
        raise RuntimeError(f"Yahoo parsing produced no points for {symbol}")

    index = pd.DatetimeIndex([row[0] for row in rows], name="date")
    series = pd.Series([row[1] for row in rows], index=index, name=symbol)
    return series.sort_index(), response.url


def fetch_fred_series(
    series_id: str,
    start_date: dt.date,
    end_date: dt.date,
    timeout_seconds: int,
) -> tuple[pd.Series, str]:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    params = {
        "id": series_id,
        "cosd": start_date.isoformat(),
        "coed": end_date.isoformat(),
    }
    headers = {
        "User-Agent": "ai-stack-fourier-cycles/0.1",
        "Accept": "text/csv",
    }
    response = requests.get(url, params=params, headers=headers, timeout=timeout_seconds)
    response.raise_for_status()

    reader = csv.DictReader(response.text.splitlines())
    if not reader.fieldnames:
        raise RuntimeError(f"FRED CSV has no header for {series_id}")

    date_column = "DATE" if "DATE" in reader.fieldnames else "observation_date"
    value_column = series_id if series_id in reader.fieldnames else reader.fieldnames[-1]

    rows: list[tuple[dt.datetime, float]] = []
    for row in reader:
        raw_date = (row.get(date_column) or "").strip()
        raw_value = (row.get(value_column) or "").strip()
        if not raw_date or not raw_value or raw_value == ".":
            continue
        try:
            date_value = dt.datetime.fromisoformat(raw_date)
            numeric = float(raw_value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric):
            continue
        rows.append((date_value, numeric))

    if not rows:
        raise RuntimeError(f"FRED parsing produced no points for {series_id}")

    index = pd.DatetimeIndex([row[0] for row in rows], name="date")
    series = pd.Series([row[1] for row in rows], index=index, name=series_id)
    return series.sort_index(), response.url


def trim_to_timeframe(levels: pd.Series, start_date: dt.date, end_date: dt.date) -> pd.Series:
    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    filtered = levels[(levels.index >= start_dt) & (levels.index <= end_dt)]
    return filtered.dropna()


def resample_levels(levels: pd.Series, rule: str) -> pd.Series:
    clean = levels[~levels.index.duplicated(keep="last")].sort_index()
    if not rule:
        return clean.dropna()
    sampled = clean.resample(rule).last().ffill()
    return sampled.dropna()


def infer_step_days(index: pd.DatetimeIndex) -> float:
    if len(index) < 2:
        return 1.0
    deltas_ns = np.diff(index.view("i8"))
    deltas_days = deltas_ns.astype(np.float64) / (24.0 * 3600.0 * 1e9)
    positive = deltas_days[deltas_days > 0]
    if len(positive) == 0:
        return 1.0
    return float(np.median(positive))


def build_signal(levels: pd.Series) -> tuple[pd.DatetimeIndex, np.ndarray, str]:
    if (levels > 0).all():
        transformed = np.log(levels).diff().dropna()
        transform_name = "log_returns"
    else:
        transformed = levels.pct_change().dropna()
        transform_name = "pct_change"

    signal = transformed.to_numpy(dtype=np.float64)
    signal = signal - np.mean(signal)
    if len(signal) > 1:
        signal = signal * np.hanning(len(signal))
    return transformed.index, signal, transform_name


def compute_spectrum(
    signal: np.ndarray,
    step_days: float,
    min_period_days: float,
    max_period_days: float,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    n = len(signal)
    coeff = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(n, d=step_days)
    power = (np.abs(coeff) ** 2) / (n * n)

    mask = freqs > 0
    with np.errstate(divide="ignore"):
        periods = np.where(freqs > 0, 1.0 / freqs, np.inf)
    mask &= periods >= min_period_days
    mask &= periods <= max_period_days

    selected_freqs = freqs[mask]
    selected_periods = periods[mask]
    selected_power = power[mask]
    if len(selected_freqs) == 0:
        raise RuntimeError("No spectrum bins left after period filters")

    total_power = float(np.sum(selected_power))
    if total_power <= 0:
        norm_power = np.zeros_like(selected_power)
    else:
        norm_power = selected_power / total_power

    spectrum = pd.DataFrame(
        {
            "freq_per_day": selected_freqs,
            "period_days": selected_periods,
            "power": selected_power,
            "norm_power": norm_power,
        }
    ).sort_values("power", ascending=False)
    return spectrum.reset_index(drop=True), freqs, power, coeff


def _window_bounds(signal_len: int, window_ratio: float, step_ratio: float) -> tuple[int, list[int]]:
    window_points = max(32, int(signal_len * window_ratio))
    window_points = min(window_points, signal_len)
    if window_points == signal_len:
        return window_points, [0]

    step_points = max(1, int(window_points * step_ratio))
    starts = list(range(0, signal_len - window_points + 1, step_points))
    if starts[-1] != signal_len - window_points:
        starts.append(signal_len - window_points)
    return window_points, starts


def evaluate_stability(
    signal: np.ndarray,
    signal_dates: pd.DatetimeIndex,
    step_days: float,
    candidate_spectrum: pd.DataFrame,
    cfg: AnalysisConfig,
) -> tuple[list[dict[str, Any]], list[str]]:
    if candidate_spectrum.empty:
        return [], []

    window_points, starts = _window_bounds(
        signal_len=len(signal),
        window_ratio=cfg.rolling_window_ratio,
        step_ratio=cfg.rolling_step_ratio,
    )

    window_mid_dates: list[str] = []
    window_freqs: list[np.ndarray] = []
    window_power: list[np.ndarray] = []
    for start in starts:
        segment = signal[start : start + window_points]
        coeff = np.fft.rfft(segment)
        freqs = np.fft.rfftfreq(len(segment), d=step_days)
        power = (np.abs(coeff) ** 2) / (len(segment) * len(segment))

        mask = freqs > 0
        with np.errstate(divide="ignore"):
            periods = np.where(freqs > 0, 1.0 / freqs, np.inf)
        mask &= periods >= cfg.min_period_days
        mask &= periods <= cfg.max_period_days

        freqs = freqs[mask]
        power = power[mask]
        window_freqs.append(freqs)
        window_power.append(power)

        mid_idx = start + (window_points // 2)
        mid_idx = min(mid_idx, len(signal_dates) - 1)
        window_mid_dates.append(signal_dates[mid_idx].date().isoformat())

    candidates: list[dict[str, Any]] = []
    for row in candidate_spectrum.itertuples(index=False):
        freq = float(row.freq_per_day)
        ratios: list[float] = []

        for freqs, power in zip(window_freqs, window_power):
            if len(freqs) == 0:
                ratios.append(0.0)
                continue
            total = float(np.sum(power))
            if total <= 0:
                ratios.append(0.0)
                continue
            if len(freqs) > 1:
                local_step = float(np.median(np.diff(freqs)))
            else:
                local_step = freq
            local_step = max(local_step, 1e-12)
            # Use a narrow local band to reduce nearest-bin leakage artifacts in short windows.
            band_half_width = max(local_step * 1.5, freq * 0.05)
            band_mask = np.abs(freqs - freq) <= band_half_width
            if not np.any(band_mask):
                ratios.append(0.0)
                continue
            band_power = float(np.sum(power[band_mask]))
            ratios.append(float(band_power / total))

        presence_ratio = sum(r >= cfg.min_window_power_ratio for r in ratios) / len(ratios)
        median_window_power_ratio = float(np.median(ratios))
        stability_score = presence_ratio * float(row.norm_power)
        stable = presence_ratio >= cfg.min_presence_ratio

        candidates.append(
            {
                "freq_per_day": freq,
                "period_days": float(row.period_days),
                "power": float(row.power),
                "norm_power": float(row.norm_power),
                "presence_ratio": presence_ratio,
                "median_window_power_ratio": median_window_power_ratio,
                "stability_score": stability_score,
                "stable": stable,
                "window_power_ratios": ratios,
            }
        )

    max_stability_score = max((cycle["stability_score"] for cycle in candidates), default=0.0)
    for cycle in candidates:
        if max_stability_score > 0:
            cycle["stability_score_norm"] = cycle["stability_score"] / max_stability_score
        else:
            cycle["stability_score_norm"] = 0.0

    candidates.sort(
        key=lambda item: (item["stable"], item["stability_score"], item["norm_power"]),
        reverse=True,
    )
    return candidates, window_mid_dates


def _period_distance_ratio(a_days: float, b_days: float) -> float:
    return abs(a_days - b_days) / max(a_days, b_days)


def select_cycles_for_output(
    evaluated_cycles: list[dict[str, Any]], cfg: AnalysisConfig
) -> list[dict[str, Any]]:
    if not evaluated_cycles:
        return []

    eligible = [
        cycle
        for cycle in evaluated_cycles
        if cycle["stable"] and cycle["presence_ratio"] >= cfg.selection_min_presence_ratio
    ]
    if not eligible:
        return []

    norm_powers = np.array([cycle["norm_power"] for cycle in eligible], dtype=np.float64)
    power_threshold = float(
        np.quantile(norm_powers, cfg.selection_min_norm_power_percentile, method="linear")
    )

    filtered = [cycle for cycle in eligible if cycle["norm_power"] >= power_threshold]
    if not filtered:
        filtered = list(eligible)

    ranked = sorted(
        filtered,
        key=lambda cycle: (cycle["stability_score"], cycle["presence_ratio"], cycle["norm_power"]),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    for cycle in ranked:
        too_close = any(
            _period_distance_ratio(cycle["period_days"], existing["period_days"])
            < cfg.selection_min_period_distance_ratio
            for existing in selected
        )
        if too_close:
            continue
        selected.append(cycle)
        if len(selected) >= cfg.selection_top_k:
            break
    return selected


def reconstruct_signal_from_cycles(
    signal: np.ndarray,
    full_freqs: np.ndarray,
    full_coeff: np.ndarray,
    selected_cycles: list[dict[str, Any]],
) -> np.ndarray:
    if not selected_cycles:
        return np.zeros_like(signal)

    keep = np.zeros_like(full_coeff)
    for cycle in selected_cycles:
        idx = int(np.argmin(np.abs(full_freqs - cycle["freq_per_day"])))
        keep[idx] = full_coeff[idx]
    reconstructed = np.fft.irfft(keep, n=len(signal))
    return reconstructed.real


def reconstruct_cycle_components(
    signal_len: int,
    full_freqs: np.ndarray,
    full_coeff: np.ndarray,
    selected_cycles: list[dict[str, Any]],
) -> list[tuple[str, np.ndarray]]:
    components: list[tuple[str, np.ndarray]] = []
    for cycle in selected_cycles:
        keep = np.zeros_like(full_coeff)
        idx = int(np.argmin(np.abs(full_freqs - cycle["freq_per_day"])))
        keep[idx] = full_coeff[idx]
        component = np.fft.irfft(keep, n=signal_len).real
        label = (
            f"{cycle['period_days']:.1f}d "
            f"(presence={cycle['presence_ratio']:.2f}, power={cycle['norm_power']:.3f})"
        )
        components.append((label, component))
    return components


def save_plot_spectrum(path: Path, spectrum: pd.DataFrame, selected_cycles: list[dict[str, Any]], title: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    view = spectrum.sort_values("period_days")
    ax.plot(view["period_days"], view["norm_power"], color="#145c9e", lw=1.5)
    for cycle in selected_cycles:
        color = "#2e7d32" if cycle["stable"] else "#b71c1c"
        ax.axvline(cycle["period_days"], color=color, ls="--", lw=1.0)
    ax.set_xscale("log")
    ax.set_xlabel("Period (days, log scale)")
    ax.set_ylabel("Normalized power")
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def save_plot_stability(
    path: Path,
    window_mid_dates: list[str],
    selected_cycles: list[dict[str, Any]],
    threshold: float,
    title: str,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    x = pd.to_datetime(window_mid_dates)
    if not selected_cycles:
        ax.text(0.5, 0.5, "No stable cycles passed thresholds", ha="center", va="center")
        ax.set_axis_off()
    else:
        for cycle in selected_cycles:
            label = f"{cycle['period_days']:.1f}d (presence={cycle['presence_ratio']:.2f})"
            ax.plot(x, cycle["window_power_ratios"], marker="o", ms=3, lw=1.1, label=label)
        ax.axhline(threshold, color="#616161", ls=":", lw=1.0, label="window threshold")
        ax.set_ylabel("Window power ratio")
        ax.set_xlabel("Window midpoint")
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.25)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def save_plot_reconstruction(
    path: Path,
    signal_dates: pd.DatetimeIndex,
    signal: np.ndarray,
    reconstructed: np.ndarray,
    title: str,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    x = pd.to_datetime(signal_dates)
    ax.plot(x, signal, color="#263238", lw=1.1, label="Signal")
    ax.plot(x, reconstructed, color="#ef6c00", lw=1.4, label="Stable-cycle reconstruction")
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Transformed value")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def save_plot_price(path: Path, levels: pd.Series, title: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    x = pd.to_datetime(levels.index)
    ax.plot(x, levels.to_numpy(dtype=np.float64), color="#145c9e", lw=1.4, label="Price level")
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Price / level")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _normalize_for_overlay(values: np.ndarray) -> np.ndarray:
    std = float(np.std(values))
    if std <= 0:
        return values - np.mean(values)
    return (values - np.mean(values)) / std


def save_plot_cycle_components(
    path: Path,
    signal_dates: pd.DatetimeIndex,
    components: list[tuple[str, np.ndarray]],
    title: str,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    x = pd.to_datetime(signal_dates)
    if not components:
        ax.text(0.5, 0.5, "No cycle components selected", ha="center", va="center")
        ax.set_axis_off()
    else:
        for label, component in components:
            normalized = _normalize_for_overlay(component)
            ax.plot(x, normalized, lw=1.2, label=label)
        ax.axhline(0.0, color="#616161", ls=":", lw=1.0)
        ax.set_ylabel("Normalized component value")
        ax.set_xlabel("Date")
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.25)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def save_plot_price_cycle_overlay(
    path: Path,
    levels: pd.Series,
    signal_dates: pd.DatetimeIndex,
    reconstructed: np.ndarray,
    title: str,
) -> None:
    fig, ax_price = plt.subplots(figsize=(12, 6))
    x_signal = pd.to_datetime(signal_dates)
    price_aligned = levels.reindex(signal_dates).ffill().bfill()
    cycle_index = np.cumsum(reconstructed)
    cycle_index = _normalize_for_overlay(cycle_index)

    ax_price.plot(x_signal, price_aligned.to_numpy(dtype=np.float64), color="#145c9e", lw=1.4)
    ax_price.set_xlabel("Date")
    ax_price.set_ylabel("Price / level", color="#145c9e")
    ax_price.tick_params(axis="y", labelcolor="#145c9e")
    ax_price.grid(True, alpha=0.2)

    ax_cycle = ax_price.twinx()
    ax_cycle.plot(x_signal, cycle_index, color="#ef6c00", lw=1.3, alpha=0.9)
    ax_cycle.axhline(0.0, color="#616161", ls=":", lw=1.0)
    ax_cycle.set_ylabel("Composite cycle index (normalized)", color="#ef6c00")
    ax_cycle.tick_params(axis="y", labelcolor="#ef6c00")

    ax_price.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def write_cycles_csv(path: Path, cycles: list[dict[str, Any]]) -> None:
    columns = [
        "period_days",
        "freq_per_day",
        "power",
        "norm_power",
        "presence_ratio",
        "median_window_power_ratio",
        "stability_score",
        "stability_score_norm",
        "stable",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for cycle in cycles:
            writer.writerow({key: cycle[key] for key in columns})


def write_waves_csv(
    path: Path,
    signal_dates: pd.DatetimeIndex,
    selected_cycles: list[dict[str, Any]],
    components: list[tuple[str, np.ndarray]],
) -> None:
    columns = ["date", "period_days", "component_value"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()

        if not selected_cycles or not components:
            return

        date_values = [ts.date().isoformat() for ts in pd.to_datetime(signal_dates)]
        for cycle, (_, component) in zip(selected_cycles, components):
            period_days = float(cycle["period_days"])
            for date_value, component_value in zip(date_values, component):
                writer.writerow(
                    {
                        "date": date_value,
                        "period_days": period_days,
                        "component_value": float(component_value),
                    }
                )


def process_single_series(
    source: str,
    series_name: str,
    levels: pd.Series,
    fetch_url: str,
    run_dir: Path,
    cfg: AnalysisConfig,
    start_date: dt.date,
) -> dict[str, Any]:
    levels = trim_to_timeframe(levels, start_date=start_date, end_date=cfg.end_date)
    levels = resample_levels(levels, cfg.resample_rule)
    if len(levels) < cfg.min_points:
        raise RuntimeError(
            f"Series too short after resample ({len(levels)} < {cfg.min_points}) for {source}:{series_name}"
        )

    signal_dates, signal, transform_name = build_signal(levels)
    if len(signal) < cfg.min_points:
        raise RuntimeError(
            f"Signal too short after transform ({len(signal)} < {cfg.min_points}) for {source}:{series_name}"
        )

    step_days = infer_step_days(signal_dates)
    spectrum, full_freqs, _, full_coeff = compute_spectrum(
        signal=signal,
        step_days=step_days,
        min_period_days=cfg.min_period_days,
        max_period_days=cfg.max_period_days,
    )

    candidate_pool_size = max(cfg.top_k * 3, cfg.selection_top_k * 8)
    candidate_pool = spectrum.head(candidate_pool_size)
    evaluated, window_mid_dates = evaluate_stability(
        signal=signal,
        signal_dates=signal_dates,
        step_days=step_days,
        candidate_spectrum=candidate_pool,
        cfg=cfg,
    )

    stable_cycles = [cycle for cycle in evaluated if cycle["stable"]]
    selected_cycles = select_cycles_for_output(evaluated, cfg)

    reconstructed = reconstruct_signal_from_cycles(
        signal=signal,
        full_freqs=full_freqs,
        full_coeff=full_coeff,
        selected_cycles=selected_cycles,
    )
    components = reconstruct_cycle_components(
        signal_len=len(signal),
        full_freqs=full_freqs,
        full_coeff=full_coeff,
        selected_cycles=selected_cycles,
    )

    series_dir = run_dir / f"{source}-{_slug(series_name)}"
    series_dir.mkdir(parents=True, exist_ok=False)

    levels.to_frame(name="value").to_csv(series_dir / "series.csv", index_label="date")
    pd.DataFrame({"date": signal_dates, "signal": signal}).to_csv(
        series_dir / "signal.csv", index=False
    )
    spectrum.to_csv(series_dir / "spectrum.csv", index=False)
    write_cycles_csv(series_dir / "cycles.csv", stable_cycles)
    write_waves_csv(
        series_dir / "waves.csv",
        signal_dates=signal_dates,
        selected_cycles=selected_cycles,
        components=components,
    )
    save_plot_price(
        series_dir / "price.png",
        levels,
        f"{source}:{series_name} price/level ({cfg.timeframe_days}d)",
    )
    save_plot_price_cycle_overlay(
        series_dir / "price_cycle_overlay.png",
        levels,
        signal_dates,
        reconstructed,
        f"{source}:{series_name} price with composite cycle overlay",
    )
    save_plot_cycle_components(
        series_dir / "cycle_components.png",
        signal_dates,
        components,
        f"{source}:{series_name} top cycle components",
    )

    save_plot_spectrum(
        series_dir / "spectrum.png",
        spectrum,
        selected_cycles,
        f"{source}:{series_name} spectrum ({cfg.timeframe_days}d)",
    )
    save_plot_stability(
        series_dir / "stability.png",
        window_mid_dates,
        selected_cycles,
        threshold=cfg.min_window_power_ratio,
        title=f"{source}:{series_name} rolling stability",
    )
    save_plot_reconstruction(
        series_dir / "reconstruction.png",
        signal_dates,
        signal,
        reconstructed,
        f"{source}:{series_name} {transform_name} signal vs stable-cycle reconstruction",
    )

    summary = {
        "source": source,
        "series": series_name,
        "fetch_url": fetch_url,
        "timeframe_days": cfg.timeframe_days,
        "resample_rule": cfg.resample_rule,
        "transform": transform_name,
        "step_days": step_days,
        "points": int(len(levels)),
        "signal_points": int(len(signal)),
        "stable_cycle_count": len(stable_cycles),
        "selected_cycle_count": len(selected_cycles),
        "selection_top_k": cfg.selection_top_k,
        "selection_min_presence_ratio": cfg.selection_min_presence_ratio,
        "selection_min_norm_power_percentile": cfg.selection_min_norm_power_percentile,
        "selection_min_period_distance_ratio": cfg.selection_min_period_distance_ratio,
        "selected_cycles": selected_cycles,
    }
    (series_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def update_latest_symlink(output_dir: Path, run_dir: Path) -> None:
    latest = output_dir / "latest"
    if latest.is_symlink() or latest.exists():
        if latest.is_dir() and not latest.is_symlink():
            shutil.rmtree(latest)
        else:
            latest.unlink()
    latest.symlink_to(run_dir.name)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def main() -> int:
    cfg = parse_args()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    if not cfg.yahoo_symbols and not cfg.fred_series:
        raise RuntimeError("No symbols configured: both Yahoo and FRED lists are empty")

    start_date = cfg.end_date - dt.timedelta(days=cfg.timeframe_days)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    run_dir = cfg.output_dir / run_id
    run_dir.mkdir(parents=False, exist_ok=False)

    successes: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for symbol in cfg.yahoo_symbols:
        try:
            levels, fetch_url = fetch_yahoo_series(
                symbol=symbol,
                start_date=start_date,
                end_date=cfg.end_date,
                timeout_seconds=cfg.timeout_seconds,
            )
            summary = process_single_series(
                source="yahoo",
                series_name=symbol,
                levels=levels,
                fetch_url=fetch_url,
                run_dir=run_dir,
                cfg=cfg,
                start_date=start_date,
            )
            successes.append(summary)
            print(f"ok source=yahoo series={symbol} stable_cycles={summary['stable_cycle_count']}")
        except Exception as exc:  # noqa: BLE001
            failures.append({"source": "yahoo", "series": symbol, "error": str(exc)})
            print(f"error source=yahoo series={symbol} msg={exc}", file=sys.stderr)

    for series_id in cfg.fred_series:
        try:
            levels, fetch_url = fetch_fred_series(
                series_id=series_id,
                start_date=start_date,
                end_date=cfg.end_date,
                timeout_seconds=cfg.timeout_seconds,
            )
            summary = process_single_series(
                source="fred",
                series_name=series_id,
                levels=levels,
                fetch_url=fetch_url,
                run_dir=run_dir,
                cfg=cfg,
                start_date=start_date,
            )
            successes.append(summary)
            print(f"ok source=fred series={series_id} stable_cycles={summary['stable_cycle_count']}")
        except Exception as exc:  # noqa: BLE001
            failures.append({"source": "fred", "series": series_id, "error": str(exc)})
            print(f"error source=fred series={series_id} msg={exc}", file=sys.stderr)

    run_summary = {
        "run_id": run_id,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "config": {key: _jsonable(value) for key, value in asdict(cfg).items()},
        "start_date": start_date.isoformat(),
        "end_date": cfg.end_date.isoformat(),
        "success_count": len(successes),
        "failure_count": len(failures),
        "successes": successes,
        "failures": failures,
    }
    (run_dir / "summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")

    if successes:
        update_latest_symlink(cfg.output_dir, run_dir)

    print(f"run_dir={run_dir}")
    print(f"success={len(successes)} failure={len(failures)}")
    if failures and not successes:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
