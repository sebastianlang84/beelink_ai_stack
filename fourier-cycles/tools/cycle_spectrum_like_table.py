#!/usr/bin/env python3
"""Build a cycle table similar to third-party spectrum UIs for quick comparisons.

Columns:
- Len  : rounded period in days
- Amp  : scaled amplitude (amp_median * amp_scale)
- Strg : snr_median
- Stab : stability_score_norm

The script reads one `cycles.csv` and the matching `summary.json` to mark selected cycles.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Row:
    period_days: float
    amp_median: float
    snr_median: float
    stability_score_norm: float
    presence_ratio: float
    phase_locking_r: float
    selected: bool

    @property
    def len_days(self) -> int:
        return int(round(self.period_days))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        default="fourier-cycles/output/latest",
        help="Run directory path (default: fourier-cycles/output/latest)",
    )
    parser.add_argument(
        "--series-dir",
        default="yahoo-spy",
        help="Series subdirectory inside run dir, for example: yahoo-spy",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=12,
        help="Top rows by Stab to print (default: 12)",
    )
    parser.add_argument(
        "--amp-scale",
        type=float,
        default=100.0,
        help="Scale factor for Amp column (default: 100.0)",
    )
    parser.add_argument(
        "--export-csv",
        default="",
        help="Optional output CSV path for the transformed table",
    )
    return parser.parse_args()


def load_selected_periods(series_summary_path: Path) -> set[float]:
    if not series_summary_path.exists():
        return set()
    data = json.loads(series_summary_path.read_text(encoding="utf-8"))
    selected = data.get("selected_cycles", [])
    return {float(item.get("period_days")) for item in selected}


def read_rows(cycles_csv_path: Path, selected_periods: set[float]) -> list[Row]:
    rows: list[Row] = []
    raw_scores: list[float] = []

    def pick_float(item: dict[str, str], keys: list[str], default: float = 0.0) -> float:
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return float(value)
        return default

    with cycles_csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        has_stab_norm = "stability_score_norm" in fieldnames
        for item in reader:
            period_days = float(item["period_days"])
            selected = any(abs(period_days - value) <= 1e-6 for value in selected_periods)
            amp_median = pick_float(item, ["amp_median", "norm_power", "power"], default=0.0)
            snr_median = pick_float(
                item,
                ["snr_median", "median_window_power_ratio", "norm_power", "power"],
                default=0.0,
            )
            phase_locking_r = pick_float(item, ["phase_locking_r"], default=math.nan)
            stability_score_norm = pick_float(
                item,
                ["stability_score_norm"],
                default=math.nan,
            )
            raw_score = pick_float(item, ["stability_score", "norm_power", "power"], default=0.0)
            raw_scores.append(raw_score)
            rows.append(
                Row(
                    period_days=period_days,
                    amp_median=amp_median,
                    snr_median=snr_median,
                    stability_score_norm=stability_score_norm,
                    presence_ratio=pick_float(item, ["presence_ratio"], default=0.0),
                    phase_locking_r=phase_locking_r,
                    selected=selected,
                )
            )

    if not has_stab_norm and rows:
        max_score = max(raw_scores) if raw_scores else 0.0
        max_score = max_score if max_score > 0 else 1.0
        normalized_rows: list[Row] = []
        for row, score in zip(rows, raw_scores):
            normalized_rows.append(
                Row(
                    period_days=row.period_days,
                    amp_median=row.amp_median,
                    snr_median=row.snr_median,
                    stability_score_norm=score / max_score,
                    presence_ratio=row.presence_ratio,
                    phase_locking_r=row.phase_locking_r,
                    selected=row.selected,
                )
            )
        rows = normalized_rows
    return rows


def print_table(rows: Iterable[Row], amp_scale: float, top: int) -> None:
    sorted_rows = sorted(
        rows,
        key=lambda row: (row.stability_score_norm, row.snr_median, row.amp_median),
        reverse=True,
    )[:top]

    print("Len\tAmp\tStrg\tStab\tSel\tPresence\tPhaseR")
    for row in sorted_rows:
        print(
            f"{row.len_days}\t"
            f"{row.amp_median * amp_scale:.2f}\t"
            f"{row.snr_median:.2f}\t"
            f"{row.stability_score_norm:.2f}\t"
            f"{'x' if row.selected else ''}\t"
            f"{row.presence_ratio:.2f}\t"
            f"{row.phase_locking_r:.2f}"
        )

    selected_lens = [str(row.len_days) for row in sorted_rows if row.selected]
    if selected_lens:
        print("")
        print("Selected Len:", ", ".join(selected_lens))


def export_csv(path: Path, rows: Iterable[Row], amp_scale: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Len", "Amp", "Strg", "Stab", "Sel", "Presence", "PhaseR"])
            for row in sorted(
                rows,
                key=lambda item: (
                    item.stability_score_norm,
                    item.snr_median,
                    item.amp_median,
                ),
                reverse=True,
            ):
                writer.writerow(
                    [
                        row.len_days,
                        f"{row.amp_median * amp_scale:.4f}",
                        f"{row.snr_median:.4f}",
                        f"{row.stability_score_norm:.4f}",
                        "x" if row.selected else "",
                        f"{row.presence_ratio:.4f}",
                        f"{row.phase_locking_r:.4f}",
                    ]
                )
    except PermissionError as exc:
        raise SystemExit(
            f"cannot write export file (permission denied): {path} "
            f"(try a user-writable path like /tmp/...)"
        ) from exc


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    series_dir = run_dir / args.series_dir
    cycles_csv_path = series_dir / "cycles.csv"
    summary_json_path = series_dir / "summary.json"

    if not cycles_csv_path.exists():
        raise SystemExit(f"cycles.csv not found: {cycles_csv_path}")

    selected_periods = load_selected_periods(summary_json_path)
    rows = read_rows(cycles_csv_path, selected_periods)
    if not rows:
        raise SystemExit(f"no rows in cycles.csv: {cycles_csv_path}")

    print_table(rows, amp_scale=args.amp_scale, top=args.top)

    if args.export_csv:
        export_csv(Path(args.export_csv).expanduser(), rows, amp_scale=args.amp_scale)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
