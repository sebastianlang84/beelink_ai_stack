"""
YouTube API Client

Bereitstellung von Low-Level-Funktionen zur Interaktion mit der YouTube Data API.
"""

import logging
import random
import socket
import time
import json
from datetime import datetime
from typing import List, Optional, TypeVar

# NOTE (offline/--help robustness):
# `google-api-python-client` (googleapiclient) kann in manchen Umgebungen fehlen.
# Wenn wir es top-level importieren, schlägt schon ein reiner `--help`/Import fehl.
# Deshalb importieren wir googleapiclient erst bei tatsächlicher API-Nutzung.

# Typ für den Google API-Client
Resource = TypeVar("Resource")

# Retry/timeout defaults for YouTube Data API calls.
# Policy: We implement a small retry loop with exponential backoff + jitter for
# retryable transient errors (timeouts, 429/5xx, and quota/user-rate related 403).
DEFAULT_YOUTUBE_API_NUM_RETRIES = 4
DEFAULT_YOUTUBE_API_TIMEOUT_SEC = 30
DEFAULT_YOUTUBE_API_BACKOFF_BASE_SEC = 1.0
DEFAULT_YOUTUBE_API_BACKOFF_MAX_SEC = 30.0
_YOUTUBE_API_TIMEOUT_SEC = DEFAULT_YOUTUBE_API_TIMEOUT_SEC


def configure_youtube_api_timeout_sec(timeout_sec: int | None) -> None:
    """Configure per-request timeout for YouTube Data API calls."""

    global _YOUTUBE_API_TIMEOUT_SEC
    if timeout_sec is None:
        _YOUTUBE_API_TIMEOUT_SEC = DEFAULT_YOUTUBE_API_TIMEOUT_SEC
        return
    try:
        parsed = int(timeout_sec)
    except Exception:
        _YOUTUBE_API_TIMEOUT_SEC = DEFAULT_YOUTUBE_API_TIMEOUT_SEC
        return
    _YOUTUBE_API_TIMEOUT_SEC = max(5, min(300, parsed))


def _require_googleapiclient():
    """Importiert googleapiclient erst bei Bedarf.

    Returns:
        (build, HttpError)

    Raises:
        ImportError: falls google-api-python-client nicht installiert ist.
    """
    try:
        from googleapiclient.discovery import build  # type: ignore
        from googleapiclient.errors import HttpError  # type: ignore

        return build, HttpError
    except ModuleNotFoundError as e:
        raise ImportError(
            "Missing dependency 'google-api-python-client' (module 'googleapiclient'). "
            "Install it to use the YouTube API."
        ) from e


def _get_http_status(exc: Exception) -> Optional[int]:
    resp = getattr(exc, "resp", None)
    status = getattr(resp, "status", None)
    try:
        return int(status) if status is not None else None
    except Exception:
        return None


def _extract_http_error_reason(exc: Exception) -> Optional[str]:
    """Best-effort extraction of the first google API error reason."""

    content = getattr(exc, "content", None)
    if not content:
        return None

    try:
        if isinstance(content, (bytes, bytearray)):
            payload = json.loads(content.decode("utf-8", errors="replace"))
        elif isinstance(content, str):
            payload = json.loads(content)
        else:
            return None

        errors = payload.get("error", {}).get("errors", [])
        if errors and isinstance(errors, list):
            reason = errors[0].get("reason")
            return str(reason) if reason else None
    except Exception:
        return None

    return None


def _is_retryable_google_http_error(
    status: Optional[int], reason: Optional[str]
) -> bool:
    if status is None:
        return False

    # Retryable transient / rate limiting.
    if status in {429, 500, 502, 503, 504}:
        return True

    # Quota / user-rate related errors sometimes come as 403.
    if status == 403 and reason in {
        "quotaExceeded",
        "userRateLimitExceeded",
        "rateLimitExceeded",
        "dailyLimitExceeded",
    }:
        return True

    return False


def _execute_with_retries(request, *, num_retries: int, timeout_sec: int):
    """Executes a googleapiclient HttpRequest with retry/backoff and socket timeout.

    The retry loop is implemented here (instead of relying on `execute(num_retries=...)`)
    to make quota/rate-limit handling and logging explicit.
    """

    max_attempts = max(1, int(num_retries) + 1)

    for attempt in range(1, max_attempts + 1):
        # Apply a per-call socket timeout (best-effort) and restore afterwards.
        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout_sec)
        try:
            # Avoid double-retry (we implement retries here).
            return request.execute(num_retries=0)
        except Exception as e:
            status = _get_http_status(e)
            reason = _extract_http_error_reason(e)

            retryable = _is_retryable_google_http_error(status, reason) or isinstance(
                e, socket.timeout
            )

            if (not retryable) or attempt >= max_attempts:
                raise

            # Best-effort telemetry (don't import at module import time).
            try:
                from common.telemetry import record_pipeline_error

                record_pipeline_error(
                    error_type="youtube_data_api_retry",
                    where=f"_execute_with_retries.status_{status or 'unknown'}",
                )
            except Exception:
                pass

            # Exponential backoff with jitter, capped.
            exp = min(attempt - 1, 10)
            base = DEFAULT_YOUTUBE_API_BACKOFF_BASE_SEC * (2**exp)
            sleep_sec = min(DEFAULT_YOUTUBE_API_BACKOFF_MAX_SEC, base) + random.random()
            logging.warning(
                "YouTube Data API request failed (attempt %s/%s, status=%s, reason=%s). "
                "Retrying in %.1fs...",
                attempt,
                max_attempts,
                status,
                reason,
                sleep_sec,
            )
            time.sleep(sleep_sec)
        finally:
            socket.setdefaulttimeout(previous_timeout)


