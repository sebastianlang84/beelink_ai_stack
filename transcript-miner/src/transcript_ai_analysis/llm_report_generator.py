from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import yaml

from common.utils import call_openai_with_retry

logger = logging.getLogger(__name__)

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_TICKER_IN_PARENS_RE = re.compile(
    r"^(.+?)\s*\((?P<ticker>[A-Z][A-Z0-9.\-]{0,9})\)\s*$"
)

# Model context limits (approximate, in tokens) — OpenRouter model IDs
MODEL_LIMITS = {
    "openai/gpt-5.2": 400_000,
    "google/gemini-3-pro-preview": 1_000_000,
    "google/gemini-3-flash-preview": 1_000_000,
    "anthropic/claude-sonnet-4.5": 200_000,
}

# Default Prompts (Fallback)
DEFAULT_PROMPTS = {
    "de": "Du bist ein erfahrener Analyst für Video-Transkripte. Erstelle einen strukturierten Bericht.",
    "en": "You are an experienced video transcript analyst. Create a structured report.",
}

GLOSSARY = {
    "mNAV": {"de": "multiple of Net Asset Value", "en": "multiple of Net Asset Value"},
    "NAV": {"de": "Net Asset Value", "en": "Net Asset Value"},
    "YTD": {"de": "Year-to-Date", "en": "Year-to-Date"},
    "DCF": {"de": "Discounted Cash Flow", "en": "Discounted Cash Flow"},
    "EV": {"de": "Enterprise Value", "en": "Enterprise Value"},
    "FCF": {"de": "Free Cash Flow", "en": "Free Cash Flow"},
    "P/E": {"de": "Price/Earnings", "en": "Price/Earnings"},
    "P/FCF": {"de": "Price/Free Cash Flow", "en": "Price/Free Cash Flow"},
    "ICE": {"de": "Internal Combustion Engine", "en": "Internal Combustion Engine"},
    "TPU": {"de": "Tensor Processing Unit", "en": "Tensor Processing Unit"},
}


def _canonicalize_symbol_key(symbol_label: str) -> str:
    s = symbol_label.strip()
    m = _TICKER_IN_PARENS_RE.match(s)
    if m:
        return m.group("ticker")
    return s


def _normalize_channel_namespace(raw: str | None, transcript_path: str | None) -> str:
    ns = (raw or "").strip()
    if ns:
        if ns.endswith("/1_transcripts"):
            return ns[: -len("/1_transcripts")]
        return ns

    if transcript_path:
        try:
            p = Path(transcript_path)
            parts = p.parts
            if "1_transcripts" in parts:
                idx = parts.index("1_transcripts")
                if idx + 1 < len(parts) - 1:
                    return parts[idx + 1]
                if idx - 1 >= 0:
                    return parts[idx - 1]
        except Exception:
            pass

    return "unknown"


def _format_glossary_md(lang: str) -> str:
    lines = []
    for key in sorted(GLOSSARY.keys()):
        expl = GLOSSARY[key].get(lang) or GLOSSARY[key]["en"]
        lines.append(f"- **{key}**: {expl}")
    return "\n".join(lines)


def _quality_bucket(quality: dict[str, Any] | None) -> str:
    if not isinstance(quality, dict):
        return "unknown"
    grade = str(quality.get("grade") or "unknown").strip().lower()
    reasons = quality.get("reasons") or []
    if isinstance(reasons, list):
        reasons_text = " ".join(str(r).lower() for r in reasons)
        if "truncat" in reasons_text or "cuts off" in reasons_text:
            return "truncated"
    return grade or "unknown"


