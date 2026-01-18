"""
Utility-Funktionen für das YouTube Transcript Miner Projekt.

Dieses Modul enthält allgemeine Hilfsfunktionen, die von der Mining-Pipeline
und nachgelagerten Analysen verwendet werden.
"""

import logging
import os
import random
import re
import json
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Any, Optional, Callable, Iterable
import time

# --- Structured JSON Logging for LLM Requests ---
_LLM_JSON_LOG_ENV = "ENABLE_LLM_JSON_LOG"
_LLM_JSON_LOG_PATH = Path("logs/llm_requests.json")
_llm_json_logger: Optional[logging.Logger] = None


def _llm_json_log_env_enabled() -> bool:
    return os.getenv(_LLM_JSON_LOG_ENV, "false").lower() == "true"


def _llm_json_log_enabled(log_json: Optional[bool]) -> bool:
    env_enabled = _llm_json_log_env_enabled()
    if log_json is None:
        return env_enabled
    return bool(log_json) or env_enabled


def _get_llm_json_logger() -> logging.Logger:
    global _llm_json_logger
    if _llm_json_logger is not None:
        return _llm_json_logger

    json_logger = logging.getLogger("llm_requests")
    if not json_logger.handlers:
        _LLM_JSON_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(_LLM_JSON_LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        json_logger.addHandler(handler)
    json_logger.setLevel(logging.INFO)
    _llm_json_logger = json_logger
    return json_logger

# --- OpenAI robust error handling utility ---
DEFAULT_OPENAI_MAX_RETRIES = 5  # Maximale Anzahl automatischer Retries für OpenAI-API
DEFAULT_OPENAI_BACKOFF_BASE = 2.0  # Basis für exponentielles Backoff (Sekunden)
DEFAULT_OPENAI_BACKOFF_CAP_S = 60.0  # Upper bound for backoff sleep (seconds)
DEFAULT_OPENAI_BACKOFF_JITTER_S = 1.0  # Max jitter added to backoff sleep (seconds)
DEFAULT_OPENAI_RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)


