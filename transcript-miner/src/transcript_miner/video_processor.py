"""
Video processing logic for the YouTube Transcript Miner.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.config import Config
from common.utils import (
    calculate_token_count,
    generate_filename_base,
    save_metadata,
    save_transcript,
)
from common.telemetry import record_pipeline_error
from .transcript_downloader import download_transcript_result, search_keywords
from common.error_history import append_error_history
from .transcript_models import TranscriptStatus

# Default token limit for transcripts (used when no model limit is configured)
TRANSCRIPT_TOKEN_LIMIT = 200000


def _validate_processed_videos(data: Any) -> Dict[str, List[str]]:
    """Validate/normalize the processed-videos JSON structure.

    Expected shape: {channel_id: [video_id, ...]}.
    """

    if not isinstance(data, dict):
        raise ValueError("progress.json must be a JSON object (dict)")

    normalized: Dict[str, List[str]] = {}
    for k, v in data.items():
        if not isinstance(k, str):
            raise ValueError("progress.json keys must be strings (channel_id)")
        if v is None:
            normalized[k] = []
            continue
        if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
            raise ValueError(
                f"progress.json values must be list[str] (channel_id={k!r})"
            )
        normalized[k] = v
    return normalized


def _load_json_file(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _backup_corrupted_json(path: Path, *, logger: logging.Logger) -> None:
    """Move a corrupted JSON file out of the way for investigation."""

    if not path.exists():
        return
    backup_path = path.with_suffix(f".corrupted.{int(time.time())}.json")
    try:
        path.rename(backup_path)
        logger.warning("Backed up corrupted file to %s", backup_path)
    except Exception:
        logger.exception("Failed to backup corrupted file: %s", path)


def _has_summary(
    config: Config, video_id: str, channel_handle: Optional[str] = None
) -> bool:
    """Check if a summary exists and is minimally valid for the video (PRD).

    Policy:
    - If a summary exists, we don't need to re-download the transcript
      unless forced.
    - Global layout: output/data/summaries/by_video_id/<video_id>.summary.md
    - Legacy layout: output/<profile>/<channel>/2_summaries/<video_id>.md
    """
    logger = logging.getLogger(__name__)
    summary_path = config.output.get_summary_path(
        video_id, channel_handle=channel_handle
    )
    if not summary_path.exists():
        # Cold storage: summaries moved out of the active folder must still count as "present"
        # so we don't re-run LLM analysis on old videos.
        cold = (
            config.output.get_data_root()
            / "summaries"
            / "cold"
            / "by_video_id"
            / f"{video_id}.summary.md"
        )
        if not cold.exists():
            return False
        summary_path = cold

    try:
        text = summary_path.read_text(encoding="utf-8")
    except Exception as exc:
        _backup_corrupted_summary(summary_path, logger=logger)
        logger.warning(
            "Summary unreadable; treating as missing (video_id=%s, error=%s)",
            video_id,
            exc,
        )
        return False

    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end == -1:
            _backup_corrupted_summary(summary_path, logger=logger)
            logger.warning(
                "Summary frontmatter not terminated; treating as missing (video_id=%s)",
                video_id,
            )
            return False

        raw = text[4:end]
        meta: dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if k:
                meta[k] = v

        if meta.get("video_id") != video_id:
            _backup_corrupted_summary(summary_path, logger=logger)
            logger.warning(
                "Summary video_id mismatch; treating as missing (video_id=%s, found=%s)",
                video_id,
                meta.get("video_id"),
            )
            return False

        return True

    source_meta = _parse_source_block(text)
    if source_meta:
        if source_meta.get("video_id") != video_id:
            _backup_corrupted_summary(summary_path, logger=logger)
            logger.warning(
                "Summary Source video_id mismatch; treating as missing (video_id=%s, found=%s)",
                video_id,
                source_meta.get("video_id"),
            )
            return False
        return True

    wrapped_meta = _parse_wrapped_doc_frontmatters(text)
    if not wrapped_meta:
        _backup_corrupted_summary(summary_path, logger=logger)
        logger.warning(
            "Summary has neither Source block nor wrapped docs; treating as missing (video_id=%s)",
            video_id,
        )
        return False

    if not any(meta.get("video_id") == video_id for meta in wrapped_meta):
        _backup_corrupted_summary(summary_path, logger=logger)
        found_ids = sorted(
            {meta.get("video_id", "") for meta in wrapped_meta if meta.get("video_id")}
        )
        logger.warning(
            "Summary wrapped-doc video_id mismatch; treating as missing (video_id=%s, found=%s)",
            video_id,
            ",".join(found_ids) if found_ids else "none",
        )
        return False

    return True


def _parse_source_block(text: str) -> dict[str, str]:
    """Extract key/value pairs from a '## Source' block."""
    idx = text.find("## Source")
    if idx == -1:
        return {}
    lines = text[idx:].splitlines()
    if not lines:
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        line = line.strip()
        if line.startswith("## "):
            break
        if not line.startswith("- "):
            continue
        item = line[2:].strip()
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key:
            meta[key] = value
    return meta


def _parse_wrapped_doc_frontmatters(text: str) -> list[dict[str, str]]:
    matches = re.findall(
        r"<<<DOC_START>>>\s*(.*?)\s*<<<DOC_END>>>",
        text.replace("\r\n", "\n"),
        flags=re.DOTALL,
    )
    metas: list[dict[str, str]] = []
    for raw in matches:
        body = (raw or "").strip()
        if not body:
            continue
        m_frontmatter = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n?", body, flags=re.DOTALL)
        if not m_frontmatter:
            continue
        meta: dict[str, str] = {}
        for line in m_frontmatter.group(1).splitlines():
            m_kv = re.match(r"^\s*([a-zA-Z0-9_]+)\s*:\s*(.*?)\s*$", line)
            if not m_kv:
                continue
            key = m_kv.group(1).strip()
            value = m_kv.group(2).strip()
            if key:
                meta[key] = value
        if meta:
            metas.append(meta)
    return metas


def _backup_corrupted_summary(path: Path, *, logger: logging.Logger) -> None:
    """Move a corrupted summary file out of the way for investigation."""

    if not path.exists():
        return
    backup_path = path.with_name(f"{path.stem}.corrupted.{int(time.time())}{path.suffix}")
    try:
        path.rename(backup_path)
        logger.warning("Backed up corrupted summary to %s", backup_path)
    except Exception:
        logger.exception("Failed to backup corrupted summary: %s", path)


def _find_transcript_file(transcripts_dir: Path, video_id: str) -> Optional[Path]:
    if not transcripts_dir.exists():
        return None
    direct = transcripts_dir / f"{video_id}.txt"
    if direct.exists():
        return direct
    matches = sorted(transcripts_dir.glob(f"*_{video_id}.txt"))
    return matches[0] if matches else None


def _check_transcript_health(
    transcripts_dir: Path, video_id: str, *, logger: logging.Logger
) -> tuple[bool, str]:
    transcript_path = _find_transcript_file(transcripts_dir, video_id)
    if transcript_path is None:
        return False, "missing"

    try:
        text = transcript_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning(
            "Transcript read failed; treating as unhealthy (video_id=%s, error=%s)",
            video_id,
            exc,
        )
        return False, "unreadable"

    if not text.strip():
        return False, "empty"

    if transcript_path.name == f"{video_id}.txt":
        meta_path = transcript_path.with_suffix(".meta.json")
    else:
        meta_path = transcript_path.with_name(
            transcript_path.name.replace(f"_{video_id}.txt", f"_{video_id}_meta.json")
        )
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if not isinstance(meta, dict):
                return False, "metadata_invalid"
            status = meta.get("transcript_status")
            if isinstance(status, str) and status != TranscriptStatus.SUCCESS.value:
                return False, f"metadata_status={status}"
        except Exception as exc:
            logger.warning(
                "Transcript metadata read failed; treating as unhealthy (video_id=%s, error=%s)",
                video_id,
                exc,
            )
            return False, "metadata_unreadable"

    return True, "ok"


@dataclass(frozen=True)
class CleanupResult:
    deleted_transcripts: int
    deleted_metadata: int
    deleted_total: int
    deleted_video_ids: List[str]


def load_processed_videos(path: Path) -> Dict[str, List[str]]:
    """
    Load processed videos mapping from a JSON file, with corruption fallback.

    Args:
        path: Path to the JSON file containing processed video IDs per channel.

    Returns:
        A dict of channel_id -> list of video IDs; empty if file missing or corrupted.
    """
    logger = logging.getLogger(__name__)

    backup_path = path.with_suffix(".bak")

    # If the main file is missing but a backup exists (e.g. crash between rename/replace), restore.
    if (not path.exists()) and backup_path.exists():
        try:
            data = _validate_processed_videos(_load_json_file(backup_path))
            atomic_save_processed_videos(path, data, create_backup=False)
            logger.warning(
                "Restored missing progress.json from backup: %s", backup_path
            )
            return data
        except Exception:
            logger.exception(
                "Failed to restore progress.json from backup: %s", backup_path
            )
            return {}

    if not path.exists():
        return {}

    try:
        return _validate_processed_videos(_load_json_file(path))
    except Exception as e:
        # Corruption policy:
        # 1) Move corrupted file aside for investigation
        # 2) Try restore from last known-good backup (progress.bak)
        # 3) Continue with restored (or empty) state
        logger.warning("Error loading processed videos from %s: %s", path, e)

        _backup_corrupted_json(path, logger=logger)

        if backup_path.exists():
            try:
                restored = _validate_processed_videos(_load_json_file(backup_path))
                atomic_save_processed_videos(path, restored, create_backup=False)
                logger.warning("Restored progress.json from backup: %s", backup_path)
                return restored
            except Exception:
                logger.exception(
                    "Failed to restore progress.json from backup: %s", backup_path
                )

        return {}


def atomic_save_processed_videos(
    path: Path,
    data: Dict[str, List[str]],
    *,
    create_backup: bool = True,
) -> bool:
    """
    Atomically write processed videos data to JSON file.

    Writes data to a temporary file and replaces the target file, avoiding partial writes.

    Args:
        path: Path to the target JSON file.
        data: The mapping of channel IDs to processed video ID lists.

    Returns:
        True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    temp_path = path.with_suffix(".tmp")
    backup_path = path.with_suffix(".bak")
    try:
        # Lazy Creation: Ensure parent directory exists before writing
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Keep a last-known-good backup. We move the previous file (if any) to .bak
        # before replacing. If the process crashes after this step, load_processed_videos()
        # can restore from the backup.
        if create_backup and path.exists():
            try:
                path.replace(backup_path)
            except Exception:
                logger.exception("Failed to create progress backup at %s", backup_path)

        temp_path.replace(path)  # Atomic replace
        return True
    except Exception as e:
        logging.error(f"Error saving processed videos to {path}: {e}")

        # Best-effort restore if we moved the original away but failed to replace.
        try:
            if (not path.exists()) and backup_path.exists() and not temp_path.exists():
                backup_path.replace(path)
        except Exception:
            logger.exception("Failed to restore progress.json after write error")

        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            logger.exception("Failed to cleanup temp file: %s", temp_path)
        return False