def _compact_summary_for_llm(summary: dict[str, Any]) -> dict[str, Any]:
    source = summary.get("source") or {}
    if not isinstance(source, dict):
        source = {}

    raw_channel = source.get("channel_namespace")
    transcript_path = source.get("transcript_path")
    channel = _normalize_channel_namespace(raw_channel, transcript_path)

    video_id = source.get("video_id") or summary.get("video_id")
    if not isinstance(video_id, str):
        video_id = ""
    video_title = summary.get("video_title") or summary.get("title")
    channel_name = summary.get("channel_name")

    out: dict[str, Any] = {
        "video_id": video_id,
        "channel": channel,
        "transcript_quality": summary.get("transcript_quality"),
        "stocks_covered": [],
        "macro_insights": [],
    }
    if isinstance(video_title, str) and video_title.strip():
        out["video_title"] = video_title
    if isinstance(channel_name, str) and channel_name.strip():
        out["channel_name"] = channel_name

    stocks = summary.get("stocks_covered") or []
    if isinstance(stocks, list):
        compact_stocks = []
        for s in stocks[:10]:
            if not isinstance(s, dict):
                continue
            canonical = s.get("canonical")
            if not isinstance(canonical, str) or not canonical.strip():
                continue
            compact_stocks.append(
                {
                    "canonical": canonical,
                    "key": _canonicalize_symbol_key(canonical),
                    "confidence": s.get("confidence"),
                    "why_covered": s.get("why_covered"),
                    "evidence_quotes": [
                        (e.get("quote") if isinstance(e, dict) else None)
                        for e in (s.get("evidence") or [])[:2]
                        if isinstance(e, dict) and isinstance(e.get("quote"), str)
                    ],
                }
            )
        out["stocks_covered"] = compact_stocks

    macro = summary.get("macro_insights") or []
    if isinstance(macro, list):
        out["macro_insights"] = [
            {"claim": m.get("claim"), "confidence": m.get("confidence")}
            for m in macro[:5]
            if isinstance(m, dict) and isinstance(m.get("claim"), str)
        ]

    return out


