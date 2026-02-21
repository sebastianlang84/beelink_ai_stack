from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import requests

from common.config import load_config
from common.path_utils import archive_existing_reports
from common.run_summary import RunStats

from common.telemetry import record_pipeline_error
from common.utils import calculate_token_count, call_openai_with_retry

SCHEMA_VERSION = 1


_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


logger = logging.getLogger(__name__)


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _owui_api_key() -> str:
    return (os.environ.get("OPEN_WEBUI_API_KEY") or os.environ.get("OWUI_API_KEY") or "").strip()


def _owui_base_url() -> str:
    return os.environ.get("OPEN_WEBUI_BASE_URL", "http://owui:8080").rstrip("/")


def _owui_sync_base_url() -> str:
    return os.environ.get("OPEN_WEBUI_SYNC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _owui_list_knowledge() -> list[dict[str, Any]]:
    key = _owui_api_key()
    if not key:
        return []
    url = f"{_owui_base_url()}/api/v1/knowledge/"
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=30)
    except Exception as exc:
        logger.warning("OWUI knowledge list failed: %s", exc)
        return []
    if resp.status_code >= 400:
        logger.warning("OWUI knowledge list failed: %s %s", resp.status_code, resp.text[:200])
        return []
    try:
        data = resp.json()
    except Exception as exc:
        logger.warning("OWUI knowledge list JSON error: %s", exc)
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return list(data["items"])
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return list(data["data"])
    if isinstance(data, dict) and isinstance(data.get("knowledge"), list):
        return list(data["knowledge"])
    return []


def _owui_find_knowledge_id_by_name(name: str) -> str | None:
    name_norm = (name or "").strip().casefold()
    if not name_norm:
        return None
    for kb in _owui_list_knowledge():
        kb_name = str(kb.get("name") or "").strip().casefold()
        if kb_name == name_norm:
            kid = str(kb.get("id") or "").strip()
            return kid or None
    return None


def _owui_create_knowledge(name: str) -> str | None:
    key = _owui_api_key()
    if not key:
        return None
    url = f"{_owui_base_url()}/api/v1/knowledge/create"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"name": name, "description": ""},
            timeout=30,
        )
    except Exception as exc:
        logger.warning("OWUI knowledge create failed: %s", exc)
        return None
    if resp.status_code >= 400:
        logger.warning("OWUI knowledge create failed: %s %s", resp.status_code, resp.text[:200])
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    kid = str(data.get("id") or "").strip() if isinstance(data, dict) else ""
    return kid or None


def _maybe_sync_summary_to_owui(
    *,
    topic: str,
    video_id: str,
    channel_namespace: str,
    title: str,
    published_at: str,
    markdown: str,
) -> None:
    if not _truthy_env("OPEN_WEBUI_SYNC_ON_SUMMARY"):
        return
    if not topic:
        logger.warning("OWUI per-summary sync skipped: missing topic")
        return
    if not _owui_api_key():
        logger.warning("OWUI per-summary sync skipped: OPEN_WEBUI_API_KEY not set")
        return

    knowledge_id = _owui_find_knowledge_id_by_name(topic)
    if not knowledge_id and _truthy_env("OPEN_WEBUI_CREATE_KNOWLEDGE_IF_MISSING"):
        knowledge_id = _owui_create_knowledge(topic)
    if not knowledge_id:
        logger.warning("OWUI per-summary sync skipped: knowledge not found (topic=%s)", topic)
        return

    payload = {
        "source_id": f"youtube:{video_id}",
        "text": markdown,
        "title": title,
        "url": _youtube_url(video_id),
        "channel": channel_namespace,
        "published_at": published_at,
        "fetched_at": _now_utc_iso(),
        "knowledge_id": knowledge_id,
    }
    url = f"{_owui_sync_base_url()}/index/transcript"
    try:
        resp = requests.post(url, json=payload, timeout=300)
    except Exception as exc:
        logger.warning("OWUI per-summary sync failed: %s", exc)
        return
    if resp.status_code >= 400:
        logger.warning("OWUI per-summary sync failed: %s %s", resp.status_code, resp.text[:200])
        return
    try:
        data = resp.json()
    except Exception:
        data = None
    status = data.get("status") if isinstance(data, dict) else None
    logger.info(
        "OWUI per-summary sync done: video_id=%s status=%s",
        video_id,
        status or resp.status_code,
    )