def cleanup_old_outputs(
    transcripts_dir: Path,
    *,
    retention_days: int | None,
    now: datetime | None = None,
) -> CleanupResult:
    """Delete transcript outputs older than N days.

    Policy (deterministic for a given `now`):
    - Delete `*.txt` whose mtime is older than `now - retention_days`.
      When deleting a transcript, also delete its corresponding `_meta.json` (if present),
      regardless of the metadata file's own mtime (avoid orphan metadata).
    - Additionally delete standalone `*_meta.json` older than the cutoff (covers skipped-only metadata).
    """

    logger = logging.getLogger(__name__)

    if retention_days is None:
        return CleanupResult(0, 0, 0, [])
    if retention_days < 0:
        raise ValueError("retention_days must be >= 0 or None")

    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)

    cutoff_ts = now_dt.timestamp() - (retention_days * 24 * 60 * 60)

    video_id_from_txt = re.compile(r"_([a-zA-Z0-9_-]{11})\.txt$")
    video_id_from_meta = re.compile(r"_([a-zA-Z0-9_-]{11})_meta\.json$")

    deleted_transcripts = 0
    deleted_metadata = 0
    deleted_video_ids: List[str] = []

    if not transcripts_dir.exists():
        return CleanupResult(0, 0, 0, [])

    # 1) Delete old transcripts (+ their metadata).
    for txt_file in sorted(transcripts_dir.glob("*.txt")):
        try:
            st = txt_file.stat()
        except FileNotFoundError:
            continue

        if st.st_mtime >= cutoff_ts:
            continue

        vid_match = video_id_from_txt.search(txt_file.name)
        video_id = vid_match.group(1) if vid_match else None

        try:
            txt_file.unlink()
            deleted_transcripts += 1
            if video_id:
                deleted_video_ids.append(video_id)
            logger.info("Deleted old transcript file: %s", txt_file)
        except Exception:
            logger.exception("Failed to delete transcript file: %s", txt_file)
            continue

        if video_id:
            meta_file = transcripts_dir / txt_file.name.replace(
                f"_{video_id}.txt", f"_{video_id}_meta.json"
            )
            if meta_file.exists():
                try:
                    meta_file.unlink()
                    deleted_metadata += 1
                    logger.info("Deleted metadata for old transcript: %s", meta_file)
                except Exception:
                    logger.exception("Failed to delete metadata file: %s", meta_file)

    # 2) Delete old standalone metadata (e.g. skipped-only metadata).
    for meta_file in sorted(transcripts_dir.glob("*_meta.json")):
        try:
            st = meta_file.stat()
        except FileNotFoundError:
            continue

        if st.st_mtime >= cutoff_ts:
            continue

        try:
            meta_file.unlink()
            deleted_metadata += 1
            match = video_id_from_meta.search(meta_file.name)
            if match:
                deleted_video_ids.append(match.group(1))
            logger.info("Deleted old metadata file: %s", meta_file)
        except Exception:
            logger.exception("Failed to delete metadata file: %s", meta_file)

    # Dedup IDs but keep deterministic order.
    seen: set[str] = set()
    deduped_ids: List[str] = []
    for vid in deleted_video_ids:
        if vid not in seen:
            seen.add(vid)
            deduped_ids.append(vid)

    return CleanupResult(
        deleted_transcripts=deleted_transcripts,
        deleted_metadata=deleted_metadata,
        deleted_total=deleted_transcripts + deleted_metadata,
        deleted_video_ids=deduped_ids,
    )