def _get_http_status(error: BaseException) -> Optional[int]:
    for attr in ("status_code", "http_status"):
        value = getattr(error, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(error, "response", None)
    if response is not None:
        for attr in ("status_code", "status"):
            value = getattr(response, attr, None)
            if isinstance(value, int):
                return value
    return None


def _get_retry_after_seconds(error: BaseException) -> Optional[float]:
    headers = getattr(error, "headers", None)
    response = getattr(error, "response", None)
    if headers is None and response is not None:
        headers = getattr(response, "headers", None)
    if not headers:
        return None
    retry_after = None
    if isinstance(headers, dict):
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
    else:
        retry_after = getattr(headers, "get", lambda *_: None)("Retry-After")
        if retry_after is None:
            retry_after = getattr(headers, "get", lambda *_: None)("retry-after")
    if retry_after is None:
        return None
    try:
        return max(0.0, float(retry_after))
    except (TypeError, ValueError):
        try:
            parsed = parsedate_to_datetime(str(retry_after))
        except (TypeError, ValueError, OverflowError, IndexError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())


def call_openai_with_retry(
    api_func: Callable,
    *args,
    max_retries: int = DEFAULT_OPENAI_MAX_RETRIES,
    backoff_base: float = DEFAULT_OPENAI_BACKOFF_BASE,
    backoff_cap_s: float = DEFAULT_OPENAI_BACKOFF_CAP_S,
    jitter_s: float = DEFAULT_OPENAI_BACKOFF_JITTER_S,
    retryable_status_codes: Optional[Iterable[int]] = None,
    log_json: Optional[bool] = None,
    **kwargs,
) -> Any:
    """
    Robust wrapper for OpenAI API calls with automatic retry, exponential backoff, and logging.
    Usage: call_openai_with_retry(openai.ChatCompletion.create, model=..., messages=...)
    max_retries (int): Number of retry attempts after the initial call
        (total attempts = max_retries + 1).
    backoff_base (float): Exponential backoff base in seconds (default: DEFAULT_OPENAI_BACKOFF_BASE)
    backoff_cap_s (float): Upper bound for backoff sleep (seconds).
    jitter_s (float): Max jitter added to backoff sleep (seconds).
    retryable_status_codes (Iterable[int] | None): HTTP status codes that are retryable.
    log_json (bool | None): When true, writes JSON logs to logs/llm_requests.json; when None,
    uses ENABLE_LLM_JSON_LOG (default: false).
    """
    try:
        import openai
    except ImportError:
        logging.error("openai package not installed. Cannot call LLM API.")
        raise

    # OpenAI Python SDK v1+ exposes exception types at the top-level (e.g. openai.RateLimitError)
    # and no longer under `openai.error.*`.
    retryable_exc: tuple[type[BaseException], ...]
    _retryable: list[type[BaseException]] = []
    for _name in [
        "RateLimitError",
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "APIStatusError",
        "APIError",
    ]:
        _cls = getattr(openai, _name, None)
        if isinstance(_cls, type) and issubclass(_cls, BaseException):
            _retryable.append(_cls)
    retryable_exc = tuple(_retryable) or (getattr(openai, "OpenAIError", Exception),)
    max_attempts = max(1, max_retries + 1)
    retryable_status = set(
        retryable_status_codes or DEFAULT_OPENAI_RETRYABLE_STATUS_CODES
    )
    log_json_enabled = _llm_json_log_enabled(log_json)
    json_logger = _get_llm_json_logger() if log_json_enabled else None
    for attempt in range(1, max_attempts + 1):
        try:
            start_time = time.time()
            response = api_func(*args, **kwargs)
            latency_ms = (time.time() - start_time) * 1000
            # Extract usage
            try:
                usage = getattr(response, "usage", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_tokens", None)
                    completion_tokens = getattr(usage, "completion_tokens", None)
                    total_tokens = getattr(usage, "total_tokens", None)
                else:
                    prompt_tokens = completion_tokens = total_tokens = None

                # Log request details to JSON file
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "model": kwargs.get("model", "unknown"),
                    "success": True,
                    "latency_ms": round(latency_ms, 2),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "retry_count": attempt - 1,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                }
                if json_logger:
                    json_logger.info(json.dumps(log_entry))

                # Update Prometheus metrics if telemetry module is available
                try:
                    from common.telemetry import record_llm_prompt_tokens

                    if prompt_tokens:
                        record_llm_prompt_tokens(int(prompt_tokens))
                except (ImportError, AttributeError):
                    pass  # Telemetry module not available or counter not defined

            except Exception as e:
                logging.warning(f"Failed to log OpenAI API usage: {e}")

            return response

        except retryable_exc as e:
            status_code = _get_http_status(e)
            retry_after_s = _get_retry_after_seconds(e)
            retry_count = attempt - 1

            if status_code is not None and status_code not in retryable_status:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "model": kwargs.get("model", "unknown"),
                    "success": False,
                    "error_type": e.__class__.__name__,
                    "error_message": str(e),
                    "retry_count": retry_count,
                    "status_code": status_code,
                    "retry_after_s": retry_after_s,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "retryable": False,
                }
                if json_logger:
                    json_logger.info(json.dumps(log_entry))
                logging.error(
                    f"OpenAI API error (non-retryable status {status_code}): {e}"
                )
                raise

            if attempt >= max_attempts:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "model": kwargs.get("model", "unknown"),
                    "success": False,
                    "error_type": e.__class__.__name__,
                    "error_message": str(e),
                    "retry_count": retry_count,
                    "status_code": status_code,
                    "retry_after_s": retry_after_s,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "retryable": False,
                }
                if json_logger:
                    json_logger.info(json.dumps(log_entry))
                logging.error(
                    f"OpenAI API error after {max_attempts} attempts: {e}"
                )
                raise

            cap_s = max(0.0, backoff_cap_s)
            retry_index = attempt - 1
            if retry_after_s is not None:
                wait_time = max(0.0, retry_after_s)
                if cap_s > 0:
                    wait_time = min(cap_s, wait_time)
            else:
                base_delay = backoff_base**retry_index
                if cap_s > 0:
                    base_delay = min(cap_s, base_delay)
                jitter = random.uniform(0.0, max(0.0, jitter_s))
                wait_time = base_delay + jitter

            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "model": kwargs.get("model", "unknown"),
                "success": False,
                "error_type": e.__class__.__name__,
                "error_message": str(e),
                "retry_count": retry_count,
                "status_code": status_code,
                "retry_after_s": retry_after_s,
                "wait_time": wait_time,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "retryable": True,
            }
            if json_logger:
                json_logger.info(json.dumps(log_entry))

            logging.warning(
                f"OpenAI API error: {e}. Retrying in {wait_time:.1f}s "
                f"(attempt {attempt + 1}/{max_attempts})..."
            )
            time.sleep(wait_time)
        except Exception as e:
            # Log unexpected errors but don't retry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "model": kwargs.get("model", "unknown"),
                "success": False,
                "error_type": e.__class__.__name__,
                "error_message": str(e),
                "retry_count": attempt - 1,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "fatal": True,
            }
            if json_logger:
                json_logger.info(json.dumps(log_entry))
            logging.error(f"Unexpected error calling OpenAI API: {e}")
            raise