def _build_deterministic_appendix(
    *,
    lang: str,
    global_data: dict[str, Any],
    by_symbol_data: dict[str, Any] | None,
    by_channel_data: dict[str, Any] | None,
    summaries: list[dict[str, Any]],
) -> str:
    title = (
        "Deterministische Daten (Appendix)"
        if lang == "de"
        else "Deterministic Data (Appendix)"
    )
    lines = [f"## {title}"]

    freshness = global_data.get("freshness") or {}
    covered_period = global_data.get("covered_period") or {}
    if isinstance(freshness, dict) or isinstance(covered_period, dict):
        lines.append("")
        lines.append("### Scope & Freshness" if lang == "en" else "### Zeitraum & Freshness")
        as_of = global_data.get("as_of")
        if isinstance(as_of, str):
            lines.append(f"- as_of: `{as_of}`")
        if isinstance(covered_period, dict):
            min_d = covered_period.get("min_published_date")
            max_d = covered_period.get("max_published_date")
            if min_d or max_d:
                lines.append(f"- covered_period: {min_d} .. {max_d}")
        if isinstance(freshness, dict) and freshness:
            for k in ("video_count", "median_age_days", "pct_videos_lt_30d", "pct_videos_lt_60d", "pct_videos_lt_90d"):
                if k in freshness:
                    lines.append(f"- {k}: {freshness[k]}")

    # Top stocks table
    metrics = (by_symbol_data or {}).get("metrics") or []
    if isinstance(metrics, list) and metrics:
        sorted_metrics = sorted(
            (m for m in metrics if isinstance(m, dict)),
            key=lambda m: (
                -int(m.get("mention_count") or 0),
                str(m.get("key") or ""),
            ),
        )
        top = sorted_metrics[:20]
        lines.append("")
        lines.append("### Top Stocks" if lang == "en" else "### Top-Aktien")
        lines.append("")
        lines.append("| Stock | Mentions | Videos | Channels | Recent30 Videos | Stale Days | Quality (uniq videos) |")
        lines.append("|---|---:|---:|---:|---:|---:|---|")
        for m in top:
            label = m.get("preferred_label") or m.get("key") or "N/A"
            recent_30_v = m.get("recent_30_unique_video_count", 0)
            stale_days = m.get("stale_days", "")
            q = m.get("quality_unique_video_counts") or {}
            q_str = (
                ", ".join(f"{k}={v}" for k, v in q.items())
                if isinstance(q, dict) and q
                else "unknown"
            )
            lines.append(
                f"| {label} | {m.get('mention_count', 0)} | {m.get('unique_video_count', 0)} | {m.get('creator_count', 0)} | {recent_30_v} | {stale_days} | {q_str} |"
            )

        # Traceability: sources per top stock
        sources_by_key: dict[str, list[tuple[str, str, str]]] = {}
        quality_by_video: dict[str, str] = {}
        quotes_by_key: dict[str, list[tuple[str, str, str]]] = {}
        for s in summaries:
            if not isinstance(s, dict):
                continue
            source = s.get("source") or {}
            if not isinstance(source, dict):
                continue
            video_id = source.get("video_id")
            if not isinstance(video_id, str) or not video_id:
                continue
            channel = _normalize_channel_namespace(
                source.get("channel_namespace"), source.get("transcript_path")
            )
            title = s.get("video_title") or s.get("title")
            if not isinstance(title, str) or not title.strip():
                title = ""
            quality_by_video[video_id] = _quality_bucket(s.get("transcript_quality"))
            for stock in (s.get("stocks_covered") or []):
                if not isinstance(stock, dict):
                    continue
                canonical = stock.get("canonical")
                if not isinstance(canonical, str) or not canonical.strip():
                    continue
                key = _canonicalize_symbol_key(canonical)
                sources_by_key.setdefault(key, []).append((channel, title, video_id))
                evidence = stock.get("evidence") or []
                if isinstance(evidence, list):
                    for ev in evidence:
                        if not isinstance(ev, dict):
                            continue
                        q = ev.get("quote")
                        if isinstance(q, str) and q.strip():
                            quotes_by_key.setdefault(key, []).append((channel, title, q.strip()))

        lines.append("")
        lines.append("### Sources (Top Stocks)" if lang == "en" else "### Quellen (Top-Aktien)")
        for m in top:
            key = m.get("key")
            label = m.get("preferred_label") or key
            if not isinstance(key, str) or not key:
                continue
            sources = sources_by_key.get(key) or []
            parts = []
            seen_src: set[tuple[str, str, str]] = set()
            for ch, title, vid in sorted(sources, key=lambda x: (x[0], x[2], x[1])):
                key_t = (ch, title or "", vid)
                if key_t in seen_src:
                    continue
                seen_src.add(key_t)
                if title:
                    parts.append(f"{ch} — {title} ({vid})")
                else:
                    parts.append(f"{ch} ({vid})")
            src_line = "; ".join(parts) if parts else ("(none)" if lang == "en" else "(keine)")

            # Quality summary for this key based on source videos
            vids_all: set[str] = set()
            for vids in sources.values():
                vids_all |= vids
            q_counts: dict[str, int] = {}
            for vid in vids_all:
                q = quality_by_video.get(vid, "unknown")
                q_counts[q] = q_counts.get(q, 0) + 1
            q_str = (
                ", ".join(f"{k}={v}" for k, v in sorted(q_counts.items()))
                if q_counts
                else "unknown"
            )
            lines.append(f"- **{label}** — sources: {src_line} — quality: {q_str}")

            # Add 1–2 verbatim quotes as traceability anchors (deterministic order).
            quotes = quotes_by_key.get(key, [])
            if quotes:
                seen: set[str] = set()
                picked: list[tuple[str, str, str]] = []
                for ch, title, q in quotes:
                    if q in seen:
                        continue
                    seen.add(q)
                    picked.append((ch, title, q))
                    if len(picked) >= 2:
                        break
                for ch, title, q in picked:
                    src = f"{ch} — {title}" if title else ch
                    lines.append(f"  - quote ({src}): {q}")

    # Channel table (with transcript/summaries counts if present)
    cmetrics = (by_channel_data or {}).get("metrics") or []
    if isinstance(cmetrics, list) and cmetrics:
        lines.append("")
        lines.append("### Channels" if lang == "en" else "### Channels")
        lines.append("")
        lines.append("| Channel | Transcripts | Summaries | Videos w/ Mentions | Mentions |")
        lines.append("|---|---:|---:|---:|---:|")
        for m in cmetrics:
            if not isinstance(m, dict):
                continue
            lines.append(
                f"| {m.get('key','?')} | {m.get('transcript_video_count', 0)} | {m.get('summary_video_count', 0)} | {m.get('unique_video_count', 0)} | {m.get('mention_count', 0)} |"
            )

    return "\n".join(lines).strip() + "\n"


def estimate_tokens(text: str) -> int:
    """Rough estimation of tokens (4 chars per token)."""
    return len(text) // 4


def load_yaml_config(config_path: Path) -> Optional[dict[str, Any]]:
    """Loads a YAML config file."""
    try:
        if not config_path.exists():
            return None
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error("Error loading config %s: %s", config_path, e)
        return None