def _summary_meta_from_markdown(text: str) -> dict[str, str]:
    # Legacy canonical format: derive from `## Source`.
    src = _parse_source_block(text)
    title = src.get("title", "").strip()
    published_at = src.get("published_at", "").strip()
    channel_namespace = src.get("channel_namespace", "").strip()
    if title or published_at or channel_namespace:
        return {
            "title": title,
            "published_at": published_at,
            "channel_namespace": channel_namespace,
        }

    # Prompt V2 format: derive from first wrapped doc frontmatter.
    wrapped = _extract_rag_wrapped_docs(text)
    if not wrapped:
        return {"title": "", "published_at": "", "channel_namespace": ""}

    fm = wrapped[0].get("frontmatter") or {}
    if not isinstance(fm, dict):
        fm = {}
    return {
        "title": str(fm.get("title") or "").strip(),
        "published_at": str(fm.get("published_at") or "").strip(),
        "channel_namespace": str(fm.get("channel_namespace") or "").strip(),
    }


def _sync_existing_summary(
    *,
    summary_path: Path,
    topic: str,
    ref: "TranscriptRef",
    fallback_title: str,
    fallback_published_at: str,
) -> None:
    if not _truthy_env("OPEN_WEBUI_SYNC_ON_SUMMARY"):
        return
    try:
        text = summary_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("OWUI per-summary sync read failed: %s", exc)
        return
    meta = _summary_meta_from_markdown(text)
    _maybe_sync_summary_to_owui(
        topic=topic,
        video_id=ref.video_id,
        channel_namespace=meta.get("channel_namespace") or ref.channel_namespace,
        title=meta.get("title") or fallback_title,
        published_at=meta.get("published_at") or fallback_published_at,
        markdown=text,
    )


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _now_utc_hm() -> str:
    return _format_utc_hm(datetime.now(timezone.utc))


def _now_vienna_hm() -> str:
    try:
        return datetime.now(ZoneInfo("Europe/Vienna")).strftime("%Y-%m-%d %H:%M %Z")
    except Exception:
        return "unknown"


def _build_time_awareness_block(*, current_utc: str, current_vienna: str) -> str:
    return (
        "Current reference time:\n"
        f"- utc_now: {current_utc}\n"
        f"- vienna_now: {current_vienna}\n"
        "Recency rule: weigh newer information higher and call out when evidence is older.\n\n"
    )

