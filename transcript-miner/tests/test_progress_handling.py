from __future__ import annotations

import json
from pathlib import Path

from common.config_models import Config, OutputConfig
from transcript_miner.video_processor import (
    atomic_save_processed_videos,
    load_processed_videos,
    is_video_already_processed,
    sync_progress_with_filesystem,
)


def _write_progress(progress_file: Path, data: dict) -> None:
    progress_file.write_text(json.dumps(data), encoding="utf-8")


# --- Atomic Write Tests ---


def test_atomic_save_processed_videos_creates_backup_when_enabled(
    tmp_path: Path,
) -> None:
    progress = tmp_path / "progress.json"
    progress.write_text(json.dumps({"chan": ["old"]}), encoding="utf-8")

    new_data = {"chan": ["new1", "new2"]}
    ok = atomic_save_processed_videos(progress, new_data, create_backup=True)
    assert ok is True

    backup = tmp_path / "progress.bak"
    assert backup.exists()
    assert json.loads(backup.read_text(encoding="utf-8")) == {"chan": ["old"]}

    assert json.loads(progress.read_text(encoding="utf-8")) == new_data
    assert not (tmp_path / "progress.tmp").exists()


def test_atomic_save_processed_videos_does_not_create_backup_when_disabled(
    tmp_path: Path,
) -> None:
    progress = tmp_path / "progress.json"
    progress.write_text(json.dumps({"chan": ["old"]}), encoding="utf-8")

    new_data = {"chan": ["new"]}
    ok = atomic_save_processed_videos(progress, new_data, create_backup=False)
    assert ok is True

    backup = tmp_path / "progress.bak"
    assert not backup.exists()

    assert json.loads(progress.read_text(encoding="utf-8")) == new_data
    assert not (tmp_path / "progress.tmp").exists()


# --- Corruption Policy Tests ---


def test_load_processed_videos_restores_from_backup_on_corruption(
    tmp_path: Path,
) -> None:
    progress = tmp_path / "progress.json"
    backup = tmp_path / "progress.bak"

    # Corrupted primary file
    progress.write_text("{not: json", encoding="utf-8")

    # Valid backup
    backup.write_text(json.dumps({"chan": ["dQw4w9WgXcQ"]}), encoding="utf-8")

    restored = load_processed_videos(progress)
    assert restored == {"chan": ["dQw4w9WgXcQ"]}

    # progress.json should now be valid JSON and match restored
    reloaded = json.loads(progress.read_text(encoding="utf-8"))
    assert reloaded == restored

    # Corrupted file should be backed up for investigation.
    assert any(tmp_path.glob("progress.corrupted.*.json"))


def test_load_processed_videos_restores_when_missing_but_backup_exists(
    tmp_path: Path,
) -> None:
    progress = tmp_path / "progress.json"
    backup = tmp_path / "progress.bak"

    backup.write_text(json.dumps({"chan": ["dQw4w9WgXcQ"]}), encoding="utf-8")
    assert not progress.exists()

    restored = load_processed_videos(progress)
    assert restored == {"chan": ["dQw4w9WgXcQ"]}
    assert progress.exists()


# --- Dedup Tests ---


def test_is_video_already_processed_detects_existing_transcript_file(
    tmp_path: Path,
) -> None:
    """Regression: file-existence check must match real filename pattern.

    Real transcripts are saved as `..._{video_id}.txt`, not `{video_id}.txt`.
    """
    video_id = "dQw4w9WgXcQ"  # 11 chars, matches YouTube ID format
    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir()

    (transcripts_dir / f"2025-01-01_channel_{video_id}.txt").write_text(
        "hi", encoding="utf-8"
    )

    assert is_video_already_processed(
        video_id, channel_processed=[], transcripts_dir=transcripts_dir
    )


# --- Sync Tests ---


def test_sync_progress_adds_missing_ids_from_filesystem_deterministically(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    transcripts_dir = out / "1_transcripts"
    transcripts_dir.mkdir(parents=True)
    progress_file = out / "progress.json"
    channel_id = "chan"

    config = Config(output=OutputConfig(root_path=out, use_channel_subfolder=False))

    # Two valid transcript files (glob order is not guaranteed), plus one unrelated file.
    id_a = "aaaaaaaaaaa"  # 11 chars
    id_b = "bbbbbbbbbbb"  # 11 chars
    (transcripts_dir / f"2025-01-01_chan_{id_b}.txt").write_text("x", encoding="utf-8")
    (transcripts_dir / f"2025-01-02_chan_{id_a}.txt").write_text("x", encoding="utf-8")
    (transcripts_dir / "README.txt").write_text("ignore", encoding="utf-8")

    # Start with empty progress file.
    synced = sync_progress_with_filesystem(
        transcripts_dir, progress_file, channel_id, config, channel_handle=None
    )
    assert synced[channel_id] == [id_a, id_b]

    # Ensure it's persisted deterministically.
    reloaded = load_processed_videos(progress_file)
    assert reloaded[channel_id] == [id_a, id_b]


def test_sync_progress_removes_orphaned_ids_from_progress(tmp_path: Path) -> None:
    out = tmp_path / "out"
    transcripts_dir = out / "1_transcripts"
    transcripts_dir.mkdir(parents=True)
    progress_file = out / "progress.json"
    channel_id = "chan"

    config = Config(output=OutputConfig(root_path=out, use_channel_subfolder=False))

    existing_id = "dQw4w9WgXcQ"
    orphan_id = "ccccccccccc"

    (transcripts_dir / f"2025-01-01_chan_{existing_id}.txt").write_text(
        "x", encoding="utf-8"
    )
    _write_progress(progress_file, {channel_id: [existing_id, orphan_id]})

    synced = sync_progress_with_filesystem(
        transcripts_dir, progress_file, channel_id, config, channel_handle=None
    )
    assert synced[channel_id] == [existing_id]

    reloaded = load_processed_videos(progress_file)
    assert reloaded[channel_id] == [existing_id]


def test_sync_progress_with_filesystem_treats_corrupt_progress_as_empty_and_recovers(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    transcripts_dir = out / "1_transcripts"
    transcripts_dir.mkdir(parents=True)
    progress_file = out / "progress.json"
    channel_id = "chan"

    config = Config(output=OutputConfig(root_path=out, use_channel_subfolder=False))

    existing_id = "dQw4w9WgXcQ"
    (transcripts_dir / f"2025-01-01_chan_{existing_id}.txt").write_text(
        "x", encoding="utf-8"
    )

    # Corrupt progress file.
    progress_file.write_text("{not: json", encoding="utf-8")

    synced = sync_progress_with_filesystem(
        transcripts_dir, progress_file, channel_id, config, channel_handle=None
    )
    assert synced[channel_id] == [existing_id]

    # Loader should now succeed (restored/rewritten).
    reloaded = load_processed_videos(progress_file)
    assert reloaded[channel_id] == [existing_id]
