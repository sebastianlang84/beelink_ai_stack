from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from transcript_miner.transcript_index.runner import write_analysis_index


def test_analysis_runner_writes_manifest_and_index() -> None:
    with TemporaryDirectory() as d:
        tmp = Path(d)

        # Simulate a single-channel output dir (legacy output.path)
        out = tmp / "out"
        transcripts_dir = out / "transcripts"
        transcripts_dir.mkdir(parents=True)

        txt = transcripts_dir / "2025-12-24_TestChannel_abcdefghijk.txt"
        txt.write_text("hello transcript", encoding="utf-8")

        meta = transcripts_dir / "2025-12-24_TestChannel_abcdefghijk_meta.json"
        meta.write_text(
            json.dumps(
                {
                    "video_id": "abcdefghijk",
                    "channel_name": "TestChannel",
                    "video_title": "T1",
                    "transcript_status": "success",
                }
            ),
            encoding="utf-8",
        )

        analysis_dir = tmp / "analysis"
        rc = write_analysis_index(output_dir=analysis_dir, input_roots=[out])
        assert rc == 0

        assert (analysis_dir / "manifest.json").exists()
        assert (analysis_dir / "transcripts.jsonl").exists()
        assert (analysis_dir / "audit.jsonl").exists()

        manifest = json.loads(
            (analysis_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["schema_version"] == 1
        assert manifest["transcript_count"] == 1
        assert manifest["unique_video_count"] == 1

        lines = (
            (analysis_dir / "transcripts.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        assert len(lines) == 1

        row = json.loads(lines[0])
        assert row["video_id"] == "abcdefghijk"
        assert row["channel_namespace"] == "default"


def test_analysis_runner_detects_channel_namespace_from_subfolder() -> None:
    with TemporaryDirectory() as d:
        tmp = Path(d)

        out_root = tmp / "out_root"
        chan_dir = out_root / "my_channel"
        transcripts_dir = chan_dir / "transcripts"
        transcripts_dir.mkdir(parents=True)

        (transcripts_dir / "2025-12-24_TestChannel_abcdefghijk.txt").write_text(
            "hello transcript", encoding="utf-8"
        )

        analysis_dir = tmp / "analysis"
        rc = write_analysis_index(output_dir=analysis_dir, input_roots=[out_root])
        assert rc == 0

        lines = (
            (analysis_dir / "transcripts.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["channel_namespace"] == "my_channel"


def test_analysis_runner_reports_error_for_invalid_root() -> None:
    with TemporaryDirectory() as d:
        tmp = Path(d)
        analysis_dir = tmp / "analysis"

        rc = write_analysis_index(
            output_dir=analysis_dir, input_roots=[tmp / "missing"]
        )  # type: ignore[list-item]
        assert rc == 1

        audit_lines = (
            (analysis_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        )
        assert len(audit_lines) == 1
        audit = json.loads(audit_lines[0])
        assert audit["kind"] == "scan_error"
        assert "does not exist" in audit["error"]


def test_analysis_runner_is_deterministic_across_input_root_order() -> None:
    with TemporaryDirectory() as d:
        tmp = Path(d)

        out1 = tmp / "out1"
        (out1 / "transcripts").mkdir(parents=True)
        (out1 / "transcripts" / "2025-12-24_TestChannel_abcdefghijk.txt").write_text(
            "hello transcript", encoding="utf-8"
        )

        out2_root = tmp / "out2_root"
        (out2_root / "my_channel" / "transcripts").mkdir(parents=True)
        (
            out2_root
            / "my_channel"
            / "transcripts"
            / "2025-12-24_Other_0123456789_.txt"
        ).write_text("hello transcript 2", encoding="utf-8")

        analysis_a = tmp / "analysis_a"
        analysis_b = tmp / "analysis_b"

        rc_a = write_analysis_index(
            output_dir=analysis_a, input_roots=[out1, out2_root]
        )
        rc_b = write_analysis_index(
            output_dir=analysis_b, input_roots=[out2_root, out1]
        )
        assert rc_a == 0
        assert rc_b == 0

        assert (analysis_a / "manifest.json").read_text(encoding="utf-8") == (
            analysis_b / "manifest.json"
        ).read_text(encoding="utf-8")
        assert (analysis_a / "transcripts.jsonl").read_text(encoding="utf-8") == (
            analysis_b / "transcripts.jsonl"
        ).read_text(encoding="utf-8")
        assert (analysis_a / "audit.jsonl").read_text(encoding="utf-8") == (
            analysis_b / "audit.jsonl"
        ).read_text(encoding="utf-8")


def test_analysis_runner_reports_error_for_invalid_transcript_filename() -> None:
    with TemporaryDirectory() as d:
        tmp = Path(d)

        out = tmp / "out"
        transcripts_dir = out / "transcripts"
        transcripts_dir.mkdir(parents=True)

        # One valid transcript and one invalid filename inside transcripts/.
        (transcripts_dir / "2025-12-24_TestChannel_abcdefghijk.txt").write_text(
            "ok", encoding="utf-8"
        )
        (transcripts_dir / "badname.txt").write_text("bad", encoding="utf-8")

        analysis_dir = tmp / "analysis"
        rc = write_analysis_index(output_dir=analysis_dir, input_roots=[out])
        assert rc == 1

        lines = (
            (analysis_dir / "transcripts.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        assert len(lines) == 1
        assert json.loads(lines[0])["video_id"] == "abcdefghijk"

        audit_lines = (
            (analysis_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        )
        assert any(json.loads(line)["kind"] == "scan_error" for line in audit_lines)
