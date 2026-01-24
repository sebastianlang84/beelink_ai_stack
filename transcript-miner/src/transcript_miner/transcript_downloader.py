"""
Funktionen zum Herunterladen und Verarbeiten von YouTube-Transkripten.

Dieses Modul stellt Funktionen zum Herunterladen von Transkripten von YouTube-Videos
und zum Durchsuchen dieser Transkripte nach Schlüsselwörtern bereit.
"""

import logging
import re
import time
import random
import threading
from typing import List, Tuple, Optional, Any
from xml.etree.ElementTree import ParseError

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeRequestFailed,
)

# youtube-transcript-api 1.x removed `TooManyRequests` in favor of `RequestBlocked`.
try:  # pragma: no cover
    from youtube_transcript_api._errors import TooManyRequests
except ImportError:  # pragma: no cover
    try:
        from youtube_transcript_api._errors import RequestBlocked as TooManyRequests
    except ImportError:
        TooManyRequests = YouTubeRequestFailed  # type: ignore[misc,assignment]
from .transcript_models import TranscriptDownloadResult, TranscriptStatus

DEFAULT_LANGUAGES = [
    "en",
    "de",
    "es",
    "fr",
]  # Standard-Sprachen für YouTube-Transkripte

# Globaler Limiter-State für Thread-Sicherheit (Vorbereitung auf Parallelisierung)
_limiter_lock = threading.Lock()
_last_request_time = 0.0


def _apply_rate_limit(min_delay: float, jitter: float):
    """Wendet ein globales Rate-Limit mit Jitter an."""
    global _last_request_time

    with _limiter_lock:
        now = time.time()
        # Berechne tatsächlichen Delay mit Jitter
        actual_delay = min_delay + (random.random() * jitter)

        elapsed = now - _last_request_time
        wait_time = actual_delay - elapsed

        if wait_time > 0:
            logging.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            time.sleep(wait_time)

        _last_request_time = time.time()


def _get_proxy_config(
    proxy_settings: Optional[Any], video_id: Optional[str] = None
) -> Optional[Any]:
    """Erstellt Proxy-Dict für youtube-transcript-api (requests-style)."""
    if not proxy_settings or proxy_settings.mode == "none":
        return None

    if proxy_settings.mode == "webshare":
        # Previously implemented via youtube_transcript_api.proxies.* which is not available
        # in youtube-transcript-api 0.6.x. If we ever need webshare again, we can implement
        # URL generation explicitly here.
        logging.warning("Proxy mode 'webshare' is not supported in this build (mode ignored).")
        return None

    if proxy_settings.mode == "generic":
        proxies = {}
        if proxy_settings.http_url:
            proxies["http"] = proxy_settings.http_url
        if proxy_settings.https_url:
            proxies["https"] = proxy_settings.https_url

        if proxies:
            return proxies
        logging.warning("Generic proxy mode selected but URLs missing.")
        return None

    return None


def _list_transcripts(
    video_id: str,
    cookies: Optional[str] = None,
    proxy_config: Optional[dict[str, str]] = None,
):
    """Compatibility wrapper for youtube-transcript-api 0.6.x."""
    return YouTubeTranscriptApi.list_transcripts(video_id, proxies=proxy_config, cookies=cookies)


def download_transcript(
    video_id: str,
    preferred_languages: Optional[List[str]] = None,
    cookie_file: Optional[str] = None,
    proxy_settings: Optional[Any] = None,
    min_delay: float = 0.0,
    jitter: float = 0.0,
    session: Optional[requests.Session] = None,
) -> Optional[str]:
    """
    Downloads the transcript for a given video ID.
    """
    result = download_transcript_result(
        video_id=video_id,
        preferred_languages=preferred_languages,
        cookie_file=cookie_file,
        proxy_settings=proxy_settings,
        min_delay=min_delay,
        jitter=jitter,
        session=session,
    )
    return result.text if result.is_success() else None


