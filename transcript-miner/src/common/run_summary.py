from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import threading

from .path_utils import ensure_parent_exists


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class RunStats:
    videos_considered: int = 0
    transcripts_downloaded: int = 0
    transcripts_skipped_existing: int = 0
    transcripts_skipped_summary: int = 0
    transcripts_healed: int = 0
    transcripts_unavailable: int = 0
    transcript_blocks: int = 0
    transcript_errors: int = 0
    summaries_created: int = 0
    summaries_skipped_valid: int = 0
    summaries_healed: int = 0
    summaries_failed: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def inc(self, field_name: str, delta: int = 1) -> None:
        with self._lock:
            if not hasattr(self, field_name):
                raise AttributeError(f"Unknown counter: {field_name}")
            value = getattr(self, field_name)
            setattr(self, field_name, int(value) + delta)


def write_run_summary_md(
    *,
    out_path: Path,
    stats: RunStats,
    run_started_at: str,
    run_finished_at: str | None,
    config_path: Path | None,
    channel_count: int,
) -> None:
    finished_at = run_finished_at or _now_utc_iso()
    config_label = str(config_path) if config_path else "unknown"

    lines = [
        "# Run Summary",
        "",
        f"- Started (UTC): {run_started_at}",
        f"- Finished (UTC): {finished_at}",
        f"- Config: {config_label}",
        f"- Channels: {channel_count}",
        f"- Videos considered: {stats.videos_considered}",
        "",
        "## Transcripts",
        f"- Downloaded: {stats.transcripts_downloaded}",
        f"- Skipped (existing transcript): {stats.transcripts_skipped_existing}",
        f"- Skipped (summary exists): {stats.transcripts_skipped_summary}",
        f"- Healed (re-downloaded): {stats.transcripts_healed}",
        f"- Unavailable (no transcript/disabled): {stats.transcripts_unavailable}",
        f"- IP blocks (YouTube): {stats.transcript_blocks}",
        f"- Errors: {stats.transcript_errors}",
        "",
        "## Summaries",
        f"- Created: {stats.summaries_created}",
        f"- Skipped (valid existing): {stats.summaries_skipped_valid}",
        f"- Healed (regenerated): {stats.summaries_healed}",
        f"- Errors: {stats.summaries_failed}",
        "",
    ]

    ensure_parent_exists(out_path)
    out_path.write_text("\n".join(lines), encoding="utf-8")