# Typdefinitionen
class VideoDetails(dict):
    """Datenstruktur für Videoinformationen."""

    id: str
    title: str
    published_at: datetime


class ChannelInfo(dict):
    """Datenstruktur für Kanalinformationen."""

    id: str
    title: str
    description: str
    published_at: datetime


def get_youtube_client(api_key: Optional[str] = None) -> Resource:
    """Erstellt einen YouTube API-Client.

    Args:
        api_key: Optionaler API-Key. Falls nicht angegeben, wird die Umgebungsvariable
                YOUTUBE_API_KEY verwendet.

    Returns:
        Einen initialisierten YouTube API-Client.
    """
    if not api_key:
        import os

        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise ValueError(
                "Kein YouTube API-Key angegeben und YOUTUBE_API_KEY Umgebungsvariable nicht gesetzt"
            )

    build, _ = _require_googleapiclient()
    return build("youtube", "v3", developerKey=api_key)


def get_channel_by_handle(youtube: Resource, handle: str) -> Optional[ChannelInfo]:
    """Holt Kanalinformationen anhand eines Handles.

    Args:
        youtube: YouTube API-Client
        handle: Kanal-Handle (mit oder ohne @)

    Returns:
        ChannelInfo-Objekt oder None falls nicht gefunden
    """
    try:
        _, HttpError = _require_googleapiclient()
        # Entferne @ falls vorhanden
        handle = handle.lstrip("@")

        # Suche nach Kanal über den Handle
        request = youtube.search().list(
            part="snippet", q=f"@{handle}", type="channel", maxResults=1
        )
        search_response = _execute_with_retries(
            request,
            num_retries=DEFAULT_YOUTUBE_API_NUM_RETRIES,
            timeout_sec=_YOUTUBE_API_TIMEOUT_SEC,
        )

        if not search_response.get("items"):
            return None

        channel = search_response["items"][0]
        return {
            "id": channel["id"]["channelId"],
            "title": channel["snippet"]["title"],
            "description": channel["snippet"].get("description", ""),
            "published_at": channel["snippet"]["publishedAt"],
        }

    except HttpError as e:
        logging.error(f"Fehler beim Abrufen des Kanals {handle}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unerwarteter Fehler beim Abrufen des Kanals {handle}: {e}")
        try:
            from common.telemetry import record_pipeline_error

            record_pipeline_error(
                error_type="youtube_data_api", where="get_channel_by_handle"
            )
        except Exception:
            pass
        return None


def get_channel_videos(
    youtube: Resource,
    channel_id: str,
    *,
    max_results: int = 50,
    published_after: Optional[datetime] = None,
) -> List[VideoDetails]:
    """Holt Videos eines Kanals.

    Args:
        youtube: YouTube API-Client
        channel_id: YouTube Kanal-ID
        max_results: Maximale Anzahl an Ergebnissen
        published_after: Nur Videos nach diesem Datum berücksichtigen

    Returns:
        Liste von VideoDetails-Objekten
    """
    try:
        _, HttpError = _require_googleapiclient()
        # Hole die Upload-Playlist des Kanals
        request = youtube.channels().list(
            part="contentDetails", id=channel_id, maxResults=1
        )
        channels_response = _execute_with_retries(
            request,
            num_retries=DEFAULT_YOUTUBE_API_NUM_RETRIES,
            timeout_sec=_YOUTUBE_API_TIMEOUT_SEC,
        )

        if not channels_response.get("items"):
            return []

        uploads_playlist_id = channels_response["items"][0]["contentDetails"][
            "relatedPlaylists"
        ]["uploads"]
        videos = []
        next_page_token = None

        while len(videos) < max_results:
            # Bestimme die maximale Anzahl an Ergebnissen pro Anfrage
            results_per_page = min(50, max_results - len(videos))

            request = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=results_per_page,
                pageToken=next_page_token,
            )
            playlist_items_response = _execute_with_retries(
                request,
                num_retries=DEFAULT_YOUTUBE_API_NUM_RETRIES,
                timeout_sec=_YOUTUBE_API_TIMEOUT_SEC,
            )

            for item in playlist_items_response.get("items", []):
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})

                video_id = content_details.get("videoId")
                if not video_id:
                    continue

                published_at = datetime.strptime(
                    snippet["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
                )

                if published_after and published_at < published_after:
                    return videos

                # Check if video is a live event
                live_broadcast_content = snippet.get("liveBroadcastContent", "none")
                is_live_event = live_broadcast_content in {"live", "upcoming"}

                videos.append(
                    {
                        "id": video_id,
                        "title": snippet.get("title", "Ohne Titel"),
                        "published_at": published_at,
                        "is_live_event": is_live_event,
                    }
                )

                if len(videos) >= max_results:
                    return videos

            next_page_token = playlist_items_response.get("nextPageToken")
            if not next_page_token:
                break

        return videos

    except HttpError as e:
        logging.error(f"Fehler beim Abrufen der Videos für Kanal {channel_id}: {e}")
        return []
    except Exception as e:
        logging.error(
            f"Unerwarteter Fehler beim Abrufen der Videos für Kanal {channel_id}: {e}"
        )
        try:
            from common.telemetry import record_pipeline_error

            record_pipeline_error(
                error_type="youtube_data_api", where="get_channel_videos"
            )
        except Exception:
            pass
        return []
