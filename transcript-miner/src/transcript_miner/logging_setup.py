"""
Logging configuration for the YouTube Transcript Miner.
"""

import logging
import logging.handlers
import sys
from pathlib import Path

try:
    from rich.logging import RichHandler

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from common.config import Config, PROJECT_ROOT


def setup_logging(config: Config) -> logging.Logger:
    """
    Configure logging based on Config.

    Args:
        config: Configuration object

    Returns:
        Configured logger instance
    """
    # Get log level from config
    log_level_str = config.logging.level
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Create logger
    logger = logging.getLogger()
    # Set root logger to the configured level (e.g. DEBUG)
    # Handlers will filter further if needed.
    logger.setLevel(log_level)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create formatter for file logs (RichHandler has its own format)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Add console handler
    if RICH_AVAILABLE:
        # Use RichHandler for beautiful console output
        # We cap the console output at WARNING to keep the terminal clean.
        # The Rich Progress Bar provides the user feedback.
        # Detailed logs are always available in the log file.
        console_level = logging.WARNING

        console_handler = RichHandler(
            rich_tracebacks=True,
            markup=True,
            show_time=True,
            show_path=False,  # Hide path to keep it clean
            level=console_level,
        )
        console_handler.setLevel(console_level)
    else:
        # Fallback to standard StreamHandler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)

    logger.addHandler(console_handler)

    # Ensure logs directory exists
    log_path = Path(PROJECT_ROOT) / "logs"
    log_path.mkdir(parents=True, exist_ok=True)

    # Setup main log file
    _setup_main_log_file(logger, config, formatter, log_path, log_level)

    # Setup error log file
    _setup_error_log_file(logger, config, formatter)

    # Cleanup old logs if rotation is enabled
    if config.logging.rotation_enabled:
        cleanup_old_logs(logger, config)

    logger.info(f"Logging initialized with level: {log_level_str}")
    if RICH_AVAILABLE and log_level < logging.INFO:
        logger.info(
            "Console output limited to INFO (check log file for full DEBUG details)"
        )

    return logger


