import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .config import Config


class ErrorHistoryHandler(logging.Handler):
    def __init__(self, path: Path, level: int = logging.ERROR) -> None:
        super().__init__(level=level)
        self._path = path

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload: Dict[str, Any] = {
                "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if record.exc_info:
                exc_type = record.exc_info[0].__name__ if record.exc_info[0] else None
                payload["error_type"] = exc_type
                payload["error_message"] = logging.Formatter().formatException(
                    record.exc_info
                )
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception:
            # Avoid recursive logging on handler failures.
            pass


def append_error_history(config: Config, entry: Dict[str, Any]) -> None:
    logger = logging.getLogger(__name__)
    try:
        path = config.output.get_error_history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "topic": config.output.get_topic() if config.output.is_global_layout() else None,
            **entry,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception as exc:
        logger.warning("Failed to write error history: %s", exc)


def attach_error_history_handler(logger: logging.Logger, config: Config) -> Optional[ErrorHistoryHandler]:
    try:
        path = config.output.get_error_history_path()
        handler = ErrorHistoryHandler(path=path, level=logging.ERROR)
        logger.addHandler(handler)
        logger.info("Error history enabled: %s", path)
        return handler
    except Exception as exc:
        logger.warning("Failed to attach error history handler: %s", exc)
        return None
