from pathlib import Path

from common.config_models import OutputConfig


def test_output_get_path_prefers_root_path_when_set(tmp_path: Path) -> None:
    cfg = OutputConfig(path=tmp_path / "legacy", root_path=tmp_path / "root")

    # get_path now always returns the root path, channel subfolders are handled
    # in get_transcripts_path etc.
    assert cfg.get_path(channel_handle="@SomeChannel") == (tmp_path / "root")


def test_output_get_path_uses_legacy_path_when_root_path_missing(
    tmp_path: Path,
) -> None:
    cfg = OutputConfig(path=tmp_path / "legacy", root_path=None)
    assert cfg.get_path(channel_handle="@SomeChannel") == (tmp_path / "legacy")


def test_output_get_transcripts_path_channel_subfolder_when_enabled(
    tmp_path: Path,
) -> None:
    cfg = OutputConfig(
        path=tmp_path / "legacy",
        root_path=tmp_path / "root",
        use_channel_subfolder=True,
    )
    # PRD: channel subfolder is UNDER 1_transcripts
    assert cfg.get_transcripts_path(channel_handle="@Some/Channel") == (
        tmp_path / "root" / "1_transcripts" / "Some_Channel"
    )


def test_output_global_layout_paths(tmp_path: Path) -> None:
    cfg = OutputConfig(**{"global": tmp_path / "out", "topic": "investing"})

    assert cfg.get_transcripts_path() == (
        tmp_path / "out" / "data" / "transcripts" / "by_video_id"
    )
    assert cfg.get_summaries_path() == (
        tmp_path / "out" / "data" / "summaries" / "by_video_id"
    )
    assert cfg.get_reports_path() == (tmp_path / "out" / "reports" / "investing")
    assert cfg.get_history_root() == (tmp_path / "out" / "history" / "investing")
    assert cfg.get_index_path() == (
        tmp_path / "out" / "data" / "indexes" / "investing" / "current"
    )