def generate_filename_base(
    published_date_str: str, channel_name: str, video_id: str
) -> str:
    """
    Generates the base filename string (without extension or type).

    Args:
        published_date_str: ISO format date string (YYYY-MM-DD)
        channel_name: Channel name (will be sanitized)
        video_id: YouTube video ID

    Returns:
        A string in the format "YYYY-MM-DD_channel-name_VIDEO-ID"
    """
    # Sanitize channel name for filename
    sanitized_channel = re.sub(r"[^\w\-]", "_", channel_name)
    sanitized_channel = re.sub(
        r"_+", "_", sanitized_channel
    )  # Replace multiple underscores with one
    sanitized_channel = sanitized_channel.strip(
        "_"
    )  # Remove leading/trailing underscores

    # Format: YYYY-MM-DD_channel-name_VIDEO-ID
    return f"{published_date_str}_{sanitized_channel}_{video_id}"


def calculate_token_count(text: str, model: Optional[str] = None) -> int:
    """
    Calculates the token count using tiktoken (optional).

    Args:
        text: The text to count tokens for
        model: Optional model name passed to tiktoken for encoding selection

    Returns:
        Approximate token count
    """
    try:
        import tiktoken

        encoding = None
        if model:
            try:
                encoding = tiktoken.encoding_for_model(model)
            except Exception:
                encoding = None
        if encoding is None:
            return len(text) // 4
        return len(encoding.encode(text))
    except ImportError:
        # Fallback: rough approximation (4 chars per token)
        return len(text) // 4


# --- Hinweis: Für OpenAI-API-Aufrufe immer call_openai_with_retry verwenden! ---

# --- File Saving Utilities ---


def get_latest_transcript_date_for_channel(
    channel_name: str, transcripts_dir: Path
) -> Optional[datetime]:
    """
    Findet das neueste gespeicherte Transkript-Metadatum (published_date) für einen Channel im transcripts-Ordner.
    Args:
        channel_name (str): Name des YouTube-Kanals (wie in Metadaten gespeichert)
        transcripts_dir (Path): Pfad zum transcripts-Ordner
    Returns:
        Optional[datetime]: Das neueste Veröffentlichungsdatum (published_date) als datetime, oder None wenn nicht gefunden.
    """
    if not transcripts_dir.exists():
        return None

    latest_date = None
    sanitized_channel = re.sub(r"[^\w\-]", "_", channel_name)
    sanitized_channel = re.sub(r"_+", "_", sanitized_channel)
    sanitized_channel = sanitized_channel.strip("_")

    # Suche nach Metadaten-Dateien, die zum Kanal gehören
    for meta_file in transcripts_dir.glob(f"*_{sanitized_channel}_*_meta.json"):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                if "published_at" in metadata:
                    pub_date = datetime.fromisoformat(
                        metadata["published_at"].replace("Z", "+00:00")
                    )
                    if latest_date is None or pub_date > latest_date:
                        latest_date = pub_date
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logging.warning(f"Error reading metadata from {meta_file}: {e}")

    return latest_date


def save_transcript(transcript: str, file_path: Path) -> bool:
    """Saves the transcript text to a file atomically."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(transcript)
        temp_path.replace(file_path)
        return True
    except Exception as e:
        logging.error(f"Error saving transcript to {file_path}: {e}")
        return False


def save_metadata(metadata: Dict[str, Any], file_path: Path) -> bool:
    """Saves the metadata dictionary to a JSON file atomically."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        temp_path.replace(file_path)
        return True
    except Exception as e:
        logging.error(f"Error saving metadata to {file_path}: {e}")
        return False