def discover_config_for_run(
    run_dir: Path, config_dir: Path | None = None
) -> Optional[dict[str, Any]]:
    """Discover config by matching output paths (global or legacy)."""
    config_dir = config_dir or Path("config")
    if not config_dir.exists():
        return None

    try:
        abs_run = run_dir.resolve()
    except Exception:
        abs_run = run_dir

    for config_file in config_dir.glob("*.yaml"):
        cfg = load_yaml_config(config_file)
        if not cfg:
            continue

        output_cfg = cfg.get("output", {}) if isinstance(cfg, dict) else {}
        output_root = output_cfg.get("root_path")
        output_global = output_cfg.get("global") or output_cfg.get("global_root")
        output_topic = output_cfg.get("topic")
        if output_global and output_topic:
            config_loc = config_file.parent
            resolved_global = (config_loc / output_global).resolve()
            reports_root = resolved_global / "reports" / str(output_topic)
            history_root = resolved_global / "history" / str(output_topic)
            if str(abs_run).startswith(str(reports_root)) or str(abs_run).startswith(
                str(history_root)
            ):
                logger.info("Discovered matching config: %s", config_file)
                return cfg

        if output_root:
            config_loc = config_file.parent
            resolved_output = (config_loc / output_root).resolve()
            if str(abs_run).startswith(str(resolved_output)):
                logger.info("Discovered matching config: %s", config_file)
                return cfg

    return None


def load_template(topic: str, lang: str) -> str:
    """Loads the report template for the given topic and language."""
    template_path = Path(f"templates/report_{topic}_{lang}.md")
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def get_topic_from_config(config: dict[str, Any]) -> str:
    """Extracts topic from config output path as fallback."""
    output_cfg = config.get("output", {}) if isinstance(config, dict) else {}
    topic = output_cfg.get("topic")
    if isinstance(topic, str) and topic.strip():
        return topic.strip()
    root = output_cfg.get("root_path", "")
    parts = Path(root).parts
    if parts and parts[-1] != "output":
        return parts[-1]
    return "default"


def find_latest_run_dir(base_path: Path) -> Optional[Path]:
    """Finds the latest run directory in the given base path."""
    if not base_path.exists():
        return None

    if (base_path / "aggregates" / "global.json").exists():
        return base_path

    # Global layout: output/history/<topic>/<YYYY-MM-DD>/<bundle>
    bundles: list[Path] = []
    date_dirs = [d for d in base_path.iterdir() if d.is_dir()]
    for date_dir in date_dirs:
        for candidate in date_dir.iterdir():
            if candidate.is_dir() and "__" in candidate.name:
                bundles.append(candidate)

    if bundles:
        bundles.sort(key=lambda x: x.name, reverse=True)
        return bundles[0]

    run_dirs = [
        d for d in base_path.iterdir() if d.is_dir() and d.name.startswith("run_")
    ]
    if not run_dirs:
        return None

    run_dirs.sort(key=lambda x: x.name, reverse=True)
    return run_dirs[0]


def load_json_file(file_path: Path) -> Optional[dict[str, Any]]:
    """Loads a JSON file."""
    try:
        if not file_path.exists():
            logger.warning("File not found: %s", file_path)
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Error loading %s: %s", file_path, e)
        return None


def _load_run_metadata(run_dir: Path) -> tuple[str, str]:
    run_id = run_dir.name
    run_timestamp = "Unknown"
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            run_id = manifest.get("run_id", run_id)
            run_timestamp = manifest.get("timestamp", run_timestamp)
        except Exception:
            pass

    if run_timestamp == "Unknown":
        try:
            parts = run_dir.name.split("_")
            if len(parts) >= 3:
                date_part = parts[1]
                time_part = parts[2].rstrip("Z")
                dt = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
                run_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            pass

    return run_id, run_timestamp