def _format_utc_hm(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def _parse_iso_datetime(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    # Support common shapes: "...Z" and "...+00:00".
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _summary_backfill_mode(cfg: Any) -> str:
    llm_cfg = getattr(getattr(cfg, "analysis", None), "llm", None)
    raw = str(getattr(llm_cfg, "summary_backfill_mode", "soft") or "soft").strip().lower()
    if raw in {"off", "soft", "full"}:
        return raw
    return "soft"


def _summary_backfill_days(cfg: Any) -> int:
    llm_cfg = getattr(getattr(cfg, "analysis", None), "llm", None)
    raw = getattr(llm_cfg, "summary_backfill_days", 14)
    try:
        days = int(raw)
    except Exception:
        return 14
    return max(1, days)


def _is_soft_backfill_reason(reason: str) -> bool:
    if reason.startswith("missing_section:"):
        return True
    if reason.startswith("missing_source_key:"):
        key = reason.split(":", 1)[1].strip().lower()
        # Missing routing identity must stay hard-invalid.
        return key not in {"video_id", "channel_namespace"}
    return False


def _reference_datetime_for_ref(*, ref: "TranscriptRef", published_at: str) -> datetime | None:
    dt = _parse_iso_datetime(published_at or "")
    if dt is not None:
        return dt.astimezone(timezone.utc)
    try:
        return datetime.fromtimestamp(Path(ref.transcript_path).stat().st_mtime, tz=timezone.utc)
    except Exception:
        return None


def _allow_regeneration_for_invalid_summary(
    *,
    cfg: Any,
    reason: str,
    ref: "TranscriptRef",
    published_at: str,
) -> tuple[bool, str]:
    if not _is_soft_backfill_reason(reason):
        return True, "hard_invalid"

    mode = _summary_backfill_mode(cfg)
    if mode == "full":
        return True, "mode_full"
    if mode == "off":
        return False, "mode_off"

    days = _summary_backfill_days(cfg)
    ref_dt = _reference_datetime_for_ref(ref=ref, published_at=published_at)
    if ref_dt is None:
        # Without a reliable reference date we regenerate to avoid silent data loss.
        return True, "soft_unknown_reference_time"

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if ref_dt >= cutoff:
        return True, "soft_within_window"
    return False, f"soft_outside_window:{days}d"

def _parse_source_block(markdown: str) -> dict[str, str]:
    """Parse the required `## Source` bullet list into a dict."""
    lines = markdown.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "## Source":
            start = i + 1
            break
    if start is None:
        return {}

    out: dict[str, str] = {}
    for j in range(start, len(lines)):
        line = lines[j].rstrip()
        if line.startswith("## "):
            break
        m = re.match(r"^\s*-\s*([a-zA-Z0-9_]+)\s*:\s*(.*)\s*$", line)
        if not m:
            continue
        key = m.group(1).strip()
        value = m.group(2).strip()
        if key:
            out[key] = value
    return out

_REQUIRED_SOURCE_KEYS = [
    "topic",
    "video_id",
    "url",
    "title",
    "channel_namespace",
    "published_at",
    "fetched_at",
    "info_density",
]

_REQUIRED_SECTIONS = [
    "Source",
    "Summary",
    "Key Points & Insights",
    "Numbers",
    "Chances",
    "Risks",
    "Unknowns",
]


def _extract_rag_wrapped_docs(markdown: str) -> list[dict[str, Any]]:
    """Parse optional `<<<DOC_START>>>...<<<DOC_END>>>` wrappers from prompt v2 output."""
    text = (markdown or "").replace("\r\n", "\n")
    matches = re.findall(
        r"<<<DOC_START>>>\s*(.*?)\s*<<<DOC_END>>>",
        text,
        flags=re.DOTALL,
    )
    docs: list[dict[str, Any]] = []
    for raw in matches:
        body = (raw or "").strip()
        if not body:
            continue
        frontmatter: dict[str, str] = {}
        m_frontmatter = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n?", body, flags=re.DOTALL)
        if m_frontmatter:
            raw_fm = m_frontmatter.group(1)
            for line in raw_fm.splitlines():
                m_kv = re.match(r"^\s*([a-zA-Z0-9_]+)\s*:\s*(.*?)\s*$", line)
                if not m_kv:
                    continue
                key = m_kv.group(1).strip()
                value = m_kv.group(2).strip()
                if key:
                    frontmatter[key] = value

        topic = str(frontmatter.get("topic") or "").strip().lower() or "unknown"
        if topic == "unknown":
            m_topic = re.search(r"(?m)^topic:\s*([a-zA-Z0-9_-]+)\s*$", body)
            if m_topic:
                topic = m_topic.group(1).strip().lower()
        docs.append(
            {
                "topic": topic,
                "frontmatter": frontmatter,
                "sections": _extract_level2_sections(body),
            }
        )
    return docs


def _pick_section(
    sections: dict[str, str],
    names: list[str],
) -> str:
    for name in names:
        value = (sections.get(name) or "").strip()
        if value:
            return value
    return ""


def _coerce_to_bullets(text: str) -> str:
    body = (text or "").strip()
    if not body:
        return ""
    if re.search(r"(?m)^\s*-\s+\S", body):
        return body
    one_line = re.sub(r"\s+", " ", body).strip()
    return f"- {one_line}" if one_line else ""

def _extract_level2_sections(markdown: str) -> dict[str, str]:
    """Extract `## <name>` sections into a map of section_name -> raw body text."""
    text = markdown.replace("\r\n", "\n")
    # Split on level-2 headings; keep the heading names.
    parts = re.split(r"(?m)^##\s+(.+?)\s*$\n?", text)
    # parts: [preamble, name1, body1, name2, body2, ...]
    if len(parts) < 3:
        return {}
    out: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        name = (parts[i] or "").strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if name:
            out[name] = body.strip("\n")
    return out

def _ensure_bullets_or_none(text: str) -> str:
    body = (text or "").strip()
    if not body:
        return "- none"
    # If the model already provided bullets, keep them.
    if re.search(r"(?m)^\s*-\s+\S", body):
        return body
    # Otherwise, coerce into a single bullet.
    one_line = re.sub(r"\s+", " ", body).strip()
    return f"- {one_line}" if one_line else "- none"

def _normalize_markdown_summary(
    *,
    topic: str,
    ref: "TranscriptRef",
    title: str,
    channel_namespace: str,
    published_at_iso: str,
    llm_markdown: str,
) -> str:
    """Build the canonical per-video Markdown summary (markdown-only pipeline)."""
    sections = _extract_level2_sections(llm_markdown or "")
    wrapped_docs = _extract_rag_wrapped_docs(llm_markdown or "")
    src_from_llm = _parse_source_block(llm_markdown or "")

    density = (src_from_llm.get("info_density") or "").strip().lower()
    if density not in {"low", "medium", "high"}:
        density = "medium"

    pub_dt = _parse_iso_datetime(published_at_iso)
    published_at = _format_utc_hm(pub_dt) if pub_dt else str(published_at_iso or "unknown").strip() or "unknown"

    lines: list[str] = []
    lines.append(f"# {title or 'unknown'}")
    lines.append("")
    lines.append("## Source")
    lines.append(f"- topic: {topic}")
    lines.append(f"- video_id: {ref.video_id}")
    lines.append(f"- url: {_youtube_url(ref.video_id)}")
    lines.append(f"- title: {title or 'unknown'}")
    lines.append(f"- channel_namespace: {channel_namespace or ref.channel_namespace}")
    lines.append(f"- published_at: {published_at}")
    lines.append(f"- fetched_at: {_now_utc_hm()}")
    lines.append(f"- info_density: {density}")
    lines.append("")

    if wrapped_docs:
        summary_lines: list[str] = []
        key_points_lines: list[str] = []
        numbers_lines: list[str] = []
        chances_lines: list[str] = []
        risks_lines: list[str] = []
        unknowns_lines: list[str] = []

        for doc in wrapped_docs:
            doc_topic = str(doc.get("topic") or "unknown")
            doc_sections = doc.get("sections") or {}
            if not isinstance(doc_sections, dict):
                continue

            s_exec = _pick_section(doc_sections, ["Summary", "Executive Summary"])
            if s_exec:
                as_bullets = _coerce_to_bullets(s_exec)
                if as_bullets:
                    for line in as_bullets.splitlines():
                        clean = line.strip()
                        if clean.startswith("- "):
                            summary_lines.append(f"- [{doc_topic}] {clean[2:].strip()}")

            s_key_points = _pick_section(doc_sections, ["Key Points & Insights", "Key Points"])
            s_numbers = _pick_section(doc_sections, ["Numbers"])
            s_chances = _pick_section(doc_sections, ["Chances", "Opportunities"])
            s_risks = _pick_section(doc_sections, ["Risks"])
            s_unknowns = _pick_section(doc_sections, ["Unknowns"])

            for src, target in [
                (s_key_points, key_points_lines),
                (s_numbers, numbers_lines),
                (s_chances, chances_lines),
                (s_risks, risks_lines),
                (s_unknowns, unknowns_lines),
            ]:
                as_bullets = _coerce_to_bullets(src)
                if not as_bullets:
                    continue
                for line in as_bullets.splitlines():
                    clean = line.strip()
                    if clean.startswith("- "):
                        target.append(f"- [{doc_topic}] {clean[2:].strip()}")

        summary_body = "\n".join(summary_lines).strip()
        key_points_body = "\n".join(key_points_lines).strip()
        numbers_body = "\n".join(numbers_lines).strip()
        chances_body = "\n".join(chances_lines).strip()
        risks_body = "\n".join(risks_lines).strip()
        unknowns_body = "\n".join(unknowns_lines).strip()
    else:
        summary_body = _pick_section(sections, ["Summary", "Executive Summary"]).strip()
        key_points_body = _pick_section(sections, ["Key Points & Insights", "Key Points"]).strip()
        numbers_body = _pick_section(sections, ["Numbers"]).strip()
        chances_body = _pick_section(sections, ["Chances", "Opportunities"]).strip()
        risks_body = _pick_section(sections, ["Risks"]).strip()
        unknowns_body = _pick_section(sections, ["Unknowns"]).strip()

    if not summary_body:
        summary_body = "none"
    lines.append("## Summary")
    lines.append(summary_body)
    lines.append("")

    lines.append("## Key Points & Insights")
    lines.append(_ensure_bullets_or_none(key_points_body))
    lines.append("")

    lines.append("## Numbers")
    lines.append(_ensure_bullets_or_none(numbers_body))
    lines.append("")

    lines.append("## Chances")
    lines.append(_ensure_bullets_or_none(chances_body))
    lines.append("")

    lines.append("## Risks")
    lines.append(_ensure_bullets_or_none(risks_body))
    lines.append("")

    lines.append("## Unknowns")
    lines.append(_ensure_bullets_or_none(unknowns_body))
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


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


def _resolve_openrouter_api_key(cfg: Any) -> str | None:
    return (
        getattr(cfg.api, "openrouter_api_key", None)
        or os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("openrouter_key")
        or getattr(cfg.api, "openai_api_key", None)
        or os.environ.get("OPENAI_API_KEY")
    )


def _build_openrouter_headers(cfg: Any) -> dict[str, str]:
    headers: dict[str, str] = {}
    title_value = (getattr(cfg.api, "openrouter_app_title", None) or "TranscriptMiner").strip()
    if title_value:
        headers["X-Title"] = title_value
    referer_value = (getattr(cfg.api, "openrouter_http_referer", None) or "").strip()
    if referer_value:
        headers["HTTP-Referer"] = referer_value
    return headers


def _resolve_llm_backend(*, model: str) -> str:
    raw = (os.environ.get("TM_LLM_BACKEND") or "openrouter").strip().lower()
    if raw in {"gemini_cli", "gemini-cli"}:
        return "gemini_cli"
    if raw in {"openrouter", "openai"}:
        return "openrouter"
    if raw == "auto":
        if "gemini" in (model or "").strip().lower() and shutil.which("gemini"):
            return "gemini_cli"
        return "openrouter"
    logger.warning("Unknown TM_LLM_BACKEND=%r; falling back to openrouter", raw)
    return "openrouter"


def _normalize_gemini_cli_model(model: str) -> str:
    override = (os.environ.get("TM_GEMINI_CLI_MODEL") or "").strip()
    if override:
        return override
    normalized = (model or "").strip()
    if "/" in normalized:
        provider, suffix = normalized.split("/", 1)
        if provider.strip().lower() in {"google", "gemini"}:
            normalized = suffix.strip()
    return normalized or "gemini-3-flash-preview"


def _call_gemini_cli(
    *,
    model: str,
    system_prompt: str,
    user_prompt_text: str,
    timeout_s: int | None = None,
) -> str | None:
    gemini_bin = shutil.which("gemini")
    if not gemini_bin:
        logger.error("Gemini CLI backend selected but 'gemini' command is not available.")
        return None

    model_cli = _normalize_gemini_cli_model(model)
    if "pro" in model_cli.lower():
        logger.error("Gemini CLI model blocked by policy (no pro models): %s", model_cli)
        return None

    combined_prompt = (
        "Follow the SYSTEM PROMPT exactly.\n"
        "Use the USER PROMPT as task input.\n"
        "Return only the final answer content.\n"
        "Do not use thinking/reasoning mode.\n\n"
        "===== SYSTEM PROMPT =====\n"
        f"{system_prompt}\n\n"
        "===== USER PROMPT =====\n"
        f"{user_prompt_text}\n"
    )
    timeout_from_cfg = max(30, int(timeout_s or 900))
    timeout_s = max(
        30,
        int(os.environ.get("TM_GEMINI_CLI_TIMEOUT_SECONDS", str(timeout_from_cfg))),
    )
    cmd = [
        gemini_bin,
        "--model",
        model_cli,
        "-o",
        "json",
        "--approval-mode",
        "yolo",
        "-p",
        "Use the full prompt from stdin.",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=combined_prompt,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error("Gemini CLI call timed out after %ss (model=%s)", timeout_s, model_cli)
        return None
    except Exception as exc:
        logger.error("Gemini CLI invocation failed: %s", exc)
        return None

    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        if len(err) > 2000:
            err = err[:2000] + "..."
        logger.error("Gemini CLI call failed (exit=%s): %s", proc.returncode, err)
        return None

    raw = (proc.stdout or "").strip()
    if not raw.startswith("{"):
        # Find the first '{' to skip preamble text from Gemini CLI
        idx = raw.find("{")
        if idx != -1:
            raw = raw[idx:]
    
    try:
        payload, _ = json.JSONDecoder().raw_decode(raw)
    except Exception as exc:
        logger.error("Gemini CLI JSON parse failed (raw[:100]=%r): %s", raw[:100], exc)
        return None

    response = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(response, str):
        logger.error("Gemini CLI response missing 'response' text field.")
        return None

    try:
        stats = payload.get("stats") or {}
        models = stats.get("models") if isinstance(stats, dict) else {}
        model_stats = {}
        model_effective = model_cli
        if isinstance(models, dict):
            if model_cli in models and isinstance(models.get(model_cli), dict):
                model_stats = models[model_cli]
            elif models:
                model_effective = str(next(iter(models)))
                first = models.get(model_effective)
                if isinstance(first, dict):
                    model_stats = first
        api = model_stats.get("api") if isinstance(model_stats, dict) else {}
        tokens = model_stats.get("tokens") if isinstance(model_stats, dict) else {}
        logger.info(
            "gemini-cli usage model_requested=%s model_effective=%s requests=%s errors=%s latency_ms=%s tokens_input=%s tokens_total=%s tokens_thoughts=%s tokens_cached=%s",
            model_cli,
            model_effective,
            (api.get("totalRequests") if isinstance(api, dict) else 0),
            (api.get("totalErrors") if isinstance(api, dict) else 0),
            (api.get("totalLatencyMs") if isinstance(api, dict) else 0),
            (tokens.get("input") if isinstance(tokens, dict) else 0),
            (tokens.get("total") if isinstance(tokens, dict) else 0),
            (tokens.get("thoughts") if isinstance(tokens, dict) else 0),
            (tokens.get("cached") if isinstance(tokens, dict) else 0),
        )
    except Exception:
        pass

    return response


def summarize_transcript_ref(
    *,
    cfg: Any,
    ref: "TranscriptRef",
    run_stats: RunStats | None = None,
    rate_limit: Callable[[], None] | None = None,
) -> bool:
    """Generate a per-video summary for a single transcript (streaming-safe)."""
    llm_cfg = cfg.analysis.llm
    if not llm_cfg.enabled:
        return False
    if llm_cfg.mode != "per_video":
        logger.warning("Streaming summary skipped (analysis.llm.mode != per_video).")
        return False

    model = llm_cfg.model or ""
    system_prompt = llm_cfg.system_prompt or ""
    user_prompt_template = llm_cfg.user_prompt_template or ""
    max_input_tokens = llm_cfg.max_input_tokens
    max_output_tokens = llm_cfg.max_output_tokens
    llm_timeout_s = max(30, int(getattr(llm_cfg, "timeout_s", 600)))

    llm_backend = _resolve_llm_backend(model=model)
    openrouter_api_key: str | None = None
    openrouter_headers: dict[str, str] = {}
    if llm_backend == "openrouter":
        openrouter_api_key = _resolve_openrouter_api_key(cfg)
        if not openrouter_api_key:
            logger.error("LLM API key missing (set OPENROUTER_API_KEY).")
            if run_stats is not None:
                run_stats.inc("summaries_failed")
            return False
        openrouter_headers = _build_openrouter_headers(cfg)

    def _format_user_prompt(
        *,
        transcripts: str,
        transcript_count: int,
        transcript: str = "",
        topic: str = "",
        video_id: str = "",
        url: str = "",
        title: str = "",
        channel_namespace: str = "",
        published_at: str = "",
        fetched_at: str = "",
    ) -> str:
        current_utc = _now_utc_hm()
        current_vienna = _now_vienna_hm()
        body = user_prompt_template.format(
            transcripts=transcripts,
            transcript_count=str(transcript_count),
            transcript=transcript,
            topic=topic,
            video_id=video_id,
            url=url,
            title=title,
            channel_namespace=channel_namespace,
            published_at=published_at,
            fetched_at=fetched_at,
            current_utc=current_utc,
            current_vienna=current_vienna,
            now_utc=current_utc,
            now_vienna=current_vienna,
            current_date_utc=current_utc.split(" ")[0] if current_utc else "",
            current_date_vienna=current_vienna.split(" ")[0] if current_vienna else "",
        )
        return _build_time_awareness_block(
            current_utc=current_utc, current_vienna=current_vienna
        ) + body

    def _call_llm(*, user_prompt_text: str) -> str | None:
        if llm_backend == "gemini_cli":
            return _call_gemini_cli(
                model=model,
                system_prompt=system_prompt,
                user_prompt_text=user_prompt_text,
                timeout_s=llm_timeout_s,
            )

        try:
            req_kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt_text},
                ],
                "temperature": llm_cfg.temperature,
            }
            if llm_cfg.reasoning_effort:
                req_kwargs["extra_body"] = {"reasoning": {"effort": llm_cfg.reasoning_effort}}
            if openrouter_headers:
                req_kwargs["extra_headers"] = dict(openrouter_headers)
            if max_output_tokens is not None:
                req_kwargs["max_tokens"] = int(max_output_tokens)

            from openai import OpenAI  # type: ignore

            client = OpenAI(
                api_key=openrouter_api_key,
                base_url=_OPENROUTER_BASE_URL,
                timeout=llm_timeout_s,
            )
            response = call_openai_with_retry(
                client.chat.completions.create,
                **req_kwargs,
                log_json=cfg.logging.llm_request_json,
            )
            return _extract_chat_content(response)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return None

    tpath = Path(ref.transcript_path)
    if not tpath.exists():
        return False

    raw_hash = _sha256_raw_hash(tpath)
    transcript_text = _load_transcript_text(tpath)
    transcript_text = transcript_text[: llm_cfg.max_chars_per_transcript]

    # Load metadata for prompt + potential backfill policy checks.
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

    summary_path = cfg.output.get_summary_path(
        ref.video_id, channel_handle=ref.channel_namespace
    )
    topic = cfg.output.get_topic() if cfg.output.is_global_layout() else ""
    was_healed = False
    if summary_path.exists():
        is_valid, reason = _existing_summary_is_valid(
            summary_path=summary_path,
            ref=ref,
            raw_hash=raw_hash,
            expected_topic=cfg.output.get_topic(),
        )
        if is_valid:
            _sync_existing_summary(
                summary_path=summary_path,
                topic=topic or ref.channel_namespace,
                ref=ref,
                fallback_title="unknown",
                fallback_published_at="unknown",
            )
            if run_stats is not None:
                run_stats.inc("summaries_skipped_valid")
            return True
        allow_regen, policy_reason = _allow_regeneration_for_invalid_summary(
            cfg=cfg,
            reason=reason,
            ref=ref,
            published_at=str(published_at or ""),
        )
        if not allow_regen:
            logger.info(
                "Summary invalid but regeneration deferred by backfill policy "
                "(video_id=%s channel=%s reason=%s policy=%s)",
                ref.video_id,
                ref.channel_namespace,
                reason,
                policy_reason,
            )
            _sync_existing_summary(
                summary_path=summary_path,
                topic=topic or ref.channel_namespace,
                ref=ref,
                fallback_title=video_title,
                fallback_published_at=published_at,
            )
            if run_stats is not None:
                run_stats.inc("summaries_skipped_backfill")
            return True
        _backup_corrupted_summary(summary_path)
        was_healed = True
        logger.warning(
            "Summary invalid; regenerating (video_id=%s channel=%s reason=%s policy=%s)",
            ref.video_id,
            ref.channel_namespace,
            reason,
            policy_reason,
        )

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
        transcript=transcript_text,
        topic=topic or ref.channel_namespace,
        video_id=ref.video_id,
        url=_youtube_url(ref.video_id),
        title=str(video_title or "unknown"),
        channel_namespace=str(ref.channel_namespace or "unknown"),
        published_at=str(published_at or "unknown"),
        fetched_at=_now_utc_hm(),
    )

    if max_input_tokens is not None:
        per_prompt_tokens = calculate_token_count(
            system_prompt, model=model
        ) + calculate_token_count(per_user_prompt, model=model)
        if per_prompt_tokens > max_input_tokens:
            logger.error(
                "LLM prompt exceeds max_input_tokens (per-video) video_id=%s",
                ref.video_id,
            )
            if run_stats is not None:
                run_stats.inc("summaries_failed")
            return False

    summary_started_at = _now_utc_iso()
    logger.info(
        "Summary start: video_id=%s channel=%s at=%s",
        ref.video_id,
        ref.channel_namespace,
        summary_started_at,
    )

    if rate_limit is not None:
        rate_limit()

    out = _call_llm(user_prompt_text=per_user_prompt)
    if out is None:
        logger.info(
            "Summary finish: video_id=%s status=failed at=%s",
            ref.video_id,
            _now_utc_iso(),
        )
        if run_stats is not None:
            run_stats.inc("summaries_failed")
        return False

    if max_output_tokens is not None:
        output_tokens = calculate_token_count(out, model=model)
        if output_tokens > max_output_tokens:
            logger.error(
                "LLM output exceeds max_output_tokens (per-video) video_id=%s",
                ref.video_id,
            )
            if run_stats is not None:
                run_stats.inc("summaries_failed")
            return False

    # Keep the prompt output as the persisted summary (no post-normalization).
    md = str(out or "").strip()
    if md:
        md += "\n"
    else:
        md = "# empty\n"
    _atomic_write_text(summary_path, md)
    legacy_json = summary_path.with_suffix(".json")
    if legacy_json.exists() and legacy_json.name.endswith(".summary.json"):
        try:
            legacy_json.unlink()
        except Exception:
            logger.warning("Failed to delete legacy summary JSON: %s", legacy_json)
    _maybe_sync_summary_to_owui(
        topic=topic or ref.channel_namespace,
        video_id=ref.video_id,
        channel_namespace=ref.channel_namespace,
        title=video_title,
        published_at=published_at,
        markdown=md,
    )

    summary_finished_at = _now_utc_iso()
    logger.info(
        "Summary finish: video_id=%s status=ok at=%s",
        ref.video_id,
        summary_finished_at,
    )

    if run_stats is not None:
        run_stats.inc("summaries_created")
        if was_healed:
            run_stats.inc("summaries_healed")

    return True


