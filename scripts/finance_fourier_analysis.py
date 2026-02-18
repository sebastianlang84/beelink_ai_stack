#!/usr/bin/env python3
"""Fetch FRED/Yahoo time series and run a Fourier spectrum analysis."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import statistics
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TimePoint:
    date: dt.date
    value: float


@dataclass(frozen=True)
class SpectrumBin:
    k: int
    frequency_per_observation: float
    frequency_per_day: float
    period_observations: float
    period_days: float
    amplitude: float
    power: float


def _http_get(url: str, timeout_seconds: int) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ai-stack-finance-fourier/0.1",
            "Accept": "application/json,text/csv,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        return resp.read().decode("utf-8")


def fetch_yahoo_series(
    symbol: str,
    range_value: str,
    interval: str,
    timeout_seconds: int,
) -> tuple[list[TimePoint], str]:
    symbol_encoded = urllib.parse.quote(symbol)
    query = urllib.parse.urlencode(
        {
            "range": range_value,
            "interval": interval,
            "includePrePost": "false",
            "events": "div,splits",
        }
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol_encoded}?{query}"
    payload = _http_get(url, timeout_seconds=timeout_seconds)
    data = json.loads(payload)

    results = ((data.get("chart") or {}).get("result")) or []
    if not results:
        error_info = ((data.get("chart") or {}).get("error")) or {}
        raise RuntimeError(f"Yahoo response has no result: {error_info!r}")

    series = results[0]
    timestamps = series.get("timestamp") or []
    quote = (((series.get("indicators") or {}).get("quote")) or [{}])[0]
    closes = quote.get("close") or []
    if not timestamps or not closes:
        raise RuntimeError("Yahoo response has no timestamp/close data")

    points: list[TimePoint] = []
    for ts, value in zip(timestamps, closes):
        if value is None:
            continue
        try:
            close_value = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(close_value):
            continue
        timestamp = int(ts)
        date_value = dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc).date()
        points.append(TimePoint(date=date_value, value=close_value))

    if not points:
        raise RuntimeError("Yahoo parsing produced no valid datapoints")
    return points, url


def fetch_fred_series(series_id: str, timeout_seconds: int) -> tuple[list[TimePoint], str]:
    query = urllib.parse.urlencode({"id": series_id})
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?{query}"
    payload = _http_get(url, timeout_seconds=timeout_seconds)
    reader = csv.DictReader(payload.splitlines())
    if not reader.fieldnames:
        raise RuntimeError("FRED CSV has no header")

    date_column = "DATE" if "DATE" in reader.fieldnames else "observation_date"
    value_column = series_id if series_id in reader.fieldnames else reader.fieldnames[-1]
    points: list[TimePoint] = []
    for row in reader:
        raw_date = (row.get(date_column) or "").strip()
        raw_value = (row.get(value_column) or "").strip()
        if not raw_date or not raw_value or raw_value == ".":
            continue
        try:
            date_value = dt.date.fromisoformat(raw_date)
            numeric_value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric_value):
            continue
        points.append(TimePoint(date=date_value, value=numeric_value))

    if not points:
        raise RuntimeError("FRED parsing produced no valid datapoints")
    return points, url


def parse_iso_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date '{value}', expected YYYY-MM-DD") from exc


def filter_points_by_date(
    points: list[TimePoint], start_date: dt.date | None, end_date: dt.date | None
) -> list[TimePoint]:
    out: list[TimePoint] = []
    for point in points:
        if start_date and point.date < start_date:
            continue
        if end_date and point.date > end_date:
            continue
        out.append(point)
    return out


def infer_step_days(points: list[TimePoint]) -> float:
    day_steps: list[int] = []
    for prev, curr in zip(points, points[1:]):
        delta = (curr.date - prev.date).days
        if delta > 0:
            day_steps.append(delta)
    if not day_steps:
        return 1.0
    return float(statistics.median(day_steps))


def build_signal(points: list[TimePoint], transform: str) -> tuple[list[dt.date], list[float]]:
    dates: list[dt.date] = []
    values: list[float] = []
    if transform == "raw":
        for point in points:
            dates.append(point.date)
            values.append(point.value)
        return dates, values

    for prev, curr in zip(points, points[1:]):
        if prev.value == 0:
            continue
        simple_return = (curr.value / prev.value) - 1.0
        if transform == "returns":
            values.append(simple_return)
            dates.append(curr.date)
            continue
        if simple_return <= -1.0:
            continue
        values.append(math.log1p(simple_return))
        dates.append(curr.date)
    return dates, values


def apply_preprocessing(values: list[float], demean: bool, window: str) -> list[float]:
    out = list(values)
    if demean and out:
        mean_value = sum(out) / len(out)
        out = [v - mean_value for v in out]

    if window == "hann" and len(out) > 1:
        n = len(out)
        out = [
            value * (0.5 - 0.5 * math.cos((2.0 * math.pi * i) / (n - 1)))
            for i, value in enumerate(out)
        ]
    return out


def compute_spectrum(signal: list[float], step_days: float) -> list[SpectrumBin]:
    n = len(signal)
    max_k = n // 2
    bins: list[SpectrumBin] = []

    for k in range(1, max_k + 1):
        re = 0.0
        im = 0.0
        for idx, value in enumerate(signal):
            angle = (2.0 * math.pi * k * idx) / n
            re += value * math.cos(angle)
            im -= value * math.sin(angle)

        amplitude = math.hypot(re, im) / n
        power = (re * re + im * im) / (n * n)
        frequency_per_observation = k / n
        frequency_per_day = frequency_per_observation / step_days if step_days > 0 else 0.0
        period_observations = n / k
        period_days = period_observations * step_days
        bins.append(
            SpectrumBin(
                k=k,
                frequency_per_observation=frequency_per_observation,
                frequency_per_day=frequency_per_day,
                period_observations=period_observations,
                period_days=period_days,
                amplitude=amplitude,
                power=power,
            )
        )
    return bins


def safe_slug(value: str) -> str:
    chars = []
    for ch in value:
        chars.append(ch.lower() if ch.isalnum() else "-")
    slug = "".join(chars).strip("-")
    return slug or "series"


def write_series_csv(path: Path, points: list[TimePoint]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "value"])
        for point in points:
            writer.writerow([point.date.isoformat(), f"{point.value:.12g}"])


def write_signal_csv(path: Path, dates: list[dt.date], signal: list[float]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "date", "signal"])
        for idx, (date_value, value) in enumerate(zip(dates, signal)):
            writer.writerow([idx, date_value.isoformat(), f"{value:.12g}"])


def write_spectrum_csv(path: Path, spectrum: list[SpectrumBin]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "k",
                "frequency_per_observation",
                "frequency_per_day",
                "period_observations",
                "period_days",
                "amplitude",
                "power",
            ]
        )
        for entry in spectrum:
            writer.writerow(
                [
                    entry.k,
                    f"{entry.frequency_per_observation:.12g}",
                    f"{entry.frequency_per_day:.12g}",
                    f"{entry.period_observations:.12g}",
                    f"{entry.period_days:.12g}",
                    f"{entry.amplitude:.12g}",
                    f"{entry.power:.12g}",
                ]
            )


def write_report_md(
    path: Path,
    *,
    source: str,
    series_name: str,
    fetch_url: str,
    transform: str,
    window: str,
    step_days: float,
    total_points: int,
    used_points: int,
    top_bins: list[SpectrumBin],
) -> None:
    lines = []
    lines.append("# Finance Fourier Analysis Report")
    lines.append("")
    lines.append(f"- Source: `{source}`")
    lines.append(f"- Series: `{series_name}`")
    lines.append(f"- Fetch URL: `{fetch_url}`")
    lines.append(f"- Transform: `{transform}`")
    lines.append(f"- Window: `{window}`")
    lines.append(f"- Median step (days): `{step_days:.3f}`")
    lines.append(f"- Raw points: `{total_points}`")
    lines.append(f"- Signal points used: `{used_points}`")
    lines.append("")
    lines.append("## Top cycles by power")
    lines.append("")
    lines.append("| rank | k | period_obs | period_days | frequency/day | power |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for rank, entry in enumerate(top_bins, start=1):
        lines.append(
            "| "
            f"{rank} | {entry.k} | {entry.period_observations:.3f} | {entry.period_days:.3f} | "
            f"{entry.frequency_per_day:.6g} | {entry.power:.6g} |"
        )
    lines.append("")
    lines.append("Note: this is a basic DFT spectrum for exploratory cycle detection, not a forecasting model.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["yahoo", "fred"], required=True)
    parser.add_argument("--symbol", default="SPY", help="Yahoo ticker symbol (for --source yahoo)")
    parser.add_argument(
        "--series-id", default="DGS10", help="FRED series id (for --source fred), e.g. CPIAUCSL"
    )
    parser.add_argument("--yahoo-range", default="5y", help="Yahoo chart range, e.g. 1y,5y,10y,max")
    parser.add_argument("--yahoo-interval", default="1d", help="Yahoo chart interval, e.g. 1d,1wk")
    parser.add_argument("--start-date", type=parse_iso_date, default=None)
    parser.add_argument("--end-date", type=parse_iso_date, default=None)
    parser.add_argument("--max-points", type=int, default=1024)
    parser.add_argument("--min-points", type=int, default=128)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--transform",
        choices=["raw", "returns", "log_returns"],
        default="log_returns",
    )
    parser.add_argument("--window", choices=["none", "hann"], default="hann")
    parser.add_argument("--no-demean", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--output-dir", default="output/finance-fourier")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.source == "yahoo":
        points, fetch_url = fetch_yahoo_series(
            symbol=args.symbol,
            range_value=args.yahoo_range,
            interval=args.yahoo_interval,
            timeout_seconds=args.timeout_seconds,
        )
        series_name = args.symbol
    else:
        points, fetch_url = fetch_fred_series(
            series_id=args.series_id, timeout_seconds=args.timeout_seconds
        )
        series_name = args.series_id

    points = sorted(points, key=lambda p: p.date)
    points = filter_points_by_date(points, start_date=args.start_date, end_date=args.end_date)
    if not points:
        raise RuntimeError("No points after date filtering")

    if args.max_points > 0 and len(points) > args.max_points:
        points = points[-args.max_points :]

    step_days = infer_step_days(points)
    dates, signal = build_signal(points, transform=args.transform)
    signal = apply_preprocessing(signal, demean=not args.no_demean, window=args.window)
    if len(signal) < args.min_points:
        raise RuntimeError(
            f"Signal too short for analysis ({len(signal)} < {args.min_points}). "
            "Adjust --max-points/--min-points or date range."
        )

    spectrum = compute_spectrum(signal, step_days=step_days)
    if not spectrum:
        raise RuntimeError("Spectrum is empty")

    top_bins = sorted(spectrum, key=lambda x: x.power, reverse=True)[: args.top_k]

    now_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{now_utc}-{args.source}-{safe_slug(series_name)}"
    run_dir = Path(args.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    write_series_csv(run_dir / "series.csv", points)
    write_signal_csv(run_dir / "signal.csv", dates, signal)
    write_spectrum_csv(run_dir / "spectrum.csv", spectrum)
    write_report_md(
        run_dir / "report.md",
        source=args.source,
        series_name=series_name,
        fetch_url=fetch_url,
        transform=args.transform,
        window=args.window,
        step_days=step_days,
        total_points=len(points),
        used_points=len(signal),
        top_bins=top_bins,
    )

    print(f"run_dir={run_dir}")
    print(f"series={series_name} source={args.source} points={len(points)} signal_points={len(signal)}")
    for rank, entry in enumerate(top_bins, start=1):
        print(
            f"rank={rank} k={entry.k} period_obs={entry.period_observations:.3f} "
            f"period_days={entry.period_days:.3f} power={entry.power:.6g}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