def _setup_main_log_file(
    logger: logging.Logger,
    config: Config,
    formatter: logging.Formatter,
    log_path: Path,
    log_level: int,
) -> None:
    """Setup the main log file handler."""
    try:
        # Work with Path objects
        if hasattr(config.logging, "file") and config.logging.file:
            # Convert string to Path object if needed
            if isinstance(config.logging.file, str):
                log_filepath = Path(config.logging.file)
            else:
                log_filepath = config.logging.file

            # Ensure directory exists
            log_filepath.parent.mkdir(parents=True, exist_ok=True)

            # Convert to string for logging module
            log_filename = str(log_filepath)
        else:
            # Default logfile in logs directory
            log_filename = str(log_path / "miner.log")

        # Create file handler
        if config.logging.rotation_enabled:
            file_handler = logging.handlers.TimedRotatingFileHandler(
                log_filename,
                when=config.logging.rotation_when,
                interval=config.logging.rotation_interval,
                backupCount=config.logging.rotation_backup_count,
                encoding="utf-8",
            )
            logger.info(
                f"Log rotation enabled: when={config.logging.rotation_when}, "
                f"interval={config.logging.rotation_interval}, "
                f"backupCount={config.logging.rotation_backup_count}"
            )
        else:
            file_handler = logging.FileHandler(log_filename, encoding="utf-8")

        file_handler.setFormatter(formatter)
        file_handler.setLevel(
            log_level
        )  # File gets the full configured level (e.g. DEBUG)
        logger.addHandler(file_handler)
        logger.info(f"Logging to file: {log_filename}")

    except Exception as e:
        logger.error(f"Error setting up log handler: {e}")
        # Fallback on error
        fallback_log = str(log_path / "fallback.log")
        file_handler = logging.FileHandler(fallback_log, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        logger.addHandler(file_handler)
        logger.info(f"Using fallback log file: {fallback_log}")


def _setup_error_log_file(
    logger: logging.Logger, config: Config, formatter: logging.Formatter
) -> None:
    """Setup the error log file handler."""
    try:
        if hasattr(config.logging, "error_log_file") and config.logging.error_log_file:
            # Convert string to Path object if needed
            if isinstance(config.logging.error_log_file, str):
                error_log_filepath = Path(config.logging.error_log_file)
            else:
                error_log_filepath = config.logging.error_log_file

            # Ensure directory exists
            error_log_filepath.parent.mkdir(parents=True, exist_ok=True)

            # Convert to string for logging module
            error_log_filename = str(error_log_filepath)

            # Create error handler
            if config.logging.rotation_enabled:
                error_handler = logging.handlers.TimedRotatingFileHandler(
                    error_log_filename,
                    when=config.logging.rotation_when,
                    interval=config.logging.rotation_interval,
                    backupCount=config.logging.rotation_backup_count,
                    encoding="utf-8",
                )
            else:
                error_handler = logging.FileHandler(
                    error_log_filename, encoding="utf-8"
                )

            error_handler.setLevel(logging.WARNING)  # Only WARNING and higher
            error_handler.setFormatter(formatter)
            logger.addHandler(error_handler)
            logger.info(f"Logging errors to file: {error_log_filename}")
    except Exception as e:
        logger.error(f"Error setting up error log handler: {e}")
        # Error not fatal, main logger still works


def cleanup_old_logs(logger: logging.Logger, config: Config) -> None:
    """
    Remove orphaned or too old log files that are no longer needed.
    This is a simple cleanup that complements the built-in rotation.
    """
    try:
        import time

        # We look for files in the same directory as the main log file
        log_file = Path(config.logging.get_log_file_path())
        log_dir = log_file.parent

        if not log_dir.exists():
            return

        # Simple heuristic: files starting with the same name but having a suffix
        base_name = log_file.name
        now = time.time()
        when = str(config.logging.rotation_when).upper()
        interval = max(int(config.logging.rotation_interval), 1)
        backup_count = max(int(config.logging.rotation_backup_count), 1)

        unit_seconds = 24 * 60 * 60
        if when == "S":
            unit_seconds = 1
        elif when == "M":
            unit_seconds = 60
        elif when == "H":
            unit_seconds = 60 * 60
        elif when in {"D", "MIDNIGHT"}:
            unit_seconds = 24 * 60 * 60
        elif when.startswith("W"):
            unit_seconds = 7 * 24 * 60 * 60

        max_age_seconds = unit_seconds * interval * backup_count
        max_age_days = max_age_seconds / (24 * 60 * 60)

        logger.debug(
            "Cleaning up logs older than %.2f days in %s (when=%s interval=%s backup_count=%s)",
            max_age_days,
            log_dir,
            when,
            interval,
            backup_count,
        )

        for file in log_dir.glob(f"{base_name}*"):
            if file.is_file() and file != log_file:
                file_age = now - file.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        file.unlink()
                        logger.info(f"Deleted old log file: {file}")
                    except Exception as e:
                        logger.warning(f"Could not delete old log file {file}: {e}")

    except Exception as e:
        logger.error(f"Error during log cleanup: {e}")


def setup_basic_logging() -> logging.Logger:
    """
    Setup basic logging for early initialization.

    Returns:
        Basic logger instance
    """
    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.setLevel(logging.INFO)  # Default to INFO for basic logging

    if RICH_AVAILABLE:
        console_handler = RichHandler(
            rich_tracebacks=True, markup=True, show_time=True, show_path=False
        )
    else:
        # Create console handler with a higher log level
        console_handler = logging.StreamHandler(sys.stdout)
        # Create formatter and add it to the handler
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

    console_handler.setLevel(logging.INFO)  # Basic logging is INFO

    # Add the handler to the root logger
    root_logger.addHandler(console_handler)

    # Enable debug logging for our modules if needed, but console handler filters it
    logging.getLogger("transcript_miner").setLevel(logging.DEBUG)
    logging.getLogger("googleapiclient").setLevel(
        logging.INFO
    )  # Reduce API client logs

    return logging.getLogger(__name__)
