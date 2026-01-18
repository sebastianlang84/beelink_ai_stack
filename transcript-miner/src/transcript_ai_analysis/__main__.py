from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .aggregation_runner import run_aggregation


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Aggregation analysis runner: reads transcript index and summaries to write aggregated reports."
        )
    )
    p.add_argument(
        "--profile-root",
        required=True,
        help=(
            "Legacy profile root directory (e.g. output/stocks). "
            "For global layout, reports are written under output/history/<topic>/."
        ),
    )
    p.add_argument(
        "--index-dir",
        default=None,
        help=(
            "Directory containing transcript index artefacts (manifest.json, transcripts.jsonl, audit.jsonl). "
            "Default: profile_root/3_reports/index (legacy). For global layout pass output/data/indexes/<topic>/current."
        ),
    )
    p.add_argument(
        "--mapping-json",
        default=None,
        help=(
            "Optional JSON mapping file for canonicalization (static_map). "
            "If omitted, canonicalization falls back to heuristics."
        ),
    )
    p.add_argument(
        "--stoplist-json",
        default=None,
        help=(
            "Optional JSON list of symbols to block heuristic resolution (false positives)."
        ),
    )
    p.add_argument(
        "--report-lang",
        default="de",
        choices=["de", "en", "both"],
        help="Report language to generate when report.llm is enabled (de|en|both). Default: de.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    profile_root = Path(args.profile_root)
    index_dir = (
        Path(args.index_dir)
        if args.index_dir is not None
        else (profile_root / "3_reports" / "index")
    )
    mapping_json = Path(args.mapping_json) if args.mapping_json else None
    stoplist_json = Path(args.stoplist_json) if args.stoplist_json else None

    return run_aggregation(
        profile_root=profile_root,
        index_dir=index_dir,
        mapping_json=mapping_json,
        stoplist_json=stoplist_json,
        report_lang=str(args.report_lang),
    )


if __name__ == "__main__":
    raise SystemExit(main())