def load_skipped_videos(path: Path) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Load skipped videos mapping from JSON with corruption fallback.

    Structure: {channel_id: {video_id: {"status": str, "reason": str, ...}}}
    """

    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(
            f"Error loading skipped videos from {path}: {e}. Starting with empty state."
        )
        if path.exists():
            backup_path = path.with_suffix(f".corrupted.{int(time.time())}.json")
            try:
                path.rename(backup_path)
                logging.info(f"Backed up corrupted skipped file to {backup_path}")
            except Exception as e:
                logging.error(f"Failed to backup corrupted skipped file: {e}")
        return {}


def atomic_save_skipped_videos(
    path: Path, data: Dict[str, Dict[str, Dict[str, Any]]]
) -> bool:
    """Atomically write skipped videos mapping to JSON."""

    temp_path = path.with_suffix(".tmp")
    try:
        # Lazy Creation: Ensure parent directory exists before writing
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.replace(path)
        return True
    except Exception as e:
        logging.error(f"Error saving skipped videos to {path}: {e}")
        return False


def sync_progress_with_filesystem(
    transcripts_dir: Path,
    progress_file: Path,
    channel_id: str,
    config: Config,
    channel_handle: Optional[str] = None,
) -> Dict[str, List[str]]:
    """
    Intelligente bidirektionale Synchronisation zwischen progress.json und Dateisystem.

    A → B: Fehlende JSON-Einträge für vorhandene Dateien hinzufügen
    B → A: Verwaiste JSON-Einträge ohne entsprechende Dateien entfernen
           (Es sei denn, eine Summary existiert gemäß PRD).

    Args:
        transcripts_dir: Directory containing transcript files
        progress_file: Path to progress.json file
        channel_id: Channel ID to sync for
        config: Configuration object (used to check for summaries)
        channel_handle: Optional channel handle for path resolution

    Returns:
        Updated processed videos dictionary
    """
    logger = logging.getLogger(__name__)

    # Load current progress data
    processed_videos = load_processed_videos(progress_file)
    channel_processed = processed_videos.get(channel_id, [])

    # Pattern to extract video IDs from filenames
    # Format: YYYY-MM-DD_channelname_VideoID.txt
    video_id_pattern = re.compile(r"_([a-zA-Z0-9_-]{11})\.txt$")

    is_global_layout = config.output.is_global_layout()

    # A → B: Scan filesystem for missing JSON entries.
    files_added = 0
    if transcripts_dir.exists():
        # Deterministic iteration order (stable progress.json output across runs).
        for txt_file in sorted(transcripts_dir.glob("*.txt")):
            match = video_id_pattern.search(txt_file.name)
            if match:
                video_id = match.group(1)
                if video_id not in channel_processed:
                    # In global layout, we only add it if it belongs to this channel
                    # (we can check the metadata file if it exists)
                    if is_global_layout:
                        meta_path = txt_file.with_suffix(".meta.json")
                        if meta_path.exists():
                            try:
                                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                                if meta.get("channel_id") == channel_id:
                                    channel_processed.append(video_id)
                                    files_added += 1
                                    logger.info(f"Added migrated video ID to progress: {video_id}")
                            except Exception:
                                pass
                    else:
                        channel_processed.append(video_id)
                        files_added += 1
                        logger.info(f"Added missing video ID to progress: {video_id}")

    # B → A: Remove orphaned JSON entries
    files_removed = 0
    valid_video_ids = []
    for video_id in channel_processed:
        # Check if corresponding transcript file exists
        transcript_exists = _find_transcript_file(transcripts_dir, video_id) is not None

        # Policy PRD: Keep in progress if transcript exists OR summary exists.
        if transcript_exists or _has_summary(
            config, video_id, channel_handle=channel_handle
        ):
            valid_video_ids.append(video_id)
        else:
            files_removed += 1
            logger.info(f"Removed orphaned video ID from progress: {video_id}")

    # Update progress data
    # Deterministic ordering: progress.json should be stable across runs.
    # Order has no semantic meaning (membership-only), so we sort by video_id.
    processed_videos[channel_id] = sorted(valid_video_ids)

    # Save updated progress if changes were made
    if files_added > 0 or files_removed > 0:
        if atomic_save_processed_videos(progress_file, processed_videos):
            logger.info(
                f"Progress sync completed: +{files_added} added, -{files_removed} removed"
            )
        else:
            logger.error("Failed to save updated progress data")
    else:
        logger.info("Progress sync: No changes needed")

    return processed_videos


def is_video_already_processed(
    video_id: str, channel_processed: List[str], transcripts_dir: Path
) -> tuple[bool, str]:
    """
    Check if a video has already been processed.

    Args:
        video_id: The video ID to check
        channel_processed: List of processed video IDs for the channel
        transcripts_dir: Directory containing transcripts

    Returns:
        Tuple (already_processed, transcript_health_reason).
    """
    logger = logging.getLogger(__name__)

    healthy, reason = _check_transcript_health(
        transcripts_dir, video_id, logger=logger
    )

    # 1. Check in progress.json (fastest check)
    if video_id in channel_processed:
        if healthy:
            return True, "ok"
        logger.warning(
            "Processed video marked but transcript unhealthy (%s); will reprocess (video_id=%s)",
            reason,
            video_id,
        )
        return False, reason

    # 2. Check if transcript file already exists and is healthy.
    if healthy:
        logger.info(f"Found existing transcript file for video ID: {video_id}")
        return True, "ok"

    return False, reason


def process_single_video(
    video: Dict,
    channel_id: str,
    channel_name: str,
    config: Config,
    transcripts_dir: Path,
    processed_videos: Dict[str, List[str]],
    progress_file: Path,
    skipped_videos: Dict[str, Dict[str, Dict[str, Any]]],
    skipped_file: Path,
    channel_handle: Optional[str] = None,
    run_stats: Optional["RunStats"] = None,
    stream_queue=None,
) -> bool:
    """
    Process a single video: download transcript, save files, update progress.

    Args:
        video: Video information dictionary
        channel_id: Channel ID
        channel_name: Channel name
        config: Configuration object
        transcripts_dir: Directory to save transcripts
        processed_videos: Dictionary tracking processed videos
        progress_file: Path to progress tracking file
        channel_handle: Optional channel handle for path resolution

    Returns:
        True if processing was successful, False otherwise
    """
    logger = logging.getLogger(__name__)

    video_id = video["id"]
    video_title = video.get("title", "Unknown")

    # Get or initialize channel processed list
    channel_processed = processed_videos.get(channel_id, [])

    channel_skipped = skipped_videos.get(channel_id, {})

    # Check if already processed
    already_processed, transcript_health = is_video_already_processed(
        video_id, channel_processed, transcripts_dir
    )
    if already_processed:
        if run_stats is not None:
            run_stats.inc("transcripts_skipped_existing")
        logger.info(
            f"Skipping video (already processed): {video_title} (ID: {video_id})"
        )
        # Add to processed list if found in file system but not in progress
        if video_id not in channel_processed:
            channel_processed.append(video_id)
            processed_videos[channel_id] = channel_processed
            atomic_save_processed_videos(progress_file, processed_videos)
        return True

    # Policy PRD: Skip download if summary exists and re-download not forced.
    summary_ok = _has_summary(config, video_id, channel_handle=channel_handle)
    if (
        not config.youtube.force_redownload_transcripts
        and transcript_health == "missing"
        and summary_ok
    ):
        if run_stats is not None:
            run_stats.inc("transcripts_skipped_summary")
        logger.info(
            f"Skipping transcript download (summary exists): {video_title} (ID: {video_id})"
        )
        # Mark as processed so we don't check again in this run.
        if video_id not in channel_processed:
            channel_processed.append(video_id)
            processed_videos[channel_id] = channel_processed
            atomic_save_processed_videos(progress_file, processed_videos)
        return True

    # Skip videos that were previously determined to have no transcripts.
    existing_skip = channel_skipped.get(video_id)
    if isinstance(existing_skip, dict) and existing_skip.get("status") in {
        TranscriptStatus.NO_TRANSCRIPT.value,
        TranscriptStatus.TRANSCRIPTS_DISABLED.value,
    }:
        if run_stats is not None:
            run_stats.inc("transcripts_unavailable")
        logger.info(
            "Skipping video (previously no transcript): %s (ID: %s, status=%s, reason=%s)",
            video_title,
            video_id,
            existing_skip.get("status"),
            existing_skip.get("reason"),
        )
        return True

    logger.info(f"Processing video: {video_title} (ID: {video_id})")

    # Download transcript (differentiated result)
    download_started_at = datetime.now(timezone.utc)
    logger.info(
        "Transcript download start: video_id=%s channel=%s at=%s",
        video_id,
        channel_handle or channel_name,
        download_started_at.isoformat(),
    )
    dl = download_transcript_result(
        video_id,
        config.youtube.preferred_languages,
        cookie_file=config.api.youtube_cookies,
        proxy_settings=config.youtube.proxy,
        min_delay=config.youtube.min_delay_s,
        jitter=config.youtube.jitter_s,
        max_retries=config.youtube.max_retries,
        backoff_base=config.youtube.backoff_base_s,
        backoff_cap=config.youtube.backoff_cap_s,
    )
    download_finished_at = datetime.now(timezone.utc)
    download_duration_s = (download_finished_at - download_started_at).total_seconds()
    logger.info(
        "Transcript download finish: video_id=%s status=%s duration_s=%.2f at=%s",
        video_id,
        dl.status.value,
        download_duration_s,
        download_finished_at.isoformat(),
    )

    if dl.status == TranscriptStatus.BLOCKED:
        append_error_history(
            config,
            {
                "stage": "transcript_download",
                "status": dl.status.value,
                "reason": dl.reason,
                "error_type": dl.error_type,
                "error_message": dl.error_message,
                "video_id": video_id,
                "video_title": video_title,
                "channel_handle": channel_handle,
                "channel_name": channel_name,
            },
        )
        if run_stats is not None:
            run_stats.inc("transcript_blocks")
        logger.critical(
            "CRITICAL: YouTube blocked the request. Circuit breaker triggered. "
            "Aborting run to prevent further blocking."
        )
        # Wir geben False zurück, was in der Hauptschleife zum Abbruch führen sollte.
        # Zusätzlich könnten wir eine spezifische Exception werfen.
        raise RuntimeError(f"YouTube IP Block detected: {dl.error_message}")

    if not dl.is_success():
        append_error_history(
            config,
            {
                "stage": "transcript_download",
                "status": dl.status.value,
                "reason": dl.reason,
                "error_type": dl.error_type,
                "error_message": dl.error_message,
                "video_id": video_id,
                "video_title": video_title,
                "channel_handle": channel_handle,
                "channel_name": channel_name,
            },
        )
        if dl.status in {
            TranscriptStatus.NO_TRANSCRIPT,
            TranscriptStatus.TRANSCRIPTS_DISABLED,
        }:
            if run_stats is not None:
                run_stats.inc("transcripts_unavailable")
            logger.info(
                "No transcript for video: %s (ID: %s, status=%s, reason=%s)",
                video_title,
                video_id,
                dl.status.value,
                dl.reason,
            )

            # Persist skip state (separate from progress.json to avoid filesystem-sync deletion).
            channel_skipped[video_id] = {
                "status": dl.status.value,
                "reason": dl.reason,
                "marked_at": datetime.now(timezone.utc).isoformat(),
            }
            skipped_videos[channel_id] = channel_skipped
            atomic_save_skipped_videos(skipped_file, skipped_videos)

            # Optionally write metadata for the skipped case.
            if config.output.metadata:
                published_at = video.get("published_at")
                if isinstance(published_at, str):
                    published_date = datetime.fromisoformat(published_at).strftime(
                        "%Y-%m-%d"
                    )
                    published_at_iso = published_at
                elif hasattr(published_at, "strftime"):
                    published_date = published_at.strftime("%Y-%m-%d")
                    published_at_iso = published_at.isoformat()
                else:
                    published_date = datetime.now().strftime("%Y-%m-%d")
                    published_at_iso = str(published_at)

                if config.output.is_global_layout():
                    metadata_filepath = config.output.get_transcript_meta_path(
                        video_id, channel_handle=channel_handle
                    )
                else:
                    filename_base = generate_filename_base(
                        published_date, channel_name, video_id
                    )
                    metadata_filepath = transcripts_dir / f"{filename_base}_meta.json"
                metadata: Dict[str, Any] = {
                    "video_id": video_id,
                    "video_title": video_title,
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "published_at": published_at_iso,
                    "downloaded_at": datetime.now(timezone.utc).isoformat(),
                    **dl.to_metadata_fields(),
                }
                if channel_handle:
                    metadata["channel_handle_raw"] = channel_handle
                    metadata["channel_handle"] = channel_handle.lstrip("@").replace(
                        "/", "_"
                    ).replace("\\", "_")
                if save_metadata(metadata, metadata_filepath):
                    logger.info(f"Saved skipped metadata to {metadata_filepath}")
                else:
                    logger.error(
                        f"Failed to save skipped metadata to {metadata_filepath}"
                    )

            # Not a success, but handled (no warning spam in caller loop).
            return True

        # Real errors: don't mark processed/skipped, allow retry next run.
        logger.error(
            "Transcript download error for video: %s (ID: %s, error_type=%s)",
            video_title,
            video_id,
            dl.error_type,
        )
        if run_stats is not None:
            run_stats.inc("transcript_errors")
        record_pipeline_error(
            error_type="transcript_download", where="process_single_video"
        )
        return False

    transcript_text = dl.text or ""

    # Calculate token count
    token_count = calculate_token_count(
        transcript_text, model=config.analysis.llm.model
    )
    logger.info(f"Transcript token count: {token_count}")

    # Check if transcript exceeds token limit
    token_limit = config.analysis.llm.max_input_tokens or TRANSCRIPT_TOKEN_LIMIT
    if token_count > token_limit:
        logger.warning(
            f"Transcript exceeds token limit ({token_count} > {token_limit})"
        )

    # Search for keywords (can be empty list)
    keywords = config.youtube.keywords
    keywords_found, found_lines = search_keywords(transcript_text, keywords)
    if keywords:  # Only log if keywords were actually searched for
        if keywords_found:
            logger.info(f"Found keywords: {', '.join(keywords_found)}")
        else:
            logger.info("No keywords found in transcript")

    # Format published date for filename
    published_at = video["published_at"]
    if isinstance(published_at, str):
        published_date = datetime.fromisoformat(published_at).strftime("%Y-%m-%d")
    elif hasattr(published_at, "strftime"):
        published_date = published_at.strftime("%Y-%m-%d")
    else:
        # Fallback: use current date
        published_date = datetime.now().strftime("%Y-%m-%d")

    if config.output.is_global_layout():
        transcript_filepath = config.output.get_transcript_path(
            video_id, channel_handle=channel_handle
        )
        transcript_filename = transcript_filepath.name
    else:
        # Generate base filename
        filename_base = generate_filename_base(published_date, channel_name, video_id)
        transcript_filename = f"{filename_base}.txt"
        transcript_filepath = transcripts_dir / transcript_filename

    if not save_transcript(transcript_text, transcript_filepath):
        logger.error(f"Failed to save transcript to {transcript_filepath}")
        if run_stats is not None:
            run_stats.inc("transcript_errors")
        return False

    if run_stats is not None:
        run_stats.inc("transcripts_downloaded")
        if transcript_health not in {"ok", "missing"}:
            run_stats.inc("transcripts_healed")

    logger.info(f"Saved transcript to {transcript_filepath}")

    # Save metadata if enabled
    if config.output.metadata:
        metadata = _create_metadata(
            video,
            channel_id,
            channel_name,
            channel_handle,
            keywords_found,
            found_lines,
            token_count,
            transcript_filename,
            transcript_filepath,
        )

        # Record transcript status for downstream debugging.
        metadata.update(dl.to_metadata_fields())

        if config.output.is_global_layout():
            metadata_filepath = config.output.get_transcript_meta_path(
                video_id, channel_handle=channel_handle
            )
        else:
            metadata_filename = f"{filename_base}_meta.json"
            metadata_filepath = transcripts_dir / metadata_filename

        if save_metadata(metadata, metadata_filepath):
            logger.info(f"Saved metadata to {metadata_filepath}")
        else:
            logger.error(f"Failed to save metadata to {metadata_filepath}")

    # Optional: enqueue streaming summary job
    if stream_queue is not None:
        try:
            from transcript_ai_analysis.llm_runner import TranscriptRef
            from queue import Full

            channel_ns = (channel_handle or channel_name).lstrip("@").replace("/", "_").replace("\\", "_")
            metadata_path = None
            if config.output.metadata:
                metadata_path = str(metadata_filepath)

            ref = TranscriptRef(
                output_root=str(config.output.get_path()),
                channel_namespace=channel_ns,
                video_id=video_id,
                transcript_path=str(transcript_filepath),
                metadata_path=metadata_path,
            )
            stream_queue.put(ref, timeout=5)
            logger.debug("Queued transcript for streaming summary (video_id=%s)", video_id)
        except Full:
            logger.warning("Streaming summary queue full; skipping video_id=%s", video_id)
        except Exception as exc:
            logger.warning("Streaming summary enqueue failed (video_id=%s): %s", video_id, exc)

    # Mark video as processed
    channel_processed.append(video_id)
    processed_videos[channel_id] = channel_processed
    atomic_save_processed_videos(progress_file, processed_videos)
    logger.info(f"Marked video {video_id} as processed")

    # Create human-readable view (optional P1)
    try:
        _create_human_view(
            config=config,
            video_id=video_id,
            video_title=video_title,
            published_date=published_date,
            channel_name=channel_name,
            channel_handle=channel_handle,
            transcript_text=transcript_text,
        )
    except Exception as e:
        logger.warning(f"Failed to create human view: {e}")

    return True


def _create_human_view(
    config: Config,
    video_id: str,
    video_title: str,
    published_date: str,
    channel_name: str,
    channel_handle: Optional[str],
    transcript_text: str,
) -> None:
    """Creates a human-readable view of the transcript (organized by channel)."""
    if not config.output.is_global_layout():
        return

    # Slugify title and channel
    title_slug = re.sub(r"[^\w\-]", "_", video_title).strip("_")
    title_slug = re.sub(r"_+", "_", title_slug)
    
    handle_slug = (channel_handle or channel_name).lstrip("@").replace("/", "_").replace("\\", "_")
    
    view_dir = config.output.get_data_root() / "views" / "by_channel" / handle_slug
    view_dir.mkdir(parents=True, exist_ok=True)
    
    view_filename = f"{published_date}__{video_id}__{title_slug}.txt"
    view_path = view_dir / view_filename
    
    # We use a simple write for the view (not critical if it fails)
    view_path.write_text(transcript_text, encoding="utf-8")


def _create_metadata(
    video: Dict,
    channel_id: str,
    channel_name: str,
    channel_handle: Optional[str],
    keywords_found: List[str],
    found_lines: List[str],
    token_count: int,
    transcript_filename: str,
    transcript_filepath: Path,
) -> Dict:
    """Create metadata dictionary for a video."""
    # Format published_at for metadata
    published_at = video["published_at"]
    if isinstance(published_at, str):
        published_at_iso = published_at
    elif hasattr(published_at, "isoformat"):
        published_at_iso = published_at.isoformat()
    else:
        published_at_iso = str(published_at)

    metadata = {
        "video_id": video["id"],
        "video_title": video["title"],
        "channel_id": channel_id,
        "channel_name": channel_name,
        "published_at": published_at_iso,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "keywords_found": keywords_found,
        "found_lines": found_lines,
        "transcript_token_count": token_count,
        "transcript_filename": transcript_filename,
        "transcript_filepath": str(transcript_filepath),
    }

    if channel_handle:
        metadata["channel_handle_raw"] = channel_handle
        metadata["channel_handle"] = channel_handle.lstrip("@").replace("/", "_").replace(
            "\\", "_"
        )

    return metadata
