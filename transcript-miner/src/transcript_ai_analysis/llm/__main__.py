from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common.config import load_config
from transcript_ai_analysis.llm_runner import run_llm_analysis


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "LLM analysis runner: reads transcript index and writes LLM artefacts under the configured output layout."
        )
    )
    p.add_argument(
        "--config",
        required=True,
        help="YAML config file (provides analysis.llm prompts/model and optional api.openrouter_api_key).",
    )
    p.add_argument(
        "--profile-root",
        required=True,
        help=(
            "Legacy profile root directory (e.g. output/stocks). "
            "For global layout this is only used for audit labels."
        ),
    )
    p.add_argument(
        "--index-dir",
        default=None,
        help=(
            "Directory containing transcript index artefacts (manifest.json, transcripts.jsonl, audit.jsonl). "
            "Default: output.data/indexes/<topic>/current (from config)."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    profile_root = Path(args.profile_root)
    cfg = load_config(Path(args.config))
    index_dir = Path(args.index_dir) if args.index_dir is not None else cfg.output.get_index_path()

    return run_llm_analysis(
        config_path=Path(args.config),
        profile_root=profile_root,
        index_dir=index_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