def generate_reports(
    *,
    run_dir: Path,
    config: Optional[dict[str, Any]] = None,
    report_lang: str = "de",
) -> list[Path]:
    """Generate Markdown report(s) under the given run directory.

    `report_lang` controls which report(s) are written:
    - "de": write `report.md` (German)
    - "en": write `report.md` (English)
    - "both": write `report_de.md` and `report_en.md`
    """
    aggregates_dir = run_dir / "aggregates"
    global_json_path = aggregates_dir / "global.json"

    logger.info("Loading data from %s", aggregates_dir)

    global_data = load_json_file(global_json_path)
    if not global_data:
        logger.error("Could not load global.json. Aborting.")
        return []

    by_symbol_data = load_json_file(aggregates_dir / "by_symbol.json")
    by_channel_data = load_json_file(aggregates_dir / "by_channel.json")

    summaries: list[dict[str, Any]] = []
    summaries_dir_path: Optional[Path] = None
    if "generated_from" in global_data and "summaries_dir" in global_data["generated_from"]:
        summaries_dir_path = Path(global_data["generated_from"]["summaries_dir"])

    if summaries_dir_path and summaries_dir_path.exists():
        logger.info("Loading summaries from %s", summaries_dir_path)
        for summary_file in summaries_dir_path.rglob("*.json"):
            s_data = load_json_file(summary_file)
            if s_data:
                summaries.append(s_data)
    elif summaries_dir_path:
        logger.warning("Summaries directory not found: %s", summaries_dir_path)

    compact_summaries = [_compact_summary_for_llm(s) for s in summaries]

    context = {
        "global_metrics": global_data,
        "stock_mentions": by_symbol_data,
        "channel_stats": by_channel_data,
        "summaries": compact_summaries,
        "glossary": {k: GLOSSARY[k] for k in sorted(GLOSSARY.keys())},
    }
    context_str = json.dumps(context, indent=2, ensure_ascii=False)

    run_id, run_timestamp = _load_run_metadata(run_dir)
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        now_vienna = datetime.now(ZoneInfo("Europe/Vienna")).strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        now_vienna = "unknown"

    topic = "default"
    report_config = {}
    if config:
        topic = get_topic_from_config(config)
        report_config = config.get("report", {}).get("llm", {})

    logger.info("Using topic: %s", topic)

    model = report_config.get("model", "openai/gpt-5.2")
    config_prompts = report_config.get("system_prompt", {})

    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("No API key found. Please set OPENROUTER_API_KEY or OPENAI_API_KEY.")
        return []

    api_config = config.get("api", {}) if isinstance(config, dict) else {}
    openrouter_headers: dict[str, str] = {}
    title_raw = api_config.get("openrouter_app_title") if isinstance(api_config, dict) else None
    title_value = title_raw.strip() if isinstance(title_raw, str) and title_raw.strip() else "TranscriptMiner"
    if title_value:
        openrouter_headers["X-Title"] = title_value
    referer_raw = api_config.get("openrouter_http_referer") if isinstance(api_config, dict) else None
    referer_value = referer_raw.strip() if isinstance(referer_raw, str) else ""
    if referer_value:
        openrouter_headers["HTTP-Referer"] = referer_value

    try:
        from openai import OpenAI
    except ImportError as exc:
        logger.error("openai package not installed: %s", exc)
        return []

    client = OpenAI(api_key=api_key, base_url=_OPENROUTER_BASE_URL)

    if report_lang not in {"de", "en", "both"}:
        logger.error("Invalid report_lang=%r (expected: de|en|both)", report_lang)
        return []

    languages: list[dict[str, str]] = []
    if report_lang == "both":
        languages.append(
            {"code": "en", "filename": "report_en.md", "lang_name": "English"}
        )
        languages.append(
            {"code": "de", "filename": "report_de.md", "lang_name": "German"}
        )
    elif report_lang == "en":
        languages.append({"code": "en", "filename": "report.md", "lang_name": "English"})
    else:
        languages.append({"code": "de", "filename": "report.md", "lang_name": "German"})

    written: list[Path] = []
    for lang in languages:
        logger.info("Generating report in %s...", lang["lang_name"])

        system_prompt = config_prompts.get(
            lang["code"], DEFAULT_PROMPTS.get(lang["code"], DEFAULT_PROMPTS["en"])
        )
        template_content = load_template(topic, lang["code"])
        template_instruction = ""
        if template_content:
            template_instruction = (
                f"\n\nUse the following structure for the report:\n\n{template_content}"
            )

        appendix = _build_deterministic_appendix(
            lang=lang["code"],
            global_data=global_data,
            by_symbol_data=by_symbol_data,
            by_channel_data=by_channel_data,
            summaries=summaries,
        )

        preamble_title = "Transkript-Analysebericht" if lang["code"] == "de" else "Transcript Analysis Report"
        disclaimer = (
            "Hinweis: Dieser Report fasst Channel-Content zusammen und ist keine Anlageberatung."
            if lang["code"] == "de"
            else "Note: This report summarizes channel content and is not investment advice."
        )
        quality_legend_title = "Datenqualität (Skala)" if lang["code"] == "de" else "Data quality (scale)"
        quality_legend_body = (
            "- ok: ausreichend vollständig\n- low: eingeschränkte Qualität\n- truncated: erkennbar abgeschnitten"
            if lang["code"] == "de"
            else "- ok: sufficiently complete\n- low: limited quality\n- truncated: clearly cut off"
        )
        preamble = (
            f"# {preamble_title}\n\n"
            f"{disclaimer}\n\n"
            f"## Glossar\n{_format_glossary_md(lang['code'])}\n\n"
            f"## {quality_legend_title}\n{quality_legend_body}\n"
        )

        if lang["code"] == "de":
            user_prompt = (
                "Hier sind die aggregierten Daten des letzten Transkript-Analyse-Laufs:\n\n"
                f"```json\n{context_str}\n```\n\n"
                "Bitte erstelle einen Markdown-Bericht.\n"
                "Wichtig:\n"
                "- Keine erfundenen Fakten/Zahlen; nutze nur das Material.\n"
                "- Harte Aussagen immer mit Quellenbezug (Channel + Video-Titel + Video-ID) und Unsicherheit bei `low`/`truncated`.\n"
                "- Für Top-Aktien: Bull-Case, Bear-Case, Katalysatoren, Widerlegungskriterien (alles aus Channel-Content abgeleitet).\n"
                "- Mini-Factsheet: Zahlen/Multiples nur wenn explizit im Material; sonst weglassen/unknown.\n"
                "- Quellenformat (pflicht): Channel + Video-Titel + Video-ID (wenn Titel fehlt: Channel + Video-ID).\n"
                f"{template_instruction}\n\n"
                "**Berichts-Metadaten**:\n"
                f"- Run ID: {run_id}\n"
                f"- Run Datum: {run_timestamp}\n"
                f"- Bericht generiert (UTC): {now_utc}\n"
                f"- Bericht generiert (Europe/Vienna): {now_vienna}\n"
                f"- Topic: {topic}\n\n"
                "Recency-Regel: Neuere Evidenz hat hoehere Prioritaet; Alter der Quellen bei relevanten Aussagen explizit nennen.\n\n"
                "Formatiere die Ausgabe als sauberes Markdown auf Deutsch."
            )
        else:
            user_prompt = (
                "Here is the aggregated data from the latest transcript analysis run:\n\n"
                f"```json\n{context_str}\n```\n\n"
                "Please generate a Markdown report.\n"
                "Important:\n"
                "- Do not invent facts/numbers; only use the provided material.\n"
                "- For hard claims, include source linkage (channel + video title + video id) and signal uncertainty for `low`/`truncated`.\n"
                "- For top stocks: bull case, bear case, catalysts, invalidation criteria (derived from channel content).\n"
                "- Mini factsheet: numbers/multiples only if explicitly present; otherwise omit/unknown.\n"
                "- Source format (required): channel + video title + video id (if title missing: channel + video id).\n"
                f"{template_instruction}\n\n"
                "**Report Metadata**:\n"
                f"- Run ID: {run_id}\n"
                f"- Run Date: {run_timestamp}\n"
                f"- Report Generated (UTC): {now_utc}\n"
                f"- Report Generated (Europe/Vienna): {now_vienna}\n"
                f"- Topic: {topic}\n\n"
                "Recency rule: prioritize newer evidence and explicitly state source age for material claims.\n\n"
                "Format the output as clean Markdown."
            )

        full_prompt_text = system_prompt + user_prompt
        token_count = estimate_tokens(full_prompt_text)
        limit = MODEL_LIMITS.get(model, 128000)

        logger.info("Estimated token count: %s (Limit: %s)", token_count, limit)
        if token_count > limit:
            logger.warning(
                "Token count (%s) exceeds estimated limit for %s (%s).",
                token_count,
                model,
                limit,
            )

        try:
            start_time = time.time()
            response = call_openai_with_retry(
                client.chat.completions.create,
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                extra_headers=openrouter_headers,
            )
            duration_ms = (time.time() - start_time) * 1000.0
            total_tokens = getattr(getattr(response, "usage", None), "total_tokens", None)
            logger.info(
                "LLM report call completed: lang=%s duration_ms=%.2f total_tokens=%s",
                lang["code"],
                duration_ms,
                total_tokens if total_tokens is not None else "unknown",
            )
        except Exception as exc:
            logger.error("LLM report call failed (%s): %s", lang["code"], exc)
            continue

        content = response.choices[0].message.content
        if not isinstance(content, str):
            logger.error("Unexpected LLM response content for %s", lang["code"])
            continue

        output_path = run_dir / lang["filename"]
        final_content = f"{preamble}\n\n{content.strip()}\n\n---\n\n{appendix}"
        output_path.write_text(final_content, encoding="utf-8")
        written.append(output_path)
        logger.info("Report saved to %s", output_path)

    return written


def generate_bilingual_reports(
    *, run_dir: Path, config: Optional[dict[str, Any]] = None
) -> list[Path]:
    """Backward-compatible wrapper (writes both reports)."""
    return generate_reports(run_dir=run_dir, config=config, report_lang="both")
