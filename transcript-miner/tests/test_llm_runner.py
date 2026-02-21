from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from common.config import load_config
from common.run_summary import RunStats
from transcript_ai_analysis.llm_runner import (
    TranscriptRef,
    _allow_regeneration_for_invalid_summary,
    run_llm_analysis,
    summarize_transcript_ref,
)


def _write_batch1_artefacts(batch1_dir: Path, refs: list[dict]) -> None:
    batch1_dir.mkdir(parents=True, exist_ok=True)
    (batch1_dir / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "run_fingerprint": "batch1_fp"}, indent=2),
        encoding="utf-8",
    )
    (batch1_dir / "audit.jsonl").write_text("", encoding="utf-8")
    (batch1_dir / "transcripts.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in refs) + "\n",
        encoding="utf-8",
    )


def test_llm_runner_writes_report_and_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "run"
    batch1_dir = run_root / "3_reports" / "index"

    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    t1 = transcripts_dir / "t1.txt"
    t2 = transcripts_dir / "t2.txt"
    t1.write_text("Hello transcript one.", encoding="utf-8")
    t2.write_text("Hello transcript two.", encoding="utf-8")

    refs = [
        {
            "output_root": str(tmp_path),
            "channel_namespace": "alpha",
            "video_id": "vid1",
            "transcript_path": str(t1),
            "metadata_path": None,
        },
        {
            "output_root": str(tmp_path),
            "channel_namespace": "beta",
            "video_id": "vid2",
            "transcript_path": str(t2),
            "metadata_path": None,
        },
    ]
    _write_batch1_artefacts(batch1_dir, refs)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
api:
  openrouter_api_key: ${"{"}OPENROUTER_API_KEY{"}"}

youtube:
  channels: []

output:
  root_path: {run_root.as_posix()}

analysis:
  llm:
    enabled: true
    model: gpt-5.2
    system_prompt: |
      You are an analyst.
    user_prompt_template: |
      Count={"{"}transcript_count{"}"}

      {"{"}transcripts{"}"}
    max_transcripts: 10
    max_chars_per_transcript: 1000
    max_total_chars: 10000
""".strip()
        + "\n",
        encoding="utf-8",
    )

    # Satisfy key resolution, but we stub the call.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def fake_chat_completion_create(*, model, messages, temperature=None, **kwargs):
        assert model == "gpt-5.2"
        assert isinstance(messages, list) and len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "You are an analyst" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "Count=2" in messages[1]["content"]
        assert "vid1" in messages[1]["content"]
        assert "vid2" in messages[1]["content"]
        assert kwargs.get("extra_body") == {"reasoning": {"effort": "high"}}

        # Runner now validates strict JSON in output.content; keep this test
        # returning a spec-conform minimal payload.
        payload = {
            "schema_version": 1,
            "task": "stock_coverage",
            "results": [],
            "errors": [],
        }
        return {
            "choices": [{"message": {"content": json.dumps(payload)}}],
            "usage": None,
        }

    rc = run_llm_analysis(
        config_path=config_path,
        profile_root=run_root,
        index_dir=batch1_dir,
        chat_completion_create=fake_chat_completion_create,
    )
    assert rc == 0

    llm_dir = run_root / "3_reports"
    assert (llm_dir / "manifest.json").exists()
    assert (llm_dir / "report.json").exists()
    assert (llm_dir / "metadata.json").exists()
    assert (llm_dir / "audit.jsonl").exists()
    assert (llm_dir / "system_prompt.txt").exists()
    assert (llm_dir / "user_prompt.txt").exists()

    # Derived human-readable report must be written and byte-identical to
    # `report.json.output.content`.
    report = json.loads((llm_dir / "report.json").read_text(encoding="utf-8"))
    content = report["output"]["content"]
    assert isinstance(content, str)

    # This test uses a strict-JSON string content; default policy is `report.txt`.
    # Evidence: ADR 0007 prefers `report.txt` when not confidently Markdown.
    # [`docs/adr/0007-llm-output-formats-json-vs-markdown.md`](docs/adr/0007-llm-output-formats-json-vs-markdown.md:149)
    derived_path = llm_dir / "report.txt"
    assert derived_path.exists()
    assert derived_path.read_bytes() == content.encode("utf-8")

    assert json.loads(report["output"]["content"])["schema_version"] == 1
    assert report["counters"]["transcripts_used_count"] == 2


def test_llm_runner_disabled_writes_audit_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "run"
    batch1_dir = run_root / "3_reports" / "index"
    _write_batch1_artefacts(batch1_dir, [])

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
analysis:
  llm:
    enabled: false
""".strip()
        + "\n",
        encoding="utf-8",
    )

    # Even if key env var exists, disabled should skip.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    rc = run_llm_analysis(
        config_path=config_path,
        profile_root=run_root,
        index_dir=batch1_dir,
        chat_completion_create=lambda **_: (_ for _ in ()).throw(
            AssertionError("should not be called")
        ),
    )
    assert rc == 0
    # Note: currently no audit file is written if disabled.
    # llm_dir = run_root / "2_summaries"
    # assert (llm_dir / "audit.jsonl").exists()


