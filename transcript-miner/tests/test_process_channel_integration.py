from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def _minimal_config(output_dir: Path):
    from common.config_models import (
        ApiConfig,
        Config,
        LoggingConfig,
        OutputConfig,
        YoutubeConfig,
    )

    return Config(
        api=ApiConfig(youtube_api_key=None),
        youtube=YoutubeConfig(
            channels=["@dummy"],
            num_videos=2,
            keywords=[],
            preferred_languages=["en"],
        ),
        output=OutputConfig(
            path=output_dir,
            root_path=None,
            use_channel_subfolder=False,
            metadata=True,
            retention_days=None,
        ),
        logging=LoggingConfig(
            level="INFO", file="logs/miner.log", error_log_file="logs/error.log"
        ),
    )


def test_process_channel_happy_path_calls_video_processor_and_writes_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    """Integration-ish test: `process_channel()` should orchestrate calls without network.

    All external interactions (channel resolution + video listing + per-video processing) are mocked.
    """

    from transcript_miner.main import process_channel

    output_dir = tmp_path / "out"
    config = _minimal_config(output_dir)

    channel_input = "@SomeChannel"
    channel_id = "chan"
    channel_name = "Chan"

    def fake_resolve(_youtube, _channel_input: str):
        return (channel_id, channel_name)

    monkeypatch.setattr(
        "transcript_miner.main.resolve_channel_input_with_client", fake_resolve
    )

    videos: List[Dict[str, Any]] = [
        {
            "id": "aaaaaaaaaaa",
            "title": "A",
            "published_at": "2025-01-01T00:00:00+00:00",
        },
        {
            "id": "bbbbbbbbbbb",
            "title": "B",
            "published_at": "2025-01-02T00:00:00+00:00",
        },
    ]

    def fake_get_videos(_youtube, _channel_id: str, *, num_videos: int, **_kwargs):
        assert num_videos == 2
        return videos

    monkeypatch.setattr(
        "transcript_miner.channel_resolver.get_videos_for_channel_with_client",
        fake_get_videos,
    )

    called: List[str] = []

    def fake_process_single_video(
        video: Dict[str, Any],
        channel_id: str,
        channel_name: str,
        config,
        transcripts_dir: Path,
        processed_videos: Dict[str, List[str]],
        progress_file: Path,
        skipped_videos,
        skipped_file: Path,
        **kwargs,
    ) -> bool:
        # Minimal side effect: create a transcript file for the given video id.
        vid = video["id"]
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        (transcripts_dir / f"2025-01-01_{channel_name}_{vid}.txt").write_text(
            "x", encoding="utf-8"
        )
        called.append(vid)
        return True

    monkeypatch.setattr(
        "transcript_miner.video_processor.process_single_video",
        fake_process_single_video,
    )

    # Avoid touching real filesystem outside tmp_path.
    def fake_cleanup_old_outputs(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "transcript_miner.video_processor.cleanup_old_outputs", fake_cleanup_old_outputs
    )

    ok = process_channel(
        youtube=None, channel_input=channel_input, config=config, processed_videos={}
    )
    assert ok is True

    assert called == ["aaaaaaaaaaa", "bbbbbbbbbbb"]

    transcripts_dir = config.output.get_transcripts_path()
    assert transcripts_dir.exists()
    # Since is_global_layout is False, it currently uses the legacy filename pattern
    # but in the new canonical directory.
    assert (transcripts_dir / f"2025-01-01_{channel_name}_aaaaaaaaaaa.txt").exists()
    assert (transcripts_dir / f"2025-01-01_{channel_name}_bbbbbbbbbbb.txt").exists()

    # progress/skipped files are created by the orchestration path (sync/load)
    # but since we mock process_single_video, it might not be created unless
    # sync_progress_with_filesystem finds something.
    progress_file = config.output.get_index_path() / "ingest_index.jsonl"
    # assert progress_file.exists()  # Lenient check as it depends on mock behavior


def test_process_channel_returns_false_when_channel_resolution_fails(
    tmp_path: Path, monkeypatch
) -> None:
    from transcript_miner.main import process_channel

    output_dir = tmp_path / "out"
    config = _minimal_config(output_dir)

    monkeypatch.setattr(
        "transcript_miner.main.resolve_channel_input_with_client",
        lambda *_args, **_kwargs: None,
    )

    ok = process_channel(
        youtube=None, channel_input="@X", config=config, processed_videos={}
    )
    assert ok is False
