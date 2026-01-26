"""
Hauptmodul für den Transcript Miner.

Dieses Modul ist der Einstiegspunkt für das Mining von YouTube-Transkripten.
Es lädt die Konfiguration, ruft die YouTube API auf, lädt Transkripte herunter
und speichert sie in der definierten Ordnerstruktur.
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Sequence, TYPE_CHECKING, Optional

from pydantic import ValidationError

# NOTE (offline/--help robustness):
# Dieses Modul wird bereits beim `python -m ... --help` importiert.
# Daher müssen Imports, die optionale/fehlende Dependencies triggern können,
# möglichst spät (innerhalb der Funktionen) erfolgen.

if TYPE_CHECKING:
    from common.config import Config
    from common.run_summary import RunStats
    from rich.progress import Progress


def _canonical_config_paths(paths: Sequence[str | Path]) -> list[Path]:
    """Kanonische Config-Order gemäß Spezifikation.

    Normativ: [`docs/config.md`](docs/config.md:78)
    - resolve → dedupe → lexicographic sort
    """

    resolved = [Path(p).resolve() for p in paths]

    # Dedupe by absolute path
    unique = {p for p in resolved}
    return sorted(unique, key=lambda p: str(p))


def _compute_config_set_id(config_paths: Sequence[Path]) -> str:
    """Deterministische ConfigSet-ID gemäß Spezifikation.

    Normativ: [`docs/config.md`](docs/config.md:165)
    """

    names_part = "+".join([p.stem for p in config_paths])

    h = hashlib.sha256()
    for idx, p in enumerate(config_paths):
        if idx:
            h.update(b"\0")
        h.update(p.read_bytes())

    hash_part = h.hexdigest()[:12]
    return f"{names_part}__cs-{hash_part}"


def _multi_run_namespace_root(config_set_id: str) -> Path:
    """Namespace-Run-Root für Multi-Config Runs.

    Policy (normativ; proposed in Implementation): [`docs/config.md`](docs/config.md:175)
    """

    from common.config import PROJECT_ROOT

    return (PROJECT_ROOT / "output" / "_runs" / config_set_id).resolve()


def _effective_output_root_for_collision_check(config: "Config") -> Path:
    """Effective output base dir used for collision checks (multi-run isolation)."""

    if config.output.is_global_layout():
        topic = config.output.get_topic()
        topic_key = topic if topic else "unknown-topic"
        return (config.output.get_global_root() / "_topic" / topic_key).resolve()

    # Note: with `output.root_path` + `use_channel_subfolder=true`, the per-channel
    # subfolder depends on the channel handle. For multi-run isolation we require
    # distinct base roots per config.
    return Path(config.output.get_path(channel_handle=None)).resolve()


def _validate_multi_run_isolation(
    *,
    configs: Sequence["Config"],
    config_paths: Sequence[Path],
) -> tuple[bool, str]:
    """Fail-fast, wenn Outputs/Logs zwischen Configs kollidieren.

    Spec: [`docs/config.md`](docs/config.md:89) + Scope-Anforderung (WP-C2/3).
    """

    if len(configs) != len(config_paths):
        return False, "internal error: configs/config_paths length mismatch"

    seen_output_roots: dict[Path, Path] = {}
    seen_log_files: dict[Path, Path] = {}
    seen_error_log_files: dict[Path, Path] = {}

    for cfg, cfg_path in zip(configs, config_paths, strict=True):
        out_root = _effective_output_root_for_collision_check(cfg)
        log_file = Path(cfg.logging.file).resolve()
        err_log_file = Path(cfg.logging.error_log_file).resolve()

        if out_root in seen_output_roots:
            other = seen_output_roots[out_root]
            return (
                False,
                "multi-run output collision: "
                f"{cfg_path} and {other} resolve to the same output root {out_root}",
            )
        if log_file in seen_log_files:
            other = seen_log_files[log_file]
            return (
                False,
                "multi-run logging.file collision: "
                f"{cfg_path} and {other} resolve to the same log file {log_file}",
            )
        if err_log_file in seen_error_log_files:
            other = seen_error_log_files[err_log_file]
            return (
                False,
                "multi-run logging.error_log_file collision: "
                f"{cfg_path} and {other} resolve to the same error log file {err_log_file}",
            )

        seen_output_roots[out_root] = cfg_path
        seen_log_files[log_file] = cfg_path
        seen_error_log_files[err_log_file] = cfg_path

    return True, ""


def resolve_channel_input_with_client(youtube, channel_input: str):
    """Resolves a channel input (URL, handle, or ID) to a channel ID and name.

    Args:
        youtube: YouTube API client
        channel_input: Channel URL, @handle, or channel ID

    Returns:
        Tuple of (channel_id, channel_name) or None if resolution fails
    """
    logger = logging.getLogger(__name__)

    try:
        from .channel_resolver import ChannelResolver

        resolver = ChannelResolver(youtube)
        channel_info = resolver._resolve_handle(channel_input)

        if not channel_info:
            logger.error(f"Could not resolve channel: {channel_input}")
            return None

        logger.debug(f"Resolved channel info: {channel_info}")
        return (channel_info["id"], channel_info["display_name"])

    except Exception as e:
        logger.exception(f"Error resolving channel {channel_input}: {e}")
        return None


def process_channel(
    youtube,
    channel_input: str,
    config: "Config",
    processed_videos: Dict[str, List[str]],
    progress: Optional["Progress"] = None,
    run_stats: Optional["RunStats"] = None,
) -> bool:
    """
    Process a single channel: resolve, fetch videos, and process each video.

    Returns:
        True if channel processing was successful, False otherwise
    """
    logger = logging.getLogger(__name__)

    try:
        from .channel_resolver import get_videos_for_channel_with_client
        from .video_processor import (
            cleanup_old_outputs,
            load_skipped_videos,
            process_single_video,
            sync_progress_with_filesystem,
        )
        from common.output_migration import migrate_legacy_outputs

        logger.info(f"Resolving channel: {channel_input}")

        # Resolve channel input to channel ID and name
        channel_info = resolve_channel_input_with_client(youtube, channel_input)
        if not channel_info:
            logger.error(f"Could not resolve channel: {channel_input}")
            return False

        channel_id, channel_name = channel_info
        logger.info(f"Successfully resolved channel: {channel_name} (ID: {channel_id})")

        # Perform migration from legacy layout if needed
        if config.output.is_global_layout():
            logger.info("Checking for legacy outputs to migrate...")
            migration_counts = migrate_legacy_outputs(config.output)
            if any(migration_counts.values()):
                logger.info(f"Migrated legacy outputs: {migration_counts}")

        # Get the output directory with channel-specific path
        output_dir = config.output.get_path(channel_handle=channel_input)
        logger.info(f"Output directory for channel {channel_name}: {output_dir}")

        # Path for tracking processed videos (per channel)
        # Index path is now global layout aware (output.data/indexes/<topic>/current).
        index_dir = config.output.get_index_path()
        progress_file = index_dir / "ingest_index.jsonl"
        logger.debug(f"Progress file: {progress_file}")

        # Path for tracking videos that have no transcripts / transcripts disabled.
        # Global layout: output/data/transcripts/skipped.json
        transcripts_dir = config.output.get_transcripts_path(
            channel_handle=channel_input
        )
        skipped_file = config.output.get_transcripts_skipped_path()

        # Retention/Cleanup policy (deterministic): delete outputs older than N days.
        retention_days = getattr(config.output, "retention_days", 30)
        cleanup_old_outputs(
            transcripts_dir,
            retention_days=retention_days,
        )

        # Intelligent bidirectional sync between progress.json and filesystem
        logger.info("Performing progress-filesystem synchronization...")
        processed_videos = sync_progress_with_filesystem(
            transcripts_dir,
            progress_file,
            channel_id,
            config,
            channel_handle=channel_input,
        )

        skipped_videos = load_skipped_videos(skipped_file)

        # Video selection: either lookback_days (with per-channel limit) or num_videos.
        filter_num_videos = getattr(config.youtube, "num_videos", 10)
        lookback_days = getattr(config.youtube, "lookback_days", None)
        max_videos_per_channel = getattr(config.youtube, "max_videos_per_channel", None)

        published_after = None
        max_results = filter_num_videos
        if lookback_days:
            published_after = datetime.utcnow() - timedelta(days=lookback_days)
            if max_videos_per_channel is not None:
                max_results = max_videos_per_channel
            else:
                logger.info(
                    "lookback_days set; using num_videos=%s as per-channel limit for %s",
                    filter_num_videos,
                    channel_name,
                )
            logger.info(
                "Using lookback_days=%s (published_after=%s) and max_videos_per_channel=%s for channel %s",
                lookback_days,
                published_after.isoformat(),
                max_results,
                channel_name,
            )
            logger.info(
                "Fetching videos from last %s days (limit %s) for channel %s",
                lookback_days,
                max_results,
                channel_name,
            )
        else:
            logger.info(
                "Using num_videos=%s for channel %s",
                filter_num_videos,
                channel_name,
            )
            logger.info(
                "Fetching the latest %s videos for channel %s",
                filter_num_videos,
                channel_name,
            )

        # Get the latest videos from the channel
        exclude_live_events = getattr(config.youtube, "exclude_live_events", True)
        videos = get_videos_for_channel_with_client(
            youtube,
            channel_id,
            num_videos=max_results,
            published_after=published_after,
            exclude_live_events=exclude_live_events,
        )

        if not videos:
            logger.info(f"No videos found for channel {channel_name}")
            return True

        logger.info(f"Found {len(videos)} videos for channel {channel_name}")
        if run_stats is not None:
            run_stats.inc("videos_considered", len(videos))

        # Add progress task for videos if progress bar is available
        video_task_id = None
        if progress:
            video_task_id = progress.add_task(
                f"[cyan]Processing videos for {channel_name}...", total=len(videos)
            )

        # Process each video
        for video in videos:
            success = process_single_video(
                video,
                channel_id,
                channel_name,
                config,
                transcripts_dir,
                processed_videos,
                progress_file,
                skipped_videos,
                skipped_file,
                channel_handle=channel_input,
                run_stats=run_stats,
            )
            if not success:
                logger.warning(
                    f"Failed to process video: {video.get('title', 'Unknown')}"
                )

            if progress and video_task_id is not None:
                progress.advance(video_task_id)

        if progress and video_task_id is not None:
            progress.remove_task(video_task_id)

        logger.info(f"Finished processing channel: {channel_name}")
        return True

    except Exception as e:
        logger.exception(f"Error processing channel {channel_input}: {e}")

        # Import locally to keep module import (and thus `--help`) robust.
        from common.telemetry import record_pipeline_error

        record_pipeline_error(error_type="channel_processing", where="process_channel")
        return False


def run_miner(config: "Config", *, run_stats: Optional["RunStats"] = None) -> int:
    """Main function to run the transcript mining process with Resume/Stop support."""
    logger = logging.getLogger("transcript_miner.run_miner")

    from common.telemetry import pipeline_duration_histogram
    from .youtube_client import get_youtube_client

    start_time = time.time()

    # Load previously processed videos (global state)
    # For the new structure, we'll load this from each channel's directory
    processed_videos = {}

    # Get YouTube API key from config or environment
    api_key = config.api.youtube_api_key
    if not api_key:
        logger.debug("API key not found in config, checking environment variables...")
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            logger.error("YouTube API key not found in config or environment variables")
            return 1
        logger.debug("Using API key from environment variable")
    else:
        logger.debug("Using API key from config")

    # Build YouTube client
    logger.info("Initializing YouTube client...")
    youtube = get_youtube_client(api_key)
    if not youtube:
        logger.error("Failed to build YouTube client")
        return 1
    logger.info("YouTube client initialized successfully")

    # Process each channel from config
    logger.info(f"Starting to process {len(config.youtube.channels)} channels")

    success_count = 0

    try:
        from rich.progress import (
            Progress,
            SpinnerColumn,
            TextColumn,
            BarColumn,
            TaskProgressColumn,
            TimeRemainingColumn,
        )

        rich_available = True
    except ImportError:
        rich_available = False

    if rich_available:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            transient=True,
        ) as progress:
            channel_task = progress.add_task(
                "[green]Processing channels...", total=len(config.youtube.channels)
            )
            for channel_input in config.youtube.channels:
                if process_channel(
                    youtube,
                    channel_input,
                    config,
                    processed_videos,
                    progress=progress,
                    run_stats=run_stats,
                ):
                    success_count += 1
                progress.advance(channel_task)
    else:
        for channel_input in config.youtube.channels:
            if process_channel(
                youtube, channel_input, config, processed_videos, run_stats=run_stats
            ):
                success_count += 1

    # Record pipeline duration
    duration = time.time() - start_time
    pipeline_duration_histogram.record(duration)
    logger.info(f"Mining process completed in {duration:.1f} seconds")
    logger.info(
        f"Successfully processed {success_count}/{len(config.youtube.channels)} channels"
    )

    return 0 if success_count > 0 else 1


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="YouTube Transcript Miner")
    parser.add_argument(
        "--config",
        dest="config_paths",
        action="append",
        default=None,
        help=(
            "Path to a configuration file (repeatable). "
            "If provided, the positional config_path must not be used."
        ),
    )
    parser.add_argument(
        "config_path",
        type=str,
        help="Path to the configuration file",
        nargs="?",
        default=None,
    )
    parser.add_argument(
        "--api-key", type=str, help="YouTube API Key (overrides any other source)"
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip analysis index generation (transcripts.jsonl/audit.jsonl/manifest.json).",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help=(
            "Skip LLM analysis (summaries). "
            "Global layout: output/data/summaries/by_video_id; legacy layout: 2_summaries."
        ),
    )
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help=(
            "Skip aggregation + report generation. "
            "Global layout: output/history/<topic>/... and output/reports/<topic>/...; "
            "legacy layout: 3_reports."
        ),
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=["mine", "index", "llm", "report"],
        default=None,
        help=(
            "Run only the given step (repeatable): mine|index|llm|report. "
            "If provided, defaults and --skip-* flags are ignored."
        ),
    )
    parser.add_argument(
        "--report-lang",
        default="de",
        choices=["de", "en", "both"],
        help="Report language to generate when report.llm is enabled (de|en|both). Default: de.",
    )
    return parser.parse_args()


def _resolve_pipeline_steps(args: argparse.Namespace) -> tuple[bool, bool, bool, bool]:
    """Return (do_mine, do_index, do_llm, do_report)."""

    only = list(getattr(args, "only", None) or [])
    if only:
        s = set(only)
        return ("mine" in s, "index" in s, "llm" in s, "report" in s)

    do_mine = True
    do_index = not bool(getattr(args, "skip_index", False))
    do_llm = not bool(getattr(args, "skip_llm", False))
    do_report = not bool(getattr(args, "skip_report", False))
    return do_mine, do_index, do_llm, do_report


def _maybe_write_timeout_report(
    *,
    logger: logging.Logger,
    config: "Config",
    config_path: Path | None,
) -> None:
    if not getattr(config.output, "write_timeout_report", False):
        return

    try:
        from common import PROJECT_ROOT
        from common.timeout_report import write_timeout_report

        log_path = Path(config.logging.file)
        if not log_path.is_absolute():
            log_path = (PROJECT_ROOT / log_path).resolve()

        out_path = config.output.get_timeout_report_path()
        write_timeout_report(
            config_dict=config.model_dump(),
            config_path=config_path,
            log_path=log_path,
            out_path=out_path,
        )
        logger.info("Timeout report written to %s", out_path)
    except Exception as exc:
        logger.warning("Timeout report generation failed: %s", exc)


def _run_analysis_pipeline_for_config(
    *,
    logger: logging.Logger,
    config: "Config",
    config_path: Path | None,
    do_index: bool,
    do_llm: bool,
    do_report: bool,
    report_lang: str,
    run_stats: Optional["RunStats"],
) -> int:
    """Run post-mining analysis steps (index → llm → report) for a single config."""

    profile_root = Path(config.output.get_path()).resolve()
    index_dir = config.output.get_index_path()

    llm_enabled = bool(getattr(getattr(config, "analysis", None), "llm", None) and getattr(config.analysis.llm, "enabled", False))  # type: ignore[attr-defined]
    if do_llm and not llm_enabled:
        logger.info("LLM analysis disabled in config (analysis.llm.enabled=false); skipping.")
        do_llm = False

    if do_report and not llm_enabled:
        # Aggregation depends on existing summaries.
        # - Global layout: output/data/summaries/by_video_id
        # - Legacy layout: profile_root/2_summaries
        # If LLM is disabled, we skip report generation instead of failing with missing inputs.
        logger.info("Report generation requires summaries; analysis.llm.enabled=false → skipping report.")
        do_report = False

    if do_index:
        from transcript_miner.transcript_index.runner import write_analysis_index

        logger.info("Building analysis index: %s", index_dir)
        rc = write_analysis_index(output_dir=index_dir, input_roots=[profile_root])
        if rc != 0:
            logger.error("Analysis index failed (exit=%s).", rc)
            return 1

    if do_llm:
        if config_path is None:
            logger.warning("No config file path available; skipping LLM analysis.")
            do_llm = False

        transcripts_jsonl = index_dir / "transcripts.jsonl"
        if not transcripts_jsonl.exists():
            logger.error("Missing transcript index: %s", transcripts_jsonl)
            return 1

        if do_llm:
            from transcript_ai_analysis.llm_runner import run_llm_analysis

            logger.info("Running LLM analysis (summaries): output_root=%s", profile_root)
            rc = run_llm_analysis(
                config_path=config_path,
                profile_root=profile_root,
                index_dir=index_dir,
                run_stats=run_stats,
            )
            if rc != 0:
                logger.error("LLM analysis failed (exit=%s).", rc)
                return 1

    if do_report:
        transcripts_jsonl = index_dir / "transcripts.jsonl"
        if not transcripts_jsonl.exists():
            logger.error("Missing transcript index: %s", transcripts_jsonl)
            return 1

        from transcript_ai_analysis.aggregation_runner import run_aggregation

        logger.info(
            "Running aggregation/report: profile_root=%s report_lang=%s",
            profile_root,
            report_lang,
        )
        rc = run_aggregation(
            profile_root=profile_root,
            index_dir=index_dir,
            report_lang=report_lang,
            output=config.output,
            config_path=config_path,
        )
        if rc != 0:
            logger.error("Aggregation/report failed (exit=%s).", rc)
            return 1

    _maybe_write_timeout_report(
        logger=logger,
        config=config,
        config_path=config_path,
    )

    return 0


def _validate_config_or_exit(
    logger: logging.Logger, config: "Config"
) -> tuple[bool, str, str | None]:
    """Domain-Validation für Configs; returns (ok, message, hint)."""

    channels = list(getattr(config.youtube, "channels", []) or [])
    if not channels:
        return (
            False,
            "configuration must define at least one YouTube channel in 'youtube.channels'.",
            "Hint: set e.g.\n  youtube:\n    channels: ['@CouchInvestor']",
        )

    invalid_channels = [
        (idx, ch)
        for idx, ch in enumerate(channels)
        if (not isinstance(ch, str)) or (not ch.strip())
    ]
    if invalid_channels:
        idx, bad = invalid_channels[0]
        return (
            False,
            f"youtube.channels contains an invalid entry at index {idx}: {bad!r}",
            "Hint: entries must be non-empty strings (e.g. '@handle' or a channel URL).",
        )

    # Trivial, common mistake: empty output paths ("" / whitespace).
    output_path = getattr(config.output, "path", None)
    if isinstance(output_path, str) and not output_path.strip():
        return (
            False,
            "output.path must be a non-empty string path.",
            "Hint: set e.g. output.path: ./output",
        )

    root_path = getattr(config.output, "root_path", None)
    if isinstance(root_path, str) and root_path is not None and not root_path.strip():
        return (
            False,
            "output.root_path must be a non-empty string path when set.",
            "Hint: either omit output.root_path or set e.g. output.root_path: ./output",
        )

    global_root = getattr(config.output, "global_root", None)
    if isinstance(global_root, str) and global_root is not None and not global_root.strip():
        return (
            False,
            "output.global must be a non-empty string path when set.",
            "Hint: set e.g. output.global: ./output",
        )

    if config.output.is_global_layout() and not config.output.get_topic():
        return (
            False,
            "output.topic must be set when using output.global layout.",
            "Hint: set e.g.\n  output:\n    global: ../output\n    topic: investing",
        )

    # Output policy enforcement (deterministic, collision-free multi-channel runs).
    if len(channels) > 1 and not (
        config.output.is_global_layout()
        or (
            getattr(config.output, "root_path", None)
            and getattr(config.output, "use_channel_subfolder", False)
        )
    ):
        logger.error(
            "Configuration error: multi-channel runs require output.global/topic or output.root_path + output.use_channel_subfolder=true"
        )
        return (
            False,
            "multi-channel configs require a deterministic output directory.",
            (
                "Either set:\n"
                "  output:\n    global: ../output\n    topic: <name>\n"
                "or set:\n  output:\n    root_path: ../output/<topic>\n    use_channel_subfolder: true\n"
                "Reason: otherwise all channels would share the same output folder "
                "(progress/transcripts collision)."
            ),
        )

    return True, "", None


def _run_with_parsed_args(args: argparse.Namespace) -> int:
    """Run CLI logic; returns process exit code instead of calling sys.exit()."""

    from .logging_setup import setup_basic_logging, setup_logging

    # Setup basic logging after argument parsing to keep `--help` as side-effect free as possible.
    logger = setup_basic_logging()
    logger.info("Basic logging configured. Starting Transcript Miner...")

    # Load .env/.config.env (best-effort) only after argparse handled `--help`.
    try:
        from dotenv import load_dotenv, find_dotenv

        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path)
        config_env_path = find_dotenv(filename=".config.env", usecwd=True)
        if config_env_path:
            load_dotenv(config_env_path, override=False)
    except Exception:
        # Keep CLI robust in minimal/offline environments.
        pass

    # If an API key is provided via CLI, expose it via environment so downstream
    # code paths (run_miner etc.) can reuse the same mechanism.
    if args.api_key:
        os.environ["YOUTUBE_API_KEY"] = args.api_key
        logger.info("Using API key from command line argument")

    from common.config import load_config

    def _print_config_error(message: str, *, hint: str | None = None) -> int:
        logger.error(f"Configuration error: {message}")
        print(f"Error: {message}", file=sys.stderr)
        if hint:
            print(hint, file=sys.stderr)
        return 1

    # --- Multi-config CLI resolution (default: multi-run) ---
    if args.config_paths and args.config_path:
        return _print_config_error(
            "Do not mix --config with positional config_path.",
            hint="Hint: use either '--config <path>' (repeatable) OR a single positional config_path.",
        )

    if args.config_paths:
        canonical_paths = _canonical_config_paths(args.config_paths)
        if not canonical_paths:
            return _print_config_error(
                "--config was provided but no valid paths were parsed."
            )
    elif args.config_path:
        canonical_paths = [Path(args.config_path).resolve()]
    else:
        canonical_paths = []

    # Multi-config mode: default multi-run
    is_multi_run = len(canonical_paths) > 1

    # Namespace run root (proposed in implementation) - deterministic + fail-fast on overwrite.
    if is_multi_run:
        try:
            config_set_id = _compute_config_set_id(canonical_paths)
        except Exception as e:
            return _print_config_error(
                f"failed to compute config_set_id: {e}",
                hint="Hint: ensure all config files exist and are readable.",
            )

        run_root = _multi_run_namespace_root(config_set_id)
        run_root.parent.mkdir(parents=True, exist_ok=True)
        if run_root.exists():
            return _print_config_error(
                f"multi-config run-root already exists: {run_root}",
                hint=(
                    "Hint: delete the folder to re-run, or implement an explicit reuse/overwrite mechanism (TODO)."
                ),
            )
        run_root.mkdir(parents=True, exist_ok=False)
        logger.info("Multi-config: config_set_id=%s", config_set_id)
        logger.info("Multi-config: namespace run_root=%s", run_root)

    # Load configurations (one per config file), validate, then fail-fast on collisions.
    loaded_configs: list[Config] = []
    loaded_paths: list[Path] = []

    if canonical_paths:
        for config_path in canonical_paths:
            try:
                logger.info("Attempting to load configuration from: %s", config_path)
                config = load_config(str(config_path))

                # Apply CLI override (highest priority) also into config object.
                if args.api_key:
                    config.api.youtube_api_key = args.api_key

                ok, msg, hint = _validate_config_or_exit(logger, config)
                if not ok:
                    return _print_config_error(msg, hint=hint)

                loaded_configs.append(config)
                loaded_paths.append(config_path)
            except FileNotFoundError as e:
                logger.error("Configuration file not found: %s", e)
                print(f"Error: Configuration file not found: {e}")
                return 1
            except ValidationError as e:
                logger.error("Configuration validation failed.")
                print("--- Configuration Validation Errors ---")
                for error in e.errors():
                    loc = ".".join(map(str, error["loc"]))
                    msg = error["msg"]
                    inp = error.get("input", "N/A")
                    error_details = f"Field: {loc}, Error: {msg}, Input: {inp!r} (type: {type(inp).__name__})"
                    print(error_details)
                    logger.error(error_details)
                print("---------------------------------------")
                return 1
            except Exception as e:
                logger.exception(
                    "An unexpected error occurred during configuration loading: %s", e
                )
                print(f"An unexpected error occurred during config loading: {e}")
                return 1
    else:
        # Backward-compatible behavior: if no config provided, load defaults (existing behavior).
        try:
            logger.info("Attempting to load configuration from: using default values")
            config = load_config(None)
            ok, msg, hint = _validate_config_or_exit(logger, config)
            if not ok:
                return _print_config_error(msg, hint=hint)
            loaded_configs = [config]
            loaded_paths = []
        except Exception as e:
            logger.exception(
                "An unexpected error occurred during configuration loading: %s", e
            )
            print(f"An unexpected error occurred during config loading: {e}")
            return 1

    if is_multi_run:
        ok, msg = _validate_multi_run_isolation(
            configs=loaded_configs, config_paths=loaded_paths
        )
        if not ok:
            return _print_config_error(msg)

    do_mine, do_index, do_llm, do_report = _resolve_pipeline_steps(args)

    # Run miner(s) sequentially
    exit_code = 0
    for cfg_idx, config in enumerate(loaded_configs):
        cfg_path = loaded_paths[cfg_idx] if cfg_idx < len(loaded_paths) else None
        run_started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        run_stats = None
        try:
            from common.run_summary import RunStats

            run_stats = RunStats()
        except Exception:
            run_stats = None

        # Setup proper logging based on loaded config (per run)
        logger.info("Reconfiguring logging based on loaded config...")
        setup_logging(config)
        logger.info("Logging configured according to config file.")

        if do_mine:
            logger.info(
                "Starting mining... (run=%s/%s)",
                cfg_idx + 1,
                len(loaded_configs),
            )
            try:
                result_code = run_miner(config, run_stats=run_stats)
                logger.info("Mining finished with exit code: %s", result_code)
                if result_code != 0:
                    exit_code = 1
            except Exception as e:
                logger.exception(
                    "An unhandled error occurred during the miner process: %s", e
                )
                print(f"An unexpected error occurred during the miner process: {e}")
                return 1

        # Default: run full analysis pipeline unless explicitly skipped/limited.
        pipeline_rc = _run_analysis_pipeline_for_config(
            logger=logger,
            config=config,
            config_path=cfg_path,
            do_index=do_index,
            do_llm=do_llm,
            do_report=do_report,
            report_lang=str(getattr(args, "report_lang", "de")),
            run_stats=run_stats,
        )
        if pipeline_rc != 0:
            exit_code = 1

        if run_stats is not None:
            try:
                from common.run_summary import write_run_summary_md

                reports_dir = Path(config.output.get_reports_path()).resolve()
                run_summary_path = reports_dir / "run_summary.md"
                run_finished_at = datetime.now(timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                )
                write_run_summary_md(
                    out_path=run_summary_path,
                    stats=run_stats,
                    run_started_at=run_started_at,
                    run_finished_at=run_finished_at,
                    config_path=cfg_path,
                    channel_count=len(config.youtube.channels),
                )
                logger.info("Run summary written to %s", run_summary_path)
            except Exception as exc:
                logger.warning("Run summary generation failed: %s", exc)

    return exit_code


def main() -> None:
    """Main function to run the transcript mining process."""
    # Parse command line arguments *before* any env/config work.
    # Rationale: `--help` must work offline without requiring env vars or optional deps.
    args = parse_arguments()
    sys.exit(_run_with_parsed_args(args))


if __name__ == "__main__":
    main()
