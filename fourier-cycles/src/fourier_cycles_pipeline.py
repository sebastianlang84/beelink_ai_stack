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
import matplotlib.dates as mdates  # noqa: E402


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
    selection_min_phase_locking_r: float
    selection_max_p_value_bandmax: float
    selection_min_amp_sigma: float
    rolling_windows_days: list[int]
    rolling_step_days: int
    harmonic_include_trend: bool
    detrend_rolling_days: int
    signal_mode_yahoo: str
    signal_mode_fred: str
    snr_presence_threshold: float
    snr_peak_bandwidth_ratio: float
    snr_background_bandwidth_ratio: float
    snr_background_exclusion_ratio: float
    surrogate_count: int
    surrogate_seed: int
    rank_weight_amp: float
    rank_weight_snr: float
    rank_weight_presence: float
    rank_weight_phase: float
    export_windows_csv: bool
    enable_wavelet_view: bool
    wavelet_period_count: int
    projection_days: int
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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid bool for {name}: {raw!r}")


def _env_int_list(name: str, default: list[int]) -> list[int]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return list(default)
    values = [item.strip() for item in raw.split(",")]
    parsed = [int(item) for item in values if item]
    return parsed or list(default)


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
        default=_env_float("FOURIER_SELECTION_MIN_PRESENCE_RATIO", 0.50),
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
    parser.add_argument(
        "--selection-min-phase-locking-r",
        type=float,
        default=_env_float("FOURIER_SELECTION_MIN_PHASE_LOCKING_R", 0.04),
    )
    parser.add_argument(
        "--selection-max-p-value-bandmax",
        type=float,
        default=_env_float("FOURIER_SELECTION_MAX_P_VALUE_BANDMAX", 1.00),
    )
    parser.add_argument(
        "--selection-min-amp-sigma",
        type=float,
        default=_env_float("FOURIER_SELECTION_MIN_AMP_SIGMA", 0.06),
    )
    parser.add_argument(
        "--rolling-windows-days",
        default=_env_str("FOURIER_ROLLING_WINDOWS_DAYS", "360,720,1260"),
        help="Comma-separated rolling window sizes in days",
    )
    parser.add_argument(
        "--rolling-step-days",
        type=int,
        default=_env_int("FOURIER_ROLLING_STEP_DAYS", 30),
    )
    parser.add_argument(
        "--harmonic-include-trend",
        type=int,
        default=1 if _env_bool("FOURIER_HARMONIC_INCLUDE_TREND", True) else 0,
        help="1=fit linear trend term in harmonic regression, 0=disable",
    )
    parser.add_argument(
        "--detrend-rolling-days",
        type=int,
        default=_env_int("FOURIER_DETREND_ROLLING_DAYS", 504),
    )
    parser.add_argument(
        "--signal-mode-yahoo",
        default=_env_str("FOURIER_SIGNAL_MODE_YAHOO", "log_returns"),
    )
    parser.add_argument(
        "--signal-mode-fred",
        default=_env_str("FOURIER_SIGNAL_MODE_FRED", "pct_change"),
    )
    parser.add_argument(
        "--snr-presence-threshold",
        type=float,
        default=_env_float("FOURIER_SNR_PRESENCE_THRESHOLD", 2.0),
    )
    parser.add_argument(
        "--snr-peak-bandwidth-ratio",
        type=float,
        default=_env_float("FOURIER_SNR_PEAK_BANDWIDTH_RATIO", 0.05),
    )
    parser.add_argument(
        "--snr-background-bandwidth-ratio",
        type=float,
        default=_env_float("FOURIER_SNR_BACKGROUND_BANDWIDTH_RATIO", 0.25),
    )
    parser.add_argument(
        "--snr-background-exclusion-ratio",
        type=float,
        default=_env_float("FOURIER_SNR_BACKGROUND_EXCLUSION_RATIO", 0.08),
    )
    parser.add_argument(
        "--surrogate-count",
        type=int,
        default=_env_int("FOURIER_SURROGATE_COUNT", 200),
    )
    parser.add_argument(
        "--surrogate-seed",
        type=int,
        default=_env_int("FOURIER_SURROGATE_SEED", 42),
    )
    parser.add_argument(
        "--rank-weight-amp",
        type=float,
        default=_env_float("FOURIER_RANK_WEIGHT_AMP", 1.0),
    )
    parser.add_argument(
        "--rank-weight-snr",
        type=float,
        default=_env_float("FOURIER_RANK_WEIGHT_SNR", 1.0),
    )
    parser.add_argument(
        "--rank-weight-presence",
        type=float,
        default=_env_float("FOURIER_RANK_WEIGHT_PRESENCE", 1.0),
    )
    parser.add_argument(
        "--rank-weight-phase",
        type=float,
        default=_env_float("FOURIER_RANK_WEIGHT_PHASE", 1.0),
    )
    parser.add_argument(
        "--export-windows-csv",
        type=int,
        default=1 if _env_bool("FOURIER_EXPORT_WINDOWS_CSV", False) else 0,
        help="1=write optional windows.csv with per-window cycle metrics, 0=disable",
    )
    parser.add_argument(
        "--enable-wavelet-view",
        type=int,
        default=1 if _env_bool("FOURIER_ENABLE_WAVELET_VIEW", False) else 0,
        help="1=write optional wavelet.png for non-stationary cycle activity, 0=disable",
    )
    parser.add_argument(
        "--wavelet-period-count",
        type=int,
        default=_env_int("FOURIER_WAVELET_PERIOD_COUNT", 48),
        help="Number of logarithmic periods used for optional wavelet view.",
    )
    parser.add_argument(
        "--projection-days",
        type=int,
        default=_env_int("FOURIER_PROJECTION_DAYS", 120),
        help="Project cycle components beyond latest observed date (days).",
    )
    parser.add_argument("--min-points", type=int, default=_env_int("FOURIER_MIN_POINTS", 180))
    parser.add_argument("--timeout-seconds", type=int, default=_env_int("FOURIER_TIMEOUT_SECONDS", 30))
    parser.add_argument("--end-date", type=parse_iso_date, default=dt.date.today())
    args = parser.parse_args()

    min_period_days = max(1.0, args.min_period_days)
    max_period_days = max(min_period_days, args.max_period_days)
    rolling_windows_days = sorted(
        {
            max(64, int(days))
            for days in _split_csv(args.rolling_windows_days)
            if days.strip()
        }
    )
    if not rolling_windows_days:
        rolling_windows_days = [360, 720, 1260]
    signal_mode_yahoo = (args.signal_mode_yahoo or "log_returns").strip().lower()
    signal_mode_fred = (args.signal_mode_fred or "pct_change").strip().lower()

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
        selection_min_phase_locking_r=max(0.0, min(1.0, args.selection_min_phase_locking_r)),
        selection_max_p_value_bandmax=max(0.0, min(1.0, args.selection_max_p_value_bandmax)),
        selection_min_amp_sigma=max(0.0, args.selection_min_amp_sigma),
        rolling_windows_days=rolling_windows_days,
        rolling_step_days=max(1, args.rolling_step_days),
        harmonic_include_trend=bool(args.harmonic_include_trend),
        detrend_rolling_days=max(0, args.detrend_rolling_days),
        signal_mode_yahoo=signal_mode_yahoo,
        signal_mode_fred=signal_mode_fred,
        snr_presence_threshold=max(0.0, args.snr_presence_threshold),
        snr_peak_bandwidth_ratio=max(0.0001, args.snr_peak_bandwidth_ratio),
        snr_background_bandwidth_ratio=max(
            args.snr_peak_bandwidth_ratio,
            args.snr_background_bandwidth_ratio,
        ),
        snr_background_exclusion_ratio=max(0.0001, args.snr_background_exclusion_ratio),
        surrogate_count=max(0, args.surrogate_count),
        surrogate_seed=args.surrogate_seed,
        rank_weight_amp=max(0.0, args.rank_weight_amp),
        rank_weight_snr=max(0.0, args.rank_weight_snr),
        rank_weight_presence=max(0.0, args.rank_weight_presence),
        rank_weight_phase=max(0.0, args.rank_weight_phase),
        export_windows_csv=bool(args.export_windows_csv),
        enable_wavelet_view=bool(args.enable_wavelet_view),
        wavelet_period_count=max(8, int(args.wavelet_period_count)),
        projection_days=max(0, int(args.projection_days)),
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


