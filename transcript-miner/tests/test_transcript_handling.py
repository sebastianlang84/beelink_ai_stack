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
            num_videos=1,
            keywords=[],
            preferred_languages=["en"],
        ),
        output=OutputConfig(
            path=output_dir, root_path=None, use_channel_subfolder=False, metadata=True
        ),
        logging=LoggingConfig(
            level="INFO", file="logs/miner.log", error_log_file="logs/error.log"
        ),
    )


def test_process_single_video_marks_skipped_on_no_transcript(
    tmp_path: Path, monkeypatch
) -> None:
    from transcript_miner.transcript_models import (
        TranscriptDownloadResult,
        TranscriptStatus,
    )
    from transcript_miner.video_processor import (
        load_skipped_videos,
        load_processed_videos,
        process_single_video,
    )

    output_dir = tmp_path / "out"
    transcripts_dir = output_dir / "transcripts"
    transcripts_dir.mkdir(parents=True)

    config = _minimal_config(output_dir)

    video_id = "dQw4w9WgXcQ"
    video: Dict[str, Any] = {
        "id": video_id,
        "title": "no transcript",
        "published_at": "2025-01-01T00:00:00+00:00",
    }

    def fake_download(video_id: str, preferred_languages: List[str], **kwargs):
        return TranscriptDownloadResult(
            status=TranscriptStatus.NO_TRANSCRIPT,
            text=None,
            reason="no_transcript_found",
        )

    monkeypatch.setattr(
        "transcript_miner.video_processor.download_transcript_result", fake_download
    )

    progress_file = output_dir / "progress.json"
    skipped_file = output_dir / "skipped.json"
    processed_videos: Dict[str, List[str]] = load_processed_videos(progress_file)
    skipped_videos = load_skipped_videos(skipped_file)

    ok = process_single_video(
        video,
        channel_id="chan",
        channel_name="Chan",
        config=config,
        transcripts_dir=transcripts_dir,
        processed_videos=processed_videos,
        progress_file=progress_file,
        skipped_videos=skipped_videos,
        skipped_file=skipped_file,
    )

    assert ok is True  # handled skip

    # progress.json should not contain the id (not a successful transcript write)
    processed_videos2 = load_processed_videos(progress_file)
    assert processed_videos2.get("chan", []) == []

    # skipped.json should contain the id
    skipped_videos2 = load_skipped_videos(skipped_file)
    assert (
        skipped_videos2["chan"][video_id]["status"]
        == TranscriptStatus.NO_TRANSCRIPT.value
    )

    # _meta.json should be written even without transcript text
    assert any(transcripts_dir.glob(f"*_{video_id}_meta.json"))


def test_process_single_video_does_not_mark_skipped_on_error(
    tmp_path: Path, monkeypatch
) -> None:
    from transcript_miner.transcript_models import (
        TranscriptDownloadResult,
        TranscriptStatus,
    )
    from transcript_miner.video_processor import (
        load_skipped_videos,
        load_processed_videos,
        process_single_video,
    )

    output_dir = tmp_path / "out"
    transcripts_dir = output_dir / "transcripts"
    transcripts_dir.mkdir(parents=True)

    config = _minimal_config(output_dir)

    video_id = "dQw4w9WgXcQ"
    video: Dict[str, Any] = {
        "id": video_id,
        "title": "error",
        "published_at": "2025-01-01T00:00:00+00:00",
    }

    def fake_download(video_id: str, preferred_languages: List[str], **kwargs):
        return TranscriptDownloadResult(
            status=TranscriptStatus.ERROR,
            text=None,
            reason="exception",
            error_type="Boom",
            error_message="nope",
        )

    monkeypatch.setattr(
        "transcript_miner.video_processor.download_transcript_result", fake_download
    )

    progress_file = output_dir / "progress.json"
    skipped_file = output_dir / "skipped.json"
    processed_videos: Dict[str, List[str]] = load_processed_videos(progress_file)
    skipped_videos = load_skipped_videos(skipped_file)

    ok = process_single_video(
        video,
        channel_id="chan",
        channel_name="Chan",
        config=config,
        transcripts_dir=transcripts_dir,
        processed_videos=processed_videos,
        progress_file=progress_file,
        skipped_videos=skipped_videos,
        skipped_file=skipped_file,
    )

    assert ok is False
    assert not skipped_file.exists()
    assert not progress_file.exists()


