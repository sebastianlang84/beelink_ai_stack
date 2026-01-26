from __future__ import annotations

import json
from pathlib import Path

from common.config_models import OutputConfig
from transcript_ai_analysis.aggregation_runner import (
    detect_summary_coverage_gaps,
    run_aggregation,
)


def test_detect_summary_coverage_gaps_reports_missing() -> None:
    transcripts = {"chan_a": {"v1", "v2"}, "chan_b": {"v3"}}
    summaries = {"chan_a": {"v1"}}

    gaps = detect_summary_coverage_gaps(transcripts, summaries)

    assert gaps == {"chan_a": ["v2"], "chan_b": ["v3"]}


def test_run_aggregation_fails_on_summary_gap(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    topic_root = output_root / "investing"
    summaries_dir = output_root / "data" / "summaries" / "by_video_id"
    summaries_dir.mkdir(parents=True, exist_ok=True)

    index_dir = tmp_path / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    transcripts_jsonl = index_dir / "transcripts.jsonl"
    transcripts_jsonl.write_text(
        json.dumps(
            {
                "video_id": "aaaaaaaaaaa",
                "channel_namespace": "chan_a",
                "transcript_path": str(tmp_path / "t.txt"),
                "published_date": "2025-01-01",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rc = run_aggregation(
        profile_root=topic_root,
        index_dir=index_dir,
        output=OutputConfig(root_path=topic_root, use_channel_subfolder=False),
        report_lang="de",
    )
    assert rc == 1
