#!/usr/bin/env python3
"""
Generates a high-quality Markdown report from aggregated JSON data using an LLM.
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src to python path
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from transcript_ai_analysis.llm_report_generator import (  # noqa: E402
    discover_config_for_run,
    find_latest_run_dir,
    generate_reports,
    load_yaml_config,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Generate LLM Report")
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument(
        "--report-lang",
        default="de",
        choices=["de", "en", "both"],
        help="Report language to generate (de|en|both). Default: de.",
    )
    args = parser.parse_args()

    # Determine Run Directory (Hardcoded fallback for now, but could be arg too)
    base_path = Path("output/reports/stocks")  # Default fallback

    # If config is provided, we might want to use its output path to find the run
    config = None
    if args.config:
        config = load_yaml_config(Path(args.config))
        if config:
            output_cfg = config.get("output", {}) if isinstance(config, dict) else {}
            root = output_cfg.get("root_path")
            global_root = output_cfg.get("global") or output_cfg.get("global_root")
            topic = output_cfg.get("topic")
            config_loc = Path(args.config).parent
            if global_root and topic:
                base_path = (config_loc / global_root / "history" / topic).resolve()
            elif root:
                # Resolve root relative to config location
                base_path = (config_loc / root / "3_reports").resolve()

    # Find latest run in the determined base_path
    if not base_path.exists():
        # Try to find base_path by discovery if no config arg
        pass

    latest_run = find_latest_run_dir(base_path)

    if not latest_run:
        logger.error(f"No run directory found in {base_path}")
        # Try discovery if we haven't already
        if not args.config:
            # This part is tricky because we need a base path to find a run to then discover config...
            # Or we iterate all configs to find ANY run?
            # For now, let's stick to the default path if discovery fails or just fail.
            pass
        return

    logger.info(f"Found latest run: {latest_run}")

    # If config was not provided via CLI, discover it from run_dir
    if not config:
        config = discover_config_for_run(latest_run)

    if config:
        logger.info("Loaded configuration for report generation.")
    else:
        logger.warning("No matching configuration found. Using defaults.")

    written = generate_reports(run_dir=latest_run, config=config, report_lang=args.report_lang)
    if not written:
        logger.error("No reports written.")


if __name__ == "__main__":
    main()
