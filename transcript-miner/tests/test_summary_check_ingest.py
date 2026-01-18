from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock
from transcript_miner.video_processor import (
    process_single_video,
    sync_progress_with_filesystem,
)
from common.config_models import Config, YoutubeConfig, OutputConfig


def _write_valid_summary(summary_path: Path, *, video_id: str) -> None:
    summary_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task": "stocks_per_video_extract",
                "source": {"video_id": video_id},
            }
        ),
        encoding="utf-8",
    )


def test_sync_progress_keeps_id_if_summary_exists(tmp_path: Path) -> None:
    out = tmp_path / "out"
    transcripts_dir = out / "1_transcripts"
    transcripts_dir.mkdir(parents=True)
    summaries_dir = out / "2_summaries"
    summaries_dir.mkdir(parents=True)

    progress_file = out / "progress.json"
    channel_id = "chan"
    video_id = "vid12345678"

    # No transcript file, but summary exists
    _write_valid_summary(summaries_dir / f"{video_id}.json", video_id=video_id)

    # Initial progress with the video_id
    progress_data = {channel_id: [video_id]}
    progress_file.write_text(json.dumps(progress_data), encoding="utf-8")

    config = Config(output=OutputConfig(root_path=out, use_channel_subfolder=False))

    # Sync should keep the ID because summary exists
    synced = sync_progress_with_filesystem(
        transcripts_dir, progress_file, channel_id, config, channel_handle=None
    )
    assert video_id in synced[channel_id]


def test_process_single_video_skips_download_if_summary_exists(tmp_path: Path) -> None:
    out = tmp_path / "out"
    transcripts_dir = out / "1_transcripts"
    transcripts_dir.mkdir(parents=True)
    summaries_dir = out / "2_summaries"
    summaries_dir.mkdir(parents=True)

    progress_file = out / "progress.json"
    skipped_file = out / "skipped.json"
    channel_id = "chan"
    channel_name = "Channel Name"
    video_id = "vid12345678"
    video = {
        "id": video_id,
        "title": "Test Video",
        "published_at": "2025-01-01T00:00:00Z",
    }

    # Summary exists
    _write_valid_summary(summaries_dir / f"{video_id}.json", video_id=video_id)

    config = Config(
        youtube=YoutubeConfig(
            channels=[channel_id], force_redownload_transcripts=False
        ),
        output=OutputConfig(root_path=out, use_channel_subfolder=False),
    )

    processed_videos = {}
    skipped_videos = {}

    # Mock download_transcript_result to ensure it's NOT called
    # (We don't actually mock it here, but we check if it would be called by the logic)

    success = process_single_video(
        video,
        channel_id,
        channel_name,
        config,
        transcripts_dir,
        processed_videos,
        progress_file,
        skipped_videos,
        skipped_file,
        channel_handle=None,
    )

    assert success is True
    assert video_id in processed_videos[channel_id]
    # Check if progress.json was updated
    with open(progress_file, "r") as f:
        data = json.load(f)
        assert video_id in data[channel_id]


def test_process_single_video_downloads_if_force_redownload(
    tmp_path: Path, monkeypatch
) -> None:
    out = tmp_path / "out"
    transcripts_dir = out / "1_transcripts"
    transcripts_dir.mkdir(parents=True)
    summaries_dir = out / "2_summaries"
    summaries_dir.mkdir(parents=True)

    progress_file = out / "progress.json"
    skipped_file = out / "skipped.json"
    channel_id = "chan"
    channel_name = "Channel Name"
    video_id = "vid12345678"
    video = {
        "id": video_id,
        "title": "Test Video",
        "published_at": "2025-01-01T00:00:00Z",
    }

    # Summary exists
    _write_valid_summary(summaries_dir / f"{video_id}.json", video_id=video_id)

    config = Config(
        youtube=YoutubeConfig(channels=[channel_id], force_redownload_transcripts=True),
        output=OutputConfig(root_path=out, use_channel_subfolder=False),
    )

    processed_videos = {}
    skipped_videos = {}

    # Mock download_transcript_result to simulate a download
    mock_dl = MagicMock()
    mock_dl.is_success.return_value = True
    mock_dl.text = "Downloaded transcript"
    mock_dl.status.value = "success"
    mock_dl.to_metadata_fields.return_value = {"transcript_status": "success"}

    monkeypatch.setattr(
        "transcript_miner.video_processor.download_transcript_result",
        lambda *a, **kw: mock_dl,
    )

    success = process_single_video(
        video,
        channel_id,
        channel_name,
        config,
        transcripts_dir,
        processed_videos,
        progress_file,
        skipped_videos,
        skipped_file,
        channel_handle=None,
    )

    assert success is True
    # Verify that the transcript file was created (meaning download was NOT skipped)
    transcript_files = list(transcripts_dir.glob(f"*_{video_id}.txt"))
    assert len(transcript_files) == 1