def _backup_corrupted_summary(path: Path) -> None:
    if not path.exists():
        return
    backup_path = path.with_name(f"{path.stem}.corrupted.{int(time.time())}{path.suffix}")
    try:
        path.rename(backup_path)
        logger.warning("Backed up corrupted summary to %s", backup_path)
    except Exception:
        logger.exception("Failed to backup corrupted summary: %s", path)


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

    # Accept either the legacy canonical summary format OR the prompt-v2 wrapped format.
    src = _parse_source_block(text)
    if src:
        sections = _extract_level2_sections(text)
        for name in _REQUIRED_SECTIONS:
            if name not in sections:
                return False, f"missing_section:{name}"
        for k in _REQUIRED_SOURCE_KEYS:
            if not src.get(k):
                return False, f"missing_source_key:{k}"
        if src.get("video_id") != ref.video_id:
            return False, "video_id_mismatch"
        if src.get("channel_namespace") != ref.channel_namespace:
            return False, "channel_namespace_mismatch"
        _ = raw_hash
        _ = expected_topic
        return True, "ok"

    wrapped_docs = _extract_rag_wrapped_docs(text)
    if not wrapped_docs:
        return False, "missing_wrapped_docs"
    has_video_id = False
    has_channel_namespace = False
    for doc in wrapped_docs:
        fm = doc.get("frontmatter") or {}
        if not isinstance(fm, dict):
            continue
        if str(fm.get("video_id") or "").strip() == ref.video_id:
            has_video_id = True
        if str(fm.get("channel_namespace") or "").strip() == ref.channel_namespace:
            has_channel_namespace = True
    if not has_video_id:
        return False, "video_id_mismatch"
    if not has_channel_namespace:
        return False, "channel_namespace_mismatch"
    # We no longer bind summaries to a transcript content hash (markdown-only).
    _ = raw_hash
    _ = expected_topic
    return True, "ok"