def _build_transformed_series(levels: pd.Series, signal_mode: str) -> tuple[pd.Series, str]:
    mode = signal_mode.strip().lower()
    if mode == "log_level":
        if not (levels > 0).all():
            raise RuntimeError("signal mode log_level requires strictly positive values")
        transformed = np.log(levels)
        return transformed.dropna(), "log_level"
    if mode == "level":
        return levels.dropna(), "level"
    if mode == "diff":
        transformed = levels.diff()
        return transformed.dropna(), "diff"
    if mode == "pct_change":
        transformed = levels.pct_change()
        return transformed.dropna(), "pct_change"
    if mode == "log_returns":
        if not (levels > 0).all():
            transformed = levels.pct_change().dropna()
            return transformed, "pct_change_fallback"
        transformed = np.log(levels).diff()
        return transformed.dropna(), "log_returns"
    raise RuntimeError(
        f"unsupported signal mode '{signal_mode}', choose one of: "
        "log_returns,pct_change,diff,log_level,level"
    )


def _detrend_rolling(series: pd.Series, rolling_days: int) -> pd.Series:
    if rolling_days <= 1:
        return series.dropna()
    if len(series) < max(8, rolling_days // 4):
        return series.dropna()
    trend = series.rolling(window=rolling_days, min_periods=max(8, rolling_days // 4)).mean()
    detrended = series - trend
    return detrended.dropna()


def _standardize(series: pd.Series) -> pd.Series:
    values = series.to_numpy(dtype=np.float64)
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std <= 0:
        standardized = values - mean
    else:
        standardized = (values - mean) / std
    return pd.Series(standardized, index=series.index, name=series.name)


def build_signal(
    levels: pd.Series,
    signal_mode: str,
    detrend_rolling_days: int,
) -> tuple[pd.DatetimeIndex, np.ndarray, str]:
    transformed, transform_name = _build_transformed_series(levels, signal_mode=signal_mode)
    detrended = _detrend_rolling(transformed, rolling_days=detrend_rolling_days)
    standardized = _standardize(detrended)

    signal = standardized.to_numpy(dtype=np.float64)
    signal = signal - np.mean(signal)
    if len(signal) > 1:
        signal = signal * np.hanning(len(signal))
    return standardized.index, signal, transform_name


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


def _compute_band_metrics(
    freqs: np.ndarray,
    power: np.ndarray,
    freq0: float,
    cfg: AnalysisConfig,
) -> tuple[float, float]:
    if len(freqs) == 0:
        return 0.0, 0.0
    total_power = float(np.sum(power))
    if total_power <= 0:
        return 0.0, 0.0

    if len(freqs) > 1:
        local_step = float(np.median(np.diff(freqs)))
    else:
        local_step = max(freq0 * 0.05, 1e-6)
    local_step = max(local_step, 1e-12)

    peak_half_width = max(local_step * 1.5, freq0 * cfg.snr_peak_bandwidth_ratio)
    background_half_width = max(peak_half_width * 2.0, freq0 * cfg.snr_background_bandwidth_ratio)
    exclusion_half_width = max(peak_half_width * 1.2, freq0 * cfg.snr_background_exclusion_ratio)

    band_mask = np.abs(freqs - freq0) <= peak_half_width
    ring_mask = (np.abs(freqs - freq0) <= background_half_width) & (
        np.abs(freqs - freq0) > exclusion_half_width
    )
    if not np.any(band_mask):
        return 0.0, 0.0

    band_power = float(np.sum(power[band_mask]))
    band_power_ratio = band_power / total_power

    n_band = int(np.sum(band_mask))
    if np.any(ring_mask):
        background_density = float(np.median(power[ring_mask]))
    else:
        background_density = float(np.median(power))
    expected_background = max(background_density * n_band, 1e-18)
    snr = band_power / expected_background
    return band_power_ratio, float(snr)


def _peak_indices(values: np.ndarray) -> list[int]:
    if len(values) <= 2:
        return list(range(len(values)))
    peaks: list[int] = []
    for i in range(1, len(values) - 1):
        if values[i] > values[i - 1] and values[i] >= values[i + 1]:
            peaks.append(i)
    if not peaks:
        peaks = [int(np.argmax(values))]
    return peaks


def discover_candidate_spectrum(spectrum: pd.DataFrame, cfg: AnalysisConfig) -> pd.DataFrame:
    if spectrum.empty:
        return spectrum

    sorted_by_period = spectrum.sort_values("period_days").reset_index(drop=True)
    peak_rows = sorted_by_period.iloc[_peak_indices(sorted_by_period["power"].to_numpy(dtype=np.float64))]
    peak_rows = peak_rows.sort_values("power", ascending=False)

    selected_rows: list[dict[str, Any]] = []
    for row in peak_rows.itertuples(index=False):
        period_days = float(row.period_days)
        too_close = any(
            _period_distance_ratio(period_days, float(existing["period_days"])) < 0.10
            for existing in selected_rows
        )
        if too_close:
            continue
        selected_rows.append(
            {
                "freq_per_day": float(row.freq_per_day),
                "period_days": period_days,
                "power": float(row.power),
                "norm_power": float(row.norm_power),
            }
        )
        if len(selected_rows) >= max(cfg.top_k * 6, cfg.selection_top_k * 12):
            break

    if not selected_rows:
        selected_rows = [
            {
                "freq_per_day": float(row.freq_per_day),
                "period_days": float(row.period_days),
                "power": float(row.power),
                "norm_power": float(row.norm_power),
            }
            for row in spectrum.head(max(cfg.top_k * 3, cfg.selection_top_k * 8)).itertuples(index=False)
        ]
    return pd.DataFrame(selected_rows)


def _window_bounds_by_days(
    signal_len: int,
    step_days: float,
    rolling_windows_days: list[int],
    rolling_step_days: int,
) -> list[tuple[int, int]]:
    bounds: list[tuple[int, int]] = []
    used: set[tuple[int, int]] = set()
    step_points = max(1, int(round(rolling_step_days / max(step_days, 1e-6))))

    for window_days in rolling_windows_days:
        window_points = max(32, int(round(window_days / max(step_days, 1e-6))))
        if window_points > signal_len:
            continue
        starts = list(range(0, signal_len - window_points + 1, step_points))
        if not starts:
            starts = [0]
        if starts[-1] != signal_len - window_points:
            starts.append(signal_len - window_points)
        for start in starts:
            key = (start, window_points)
            if key in used:
                continue
            used.add(key)
            bounds.append(key)

    if not bounds:
        bounds.append((0, signal_len))
    return sorted(bounds)


def _harmonic_fit(
    segment: np.ndarray,
    period_days: float,
    step_days: float,
    include_trend: bool,
) -> tuple[float, float, float, float]:
    if len(segment) < 8:
        return 0.0, 0.0, 0.0, 0.0

    t = np.arange(len(segment), dtype=np.float64) * step_days
    omega = (2.0 * np.pi) / max(period_days, 1e-6)
    features = [np.ones_like(t)]
    if include_trend:
        t_centered = t - float(np.mean(t))
        features.append(t_centered)
    features.extend([np.cos(omega * t), np.sin(omega * t)])
    X = np.column_stack(features)

    beta, *_ = np.linalg.lstsq(X, segment, rcond=None)
    fitted = X @ beta

    a = float(beta[-2])
    b = float(beta[-1])
    amplitude = float(np.sqrt(a * a + b * b))
    phase = float(np.arctan2(-b, a))
    best_lag_days = (phase / (2.0 * np.pi)) * period_days

    residual = segment - fitted
    sst = float(np.sum((segment - np.mean(segment)) ** 2))
    sse = float(np.sum(residual**2))
    if sst <= 0:
        r2 = 0.0
    else:
        r2 = max(0.0, min(1.0, 1.0 - (sse / sst)))
    return amplitude, phase, best_lag_days, r2


def _phase_locking(phases: list[float]) -> float:
    if not phases:
        return 0.0
    vec = np.exp(1j * np.array(phases, dtype=np.float64))
    return float(np.abs(np.mean(vec)))


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    arr = np.array(values, dtype=np.float64)
    return float(np.quantile(arr, q, method="linear"))


def _window_max_snr(signal: np.ndarray, step_days: float, cfg: AnalysisConfig) -> float:
    try:
        spectrum, freqs, power, _ = compute_spectrum(
            signal=signal,
            step_days=step_days,
            min_period_days=cfg.min_period_days,
            max_period_days=cfg.max_period_days,
        )
    except Exception:
        return 0.0
    candidates = discover_candidate_spectrum(spectrum, cfg=cfg)
    if candidates.empty:
        return 0.0
    max_snr = 0.0
    for row in candidates.itertuples(index=False):
        _, snr = _compute_band_metrics(freqs=freqs, power=power, freq0=float(row.freq_per_day), cfg=cfg)
        if snr > max_snr:
            max_snr = snr
    return float(max_snr)


def _phase_randomized_surrogate(signal: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    coeff = np.fft.rfft(signal)
    if len(coeff) <= 2:
        return signal.copy()
    randomized = coeff.copy()
    random_phases = rng.uniform(0.0, 2.0 * np.pi, len(coeff) - 2)
    randomized[1:-1] = np.abs(randomized[1:-1]) * np.exp(1j * random_phases)
    randomized[-1] = randomized[-1].real + 0j
    surrogate = np.fft.irfft(randomized, n=len(signal)).real
    surrogate = surrogate - np.mean(surrogate)
    return surrogate


def estimate_bandmax_p_values(
    signal: np.ndarray,
    step_days: float,
    cycles: list[dict[str, Any]],
    cfg: AnalysisConfig,
) -> list[dict[str, Any]]:
    if not cycles:
        return cycles
    if cfg.surrogate_count <= 0:
        for cycle in cycles:
            cycle["p_value_bandmax"] = 1.0
        return cycles

    rng = np.random.default_rng(cfg.surrogate_seed)
    surrogate_max_scores: list[float] = []
    for _ in range(cfg.surrogate_count):
        surrogate = _phase_randomized_surrogate(signal, rng)
        surrogate_max_scores.append(_window_max_snr(surrogate, step_days=step_days, cfg=cfg))

    surrogate_arr = np.array(surrogate_max_scores, dtype=np.float64)
    for cycle in cycles:
        score = float(cycle.get("snr_global", 0.0))
        if len(surrogate_arr) == 0:
            p_value = 1.0
        else:
            p_value = float(np.mean(surrogate_arr >= score))
        cycle["p_value_bandmax"] = p_value
    return cycles


def _add_rank_scores(cycles: list[dict[str, Any]], cfg: AnalysisConfig) -> None:
    if not cycles:
        return
    amp = np.array([max(1e-12, float(cycle["amp_median"])) for cycle in cycles], dtype=np.float64)
    snr = np.array([max(1e-12, float(cycle["snr_median"])) for cycle in cycles], dtype=np.float64)
    presence = np.array([float(cycle["presence_ratio"]) for cycle in cycles], dtype=np.float64)
    phase_lock = np.array([float(cycle["phase_locking_r"]) for cycle in cycles], dtype=np.float64)

    def zscore(values: np.ndarray) -> np.ndarray:
        mu = float(np.mean(values))
        sigma = float(np.std(values))
        if sigma <= 1e-12:
            return np.zeros_like(values)
        return (values - mu) / sigma

    z_amp = zscore(np.log1p(amp))
    z_snr = zscore(np.log1p(snr))
    z_presence = zscore(presence)
    z_phase = zscore(phase_lock)

    raw = (
        cfg.rank_weight_amp * z_amp
        + cfg.rank_weight_snr * z_snr
        + cfg.rank_weight_presence * z_presence
        + cfg.rank_weight_phase * z_phase
    )
    raw_min = float(np.min(raw))
    raw_max = float(np.max(raw))
    for idx, cycle in enumerate(cycles):
        score = float(raw[idx])
        cycle["rank_score"] = score
        if raw_max > raw_min:
            cycle["rank_score_norm"] = (score - raw_min) / (raw_max - raw_min)
        else:
            cycle["rank_score_norm"] = 0.0


def evaluate_stability(
    signal: np.ndarray,
    signal_dates: pd.DatetimeIndex,
    step_days: float,
    candidate_spectrum: pd.DataFrame,
    full_freqs: np.ndarray,
    full_power: np.ndarray,
    cfg: AnalysisConfig,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    if candidate_spectrum.empty:
        return [], [], []

    bounds = _window_bounds_by_days(
        signal_len=len(signal),
        step_days=step_days,
        rolling_windows_days=cfg.rolling_windows_days,
        rolling_step_days=cfg.rolling_step_days,
    )

    window_mid_dates: list[str] = []
    window_segments: list[np.ndarray] = []
    window_freqs: list[np.ndarray] = []
    window_power: list[np.ndarray] = []
    for start, window_points in bounds:
        segment = signal[start : start + window_points]
        coeff = np.fft.rfft(segment)
        freqs = np.fft.rfftfreq(len(segment), d=step_days)
        power = (np.abs(coeff) ** 2) / (len(segment) * len(segment))
        mask = freqs > 0
        with np.errstate(divide="ignore"):
            periods = np.where(freqs > 0, 1.0 / freqs, np.inf)
        mask &= periods >= cfg.min_period_days
        mask &= periods <= cfg.max_period_days

        window_segments.append(segment)
        window_freqs.append(freqs[mask])
        window_power.append(power[mask])

        mid_idx = min(start + (window_points // 2), len(signal_dates) - 1)
        window_mid_dates.append(signal_dates[mid_idx].date().isoformat())

    candidates: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    for row in candidate_spectrum.itertuples(index=False):
        freq = float(row.freq_per_day)
        period_days = float(row.period_days)

        band_ratios: list[float] = []
        snr_values: list[float] = []
        amplitudes: list[float] = []
        phases: list[float] = []
        lags: list[float] = []
        fit_scores: list[float] = []
        presence_flags: list[int] = []

        for window_idx, ((start, window_points), segment, freqs, power, window_mid_date) in enumerate(
            zip(bounds, window_segments, window_freqs, window_power, window_mid_dates)
        ):
            band_ratio, snr = _compute_band_metrics(freqs=freqs, power=power, freq0=freq, cfg=cfg)
            amplitude, phase, best_lag, fit_score = _harmonic_fit(
                segment=segment,
                period_days=period_days,
                step_days=step_days,
                include_trend=cfg.harmonic_include_trend,
            )

            band_ratios.append(band_ratio)
            snr_values.append(snr)
            amplitudes.append(amplitude)
            phases.append(phase)
            lags.append(best_lag)
            fit_scores.append(fit_score)
            present = int((snr >= cfg.snr_presence_threshold) and (band_ratio >= cfg.min_window_power_ratio))
            presence_flags.append(present)
            end_idx = min(start + window_points - 1, len(signal_dates) - 1)
            window_rows.append(
                {
                    "period_days": period_days,
                    "freq_per_day": freq,
                    "window_idx": int(window_idx),
                    "window_start_idx": int(start),
                    "window_points": int(window_points),
                    "window_start_date": signal_dates[start].date().isoformat(),
                    "window_mid_date": str(window_mid_date),
                    "window_end_date": signal_dates[end_idx].date().isoformat(),
                    "band_power_ratio": float(band_ratio),
                    "snr": float(snr),
                    "amplitude": float(amplitude),
                    "phase": float(phase),
                    "best_lag_days": float(best_lag),
                    "fit_score_phase_free": float(fit_score),
                    "present": int(present),
                }
            )

        presence_ratio = float(np.mean(presence_flags)) if presence_flags else 0.0
        median_window_power_ratio = _quantile(band_ratios, 0.5)
        amp_median = _quantile(amplitudes, 0.5)
        amp_p25 = _quantile(amplitudes, 0.25)
        amp_min = float(min(amplitudes)) if amplitudes else 0.0
        snr_median = _quantile(snr_values, 0.5)
        snr_p25 = _quantile(snr_values, 0.25)
        fit_score_median = _quantile(fit_scores, 0.5)
        best_lag_days_median = _quantile(lags, 0.5)
        lag_iqr = _quantile(lags, 0.75) - _quantile(lags, 0.25)
        phase_locking_r = _phase_locking(phases)
        margin_median = snr_median - cfg.snr_presence_threshold

        _, snr_global = _compute_band_metrics(freqs=full_freqs, power=full_power, freq0=freq, cfg=cfg)
        stability_score = presence_ratio * float(row.norm_power)
        stable = bool(presence_ratio >= cfg.min_presence_ratio)

        candidates.append(
            {
                "freq_per_day": freq,
                "period_days": period_days,
                "power": float(row.power),
                "norm_power": float(row.norm_power),
                "presence_ratio": presence_ratio,
                "median_window_power_ratio": median_window_power_ratio,
                "stability_score": stability_score,
                "stable": stable,
                "window_power_ratios": band_ratios,
                "amp_median": amp_median,
                "amp_p25": amp_p25,
                "amp_min": amp_min,
                "fit_score_phase_free": fit_score_median,
                "snr_median": snr_median,
                "snr_p25": snr_p25,
                "snr_global": snr_global,
                "best_lag_days_median": best_lag_days_median,
                "lag_iqr": lag_iqr,
                "phase_locking_r": phase_locking_r,
                "margin_median": margin_median,
            }
        )

    candidates = estimate_bandmax_p_values(signal=signal, step_days=step_days, cycles=candidates, cfg=cfg)
    _add_rank_scores(candidates, cfg=cfg)

    max_stability_score = max((cycle["stability_score"] for cycle in candidates), default=0.0)
    for cycle in candidates:
        if max_stability_score > 0:
            cycle["stability_score_norm"] = cycle["stability_score"] / max_stability_score
        else:
            cycle["stability_score_norm"] = 0.0

    candidates.sort(
        key=lambda item: (
            item["stable"],
            item.get("rank_score_norm", 0.0),
            item["presence_ratio"],
            item["snr_median"],
        ),
        reverse=True,
    )
    return candidates, window_mid_dates, window_rows


def _period_distance_ratio(a_days: float, b_days: float) -> float:
    return abs(a_days - b_days) / max(a_days, b_days)


def select_cycles_for_output(
    evaluated_cycles: list[dict[str, Any]], cfg: AnalysisConfig
) -> list[dict[str, Any]]:
    if not evaluated_cycles:
        return []

    strict_eligible = [
        cycle
        for cycle in evaluated_cycles
        if cycle["stable"]
        and cycle["presence_ratio"] >= cfg.selection_min_presence_ratio
        and cycle["phase_locking_r"] >= cfg.selection_min_phase_locking_r
        and cycle["amp_median"] >= cfg.selection_min_amp_sigma
        and cycle.get("p_value_bandmax", 1.0) <= cfg.selection_max_p_value_bandmax
    ]
    if strict_eligible:
        eligible = strict_eligible
    else:
        # Fail-open fallback: keep outputs usable even when strict absolute filters are too harsh.
        eligible = [
            cycle
            for cycle in evaluated_cycles
            if cycle["stable"] and cycle["presence_ratio"] >= cfg.selection_min_presence_ratio
        ]
    if not eligible:
        eligible = [cycle for cycle in evaluated_cycles if cycle["stable"]]
    if not eligible:
        return []

    filtered = list(eligible)
    if cfg.selection_min_norm_power_percentile > 0:
        norm_powers = np.array([cycle["norm_power"] for cycle in eligible], dtype=np.float64)
        power_threshold = float(
            np.quantile(norm_powers, cfg.selection_min_norm_power_percentile, method="linear")
        )
        filtered = [cycle for cycle in eligible if cycle["norm_power"] >= power_threshold]
        if not filtered:
            filtered = list(eligible)

    ranked = sorted(
        filtered,
        key=lambda cycle: (
            cycle.get("rank_score_norm", 0.0),
            cycle["presence_ratio"],
            cycle["phase_locking_r"],
            cycle["snr_median"],
        ),
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
    if not selected:
        fallback_ranked = sorted(
            [cycle for cycle in evaluated_cycles if cycle["stable"]],
            key=lambda cycle: (
                cycle.get("rank_score_norm", 0.0),
                cycle["presence_ratio"],
                cycle["snr_median"],
            ),
            reverse=True,
        )
        if fallback_ranked:
            selected.append(fallback_ranked[0])
    return selected


def reconstruct_signal_from_cycles(
    signal_len: int,
    step_days: float,
    full_freqs: np.ndarray,
    full_coeff: np.ndarray,
    selected_cycles: list[dict[str, Any]],
    output_len: int | None = None,
) -> np.ndarray:
    n_out = signal_len if output_len is None else max(1, int(output_len))
    if not selected_cycles:
        return np.zeros(n_out, dtype=np.float64)

    n_idx = np.arange(n_out, dtype=np.float64)
    reconstructed = np.zeros(n_out, dtype=np.float64)
    for cycle in selected_cycles:
        idx = int(np.argmin(np.abs(full_freqs - cycle["freq_per_day"])))
        freq_per_day = float(full_freqs[idx])
        coeff = complex(full_coeff[idx])
        phase = 2.0 * np.pi * freq_per_day * step_days * n_idx
        reconstructed += (2.0 / float(signal_len)) * np.real(coeff * np.exp(1j * phase))
    return reconstructed


def reconstruct_cycle_components(
    signal_len: int,
    step_days: float,
    full_freqs: np.ndarray,
    full_coeff: np.ndarray,
    selected_cycles: list[dict[str, Any]],
    output_len: int | None = None,
) -> list[tuple[str, np.ndarray]]:
    n_out = signal_len if output_len is None else max(1, int(output_len))
    n_idx = np.arange(n_out, dtype=np.float64)
    components: list[tuple[str, np.ndarray]] = []
    for cycle in selected_cycles:
        idx = int(np.argmin(np.abs(full_freqs - cycle["freq_per_day"])))
        freq_per_day = float(full_freqs[idx])
        coeff = complex(full_coeff[idx])
        phase = 2.0 * np.pi * freq_per_day * step_days * n_idx
        component = (2.0 / float(signal_len)) * np.real(coeff * np.exp(1j * phase))
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


def _compute_wavelet_scalogram(
    signal: np.ndarray,
    step_days: float,
    min_period_days: float,
    max_period_days: float,
    period_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    if len(signal) < 16:
        return np.array([], dtype=np.float64), np.zeros((0, len(signal)), dtype=np.float64)

    min_period = max(min_period_days, step_days * 4.0)
    max_period = max(max_period_days, min_period * 1.01)
    periods = np.geomspace(min_period, max_period, num=max(8, int(period_count)), dtype=np.float64)

    w0 = 6.0
    power = np.zeros((len(periods), len(signal)), dtype=np.float64)
    safe_step = max(step_days, 1e-6)
    for idx, period_days in enumerate(periods):
        scale = max((period_days * w0) / (2.0 * np.pi), 1e-6)
        half_width = max(8, int(round((6.0 * scale) / safe_step)))
        t = np.arange(-half_width, half_width + 1, dtype=np.float64) * safe_step
        tau = t / scale
        wavelet = (np.pi ** -0.25) * np.exp(1j * w0 * tau) * np.exp(-0.5 * (tau**2))
        wavelet *= math.sqrt(safe_step / scale)

        full = np.convolve(signal, np.conj(wavelet[::-1]), mode="full")
        start = max(0, (len(full) - len(signal)) // 2)
        coeff = full[start : start + len(signal)]
        if len(coeff) < len(signal):
            coeff = np.pad(coeff, (0, len(signal) - len(coeff)))
        elif len(coeff) > len(signal):
            coeff = coeff[: len(signal)]
        power[idx, :] = np.abs(coeff) ** 2

    row_scale = np.quantile(power, 0.90, axis=1, method="linear")
    row_scale = np.maximum(row_scale, 1e-12)[:, np.newaxis]
    normalized = power / row_scale
    return periods, normalized


def save_plot_wavelet(
    path: Path,
    signal_dates: pd.DatetimeIndex,
    signal: np.ndarray,
    step_days: float,
    cfg: AnalysisConfig,
    title: str,
) -> None:
    periods, power = _compute_wavelet_scalogram(
        signal=signal,
        step_days=step_days,
        min_period_days=cfg.min_period_days,
        max_period_days=cfg.max_period_days,
        period_count=cfg.wavelet_period_count,
    )
    fig, ax = plt.subplots(figsize=(12, 6))
    if power.size == 0:
        ax.text(0.5, 0.5, "Wavelet view unavailable (signal too short)", ha="center", va="center")
        ax.set_axis_off()
    else:
        x = mdates.date2num(pd.to_datetime(signal_dates))
        z = np.log10(np.maximum(power, 1e-12))
        mesh = ax.pcolormesh(x, periods, z, shading="auto", cmap="viridis")
        ax.set_yscale("log")
        ax.set_ylabel("Period (days, log scale)")
        ax.set_xlabel("Date")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.grid(True, alpha=0.12)
        cbar = fig.colorbar(mesh, ax=ax, pad=0.01)
        cbar.set_label("log10 normalized wavelet power")
        fig.autofmt_xdate()
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


def extend_signal_dates(
    signal_dates: pd.DatetimeIndex,
    step_days: float,
    projection_days: int,
) -> tuple[pd.DatetimeIndex, int]:
    if projection_days <= 0 or step_days <= 0:
        return signal_dates, 0
    projection_steps = int(math.ceil(float(projection_days) / float(step_days)))
    if projection_steps <= 0:
        return signal_dates, 0
    start_ts = pd.to_datetime(signal_dates[-1])
    future_dates = [start_ts + pd.to_timedelta(step_days * idx, unit="D") for idx in range(1, projection_steps + 1)]
    extended = pd.DatetimeIndex(list(pd.to_datetime(signal_dates)) + future_dates)
    return extended, projection_steps


def save_plot_price_cycle_overlay(
    path: Path,
    levels: pd.Series,
    signal_dates: pd.DatetimeIndex,
    reconstructed: np.ndarray,
    history_points: int,
    title: str,
) -> None:
    fig, ax_price = plt.subplots(figsize=(12, 6))
    x_signal_all = pd.to_datetime(signal_dates)
    history_points = max(1, min(history_points, len(x_signal_all)))
    x_history = x_signal_all[:history_points]
    price_aligned = levels.reindex(x_history).ffill().bfill()
    cycle_index = np.cumsum(reconstructed)
    cycle_index = _normalize_for_overlay(cycle_index)

    ax_price.plot(x_history, price_aligned.to_numpy(dtype=np.float64), color="#145c9e", lw=1.4)
    ax_price.set_xlabel("Date")
    ax_price.set_ylabel("Price / level", color="#145c9e")
    ax_price.tick_params(axis="y", labelcolor="#145c9e")
    ax_price.grid(True, alpha=0.2)

    ax_cycle = ax_price.twinx()
    ax_cycle.plot(x_history, cycle_index[:history_points], color="#ef6c00", lw=1.3, alpha=0.9)
    if len(x_signal_all) > history_points:
        projection_x = x_signal_all[history_points - 1 :]
        projection_y = cycle_index[history_points - 1 :]
        ax_cycle.plot(projection_x, projection_y, color="#ef6c00", lw=1.3, alpha=0.85, ls="--")
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
        "amp_median",
        "amp_p25",
        "amp_min",
        "fit_score_phase_free",
        "snr_median",
        "snr_p25",
        "snr_global",
        "best_lag_days_median",
        "lag_iqr",
        "presence_ratio",
        "margin_median",
        "phase_locking_r",
        "p_value_bandmax",
        "rank_score",
        "rank_score_norm",
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
    history_points: int,
) -> None:
    columns = ["date", "period_days", "component_value", "is_projection"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()

        if not selected_cycles or not components:
            return

        date_values = [ts.date().isoformat() for ts in pd.to_datetime(signal_dates)]
        for cycle, (_, component) in zip(selected_cycles, components):
            period_days = float(cycle["period_days"])
            for idx, (date_value, component_value) in enumerate(zip(date_values, component)):
                writer.writerow(
                    {
                        "date": date_value,
                        "period_days": period_days,
                        "component_value": float(component_value),
                        "is_projection": 1 if idx >= history_points else 0,
                    }
                )


def write_windows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = [
        "period_days",
        "freq_per_day",
        "window_idx",
        "window_start_idx",
        "window_points",
        "window_start_date",
        "window_mid_date",
        "window_end_date",
        "band_power_ratio",
        "snr",
        "amplitude",
        "phase",
        "best_lag_days",
        "fit_score_phase_free",
        "present",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in columns})


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

    signal_mode = cfg.signal_mode_yahoo if source == "yahoo" else cfg.signal_mode_fred
    signal_dates, signal, transform_name = build_signal(
        levels,
        signal_mode=signal_mode,
        detrend_rolling_days=cfg.detrend_rolling_days,
    )
    if len(signal) < cfg.min_points:
        raise RuntimeError(
            f"Signal too short after transform ({len(signal)} < {cfg.min_points}) for {source}:{series_name}"
        )

    step_days = infer_step_days(signal_dates)
    spectrum, full_freqs, full_power, full_coeff = compute_spectrum(
        signal=signal,
        step_days=step_days,
        min_period_days=cfg.min_period_days,
        max_period_days=cfg.max_period_days,
    )

    candidate_pool = discover_candidate_spectrum(spectrum, cfg=cfg)
    evaluated, window_mid_dates, window_rows = evaluate_stability(
        signal=signal,
        signal_dates=signal_dates,
        step_days=step_days,
        candidate_spectrum=candidate_pool,
        full_freqs=full_freqs,
        full_power=full_power,
        cfg=cfg,
    )

    stable_cycles = [cycle for cycle in evaluated if cycle["stable"]]
    selected_cycles = select_cycles_for_output(evaluated, cfg)

    extended_signal_dates, projection_steps = extend_signal_dates(
        signal_dates=signal_dates,
        step_days=step_days,
        projection_days=cfg.projection_days,
    )
    output_len = len(extended_signal_dates)
    history_points = len(signal_dates)

    reconstructed = reconstruct_signal_from_cycles(
        signal_len=len(signal),
        step_days=step_days,
        full_freqs=full_freqs,
        full_coeff=full_coeff,
        selected_cycles=selected_cycles,
        output_len=output_len,
    )
    # We need cycle component waves for ALL stable cycles, not just selected ones.
    # Otherwise the UI checkboxes for non-selected stable cycles cannot draw anything.
    stable_components = reconstruct_cycle_components(
        signal_len=len(signal),
        step_days=step_days,
        full_freqs=full_freqs,
        full_coeff=full_coeff,
        selected_cycles=stable_cycles,
        output_len=output_len,
    )
    
    # We still need the subset of components for the static PNG plot
    selected_components = reconstruct_cycle_components(
        signal_len=len(signal),
        step_days=step_days,
        full_freqs=full_freqs,
        full_coeff=full_coeff,
        selected_cycles=selected_cycles,
        output_len=history_points,
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
        signal_dates=extended_signal_dates,
        selected_cycles=stable_cycles,
        components=stable_components,
        history_points=history_points,
    )
    if cfg.export_windows_csv:
        write_windows_csv(series_dir / "windows.csv", window_rows)
    save_plot_price(
        series_dir / "price.png",
        levels,
        f"{source}:{series_name} price/level ({cfg.timeframe_days}d)",
    )
    save_plot_price_cycle_overlay(
        series_dir / "price_cycle_overlay.png",
        levels,
        extended_signal_dates,
        reconstructed,
        history_points=history_points,
        title=f"{source}:{series_name} price with composite cycle overlay",
    )
    save_plot_cycle_components(
        series_dir / "cycle_components.png",
        signal_dates,
        selected_components,
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
    if cfg.enable_wavelet_view:
        save_plot_wavelet(
            series_dir / "wavelet.png",
            signal_dates,
            signal,
            step_days,
            cfg=cfg,
            title=f"{source}:{series_name} wavelet activity view",
        )
    save_plot_reconstruction(
        series_dir / "reconstruction.png",
        signal_dates,
        signal,
        reconstructed[:history_points],
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
        "projection_days": cfg.projection_days,
        "projection_points": int(projection_steps),
        "stable_cycle_count": len(stable_cycles),
        "selected_cycle_count": len(selected_cycles),
        "selection_top_k": cfg.selection_top_k,
        "selection_min_presence_ratio": cfg.selection_min_presence_ratio,
        "selection_min_norm_power_percentile": cfg.selection_min_norm_power_percentile,
        "selection_min_period_distance_ratio": cfg.selection_min_period_distance_ratio,
        "selection_min_phase_locking_r": cfg.selection_min_phase_locking_r,
        "selection_max_p_value_bandmax": cfg.selection_max_p_value_bandmax,
        "selection_min_amp_sigma": cfg.selection_min_amp_sigma,
        "snr_presence_threshold": cfg.snr_presence_threshold,
        "export_windows_csv": cfg.export_windows_csv,
        "enable_wavelet_view": cfg.enable_wavelet_view,
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