def download_transcript_result(
    video_id: str,
    preferred_languages: Optional[List[str]] = None,
    cookie_file: Optional[str] = None,
    proxy_settings: Optional[Any] = None,
    min_delay: float = 0.0,
    jitter: float = 0.0,
    max_retries: int = 0,
    backoff_base: float = 2.0,
    backoff_cap: float = 120.0,
    session: Optional[requests.Session] = None,
) -> TranscriptDownloadResult:
    """Download transcript with differentiated status, retries and rate limiting."""

    if preferred_languages is None:
        preferred_languages = DEFAULT_LANGUAGES

    proxy_cfg = _get_proxy_config(proxy_settings, video_id=video_id)

    attempt = 0
    while attempt <= max_retries:
        if attempt > 0:
            # Exponentieller Backoff
            sleep_time = min(backoff_cap, backoff_base**attempt) + (
                random.random() * jitter
            )
            logging.info(
                f"Retry attempt {attempt}/{max_retries} for {video_id} after {sleep_time:.2f}s backoff"
            )
            time.sleep(sleep_time)
        else:
            # Normales Rate Limiting vor dem ersten Versuch
            if min_delay > 0 or jitter > 0:
                _apply_rate_limit(min_delay, jitter)

        attempt += 1

        try:
            logging.info(
                f"Attempting to download transcript for video ID: {video_id} (Attempt {attempt})"
            )
            transcript_list = _list_transcripts(
                video_id, cookies=cookie_file, proxy_config=proxy_cfg
            )

            transcript = None
            try:
                transcript = transcript_list.find_manually_created_transcript(
                    preferred_languages
                )
                logging.debug(
                    f"Found manually created transcript in language: {transcript.language}"
                )
            except NoTranscriptFound:
                logging.debug("No manual transcript found in preferred languages.")
                try:
                    transcript = transcript_list.find_generated_transcript(
                        preferred_languages
                    )
                    logging.debug(
                        f"Found generated transcript in language: {transcript.language}"
                    )
                except NoTranscriptFound:
                    logging.warning(
                        f"No transcript found in preferred languages for {video_id}. Trying any available."
                    )
                    for any_transcript in transcript_list:
                        transcript = any_transcript
                        logging.info(
                            f"Using available transcript in language: {transcript.language}"
                        )
                        break

            if not transcript:
                logging.info(f"No transcript available for video ID: {video_id}")
                return TranscriptDownloadResult(
                    status=TranscriptStatus.NO_TRANSCRIPT,
                    reason="no_transcript_available",
                )

            transcript_text_list = [item.text for item in transcript.fetch()]
            full_transcript = "\n".join(transcript_text_list)
            logging.info(f"Successfully downloaded transcript for video ID: {video_id}")
            return TranscriptDownloadResult(
                status=TranscriptStatus.SUCCESS, text=full_transcript
            )

        except TooManyRequests as e:
            logging.warning(f"YouTube rate limited the request: {e}")
            return TranscriptDownloadResult(
                status=TranscriptStatus.BLOCKED,
                reason="too_many_requests",
                error_type=e.__class__.__name__,
                error_message=str(e),
            )
        except (YouTubeRequestFailed, CouldNotRetrieveTranscript) as e:
            logging.error(f"YouTube request failed: {e}")
            return TranscriptDownloadResult(
                status=TranscriptStatus.BLOCKED,
                reason="request_failed",
                error_type=e.__class__.__name__,
                error_message=str(e),
            )
        except TranscriptsDisabled:
            logging.info(f"Transcripts are disabled for video ID: {video_id}")
            return TranscriptDownloadResult(
                status=TranscriptStatus.TRANSCRIPTS_DISABLED,
                reason="transcripts_disabled",
            )
        except NoTranscriptFound:
            logging.info(f"No transcript found for video ID: {video_id}")
            return TranscriptDownloadResult(
                status=TranscriptStatus.NO_TRANSCRIPT,
                reason="no_transcript_found",
            )
        except VideoUnavailable:
            logging.info(f"Video unavailable for video ID: {video_id}")
            return TranscriptDownloadResult(
                status=TranscriptStatus.NO_TRANSCRIPT,
                reason="video_unavailable",
            )
        except Exception as e:
            # Prüfe auf 429 in der Exception Message (manchmal wirft requests direkt Fehler)
            if isinstance(e, ParseError):
                logging.warning(f"Transcript parse error on attempt {attempt}: {e}")
                if attempt <= max_retries:
                    continue  # Retry loop
                return TranscriptDownloadResult(
                    status=TranscriptStatus.BLOCKED,
                    reason="parse_error",
                    error_type=e.__class__.__name__,
                    error_message=str(e),
                )

            if "429" in str(e) or "Too Many Requests" in str(e):
                logging.warning(f"Rate limited (429) on attempt {attempt}: {e}")
                if attempt <= max_retries:
                    continue  # Retry loop

            logging.error(f"Error downloading transcript for video ID {video_id}: {e}")
            return TranscriptDownloadResult(
                status=TranscriptStatus.ERROR,
                reason="exception",
                error_type=e.__class__.__name__,
                error_message=str(e),
            )

    return TranscriptDownloadResult(
        status=TranscriptStatus.ERROR,
        reason="max_retries_exceeded",
    )


def search_keywords(
    transcript: str, keywords: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Searches the transcript for keywords (case-insensitive, whole word).

    Args:
        transcript: The transcript text to search
        keywords: List of keywords to search for

    Returns:
        Tuple of (found_keywords, found_lines) where:
            found_keywords: List of keywords that were found
            found_lines: List of lines containing the keywords
    """
    if not transcript or not keywords:
        return [], []

    found_keywords = []
    found_lines = []

    for keyword in keywords:
        # Create a regex pattern for whole word, case-insensitive search
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, transcript, re.IGNORECASE):
            found_keywords.append(keyword)

            # Find all lines containing the keyword
            lines = transcript.split("\n")
            for line in lines:
                if re.search(pattern, line, re.IGNORECASE):
                    found_lines.append(line.strip())

    return found_keywords, found_lines
