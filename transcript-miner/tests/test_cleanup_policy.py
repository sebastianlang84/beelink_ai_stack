from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from common.config_models import Config, OutputConfig
from common.transcript_retention import cleanup_transcripts
from transcript_miner.video_processor import (
    atomic_save_processed_videos,
    cleanup_old_outputs,
    load_processed_videos,
    sync_progress_with_filesystem,
)


def _touch_with_mtime(path: Path, *, mtime: float) -> None:
    path.write_text("x", encoding="utf-8")
    path.chmod(0o644)
    # Set both atime+mtime.
    os.utime(path, (mtime, mtime))


# --- Transcript Retention Cleanup (Common) ---


def test_cleanup_transcripts_deletes_only_old_files_and_prunes_empty_dirs(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"

    # Create 1_transcripts structure.
    v1_dir = output_root / "1_transcripts" / "channels" / "alpha" / "videos" / "v1"
    v1_dir.mkdir(parents=True)
    v1_file = v1_dir / "raw_transcript.txt"
    v1_file.write_text("old content")

    v2_dir = output_root / "1_transcripts" / "channels" / "alpha" / "videos" / "v2"
    v2_dir.mkdir(parents=True)
    v2_file = v2_dir / "raw_transcript.txt"
    v2_file.write_text("new content")

    # Set mtimes.
    now = datetime.now(timezone.utc)
    old_ts = now.timestamp() - (31 * 24 * 60 * 60)
    new_ts = now.timestamp() - (1 * 24 * 60 * 60)

    os.utime(v1_file, (old_ts, old_ts))
    os.utime(v2_file, (new_ts, new_ts))

    res = cleanup_transcripts(output_root=output_root, retention_days=30, now=now)
    assert res.deleted_files >= 1

    assert not v1_file.exists()
    assert v2_file.exists()

    # Empty directory of v1 should be pruned (best-effort).
    assert not (
        output_root / "1_transcripts" / "channels" / "alpha" / "videos" / "v1"
    ).exists()
    assert (
        output_root / "1_transcripts" / "channels" / "alpha" / "videos" / "v2"
    ).exists()


# --- Output Retention Cleanup (Video Processor) ---


def test_cleanup_old_outputs_deletes_old_transcripts_and_meta_and_syncs_progress(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    transcripts_dir = out / "1_transcripts"
    transcripts_dir.mkdir(parents=True)
    progress_file = out / "progress.json"

    channel_id = "chan"
    old_id = "dQw4w9WgXcQ"
    new_id = "aaaaaaaaaaa"  # 11 chars

    config = Config(output=OutputConfig(root_path=out, use_channel_subfolder=False))

    # Files
    old_txt = transcripts_dir / f"2025-01-01_chan_{old_id}.txt"
    old_meta = transcripts_dir / f"2025-01-01_chan_{old_id}_meta.json"
    new_txt = transcripts_dir / f"2025-01-02_chan_{new_id}.txt"

    now = datetime(2025, 1, 10, tzinfo=timezone.utc)
    old_mtime = now.timestamp() - (31 * 24 * 60 * 60)
    new_mtime = now.timestamp() - (1 * 24 * 60 * 60)
    _touch_with_mtime(old_txt, mtime=old_mtime)
    _touch_with_mtime(
        old_meta, mtime=new_mtime
    )  # meta newer, still should be removed with transcript
    _touch_with_mtime(new_txt, mtime=new_mtime)

    # progress contains both IDs initially
    atomic_save_processed_videos(progress_file, {channel_id: [old_id, new_id]})
    assert load_processed_videos(progress_file)[channel_id] == [old_id, new_id]

    # Cleanup with 30 days retention
    res = cleanup_old_outputs(transcripts_dir, retention_days=30, now=now)
    assert res.deleted_total >= 1
    assert not old_txt.exists()
    assert not old_meta.exists()
    assert new_txt.exists()

    # Sync should remove old_id from progress but keep new_id
    synced = sync_progress_with_filesystem(
        transcripts_dir, progress_file, channel_id, config
    )
    assert synced[channel_id] == [new_id]


def test_cleanup_old_outputs_can_be_disabled(tmp_path: Path) -> None:
    transcripts_dir = tmp_path / "1_transcripts"
    transcripts_dir.mkdir(parents=True)
    f = transcripts_dir / "2025-01-01_chan_dQw4w9WgXcQ.txt"
    f.write_text("x", encoding="utf-8")

    res = cleanup_old_outputs(transcripts_dir, retention_days=None)
    assert res.deleted_total == 0
    assert f.exists()