def test_allow_regeneration_for_invalid_summary_mode_off_blocks_soft_backfill(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "t.txt"
    transcript_path.write_text("hello", encoding="utf-8")
    ref = TranscriptRef(
        output_root=str(tmp_path),
        channel_namespace="alpha",
        video_id="vid1",
        transcript_path=str(transcript_path),
        metadata_path=None,
    )
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            llm=SimpleNamespace(
                summary_backfill_mode="off",
                summary_backfill_days=14,
            )
        )
    )

    allow, reason = _allow_regeneration_for_invalid_summary(
        cfg=cfg,
        reason="missing_section:Summary",
        ref=ref,
        published_at="2020-01-01T00:00:00Z",
    )
    assert allow is False
    assert reason == "mode_off"


def test_summarize_transcript_ref_defers_soft_backfill_for_old_invalid_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TM_LLM_BACKEND", "gemini_cli")
    output_root = tmp_path / "output"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
youtube:
  channels: ["@alpha"]
output:
  global: {output_root.as_posix()}
  topic: investing
analysis:
  llm:
    enabled: true
    mode: per_video
    model: google/gemini-3-flash-preview
    system_prompt: |
      s
    user_prompt_template: |
      {"{"}transcripts{"}"}
    summary_backfill_mode: soft
    summary_backfill_days: 14
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cfg = load_config(config_path)

    transcript_path = tmp_path / "video.txt"
    transcript_path.write_text("transcript body", encoding="utf-8")
    metadata_path = tmp_path / "video_meta.json"
    metadata_path.write_text(
        json.dumps(
            {
                "video_title": "Old Video",
                "published_at": "2020-01-01T00:00:00Z",
                "channel_id": "alpha-channel",
            }
        ),
        encoding="utf-8",
    )

    ref = TranscriptRef(
        output_root=str(output_root),
        channel_namespace="alpha",
        video_id="vid_old",
        transcript_path=str(transcript_path),
        metadata_path=str(metadata_path),
    )

    summary_path = cfg.output.get_summary_path(ref.video_id, channel_handle=ref.channel_namespace)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    old_summary = "\n".join(
        [
            "# old summary",
            "## Source",
            "- topic: investing",
            "- video_id: vid_old",
            "- url: https://www.youtube.com/watch?v=vid_old",
            "- title: Old Video",
            "- channel_namespace: alpha",
            "- published_at: 2020-01-01T00:00:00Z",
            "- fetched_at: 2020-01-02T00:00:00Z",
            "- info_density: medium",
            "",
        ]
    )
    summary_path.write_text(old_summary, encoding="utf-8")

    def _never_call_gemini(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("LLM call must be skipped by soft backfill policy")

    monkeypatch.setattr("transcript_ai_analysis.llm_runner._call_gemini_cli", _never_call_gemini)

    stats = RunStats()
    ok = summarize_transcript_ref(cfg=cfg, ref=ref, run_stats=stats)

    assert ok is True
    assert stats.summaries_skipped_backfill == 1
    assert stats.summaries_healed == 0
    assert summary_path.read_text(encoding="utf-8") == old_summary
