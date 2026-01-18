from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcript_ai_analysis.llm_runner import run_llm_analysis
from transcript_ai_analysis.llm_output_validator import validate_llm_report_artefacts


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


def _write_minimal_config(config_path: Path, root_path: Path | None = None) -> None:
    root_path_str = f"  root_path: {root_path.as_posix()}" if root_path else ""
    config_path.write_text(
        f"""
api:
  openrouter_api_key: ${"{"}OPENROUTER_API_KEY{"}"}

youtube:
  channels: []

output:
{root_path_str}

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


def _assert_audit_has_validation_error(llm_dir: Path, *, expected_code: str) -> None:
    audit_lines = (llm_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert audit_lines
    events = [json.loads(line) for line in audit_lines]
    errors = [e for e in events if e.get("kind") == "error"]
    assert errors
    assert any(e.get("details", {}).get("validation_issues") for e in errors)
    assert any(
        any(
            i.get("code") == expected_code
            for i in e.get("details", {}).get("validation_issues", [])
        )
        for e in errors
    )


def test_llm_runner_invalid_json_output_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "run"
    batch1_dir = run_root / "3_reports" / "index"

    transcripts_dir = tmp_path / "1_transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    t1 = transcripts_dir / "t1.txt"
    t1.write_text("Hello transcript one.", encoding="utf-8")

    refs = [
        {
            "output_root": str(tmp_path),
            "channel_namespace": "alpha",
            "video_id": "vid1",
            "transcript_path": str(t1),
            "metadata_path": None,
        }
    ]
    _write_batch1_artefacts(batch1_dir, refs)

    config_path = tmp_path / "config.yaml"
    _write_minimal_config(config_path, root_path=run_root)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def fake_chat_completion_create(*, model, messages, temperature=None, **kwargs):
        return {"choices": [{"message": {"content": "NOT JSON"}}]}

    rc = run_llm_analysis(
        config_path=config_path,
        profile_root=run_root,
        index_dir=batch1_dir,
        chat_completion_create=fake_chat_completion_create,
    )
    assert rc == 1

    llm_dir = run_root / "3_reports"
    assert (llm_dir / "report.json").exists()
    _assert_audit_has_validation_error(llm_dir, expected_code="llm_invalid_json")


def test_llm_runner_knowledge_extract_mvp_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "run"
    batch1_dir = run_root / "3_reports" / "index"

    transcripts_dir = tmp_path / "1_transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    t1 = transcripts_dir / "t1.txt"
    t1.write_text("Hello transcript one.", encoding="utf-8")

    refs = [
        {
            "output_root": str(tmp_path),
            "channel_namespace": "alpha",
            "video_id": "vid1",
            "transcript_path": str(t1),
            "metadata_path": None,
        }
    ]
    _write_batch1_artefacts(batch1_dir, refs)

    config_path = tmp_path / "config.yaml"
    _write_minimal_config(config_path, root_path=run_root)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    payload = {
        "task": "knowledge_extract",
        "video_id": "vid1",
        "channel_id": "UC123",
        "title": "Test Video",
        "published_at": "2025-01-01",
        "knowledge_items": [
            {"text": "This is a key insight.", "entities": ["Entity1"]},
            {"text": "Another insight without entities."},
        ],
    }

    def fake_chat_completion_create(*, model, messages, temperature=None, **kwargs):
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    rc = run_llm_analysis(
        config_path=config_path,
        profile_root=run_root,
        index_dir=batch1_dir,
        chat_completion_create=fake_chat_completion_create,
    )
    assert rc == 0


def test_llm_offline_validator_ok_for_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "run"
    batch1_dir = run_root / "3_reports" / "index"

    transcripts_dir = tmp_path / "1_transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    t1 = transcripts_dir / "t1.txt"
    t1.write_text("Hello transcript one.", encoding="utf-8")

    refs = [
        {
            "output_root": str(tmp_path),
            "channel_namespace": "alpha",
            "video_id": "vid1",
            "transcript_path": str(t1),
            "metadata_path": None,
        }
    ]
    _write_batch1_artefacts(batch1_dir, refs)

    config_path = tmp_path / "config.yaml"
    _write_minimal_config(config_path, root_path=run_root)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    payload = {
        "schema_version": 1,
        "task": "stock_coverage",
        "results": [],
        "errors": [],
    }

    def fake_chat_completion_create(*, model, messages, temperature=None, **kwargs):
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    rc = run_llm_analysis(
        config_path=config_path,
        profile_root=run_root,
        index_dir=batch1_dir,
        chat_completion_create=fake_chat_completion_create,
    )
    assert rc == 0

    llm_dir = run_root / "3_reports"
    res = validate_llm_report_artefacts(llm_dir=llm_dir)
    assert res.ok, [f"{i.code} {i.path}: {i.message}" for i in res.issues]


def test_stocks_per_video_extract_mvp_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "run"
    batch1_dir = run_root / "3_reports" / "index"

    transcripts_dir = tmp_path / "1_transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    t1 = transcripts_dir / "t1.txt"
    t1.write_text("Intro...\nWe like MSFT.\nOutro...\n", encoding="utf-8")

    refs = [
        {
            "output_root": str(tmp_path),
            "channel_namespace": "alpha",
            "video_id": "vid1",
            "transcript_path": str(t1),
            "metadata_path": None,
        }
    ]
    _write_batch1_artefacts(batch1_dir, refs)

    config_path = tmp_path / "config.yaml"
    _write_minimal_config(config_path, root_path=run_root)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    payload = {
        "schema_version": 1,
        "task": "stocks_per_video_extract",
        "source": {
            "channel_namespace": "alpha",
            "video_id": "vid1",
            "transcript_path": str(t1),
        },
        "raw_hash": "sha256:" + ("0" * 64),
        "transcript_quality": {"grade": "ok", "reasons": []},
        "macro_insights": [
            {"claim": "Inflation tends to pressure margins.", "tags": []}
        ],
        "stocks_covered": [
            {
                "canonical": "MSFT",
                "why_covered": "Deep dive into the business model.",
            }
        ],
        "errors": [],
    }

    def fake_chat_completion_create(*, model, messages, temperature=None, **kwargs):
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    rc = run_llm_analysis(
        config_path=config_path,
        profile_root=run_root,
        index_dir=batch1_dir,
        chat_completion_create=fake_chat_completion_create,
    )
    assert rc == 0
