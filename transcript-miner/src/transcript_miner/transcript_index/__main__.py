from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .runner import write_analysis_index


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Offline analysis runner: scans transcript outputs and writes analysis artefacts."
        )
    )
    p.add_argument(
        "--input-root",
        action="append",
        required=True,
        help=(
            "Path to an output root to scan. Can be provided multiple times. "
            "Expected structure: output/data/transcripts/by_video_id/*.txt (global) "
            "or <root>/**/1_transcripts/*.txt (legacy)."
        ),
    )
    p.add_argument(
        "--output-dir",
        required=True,
        help="Directory where analysis artefacts are written (global: output/data/indexes/<topic>/current).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    input_roots = [Path(p) for p in args.input_root]
    output_dir = Path(args.output_dir)

    return write_analysis_index(output_dir=output_dir, input_roots=input_roots)


if __name__ == "__main__":
    raise SystemExit(main())
