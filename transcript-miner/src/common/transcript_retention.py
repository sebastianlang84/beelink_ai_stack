from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

"""Retention-Cleanup für Transkripte gemäß PRD."""


@dataclass(frozen=True)
class TranscriptCleanupResult:
    deleted_files: int
    deleted_dirs: int


def cleanup_transcripts(
    *, output_root: Path, retention_days: int | None = 30, now: datetime | None = None
) -> TranscriptCleanupResult:
    """Delete transcripts older than `retention_days`.

    Determinismus:
    - Für ein gegebenes `now` ist das Ergebnis deterministisch.
    - Es wird die File-mtime (POSIX timestamp) als Alter herangezogen.

    Args:
        output_root: Root-Verzeichnis der Config (entspricht `output.root_path`).
        retention_days: Schwelle in Tagen (PRD: 30). None deaktiviert Cleanup.
        now: Optionales "jetzt" (für Tests).
    """

    if retention_days is None:
        return TranscriptCleanupResult(deleted_files=0, deleted_dirs=0)
    if retention_days < 0:
        raise ValueError("retention_days must be >= 0")

    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)

    cutoff_ts = now_dt.timestamp() - (retention_days * 24 * 60 * 60)
    transcripts_dir = output_root / "data" / "transcripts" / "by_video_id"
    if not transcripts_dir.exists():
        transcripts_dir = output_root / "1_transcripts"
    if not transcripts_dir.exists():
        return TranscriptCleanupResult(deleted_files=0, deleted_dirs=0)

    deleted_files = 0
    deleted_dirs = 0

    # 1) Delete old files.
    for p in sorted(x for x in transcripts_dir.rglob("*") if x.is_file()):
        try:
            st = p.stat()
        except FileNotFoundError:
            continue
        if st.st_mtime >= cutoff_ts:
            continue
        try:
            p.unlink(missing_ok=True)
            deleted_files += 1
        except Exception:
            # Best-effort cleanup; must not crash a run.
            continue

    # 2) Prune empty dirs bottom-up (deterministic order).
    for d in sorted(
        (x for x in transcripts_dir.rglob("*") if x.is_dir()), reverse=True
    ):
        try:
            if any(d.iterdir()):
                continue
            d.rmdir()
            deleted_dirs += 1
        except Exception:
            continue

    return TranscriptCleanupResult(
        deleted_files=deleted_files, deleted_dirs=deleted_dirs
    )
