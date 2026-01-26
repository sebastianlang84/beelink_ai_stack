from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from common.config import load_config
from common.path_utils import archive_existing_reports
from common.run_summary import RunStats

from common.telemetry import record_pipeline_error
from common.utils import calculate_token_count, call_openai_with_retry

from .llm_output_validator import validate_llm_output_content
from .sanitizers import sanitize_stocks_per_video_extract_payload


SCHEMA_VERSION = 1


_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


logger = logging.getLogger(__name__)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _sha256_raw_hash(path: Path) -> str:
    """Return `sha256:<hex>` for the file bytes.

    This is used for change detection and to let the LLM copy a stable anchor
    into its strict JSON output.
    Policy anchor: [`docs/use-cases/stocks.md`](docs/use-cases/stocks.md)
    """

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _model_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value or "").strip("_")
    return cleaned or "model"


def _backup_corrupted_summary(path: Path) -> None:
    if not path.exists():
        return
    backup_path = path.with_name(f"{path.stem}.corrupted.{int(time.time())}{path.suffix}")
    try:
        path.rename(backup_path)
        logger.warning("Backed up corrupted summary to %s", backup_path)
    except Exception:
        logger.exception("Failed to backup corrupted summary: %s", path)

def _split_markdown_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse a minimal YAML-like frontmatter block.

    Supported:
    - Starts with `---` on the first line and ends with the next `---` line.
    - Only simple `key: value` pairs (strings). No nested YAML.
    """

    if not text.startswith("---\n"):
        return {}, text

    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text

    raw = text[4:end]
    body = text[end + len("\n---\n") :]
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        meta[key] = value
    return meta, body


def _existing_summary_is_valid(
    *,
    summary_path: Path,
    ref: "TranscriptRef",
    raw_hash: str,
    expected_topic: str | None,
) -> tuple[bool, str]:
    try:
        text = summary_path.read_text(encoding="utf-8")
    except Exception as exc:
        return False, f"read_failed:{exc}"

    meta, _ = _split_markdown_frontmatter(text)

    if meta.get("video_id") != ref.video_id:
        return False, "video_id_mismatch"
    if meta.get("channel_namespace") != ref.channel_namespace:
        return False, "channel_namespace_mismatch"
    if meta.get("transcript_path") != ref.transcript_path:
        return False, "transcript_path_mismatch"
    if meta.get("raw_hash") != raw_hash:
        return False, "raw_hash_mismatch"
    if expected_topic and meta.get("topic") and meta.get("topic") != expected_topic:
        return False, "topic_mismatch"

    return True, "ok"


def _youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _render_per_video_summary_markdown(
    *,
    topic: str,
    ref: "TranscriptRef",
    payload: dict[str, Any],
    raw_hash: str,
    video_title: str,
    published_at: str,
    channel_id: str,
) -> str:
    schema_version = payload.get("schema_version")
    task = str(payload.get("task") or "").strip() or "unknown"

    title_value = str(payload.get("title") or video_title or "unknown").strip() or "unknown"
    published_value = str(payload.get("published_at") or published_at or "unknown").strip() or "unknown"
    channel_id_value = str(payload.get("channel_id") or channel_id or "unknown").strip() or "unknown"

    lines: list[str] = []

    # Minimal frontmatter for idempotency + metadata extraction.
    lines.append("---")
    if isinstance(schema_version, int):
        lines.append(f"schema_version: {schema_version}")
    lines.append(f"task: {task}")
    lines.append(f"topic: {topic}")
    lines.append(f"video_id: {ref.video_id}")
    lines.append(f"url: {_youtube_url(ref.video_id)}")
    lines.append(f"title: {title_value}")
    lines.append(f"channel_namespace: {ref.channel_namespace}")
    lines.append(f"channel_id: {channel_id_value}")
    lines.append(f"published_at: {published_value}")
    lines.append(f"transcript_path: {ref.transcript_path}")
    lines.append(f"raw_hash: {raw_hash}")
    tq = payload.get("transcript_quality")
    if isinstance(tq, dict):
        grade = tq.get("grade")
        if isinstance(grade, str) and grade.strip():
            lines.append(f"transcript_quality_grade: {grade.strip()}")
        reasons = tq.get("reasons")
        if isinstance(reasons, list):
            cleaned = [str(r).strip() for r in reasons if str(r).strip()]
            if cleaned:
                lines.append(f"transcript_quality_reasons: {'; '.join(cleaned)}")
    lines.append(f"generated_at_utc: {_now_utc_iso()}")
    lines.append("---")
    lines.append("")

    # Human-readable body (no embedded JSON).
    lines.append(f"# {title_value}")
    lines.append("")
    lines.append("## Source")
    lines.append(f"- topic: `{topic}`")
    lines.append(f"- video_id: `{ref.video_id}`")
    lines.append(f"- url: {_youtube_url(ref.video_id)}")
    lines.append(f"- channel_namespace: `{ref.channel_namespace}`")
    lines.append(f"- published_at: `{published_value}`")
    lines.append("")

    macro = payload.get("macro_insights")
    if isinstance(macro, list):
        items = [x for x in macro if isinstance(x, dict)]
        if items:
            lines.append("## Macro Insights")
            for item in items:
                claim = str(item.get("claim") or "").strip()
                if not claim:
                    continue
                tags = item.get("tags")
                if isinstance(tags, list):
                    cleaned = [str(t).strip() for t in tags if str(t).strip()]
                else:
                    cleaned = []
                if cleaned:
                    lines.append(f"- {claim} (tags: {', '.join(cleaned)})")
                else:
                    lines.append(f"- {claim}")
            lines.append("")

    stocks = payload.get("stocks_covered")
    if isinstance(stocks, list):
        items = [x for x in stocks if isinstance(x, dict)]
        if items:
            lines.append("## Stocks Covered")
            for item in items:
                canonical = str(item.get("canonical") or "").strip()
                why = str(item.get("why_covered") or "").strip()
                if not canonical:
                    continue
                if why:
                    lines.append(f"- {canonical}: {why}")
                else:
                    lines.append(f"- {canonical}")
            lines.append("")

    knowledge_items = payload.get("knowledge_items")
    if isinstance(knowledge_items, list):
        items = [x for x in knowledge_items if isinstance(x, dict)]
        if items:
            lines.append("## Knowledge Items")
            for item in items:
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                entities = item.get("entities")
                if isinstance(entities, list):
                    cleaned = [str(e).strip() for e in entities if str(e).strip()]
                else:
                    cleaned = []
                if cleaned:
                    lines.append(f"- {text} (entities: {', '.join(cleaned)})")
                else:
                    lines.append(f"- {text}")
            lines.append("")

    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        cleaned = [str(e).strip() for e in errors if str(e).strip()]
        if cleaned:
            lines.append("## Errors")
            for e in cleaned:
                lines.append(f"- {e}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _wants_stocks_per_video_extract(
    *, system_prompt: str, user_prompt_template: str
) -> bool:
    """Heuristic switch without adding new config fields.

    We treat the presence of the task string in the prompt text as an opt-in.
    This keeps other configs compatible (which may still want the legacy
    `task=stock_coverage` or narrative reports).
    """

    marker = "stocks_per_video_extract"
    return marker in system_prompt or marker in user_prompt_template


def _is_probably_markdown(content: str) -> bool:
    """Best-effort detection whether a text blob is *likely* Markdown.

    Policy (conservative): return True only on strong Markdown signals.

    Default rule if uncertain:
    - treat as plain text (see open question in ADR 0007 about whether the
      prompt guarantees Markdown; if not guaranteed, prefer `report.txt`).
      Evidence: [`docs/adr/0007-llm-output-formats-json-vs-markdown.md`](docs/adr/0007-llm-output-formats-json-vs-markdown.md:149)
    """

    stripped = content.lstrip()
    if not stripped:
        return False

    # Fast-path: strict JSON (common in this repo) is not Markdown.
    # Evidence: validator/prompt spec expects strict JSON payloads.
    # See [`validate_llm_output_content()`](src/transcript_ai_analysis/llm_output_validator.py:1)
    if stripped[0] in "{[":
        return False

    # Strong Markdown signals.
    if re.match(r"^#{1,6}\s+\S", stripped):
        return True
    if "```" in content:
        return True
    if re.search(r"\[[^\]]+\]\([^\)]+\)", content):
        return True

    return False


def _derived_report_filename_for_content(content: str) -> str:
    """Return `report.md` if the content is likely Markdown, else `report.txt`.

    Naming convention is defined in ADR 0007.
    Evidence: [`docs/adr/0007-llm-output-formats-json-vs-markdown.md`](docs/adr/0007-llm-output-formats-json-vs-markdown.md:96)
    """

    return "report.md" if _is_probably_markdown(content) else "report.txt"


def _write_derived_report_and_metadata(*, llm_dir: Path) -> Path:
    """Create a human-readable derived report next to `report.json`.

    Implementation is strictly derived from the already persisted `report.json`
    content and is deterministic w.r.t. `report.json`.
    Evidence: ADR 0007 operationalization — derived artefact is a view on
    `report.json.output.content`.
    [`docs/adr/0007-llm-output-formats-json-vs-markdown.md`](docs/adr/0007-llm-output-formats-json-vs-markdown.md:96)
    """

    report_path = llm_dir / "report.json"
    report_bytes = report_path.read_bytes()
    data = json.loads(report_bytes.decode("utf-8"))
    output = data.get("output")
    content = output.get("content") if isinstance(output, dict) else None
    if not isinstance(content, str):
        raise ValueError("report.json missing output.content string")

    derived_name = _derived_report_filename_for_content(content)
    derived_path = llm_dir / derived_name
    _atomic_write_text(derived_path, content)

    # Minimal provenance/metadata foundation (separate file; no report schema refactor).
    # This file is strictly derivable from `report.json`.
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "batch": str(data.get("batch", "")),
        "report_schema_version": int(data.get("schema_version", 0)),
        "run_fingerprint": str(data.get("run_fingerprint", "")),
        "model": str(data.get("model", "")),
        "created_at_utc": str(data.get("created_at_utc", "")),
        "source": {
            "report_json": "report.json",
            "report_json_sha256": hashlib.sha256(report_bytes).hexdigest(),
        },
        "derived": {
            "report": derived_name,
            "format": "markdown" if derived_name.endswith(".md") else "text",
            "output_content_sha256": _sha256_hex(content),
        },
    }
    _atomic_write_json(llm_dir / "metadata.json", metadata)

    return derived_path


def _atomic_write_text(path: Path, content: str) -> None:
    # Lazy Creation: Ensure parent directory exists before writing
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    tmp.replace(path)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    # Lazy Creation: Ensure parent directory exists before writing
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


@dataclass(frozen=True)
class TranscriptRef:
    output_root: str
    channel_namespace: str
    video_id: str
    transcript_path: str
    metadata_path: str | None


def _parse_transcript_ref(line: str) -> TranscriptRef:
    data = json.loads(line)
    return TranscriptRef(
        output_root=str(data["output_root"]),
        channel_namespace=str(data["channel_namespace"]),
        video_id=str(data["video_id"]),
        transcript_path=str(data["transcript_path"]),
        metadata_path=data.get("metadata_path"),
    )


def _load_transcript_text(path: Path) -> str:
    """Load transcript text with explicit handling for encoding issues.

    Policy:
    - Primary decoding is UTF-8.
    - If decoding fails, we fall back to UTF-8 with replacement characters.
    """

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_bytes()
        return raw.decode("utf-8", errors="replace")


def _extract_chat_content(response: Any) -> str:
    """Best-effort extraction of ChatCompletion content.

    Supports both dict-like and attribute-like responses.
    """

    # dict-like
    if isinstance(response, dict):
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                return msg["content"]
            # legacy format
            if isinstance(choices[0].get("text"), str):
                return choices[0]["text"]

    # attribute-like
    choices = getattr(response, "choices", None)
    if isinstance(choices, list) and choices:
        first = choices[0]
        message = getattr(first, "message", None)
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        text = getattr(first, "text", None)
        if isinstance(text, str):
            return text

    raise ValueError(
        "Could not extract LLM response content from ChatCompletion response"
    )


def _compute_run_fingerprint(
    *,
    source_batch1_fingerprint: str,
    model: str,
    system_prompt: str,
    user_prompt_template: str,
    selected_refs: list[TranscriptRef],
) -> str:
    """Compute deterministic fingerprint for LLM-analysis inputs.

    Note: the LLM output itself is not deterministic; this fingerprint captures
    the *inputs* (batch1 fingerprint, prompts, selected transcripts).
    """

    h = hashlib.sha256()
    h.update(b"llm_analysis_v1\n")
    h.update(f"source_batch1={source_batch1_fingerprint}\n".encode("utf-8"))
    h.update(f"model={model}\n".encode("utf-8"))
    h.update(b"system_prompt\n")
    h.update(hashlib.sha256(system_prompt.encode("utf-8")).digest())
    h.update(b"\n")
    h.update(b"user_prompt_template\n")
    h.update(hashlib.sha256(user_prompt_template.encode("utf-8")).digest())
    h.update(b"\n")
    h.update(b"selected_refs\n")
    for r in sorted(
        selected_refs,
        key=lambda x: (x.channel_namespace, x.video_id, x.transcript_path),
    ):
        h.update(
            f"{r.channel_namespace}|{r.video_id}|{r.transcript_path}|{r.metadata_path or ''}\n".encode(
                "utf-8"
            )
        )
    return h.hexdigest()


def run_llm_analysis(
    *,
    config_path: Path,
    profile_root: Path,
    index_dir: Path,
    chat_completion_create: Callable[..., Any] | None = None,
    include_video_ids_by_channel: dict[str, set[str]] | None = None,
    run_stats: RunStats | None = None,
) -> int:
    """Run LLM analysis and write artefacts under the configured output layout.

    This runner uses the transcript index as input and produces a single
    report artefact for one LLM job as configured in YAML.
    """

    index_manifest_path = index_dir / "manifest.json"
    index_transcripts_path = index_dir / "transcripts.jsonl"
    index_audit_path = index_dir / "audit.jsonl"

    audit_lines: list[str] = []
    errors: list[str] = []
    audit_lock = threading.Lock()
    errors_lock = threading.Lock()

    def _append_audit(*, kind: str, message: str, details: dict[str, Any]) -> None:
        with audit_lock:
            audit_lines.append(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "kind": kind,
                        "message": message,
                        "details": details,
                    },
                    ensure_ascii=False,
                )
            )

    def _fail(error_type: str, message: str, details: dict[str, Any]) -> None:
        with errors_lock:
            errors.append(message)
        record_pipeline_error(error_type=error_type, where="analysis.llm")
        _append_audit(kind="error", message=message, details=details)

    cfg = load_config(config_path)
    llm_cfg = cfg.analysis.llm
    reports_root = cfg.output.get_reports_path()

    _append_audit(
        kind="run_started",
        message="llm analysis run started",
        details={
            "config_path": str(config_path),
            "index_dir": str(index_dir),
            "profile_root": str(profile_root),
        },
    )

    if not index_manifest_path.exists() or not index_transcripts_path.exists():
        _fail(
            "analysis_missing_index_inputs",
            f"missing index artefacts in: {index_dir}",
            {"index_dir": str(index_dir)},
        )
        # Fallback audit write if possible
        try:
            _atomic_write_text(
                reports_root / "audit_failed.jsonl",
                "\n".join(audit_lines) + "\n",
            )
        except Exception:
            pass
        return 1

    if not llm_cfg.enabled:
        _append_audit(
            kind="skipped",
            message="llm analysis disabled (analysis.llm.enabled=false)",
            details={},
        )
        # No run directory created if disabled
        return 0

    model = llm_cfg.model or ""
    system_prompt = llm_cfg.system_prompt or ""
    user_prompt_template = llm_cfg.user_prompt_template or ""
    max_input_tokens = llm_cfg.max_input_tokens
    max_output_tokens = llm_cfg.max_output_tokens
    per_video_concurrency = max(1, llm_cfg.per_video_concurrency)
    per_video_min_delay_s = max(0.0, llm_cfg.per_video_min_delay_s)
    per_video_jitter_s = max(0.0, llm_cfg.per_video_jitter_s)

    def _format_user_prompt(*, transcripts: str, transcript_count: int) -> str:
        return user_prompt_template.format(
            transcripts=transcripts,
            transcript_count=str(transcript_count),
        )

    # API key resolution (LLM): standardize on OpenRouter.
    # Keys are expected to come from `.env` (loaded by the CLI entrypoints).
    openrouter_api_key = (
        cfg.api.openrouter_api_key
        or os.environ.get("OPENROUTER_API_KEY")
        # Legacy env var used in existing local `.env`:
        or os.environ.get("openrouter_key")
        # Backward compatibility with older docs/tests:
        or cfg.api.openai_api_key
        or os.environ.get("OPENAI_API_KEY")
    )
    if not openrouter_api_key:
        _fail(
            "analysis_missing_openai_api_key",
            "LLM API key missing (set OPENROUTER_API_KEY in environment/.env)",
            {},
        )
        # Fallback audit write
        try:
            _atomic_write_text(
                reports_root / "audit_no_key.jsonl",
                "\n".join(audit_lines) + "\n",
            )
        except Exception:
            pass
        return 1

    openrouter_headers: dict[str, str] = {}
    title_value = (cfg.api.openrouter_app_title or "TranscriptMiner").strip()
    if title_value:
        openrouter_headers["X-Title"] = title_value
    referer_value = (cfg.api.openrouter_http_referer or "").strip()
    if referer_value:
        openrouter_headers["HTTP-Referer"] = referer_value

    index_manifest = json.loads(index_manifest_path.read_text(encoding="utf-8"))
    source_index_schema_version = int(index_manifest.get("schema_version", 0))
    source_index_fingerprint = str(index_manifest.get("run_fingerprint", ""))

    refs_lines = index_transcripts_path.read_text(encoding="utf-8").splitlines()
    refs_all = [_parse_transcript_ref(line) for line in refs_lines if line.strip()]
    refs_all_sorted = sorted(
        refs_all, key=lambda r: (r.channel_namespace, r.video_id, r.transcript_path)
    )

    per_video_mode = llm_cfg.mode == "per_video"
    if llm_cfg.mode == "aggregate":
        per_video_mode = _wants_stocks_per_video_extract(
            system_prompt=system_prompt, user_prompt_template=user_prompt_template
        )

    # Retention cleanup (PRD policy): delete transcripts after N days.
    # Policy: [`docs/PRD.md`](docs/PRD.md)
    if per_video_mode:
        try:
            from common.transcript_retention import cleanup_transcripts

            for out_root in sorted(
                {Path(r.output_root).resolve() for r in refs_all_sorted}
            ):
                cleanup_transcripts(
                    output_root=out_root, retention_days=cfg.output.retention_days
                )
        except Exception:
            # Cleanup must never make the runner unusable.
            pass

    selected_refs: list[TranscriptRef] = []
    selected_blocks: list[str] = []
    total_chars = 0
    total_tokens = 0
    base_prompt_tokens: int | None = None

    if max_input_tokens is not None:
        base_user_prompt = _format_user_prompt(transcripts="", transcript_count=0)
        base_prompt_tokens = calculate_token_count(
            system_prompt, model=model
        ) + calculate_token_count(base_user_prompt, model=model)
        if base_prompt_tokens > max_input_tokens:
            _fail(
                "llm_input_token_budget_exceeded",
                "LLM prompt exceeds max_input_tokens before transcripts are added",
                {
                    "max_input_tokens": max_input_tokens,
                    "base_prompt_tokens": base_prompt_tokens,
                },
            )
            try:
                _atomic_write_text(
                    reports_root / "audit_failed.jsonl",
                    "\n".join(audit_lines) + "\n",
                )
            except Exception:
                pass
            return 1

    # In per-video mode we still select at most `max_transcripts`, but each
    # transcript will become its own LLM call.
    for ref in refs_all_sorted:
        if include_video_ids_by_channel is not None:
            allowed = include_video_ids_by_channel.get(ref.channel_namespace)
            if not allowed or ref.video_id not in allowed:
                continue
        if len(selected_refs) >= llm_cfg.max_transcripts:
            break
        tpath = Path(ref.transcript_path)
        if not tpath.exists():
            _append_audit(
                kind="warning",
                message="transcript missing; skipped for LLM prompt",
                details={
                    "transcript_path": ref.transcript_path,
                    "video_id": ref.video_id,
                },
            )
            continue

        raw_hash = _sha256_raw_hash(tpath)
        text = _load_transcript_text(tpath)
        text = text[: llm_cfg.max_chars_per_transcript]

        # Try to load additional metadata for the prompt
        video_title = "unknown"
        published_at = "unknown"
        channel_id = ref.channel_namespace
        if ref.metadata_path:
            mpath = Path(ref.metadata_path)
            if mpath.exists():
                try:
                    mdata = json.loads(mpath.read_text(encoding="utf-8"))
                    video_title = mdata.get("video_title", video_title)
                    published_at = mdata.get("published_at", published_at)
                    channel_id = mdata.get("channel_id", channel_id)
                except Exception:
                    pass

        block = (
            f"=== Transcript | channel={ref.channel_namespace} | video_id={ref.video_id} ===\n"
            f"video_title={video_title}\n"
            f"published_at={published_at}\n"
            f"channel_id={channel_id}\n"
            f"transcript_path={ref.transcript_path}\n"
            f"raw_hash={raw_hash}\n"
            f"{text}\n"
        )
        block_tokens = calculate_token_count(block, model=model)
        if not per_video_mode:
            # Legacy: one big prompt; enforce total size.
            if total_chars + len(block) > llm_cfg.max_total_chars:
                break
            if (
                max_input_tokens is not None
                and base_prompt_tokens is not None
                and base_prompt_tokens + total_tokens + block_tokens > max_input_tokens
            ):
                _append_audit(
                    kind="warning",
                    message="max_input_tokens reached; truncating transcript selection",
                    details={
                        "max_input_tokens": max_input_tokens,
                        "base_prompt_tokens": base_prompt_tokens,
                        "total_tokens": total_tokens,
                        "next_block_tokens": block_tokens,
                        "transcript_path": ref.transcript_path,
                        "video_id": ref.video_id,
                    },
                )
                break
            selected_blocks.append(block)
            total_chars += len(block)
            total_tokens += block_tokens
            selected_refs.append(ref)
        else:
            if max_input_tokens is not None:
                per_user_prompt = _format_user_prompt(
                    transcripts=block,
                    transcript_count=1,
                )
                per_prompt_tokens = calculate_token_count(
                    system_prompt, model=model
                ) + calculate_token_count(per_user_prompt, model=model)
                if per_prompt_tokens > max_input_tokens:
                    _append_audit(
                        kind="warning",
                        message="per-video prompt exceeds max_input_tokens; skipped",
                        details={
                            "max_input_tokens": max_input_tokens,
                            "prompt_tokens": per_prompt_tokens,
                            "transcript_path": ref.transcript_path,
                            "video_id": ref.video_id,
                        },
                    )
                    continue
            total_chars += len(block)
            total_tokens += block_tokens
            selected_refs.append(ref)

    logger.info(
        "Preparing LLM request: %s transcripts, %s chars, ~%s tokens",
        len(selected_refs),
        total_chars,
        total_tokens,
    )

    if not per_video_mode:
        transcripts_blob = "\n".join(selected_blocks).strip() + (
            "\n" if selected_blocks else ""
        )
        user_prompt = _format_user_prompt(
            transcripts=transcripts_blob,
            transcript_count=len(selected_refs),
        )
        if max_input_tokens is not None:
            prompt_tokens = calculate_token_count(
                system_prompt, model=model
            ) + calculate_token_count(user_prompt, model=model)
            if prompt_tokens > max_input_tokens:
                _fail(
                    "llm_input_token_budget_exceeded",
                    "LLM prompt exceeds max_input_tokens after selection",
                    {
                        "max_input_tokens": max_input_tokens,
                        "prompt_tokens": prompt_tokens,
                        "transcripts_used": len(selected_refs),
                    },
                )
                try:
                    _atomic_write_text(
                        reports_root / "audit_failed.jsonl",
                        "\n".join(audit_lines) + "\n",
                    )
                except Exception:
                    pass
                return 1
    else:
        # Per-video: prompt is built per transcript.
        user_prompt = ""

    _append_audit(
        kind="prompt_built",
        message="llm prompt built",
        details={
            "transcripts_used": len(selected_refs),
            "transcripts_total": len(refs_all_sorted),
            "total_chars": total_chars,
            "total_tokens": total_tokens,
            "max_input_tokens": max_input_tokens,
            "max_output_tokens": max_output_tokens,
            "per_video_mode": per_video_mode,
            "system_prompt_sha256": _sha256_hex(system_prompt),
            "user_prompt_template_sha256": _sha256_hex(user_prompt_template),
        },
    )

    run_fingerprint = _compute_run_fingerprint(
        source_batch1_fingerprint=source_index_fingerprint,
        model=model,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        selected_refs=selected_refs,
    )

    # Skip logic (skip_on_no_new_data)
    if cfg.output.skip_on_no_new_data:
        reports_root = cfg.output.get_reports_path()
        short_hash = run_fingerprint[:8]

        if cfg.output.is_global_layout():
            history_root = cfg.output.get_history_root()
            if history_root.exists():
                for path in history_root.rglob(f"*__*__*__{short_hash}"):
                    if path.is_dir() and (path / "manifest.json").exists():
                        _append_audit(
                            kind="skipped",
                            message="skip_on_no_new_data: existing history bundle found",
                            details={"path": str(path)},
                        )
                        return 0
        elif cfg.output.daily_report:
            # Check if today's report already exists with same fingerprint
            timestamp_now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
            target_dir = cfg.output.get_run_reports_path(
                timestamp_now, run_fingerprint[:8]
            )

            if (target_dir / "manifest.json").exists():
                try:
                    m = json.loads(
                        (target_dir / "manifest.json").read_text(encoding="utf-8")
                    )
                    if m.get("run_fingerprint") == run_fingerprint:
                        _append_audit(
                            kind="skipped",
                            message="skip_on_no_new_data: daily report already exists with same fingerprint",
                            details={"path": str(target_dir)},
                        )
                        return 0
                except Exception:
                    pass
        else:
            if reports_root.exists():
                # Glob for run_*_{short_hash}
                for path in reports_root.glob(f"run_*_{short_hash}"):
                    if path.is_dir() and (path / "manifest.json").exists():
                        _append_audit(
                            kind="skipped",
                            message="skip_on_no_new_data: existing run found",
                            details={"path": str(path)},
                        )
                        return 0

    # Run-specific artifacts go into history bundles (global layout) or 3_reports/ (legacy).
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    model_slug = _model_slug(model)
    llm_dir = cfg.output.get_run_reports_path(
        timestamp, run_fingerprint[:8], model_slug=model_slug
    )
    run_id = llm_dir.name if cfg.output.is_global_layout() else f"{timestamp}_{run_fingerprint[:8]}"

    # Archive existing reports if we are in flat legacy mode
    if not cfg.output.is_global_layout() and not cfg.output.daily_report:
        archive_existing_reports(llm_dir, run_id)

    # Persist prompts for docs/audit/debugging (inputs only).
    _atomic_write_text(llm_dir / "system_prompt.txt", system_prompt)

    def _call_llm(*, user_prompt_text: str) -> str | None:
        response: Any
        try:
            req_kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt_text},
                ],
                "temperature": llm_cfg.temperature,
                "extra_body": {"reasoning": {"effort": "high"}},
            }
            if openrouter_headers:
                req_kwargs["extra_headers"] = dict(openrouter_headers)
            if max_output_tokens is not None:
                req_kwargs["max_tokens"] = int(max_output_tokens)

            if chat_completion_create is None:
                # Import openai lazily so offline environments can still import this module.
                # Use the v1+ OpenAI Python SDK client API.
                from openai import OpenAI  # type: ignore

                client = OpenAI(
                    api_key=openrouter_api_key, base_url=_OPENROUTER_BASE_URL
                )
                response = call_openai_with_retry(
                    client.chat.completions.create,
                    **req_kwargs,
                    log_json=cfg.logging.llm_request_json,
                )
            else:
                response = chat_completion_create(**req_kwargs)
        except Exception as e:
            _fail(
                "analysis_llm_call_failed",
                f"LLM call failed: {e}",
                {"model": model},
            )
            return None

        try:
            return _extract_chat_content(response)
        except Exception as e:
            _fail(
                "analysis_llm_response_parse_failed",
                f"LLM response parse failed: {e}",
                {"model": model},
            )
            return None

    def _handle_validation_failure(*, validation) -> None:
        # Persist raw output for docs/audit/debugging, but fail the run via rc=1.
        # Error types align with Spec suggestions: [`docs/analysis/llm_prompt_spec_strict_json_evidence.md`](docs/analysis/llm_prompt_spec_strict_json_evidence.md:235)
        first_code = (
            validation.issues[0].code
            if validation.issues
            else "llm_missing_required_fields"
        )
        _fail(
            first_code,
            "LLM output validation failed (see details.validation_issues)",
            {
                "validation_issues": [
                    {
                        "code": i.code,
                        "message": i.message,
                        "path": i.path,
                        "details": i.details,
                    }
                    for i in validation.issues
                ]
            },
        )

    content: str = ""
    per_video_written: list[dict[str, str]] = []

    if not per_video_mode:
        _atomic_write_text(llm_dir / "user_prompt.txt", user_prompt)
        start_time = time.time()
        content_opt = _call_llm(user_prompt_text=user_prompt)
        duration_ms = (time.time() - start_time) * 1000.0
        logger.info(
            "LLM aggregate call completed: duration_ms=%.2f status=%s",
            duration_ms,
            "ok" if content_opt is not None else "failed",
        )
        if content_opt is None:
            _atomic_write_text(llm_dir / "audit.jsonl", "\n".join(audit_lines) + "\n")
            return 1
        content = content_opt
        logger.info("LLM aggregate response received (%s chars)", len(content))
        if max_output_tokens is not None:
            output_tokens = calculate_token_count(content, model=model)
            if output_tokens > max_output_tokens:
                _fail(
                    "llm_output_token_budget_exceeded",
                    "LLM output exceeds max_output_tokens",
                    {
                        "max_output_tokens": max_output_tokens,
                        "output_tokens": output_tokens,
                    },
                )

        validation = validate_llm_output_content(content=content)
        if not validation.ok:
            _handle_validation_failure(validation=validation)
    else:
        # Per-video: run one call per transcript and persist per-video extract
        # next to the original channel output root.
        total_refs = len(selected_refs)
        per_video_written_lock = threading.Lock()
        last_output_lock = threading.Lock()
        last_output_idx = 0
        last_output: str | None = None
        rate_limit_lock = threading.Lock()
        last_request_time = 0.0

        def _apply_llm_rate_limit() -> None:
            if per_video_min_delay_s <= 0 and per_video_jitter_s <= 0:
                return
            nonlocal last_request_time
            with rate_limit_lock:
                now = time.time()
                actual_delay = per_video_min_delay_s + (
                    random.random() * per_video_jitter_s
                )
                elapsed = now - last_request_time
                wait_time = actual_delay - elapsed
                if wait_time > 0:
                    time.sleep(wait_time)
                last_request_time = time.time()

        def _maybe_set_last_output(idx: int, output: str | None) -> None:
            nonlocal last_output_idx, last_output
            with last_output_lock:
                if idx >= last_output_idx:
                    last_output_idx = idx
                    last_output = output

        def _process_ref(ref: TranscriptRef, idx: int) -> None:
            summary_failure_counted = False
            was_healed = False

            def _record_summary_failure() -> None:
                nonlocal summary_failure_counted
                if run_stats is None or summary_failure_counted:
                    return
                run_stats.inc("summaries_failed")
                summary_failure_counted = True

            tpath = Path(ref.transcript_path)
            if not tpath.exists():
                return
            raw_hash = _sha256_raw_hash(tpath)
            transcript_text = _load_transcript_text(tpath)
            transcript_text = transcript_text[: llm_cfg.max_chars_per_transcript]

            summary_path = cfg.output.get_summary_path(
                ref.video_id, channel_handle=ref.channel_namespace
            )
            target_summaries_dir = summary_path.parent
            if summary_path.exists():
                is_valid, reason = _existing_summary_is_valid(
                    summary_path=summary_path,
                    ref=ref,
                    raw_hash=raw_hash,
                    expected_topic=cfg.output.get_topic(),
                )
                if is_valid:
                    _append_audit(
                        kind="skipped",
                        message="summary exists and valid; skipping LLM",
                        details={
                            "video_id": ref.video_id,
                            "channel_namespace": ref.channel_namespace,
                            "summary_path": str(summary_path),
                        },
                    )
                    logger.info(
                        "Summary exists and valid; skipping LLM (video_id=%s channel=%s)",
                        ref.video_id,
                        ref.channel_namespace,
                    )
                    if run_stats is not None:
                        run_stats.inc("summaries_skipped_valid")
                    return
                _backup_corrupted_summary(summary_path)
                was_healed = True
                logger.warning(
                    "Summary invalid; regenerating (video_id=%s channel=%s reason=%s)",
                    ref.video_id,
                    ref.channel_namespace,
                    reason,
                )

            # Try to load additional metadata for the prompt
            video_title = "unknown"
            published_at = "unknown"
            channel_id = ref.channel_namespace
            if ref.metadata_path:
                mpath = Path(ref.metadata_path)
                if mpath.exists():
                    try:
                        mdata = json.loads(mpath.read_text(encoding="utf-8"))
                        video_title = mdata.get("video_title", video_title)
                        published_at = mdata.get("published_at", published_at)
                        channel_id = mdata.get("channel_id", channel_id)
                    except Exception:
                        pass

            transcripts_blob = (
                f"=== Transcript | channel={ref.channel_namespace} | video_id={ref.video_id} ===\n"
                f"video_title={video_title}\n"
                f"published_at={published_at}\n"
                f"channel_id={channel_id}\n"
                f"transcript_path={ref.transcript_path}\n"
                f"raw_hash={raw_hash}\n"
                f"{transcript_text}\n"
            )
            per_user_prompt = _format_user_prompt(
                transcripts=transcripts_blob,
                transcript_count=1,
            )
            # Persist the *last* prompt for debug; per-video prompts can be huge.
            if idx == total_refs:
                _atomic_write_text(llm_dir / "user_prompt.txt", per_user_prompt)

            if max_input_tokens is not None:
                per_prompt_tokens = calculate_token_count(
                    system_prompt, model=model
                ) + calculate_token_count(per_user_prompt, model=model)
                if per_prompt_tokens > max_input_tokens:
                    _fail(
                        "llm_input_token_budget_exceeded",
                        "LLM prompt exceeds max_input_tokens (per-video)",
                        {
                            "max_input_tokens": max_input_tokens,
                            "prompt_tokens": per_prompt_tokens,
                            "video_id": ref.video_id,
                            "channel_namespace": ref.channel_namespace,
                        },
                    )
                    _record_summary_failure()
                    return

            logger.info(
                "LLM per-video progress: %s/%s (%s) chars=%s tokens~%s",
                idx,
                total_refs,
                ref.video_id,
                len(transcript_text),
                calculate_token_count(transcript_text, model=model),
            )

            _apply_llm_rate_limit()
            start_time = time.time()
            out = _call_llm(user_prompt_text=per_user_prompt)
            duration_ms = (time.time() - start_time) * 1000.0
            logger.info(
                "LLM per-video call completed: video_id=%s channel=%s duration_ms=%.2f status=%s",
                ref.video_id,
                ref.channel_namespace,
                duration_ms,
                "ok" if out is not None else "failed",
            )
            _maybe_set_last_output(idx, out)
            if out is None:
                _record_summary_failure()
                return
            logger.info(
                "LLM per-video response received: %s (%s chars)",
                ref.video_id,
                len(out),
            )
            if max_output_tokens is not None:
                output_tokens = calculate_token_count(out, model=model)
                if output_tokens > max_output_tokens:
                    _fail(
                        "llm_output_token_budget_exceeded",
                        "LLM output exceeds max_output_tokens (per-video)",
                        {
                            "max_output_tokens": max_output_tokens,
                            "output_tokens": output_tokens,
                            "video_id": ref.video_id,
                            "channel_namespace": ref.channel_namespace,
                        },
                    )
                    _record_summary_failure()
                    return

            # Validate strict JSON policy (may still return a parsed payload even if not ok).
            validation = validate_llm_output_content(content=out)
            if not validation.ok:
                # Best-effort targeted retry for the common formatting failure:
                # why_covered looks like a list/enumeration.
                first_code = validation.issues[0].code if validation.issues else None
                if first_code == "llm_policy_violation_why_covered_is_list":
                    retry_hint = (
                        "\n\nCRITICAL FORMAT FIX:\n"
                        "- stocks_covered[].why_covered MUST be 1–2 full sentences (string).\n"
                        "- No bullet points, no enumerations, no comma lists.\n"
                    )
                    _apply_llm_rate_limit()
                    start_time = time.time()
                    out_retry = _call_llm(user_prompt_text=per_user_prompt + retry_hint)
                    duration_ms = (time.time() - start_time) * 1000.0
                    logger.info(
                        "LLM per-video retry completed: video_id=%s channel=%s duration_ms=%.2f status=%s",
                        ref.video_id,
                        ref.channel_namespace,
                        duration_ms,
                        "ok" if out_retry is not None else "failed",
                    )
                    if out_retry is not None:
                        out = out_retry
                        validation = validate_llm_output_content(content=out)

                # If still invalid and we do have a parsed payload, try a deterministic format-only repair.
                if not validation.ok and isinstance(validation.payload, dict):
                    task = validation.payload.get("task")
                    if task == "stocks_per_video_extract":
                        repaired, repairs = sanitize_stocks_per_video_extract_payload(
                            validation.payload
                        )
                        if repairs:
                            # Re-validate after repair.
                            repaired_text = json.dumps(repaired, ensure_ascii=False)
                            validation2 = validate_llm_output_content(content=repaired_text)
                            if validation2.ok:
                                _append_audit(
                                    kind="warning",
                                    message="llm output repaired (format-only) after validation failure",
                                    details={
                                        "video_id": ref.video_id,
                                        "channel_namespace": ref.channel_namespace,
                                        "repairs": repairs,
                                    },
                                )
                                out = repaired_text
                                validation = validation2

            if not validation.ok:
                _handle_validation_failure(validation=validation)
                _record_summary_failure()
                return

            # Use the validated payload when available.
            parsed = validation.payload
            if not isinstance(parsed, dict):
                try:
                    parsed = json.loads(out)
                except Exception:
                    _fail(
                        "llm_invalid_json",
                        "LLM output JSON parse failed after validation",
                        {
                            "video_id": ref.video_id,
                            "channel_namespace": ref.channel_namespace,
                        },
                    )
                    _record_summary_failure()
                    return

            # Strong binding: the per-video extract must refer to the transcript it was built from.
            src = parsed.get("source") if isinstance(parsed, dict) else None
            if not isinstance(src, dict):
                _fail(
                    "llm_missing_required_fields",
                    "LLM output missing source object",
                    {
                        "video_id": ref.video_id,
                        "channel_namespace": ref.channel_namespace,
                    },
                )
                _record_summary_failure()
                return
            if src.get("video_id") != ref.video_id:
                _fail(
                    "llm_invalid_input",
                    "LLM output source.video_id does not match requested video_id",
                    {"expected": ref.video_id, "actual": src.get("video_id")},
                )
                _record_summary_failure()
                return
            if src.get("channel_namespace") != ref.channel_namespace:
                _fail(
                    "llm_invalid_input",
                    "LLM output source.channel_namespace does not match requested channel_namespace",
                    {
                        "expected": ref.channel_namespace,
                        "actual": src.get("channel_namespace"),
                    },
                )
                _record_summary_failure()
                return
            if src.get("transcript_path") != ref.transcript_path:
                _fail(
                    "llm_invalid_input",
                    "LLM output source.transcript_path does not match requested transcript_path",
                    {
                        "expected": ref.transcript_path,
                        "actual": src.get("transcript_path"),
                    },
                )
                _record_summary_failure()
                return
            if parsed.get("raw_hash") != raw_hash:
                _fail(
                    "llm_invalid_input",
                    "LLM output raw_hash does not match computed transcript hash",
                    {"expected": raw_hash, "actual": parsed.get("raw_hash")},
                )
                _record_summary_failure()
                return

            # Persist raw short (audit source, 30d) under the run directory to avoid
            # mixing with miner outputs.
            raw_dir = llm_dir / "raw_transcripts" / ref.channel_namespace / ref.video_id
            raw_transcript_path = raw_dir / "raw_transcript.txt"
            _atomic_write_text(raw_transcript_path, transcript_text)
            _atomic_write_json(
                raw_dir / "meta.json",
                {
                    "channel_namespace": ref.channel_namespace,
                    "video_id": ref.video_id,
                    "transcript_path": ref.transcript_path,
                    "raw_hash": raw_hash,
                    "collected_at_utc": _now_utc_iso(),
                },
            )

            # Persist per-video extract (derived long, 365d).
            # Layout source: [`docs/use-cases/stocks.md`](docs/use-cases/stocks.md)
            out_path = summary_path
            topic = cfg.output.get_topic() if cfg.output.is_global_layout() else ""
            md = _render_per_video_summary_markdown(
                topic=topic or ref.channel_namespace,
                ref=ref,
                payload=parsed,
                raw_hash=raw_hash,
                video_title=video_title,
                published_at=published_at,
                channel_id=channel_id,
            )
            _atomic_write_text(out_path, md)
            # Enforce single-format storage: remove legacy JSON summary if present.
            legacy_json = out_path.with_suffix(".json")
            if legacy_json.exists() and legacy_json.name.endswith(".summary.json"):
                try:
                    legacy_json.unlink()
                except Exception:
                    logger.warning("Failed to delete legacy summary JSON: %s", legacy_json)
            with per_video_written_lock:
                per_video_written.append(
                    {
                        "video_id": ref.video_id,
                        "channel_namespace": ref.channel_namespace,
                        "path": str(out_path),
                    }
                )
            if run_stats is not None:
                run_stats.inc("summaries_created")
                if was_healed:
                    run_stats.inc("summaries_healed")

        if per_video_concurrency <= 1:
            for idx, ref in enumerate(selected_refs, start=1):
                _process_ref(ref, idx)
        else:
            with ThreadPoolExecutor(max_workers=per_video_concurrency) as executor:
                futures = {
                    executor.submit(_process_ref, ref, idx): (ref, idx)
                    for idx, ref in enumerate(selected_refs, start=1)
                }
                for future in as_completed(futures):
                    ref, idx = futures[future]
                    try:
                        future.result()
                    except Exception as exc:
                        _fail(
                            "analysis_llm_per_video_worker_failed",
                            "LLM per-video worker failed",
                            {
                                "video_id": ref.video_id,
                                "channel_namespace": ref.channel_namespace,
                                "error": str(exc),
                            },
                        )

        # For docs/audit/debug we still write one report.json that contains the last LLM output.
        # This keeps the runner compatible with existing artefact expectations.
        content = last_output if isinstance(last_output, str) else ""

    report = {
        "schema_version": SCHEMA_VERSION,
        "batch": "llm_v1",
        "model": model,
        "run_fingerprint": run_fingerprint,
        "created_at_utc": _now_utc_iso(),
        "source_index": {
            "schema_version": source_index_schema_version,
            "run_fingerprint": source_index_fingerprint,
            "manifest_path": str(index_manifest_path),
        },
        "input": {
            "transcripts_jsonl_path": str(index_transcripts_path),
            "audit_jsonl_path": str(index_audit_path),
            "transcripts_used": [
                {
                    "channel_namespace": r.channel_namespace,
                    "video_id": r.video_id,
                    "transcript_path": r.transcript_path,
                    "metadata_path": r.metadata_path,
                }
                for r in selected_refs
            ],
        },
        "prompt": {
            "system_prompt_sha256": _sha256_hex(system_prompt),
            "user_prompt_template_sha256": _sha256_hex(user_prompt_template),
        },
        "output": {
            "content": content,
        },
        "counters": {
            "transcript_ref_count": len(refs_all_sorted),
            "transcripts_used_count": len(selected_refs),
            "total_chars": total_chars,
            "per_video_extracts_written_count": len(per_video_written),
        },
    }
    _atomic_write_json(llm_dir / "report.json", report)

    try:
        # In per-video mode, the "report.json" only contains the last output (or empty),
        # so a derived report is misleading. The aggregation step is responsible for the full report.
        if not per_video_mode:
            derived_path = _write_derived_report_and_metadata(llm_dir=llm_dir)
            _append_audit(
                kind="derived_report_written",
                message="derived report written",
                details={"derived_report_path": str(derived_path)},
            )
    except Exception as e:
        _fail(
            "analysis_llm_derived_report_write_failed",
            f"failed to write derived report: {e}",
            {"llm_dir": str(llm_dir)},
        )

    if not errors:
        _append_audit(
            kind="llm_success",
            message="llm analysis completed",
            details={"report_path": str(llm_dir / "report.json"), "model": model},
        )
    elif per_video_mode and len(per_video_written) > 0:
        _append_audit(
            kind="llm_partial_success",
            message="llm analysis completed with partial success",
            details={
                "report_path": str(llm_dir / "report.json"),
                "model": model,
                "per_video_extracts_written_count": len(per_video_written),
                "transcripts_used_count": len(selected_refs),
                "errors_count": len(errors),
            },
        )

    exit_code = 0 if not errors else 1
    if per_video_mode and len(per_video_written) > 0:
        exit_code = 0
    _append_audit(
        kind="run_completed",
        message="llm run completed",
        details={
            "run_id": run_id,
            "run_fingerprint": run_fingerprint,
            "exit_code": exit_code,
            "errors_count": len(errors),
            "audit_path": str(llm_dir / "audit.jsonl"),
            "per_video_extracts_written_count": len(per_video_written),
        },
    )
    _atomic_write_text(llm_dir / "audit.jsonl", "\n".join(audit_lines) + "\n")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "batch": "llm_v1",
        "run_fingerprint": run_fingerprint,
        "created_at_utc": _now_utc_iso(),
        "source_index": {
            "schema_version": source_index_schema_version,
            "run_fingerprint": source_index_fingerprint,
            "manifest_path": str(index_manifest_path),
        },
        "input": {
            "transcripts_jsonl_path": str(index_transcripts_path),
            "audit_jsonl_path": str(index_audit_path),
        },
        "llm": {
            "model": model,
            "system_prompt_sha256": _sha256_hex(system_prompt),
            "user_prompt_template_sha256": _sha256_hex(user_prompt_template),
        },
        "counters": report["counters"],
        "artefacts": {
            "report_json": str(llm_dir / "report.json"),
            "metadata_json": str(llm_dir / "metadata.json"),
            "audit_jsonl": str(llm_dir / "audit.jsonl"),
            "system_prompt_txt": str(llm_dir / "system_prompt.txt"),
            "user_prompt_txt": str(llm_dir / "user_prompt.txt"),
            "raw_transcripts_dir": (
                str(llm_dir / "raw_transcripts") if per_video_mode else None
            ),
        },
    }
    _atomic_write_json(llm_dir / "manifest.json", manifest)

    reports_root = cfg.output.get_reports_path()
    run_manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "llm",
        "run_id": run_id,
        "timestamp": _now_utc_iso(),
        "run_fingerprint": run_fingerprint,
        "fingerprint": run_fingerprint[:8],
        "per_video_mode": per_video_mode,
        "model": model,
        "llm_dir": str(llm_dir),
        "reports_root": str(reports_root),
        "counters": report["counters"],
        "artefacts": {
            "report_json": str(llm_dir / "report.json"),
            "metadata_json": str(llm_dir / "metadata.json"),
            "audit_jsonl": str(llm_dir / "audit.jsonl"),
            "system_prompt_txt": str(llm_dir / "system_prompt.txt"),
            "user_prompt_txt": str(llm_dir / "user_prompt.txt"),
            "manifest_json": str(llm_dir / "manifest.json"),
            "raw_transcripts_dir": (
                str(llm_dir / "raw_transcripts") if per_video_mode else None
            ),
        },
    }
    _atomic_write_json(reports_root / "run_manifest.json", run_manifest)

    logger.info(
        "LLM run completed: run_id=%s run_fingerprint=%s exit=%s audit=%s errors=%s",
        run_id,
        run_fingerprint[:8],
        exit_code,
        llm_dir / "audit.jsonl",
        len(errors),
    )

    return exit_code