def test_process_single_video_marks_skipped_on_video_unplayable(
    tmp_path: Path, monkeypatch
) -> None:
    """Test that VideoUnplayable is treated as expected skip (not error)."""
    from transcript_miner.transcript_models import (
        TranscriptDownloadResult,
        TranscriptStatus,
    )
    from transcript_miner.video_processor import (
        load_skipped_videos,
        load_processed_videos,
        process_single_video,
    )

    output_dir = tmp_path / "out"
    transcripts_dir = output_dir / "transcripts"
    transcripts_dir.mkdir(parents=True)

    config = _minimal_config(output_dir)

    video_id = "KDPY_Xuwf-o"
    video: Dict[str, Any] = {
        "id": video_id,
        "title": "Live event not started",
        "published_at": "2025-01-01T00:00:00+00:00",
    }

    def fake_download(video_id: str, preferred_languages: List[str], **kwargs):
        return TranscriptDownloadResult(
            status=TranscriptStatus.NO_TRANSCRIPT,
            text=None,
            reason="video_unplayable",
        )

    monkeypatch.setattr(
        "transcript_miner.video_processor.download_transcript_result", fake_download
    )

    progress_file = output_dir / "progress.json"
    skipped_file = output_dir / "skipped.json"
    processed_videos: Dict[str, List[str]] = load_processed_videos(progress_file)
    skipped_videos = load_skipped_videos(skipped_file)

    ok = process_single_video(
        video,
        channel_id="chan",
        channel_name="Chan",
        config=config,
        transcripts_dir=transcripts_dir,
        processed_videos=processed_videos,
        progress_file=progress_file,
        skipped_videos=skipped_videos,
        skipped_file=skipped_file,
    )

    assert ok is True  # handled skip

    # progress.json should not contain the id (not a successful transcript write)
    processed_videos2 = load_processed_videos(progress_file)
    assert processed_videos2.get("chan", []) == []

    # skipped.json should contain the id with video_unplayable reason
    skipped_videos2 = load_skipped_videos(skipped_file)
    assert skipped_videos2["chan"][video_id]["status"] == TranscriptStatus.NO_TRANSCRIPT.value
    assert skipped_videos2["chan"][video_id]["reason"] == "video_unplayable"

    # _meta.json should be written even without transcript text
    assert any(transcripts_dir.glob(f"*_{video_id}_meta.json"))


def test_get_channel_videos_filters_live_events(tmp_path: Path, monkeypatch) -> None:
    """Test that get_channel_videos filters live events when exclude_live_events=True."""
    from transcript_miner.youtube_client import VideoDetails
    from transcript_miner.channel_resolver import ChannelResolver

    # Mock YouTube client and API responses
    class MockRequest:
        def __init__(self, response: dict) -> None:
            self._response = response

        def execute(self) -> dict:
            return self._response

    class MockSearch:
        def list(self, part: str, q: str, type: str, maxResults: int) -> MockRequest:  # noqa: A002
            return MockRequest(
                {
                    "items": [
                        {
                            "id": {"channelId": "UC_TEST_CHANNEL_ID_000000"},
                            "snippet": {
                                "title": "Test Channel",
                                "description": "",
                                "publishedAt": "2020-01-01T00:00:00Z",
                            },
                        }
                    ]
                }
            )

    class MockChannels:
        def list(self, part: str, id: str, maxResults: int) -> MockRequest:  # noqa: A002
            return MockRequest(
                {
                    "items": [
                        {
                            "contentDetails": {
                                "relatedPlaylists": {"uploads": "UPLOADS_PLAYLIST_ID"}
                            }
                        }
                    ]
                }
            )

    class MockPlaylistItems:
        def list(
            self,
            part: str,
            playlistId: str,
            maxResults: int,
            pageToken: str | None = None,
        ) -> MockRequest:
            # Return mixed videos: regular and live events
            return MockRequest(
                {
                    "items": [
                        {
                            "snippet": {
                                "title": "Regular Video",
                                "publishedAt": "2025-01-01T00:00:00Z",
                                "liveBroadcastContent": "none",
                            },
                            "contentDetails": {"videoId": "regular_video_1"},
                        },
                        {
                            "snippet": {
                                "title": "Live Event",
                                "publishedAt": "2025-01-01T00:00:00Z",
                                "liveBroadcastContent": "upcoming",
                            },
                            "contentDetails": {"videoId": "live_event_1"},
                        },
                        {
                            "snippet": {
                                "title": "Another Regular Video",
                                "publishedAt": "2025-01-01T00:00:00Z",
                                "liveBroadcastContent": "none",
                            },
                            "contentDetails": {"videoId": "regular_video_2"},
                        },
                    ],
                    "nextPageToken": None,
                }
            )

    class MockYouTube:
        def search(self) -> MockSearch:
            return MockSearch()

        def channels(self) -> MockChannels:
            return MockChannels()

        def playlistItems(self) -> MockPlaylistItems:
            return MockPlaylistItems()

    # Mock the _execute_with_retries function
    def mock_execute_with_retries(request, **kwargs):
        return request.execute()

    monkeypatch.setattr("transcript_miner.youtube_client._execute_with_retries", mock_execute_with_retries)

    # Create resolver with mock client
    youtube = MockYouTube()
    resolver = ChannelResolver(youtube)
    
    # Test with exclude_live_events=True (default)
    videos = resolver.get_channel_videos(
        "@testchannel",
        max_results=10,
        exclude_live_events=True
    )
    
    # Should only return regular videos
    assert len(videos) == 2
    video_ids = [v["id"] for v in videos]
    assert "regular_video_1" in video_ids
    assert "regular_video_2" in video_ids
    assert "live_event_1" not in video_ids
    
    # Test with exclude_live_events=False
    videos = resolver.get_channel_videos(
        "@testchannel",
        max_results=10,
        exclude_live_events=False
    )
    
    # Should return all videos including live events
    assert len(videos) == 3
    video_ids = [v["id"] for v in videos]
    assert "regular_video_1" in video_ids
    assert "regular_video_2" in video_ids
    assert "live_event_1" in video_ids