def _youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


### JSON-based summary rendering was removed in favor of a markdown-only pipeline.


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

    # Fast-path: strict JSON is not Markdown.
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
    llm_timeout_s = max(30, int(getattr(llm_cfg, "timeout_s", 600)))

    def _format_user_prompt(
        *,
        transcripts: str,
        transcript_count: int,
        transcript: str = "",
        topic: str = "",
        video_id: str = "",
        url: str = "",
        title: str = "",
        channel_namespace: str = "",
        published_at: str = "",
        fetched_at: str = "",
    ) -> str:
        current_utc = _now_utc_hm()
        current_vienna = _now_vienna_hm()
        body = user_prompt_template.format(
            transcripts=transcripts,
            transcript_count=str(transcript_count),
            transcript=transcript,
            topic=topic,
            video_id=video_id,
            url=url,
            title=title,
            channel_namespace=channel_namespace,
            published_at=published_at,
            fetched_at=fetched_at,
            current_utc=current_utc,
            current_vienna=current_vienna,
            now_utc=current_utc,
            now_vienna=current_vienna,
            current_date_utc=current_utc.split(" ")[0] if current_utc else "",
            current_date_vienna=current_vienna.split(" ")[0] if current_vienna else "",
        )
        return _build_time_awareness_block(
            current_utc=current_utc, current_vienna=current_vienna
        ) + body

    llm_backend = _resolve_llm_backend(model=model)
    openrouter_api_key: str | None = None
    openrouter_headers: dict[str, str] = {}
    if llm_backend == "openrouter":
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
                    transcript=text,
                    topic=cfg.output.get_topic() if cfg.output.is_global_layout() else ref.channel_namespace,
                    video_id=ref.video_id,
                    url=_youtube_url(ref.video_id),
                    title=str(video_title or "unknown"),
                    channel_namespace=str(ref.channel_namespace or "unknown"),
                    published_at=str(published_at or "unknown"),
                    fetched_at=_now_utc_hm(),
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
            topic=cfg.output.get_topic() if cfg.output.is_global_layout() else "",
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
        if llm_backend == "gemini_cli":
            content = _call_gemini_cli(
                model=model,
                system_prompt=system_prompt,
                user_prompt_text=user_prompt_text,
                timeout_s=llm_timeout_s,
            )
            if content is None:
                _fail(
                    "analysis_llm_call_failed",
                    "Gemini CLI call failed",
                    {"model": model},
                )
            return content

        response: Any
        try:
            req_kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt_text},
                ],
                "temperature": llm_cfg.temperature,
            }
            if llm_cfg.reasoning_effort:
                req_kwargs["extra_body"] = {"reasoning": {"effort": llm_cfg.reasoning_effort}}
            if openrouter_headers:
                req_kwargs["extra_headers"] = dict(openrouter_headers)
            if max_output_tokens is not None:
                req_kwargs["max_tokens"] = int(max_output_tokens)

            if chat_completion_create is None:
                # Import openai lazily so offline environments can still import this module.
                # Use the v1+ OpenAI Python SDK client API.
                from openai import OpenAI  # type: ignore

                client = OpenAI(
                    api_key=openrouter_api_key,
                    base_url=_OPENROUTER_BASE_URL,
                    timeout=llm_timeout_s,
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

        # Markdown-only pipeline: aggregate output is treated as free-form markdown.
    else:
        # Per-video: run one call per transcript and persist per-video extract
        # next to the original channel output root.
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
            # Markdown-only pipeline: use the same helper as streaming summaries.
            ok = summarize_transcript_ref(
                cfg=cfg,
                ref=ref,
                run_stats=run_stats,
                rate_limit=_apply_llm_rate_limit,
            )
            _maybe_set_last_output(idx, None)
            if not ok:
                _fail(
                    "analysis_llm_per_video_failed",
                    "LLM per-video summary failed",
                    {"video_id": ref.video_id, "channel_namespace": ref.channel_namespace},
                )
                return

            summary_path = cfg.output.get_summary_path(
                ref.video_id, channel_handle=ref.channel_namespace
            )
            with per_video_written_lock:
                per_video_written.append(
                    {
                        "video_id": ref.video_id,
                        "channel_namespace": ref.channel_namespace,
                        "path": str(summary_path),
                    }
                )

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
