from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import date
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .aggregation import (
    CanonicalMention,
    aggregate_by_channel,
    aggregate_by_symbol,
    aggregate_global,
)
from .llm_report_generator import discover_config_for_run, generate_reports
from .report_generator import generate_markdown_report
from common.config import load_config
from common.config_models import OutputConfig
from common.path_utils import archive_existing_reports

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_TICKER_IN_PARENS_RE = re.compile(
    r"^(.+?)\s*\((?P<ticker>[A-Z][A-Z0-9.\-]{0,9})\)\s*$"
)


def detect_summary_coverage_gaps(
    transcripts_video_ids_by_channel: dict[str, set[str]],
    summaries_video_ids_by_channel: dict[str, set[str]],
) -> dict[str, list[str]]:
    """Return missing summary video IDs per channel.

    The returned dict contains only channels where at least one transcript video_id
    has no corresponding summary video_id.
    """

    gaps: dict[str, list[str]] = {}
    channels = set(transcripts_video_ids_by_channel.keys()) | set(
        summaries_video_ids_by_channel.keys()
    )
    for channel in sorted(channels):
        transcript_ids = transcripts_video_ids_by_channel.get(channel, set())
        summary_ids = summaries_video_ids_by_channel.get(channel, set())
        missing = sorted(transcript_ids - summary_ids)
        if missing:
            gaps[channel] = missing
    return gaps


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    # Lazy Creation: Ensure parent directory exists before writing
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def _atomic_write_text(path: Path, content: str) -> None:
    # Lazy Creation: Ensure parent directory exists before writing
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    tmp.replace(path)

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

            # PRD layout: .../<profile_root>/1_transcripts/<channel>/<file>
            if "1_transcripts" in parts:
                idx = parts.index("1_transcripts")
                if idx + 1 < len(parts) - 1:
                    return parts[idx + 1]
                if idx - 1 >= 0:
                    return parts[idx - 1]
        except Exception:
            pass

    return "unknown"


def _load_metadata_from_transcript_path(
    transcript_path: str | None, video_id: str | None
) -> dict[str, Any]:
    if not transcript_path or not video_id:
        return {}
    try:
        tpath = Path(transcript_path)
        suffix = f"_{video_id}.txt"
        if not tpath.name.endswith(suffix):
            return {}
        meta_name = tpath.name.replace(suffix, f"_{video_id}_meta.json")
        meta_path = tpath.with_name(meta_name)
        if not meta_path.exists():
            return {}
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load metadata for %s: %s", transcript_path, exc)
        return {}


def _canonicalize_symbol_key(symbol_label: str) -> str:
    s = symbol_label.strip()
    m = _TICKER_IN_PARENS_RE.match(s)
    if m:
        return m.group("ticker")
    return s


def _summary_video_id(summary_file: Path) -> str:
    name = summary_file.name
    if name.endswith(".summary.md"):
        return name[: -len(".summary.md")]
    if name.endswith(".summary.json"):
        return name[: -len(".summary.json")]
    return summary_file.stem


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def _median(values: list[int]) -> float | None:
    if not values:
        return None
    sorted_vals = sorted(values)
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 == 1:
        return float(sorted_vals[mid])
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0


def run_aggregation(
    *,
    profile_root: Path,
    index_dir: Path,
    mapping_json: Path | None = None,
    stoplist_json: Path | None = None,
    report_lang: str = "de",
    output: OutputConfig | None = None,
    config_path: Path | None = None,
) -> int:
    """Run aggregation analysis and write artefacts under profile_root/3_reports/ (legacy).

    This runner reads transcript index and LLM summaries to produce
    aggregated coverage reports.
    """
    import time

    t0 = time.time()
    print(f"[{time.time() - t0:.3f}s] Starting aggregation run")

    # 1. Check inputs
    transcripts_jsonl = index_dir / "transcripts.jsonl"
    if not transcripts_jsonl.exists():
        logger.error(f"Missing transcript index: {transcripts_jsonl}")
        return 1

    if output and output.is_global_layout():
        summaries_dir = output.get_summaries_path()
        reports_root = output.get_reports_path()
    else:
        summaries_dir = profile_root / "2_summaries"
        reports_root = profile_root / "3_reports"
    if not summaries_dir.exists():
        logger.error(f"Missing summaries directory: {summaries_dir}")
        return 1

    # 2. Load transcript index to get channel/video baseline + recency stats
    index_rows: list[dict[str, Any]] = []
    transcripts_video_ids_by_channel: dict[str, set[str]] = {}
    published_dates: list[date] = []
    published_date_by_video_id: dict[str, date] = {}
    try:
        with open(transcripts_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                index_rows.append(row)
                channel = _normalize_channel_namespace(
                    row.get("channel_namespace"), row.get("transcript_path")
                )
                video_id = row.get("video_id")
                if isinstance(video_id, str) and video_id:
                    transcripts_video_ids_by_channel.setdefault(channel, set()).add(
                        video_id
                    )
                published = _parse_iso_date(row.get("published_date"))
                if published and isinstance(video_id, str) and video_id:
                    published_date_by_video_id[video_id] = published
                if published:
                    published_dates.append(published)
    except Exception as e:
        logger.warning("Failed to load transcript index JSONL (%s): %s", transcripts_jsonl, e)

    # 3. Load summaries and extract mentions
    try:
        from rich.progress import (
            Progress,
            SpinnerColumn,
            TextColumn,
            BarColumn,
            TaskProgressColumn,
        )

        rich_available = True
    except ImportError:
        rich_available = False

    def _load_summaries() -> tuple[
        list[CanonicalMention],
        list[dict[str, Any]],
        dict[str, set[str]],
        dict[str, str],
    ]:
        mentions: list[CanonicalMention] = []
        summaries_data: list[dict[str, Any]] = []
        summaries_video_ids_by_channel: dict[str, set[str]] = {}
        quality_by_video_id: dict[str, str] = {}

        summary_files = sorted(
            {
                *summaries_dir.rglob("*.summary.md"),
                *summaries_dir.rglob("*.summary.json"),
            },
            key=lambda p: str(p),
        )

        def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
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
                if key:
                    meta[key] = value
            return meta, body

        def _load_summary_payload(path: Path) -> dict[str, Any] | None:
            if path.name.endswith(".summary.json"):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, dict) else None

            if path.name.endswith(".summary.md"):
                text = path.read_text(encoding="utf-8")
                meta, body = _split_frontmatter(text)
                if not meta:
                    return None

                task = meta.get("task") or "unknown"
                out: dict[str, Any] = {"task": task}
                schema_version = meta.get("schema_version")
                if schema_version and schema_version.isdigit():
                    out["schema_version"] = int(schema_version)

                video_id = meta.get("video_id") or _summary_video_id(path)
                source = {
                    "video_id": video_id,
                    "channel_namespace": meta.get("channel_namespace") or "",
                    "transcript_path": meta.get("transcript_path") or "",
                }
                out["source"] = source
                out["raw_hash"] = meta.get("raw_hash") or ""

                if meta.get("title"):
                    out["video_title"] = meta.get("title")
                    out["title"] = meta.get("title")
                if meta.get("published_at"):
                    out["published_at"] = meta.get("published_at")
                if meta.get("channel_id"):
                    out["channel_id"] = meta.get("channel_id")

                tq_grade = meta.get("transcript_quality_grade")
                tq_reasons = meta.get("transcript_quality_reasons")
                if tq_grade or tq_reasons:
                    reasons_list: list[str] = []
                    if isinstance(tq_reasons, str) and tq_reasons.strip():
                        reasons_list = [p.strip() for p in tq_reasons.split(";") if p.strip()]
                    out["transcript_quality"] = {
                        "grade": (tq_grade or "unknown").strip().lower(),
                        "reasons": reasons_list,
                    }

                # Parse a small subset of sections for downstream aggregation.
                section: str | None = None
                stocks: list[dict[str, Any]] = []
                macro: list[dict[str, Any]] = []
                knowledge: list[dict[str, Any]] = []
                errors: list[str] = []

                for raw_line in body.splitlines():
                    line = raw_line.strip()
                    if line.startswith("## "):
                        section = line[3:].strip().lower()
                        continue
                    if not line.startswith("- "):
                        continue
                    item = line[2:].strip()
                    if not item:
                        continue

                    if section == "stocks covered":
                        if ":" in item:
                            canonical, why = item.split(":", 1)
                            canonical = canonical.strip()
                            why = why.strip()
                            if canonical:
                                stocks.append(
                                    {"canonical": canonical, "why_covered": why}
                                )
                        else:
                            stocks.append({"canonical": item, "why_covered": ""})
                    elif section == "macro insights":
                        # Format: "<claim> (tags: a, b)"
                        claim = item
                        tags: list[str] = []
                        if "(tags:" in item and item.endswith(")"):
                            head, tail = item.rsplit("(tags:", 1)
                            claim = head.strip()
                            tail = tail[:-1].strip()
                            tags = [t.strip() for t in tail.split(",") if t.strip()]
                        macro.append({"claim": claim, "tags": tags or None})
                    elif section == "knowledge items":
                        text_value = item
                        entities: list[str] = []
                        if "(entities:" in item and item.endswith(")"):
                            head, tail = item.rsplit("(entities:", 1)
                            text_value = head.strip()
                            tail = tail[:-1].strip()
                            entities = [e.strip() for e in tail.split(",") if e.strip()]
                        knowledge.append({"text": text_value, "entities": entities or None})
                    elif section == "errors":
                        errors.append(item)

                if stocks:
                    out["stocks_covered"] = stocks
                if macro:
                    # Remove None tags to keep downstream stable.
                    cleaned_macro: list[dict[str, Any]] = []
                    for m in macro:
                        if not isinstance(m, dict):
                            continue
                        if m.get("tags") is None:
                            m = {k: v for k, v in m.items() if k != "tags"}
                        cleaned_macro.append(m)
                    out["macro_insights"] = cleaned_macro
                if knowledge:
                    cleaned_knowledge: list[dict[str, Any]] = []
                    for k in knowledge:
                        if not isinstance(k, dict):
                            continue
                        if k.get("entities") is None:
                            k = {kk: vv for kk, vv in k.items() if kk != "entities"}
                        cleaned_knowledge.append(k)
                    out["knowledge_items"] = cleaned_knowledge
                if errors:
                    out["errors"] = errors

                return out

            return None

        def _process_summary(
            summary_file: Path,
        ) -> tuple[list[CanonicalMention], dict[str, Any] | None]:
            local_mentions: list[CanonicalMention] = []
            data = None
            try:
                data = _load_summary_payload(summary_file)
                if not isinstance(data, dict):
                    return local_mentions, None

                video_id = _summary_video_id(summary_file)
                source = data.get("source", {})
                raw_channel_namespace = source.get("channel_namespace")
                transcript_path = source.get("transcript_path")
                channel_namespace = _normalize_channel_namespace(
                    raw_channel_namespace, transcript_path
                )

                # Normalize in-memory copy so downstream report generation sees stable handles.
                if isinstance(source, dict):
                    source["channel_namespace"] = channel_namespace

                metadata = _load_metadata_from_transcript_path(transcript_path, video_id)
                if metadata:
                    if not data.get("video_id"):
                        data["video_id"] = metadata.get("video_id") or video_id
                    if not data.get("video_title") and metadata.get("video_title"):
                        data["video_title"] = metadata.get("video_title")
                    if not data.get("channel_name") and metadata.get("channel_name"):
                        data["channel_name"] = metadata.get("channel_name")
                    if not data.get("channel_id") and metadata.get("channel_id"):
                        data["channel_id"] = metadata.get("channel_id")
                    if not data.get("published_at") and metadata.get("published_at"):
                        data["published_at"] = metadata.get("published_at")

                summaries_video_ids_by_channel.setdefault(channel_namespace, set()).add(
                    video_id
                )
                quality = (
                    (data.get("transcript_quality") or {})
                    if isinstance(data, dict)
                    else {}
                )
                grade = str(
                    (quality.get("grade") if isinstance(quality, dict) else None)
                    or "unknown"
                ).strip().lower()
                reasons = quality.get("reasons") if isinstance(quality, dict) else None
                if isinstance(reasons, list):
                    reasons_text = " ".join(str(r).lower() for r in reasons)
                    if "truncat" in reasons_text or "cuts off" in reasons_text:
                        grade = "truncated"
                quality_by_video_id[video_id] = grade or "unknown"

                items = data.get("knowledge_items", [])
                for item in items:
                    entities = item.get("entities", [])
                    for entity in entities:
                        symbol = (
                            entity if isinstance(entity, str) else entity.get("symbol")
                        )
                        if symbol:
                            symbol_label = str(symbol)
                            canonical_key = _canonicalize_symbol_key(symbol_label)
                            local_mentions.append(
                                CanonicalMention(
                                    channel_namespace=channel_namespace,
                                    video_id=video_id,
                                    canonical_symbol=canonical_key,
                                    symbol_label=symbol_label,
                                )
                            )

                stocks_covered = data.get("stocks_covered", [])
                for stock in stocks_covered:
                    symbol = stock.get("canonical")
                    if symbol:
                        symbol_label = str(symbol)
                        canonical_key = _canonicalize_symbol_key(symbol_label)
                        local_mentions.append(
                            CanonicalMention(
                                channel_namespace=channel_namespace,
                                video_id=video_id,
                                canonical_symbol=canonical_key,
                                symbol_label=symbol_label,
                            )
                        )
            except Exception as e:
                logger.warning(f"Failed to process summary {summary_file}: {e}")
            return local_mentions, data

        print(f"[{time.time() - t0:.3f}s] Loading {len(summary_files)} summaries...")
        if rich_available:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                transient=True,
            ) as progress:
                task = progress.add_task(
                    "[cyan]Loading summaries...", total=len(summary_files)
                )
                for summary_file in summary_files:
                    local_m, local_d = _process_summary(summary_file)
                    mentions.extend(local_m)
                    if local_d:
                        summaries_data.append(local_d)
                    progress.advance(task)
        else:
            for idx, summary_file in enumerate(summary_files):
                if idx % 10 == 0:
                    print(
                        f"[{time.time() - t0:.3f}s] Processing summary {idx}/{len(summary_files)}..."
                    )
                local_m, local_d = _process_summary(summary_file)
                mentions.extend(local_m)
                if local_d:
                    summaries_data.append(local_d)

        return (
            mentions,
            summaries_data,
            summaries_video_ids_by_channel,
            quality_by_video_id,
        )

    mentions, summaries_data, summaries_video_ids_by_channel, quality_by_video_id = (
        _load_summaries()
    )

    gaps = detect_summary_coverage_gaps(
        transcripts_video_ids_by_channel, summaries_video_ids_by_channel
    )
    if gaps:
        if config_path is not None:
            try:
                cfg = load_config(config_path)
                llm_cfg = cfg.analysis.llm
            except Exception:
                llm_cfg = None
            if llm_cfg and llm_cfg.enabled and llm_cfg.mode == "per_video":
                logger.warning(
                    "Missing summaries for %d channel(s); attempting healing pass. Examples: %s",
                    len(gaps),
                    {k: v[:5] for k, v in list(gaps.items())[:3]},
                )
                include_video_ids_by_channel = {
                    channel: set(video_ids) for channel, video_ids in gaps.items()
                }
                try:
                    from transcript_ai_analysis.llm_runner import run_llm_analysis

                    rc = run_llm_analysis(
                        config_path=config_path,
                        profile_root=profile_root,
                        index_dir=index_dir,
                        include_video_ids_by_channel=include_video_ids_by_channel,
                    )
                except Exception as exc:
                    logger.error("Summary healing failed: %s", exc)
                    return 1
                if rc != 0:
                    logger.error("Summary healing failed (exit=%s).", rc)
                    return 1
                (
                    mentions,
                    summaries_data,
                    summaries_video_ids_by_channel,
                    quality_by_video_id,
                ) = _load_summaries()
                gaps = detect_summary_coverage_gaps(
                    transcripts_video_ids_by_channel, summaries_video_ids_by_channel
                )
                if gaps:
                    logger.error(
                        "Missing summaries for %d channel(s) after healing. Examples: %s",
                        len(gaps),
                        {k: v[:5] for k, v in list(gaps.items())[:3]},
                    )
                    return 1
            else:
                logger.error(
                    "Missing summaries for %d channel(s). Examples: %s",
                    len(gaps),
                    {k: v[:5] for k, v in list(gaps.items())[:3]},
                )
                return 1
        else:
            logger.error(
                "Missing summaries for %d channel(s). Examples: %s",
                len(gaps),
                {k: v[:5] for k, v in list(gaps.items())[:3]},
            )
            return 1

    print(f"[{time.time() - t0:.3f}s] Aggregating data...")
    if not mentions:
        logger.warning("No mentions found in summaries. Aggregation will be empty.")

    # 4. Perform aggregations
    generated_from = {
        "index_file": str(transcripts_jsonl),
        "summaries_dir": str(summaries_dir),
    }

    by_channel = aggregate_by_channel(mentions=mentions, generated_from=generated_from)
    by_symbol = aggregate_by_symbol(mentions=mentions, generated_from=generated_from)
    global_stats = aggregate_global(mentions=mentions, generated_from=generated_from)

    # 4.1 Enrich global stats with baseline counts and recency metadata
    now = datetime.now(timezone.utc)
    global_metric = (global_stats.get("metrics") or [{}])[0]
    global_metric["transcript_unique_video_count"] = sum(
        len(v) for v in transcripts_video_ids_by_channel.values()
    )
    global_metric["summary_unique_video_count"] = sum(
        len(v) for v in summaries_video_ids_by_channel.values()
    )

    if published_dates:
        min_d = min(published_dates)
        max_d = max(published_dates)
        ages = [(now.date() - d).days for d in published_dates]
        global_stats["as_of"] = now.isoformat()
        global_stats["covered_period"] = {
            "min_published_date": min_d.isoformat(),
            "max_published_date": max_d.isoformat(),
        }
        global_stats["freshness"] = {
            "video_count": len(published_dates),
            "median_age_days": _median(ages),
            "pct_videos_lt_30d": round(100.0 * sum(1 for a in ages if a < 30) / len(ages), 2),
            "pct_videos_lt_60d": round(100.0 * sum(1 for a in ages if a < 60) / len(ages), 2),
            "pct_videos_lt_90d": round(100.0 * sum(1 for a in ages if a < 90) / len(ages), 2),
        }

    # 4.1b Enrich by_symbol with recent windows + staleness + quality breakdown
    now_date = now.date()
    windows = [30, 60, 90]

    # Build refs per symbol from in-memory mentions (keeps mention_count semantics consistent).
    refs_by_symbol: dict[str, list[tuple[str, str, date | None]]] = {}
    for m in mentions:
        if not m.canonical_symbol:
            continue
        pub = published_date_by_video_id.get(m.video_id)
        refs_by_symbol.setdefault(m.canonical_symbol, []).append(
            (m.video_id, m.channel_namespace, pub)
        )

    for metric in (by_symbol.get("metrics") or []):
        if not isinstance(metric, dict):
            continue
        key = metric.get("key")
        if not isinstance(key, str) or not key:
            continue

        refs = refs_by_symbol.get(key, [])
        dated_refs = [(vid, ch, pub) for (vid, ch, pub) in refs if pub is not None]
        last_pub: date | None = max((pub for (_, _, pub) in dated_refs), default=None) if dated_refs else None
        if last_pub:
            metric["last_published_date"] = last_pub.isoformat()
            metric["stale_days"] = (now_date - last_pub).days

        # Quality breakdown based on unique videos for this key.
        unique_videos = sorted({vid for (vid, _, _) in refs})
        q_counts: dict[str, int] = {}
        for vid in unique_videos:
            q = quality_by_video_id.get(vid, "unknown")
            q_counts[q] = q_counts.get(q, 0) + 1
        metric["quality_unique_video_counts"] = {k: q_counts[k] for k in sorted(q_counts.keys())}

        for w in windows:
            recent = [
                (vid, ch)
                for (vid, ch, pub) in dated_refs
                if (now_date - pub).days <= w
            ]
            metric[f"recent_{w}_mention_count"] = len(recent)
            metric[f"recent_{w}_unique_video_count"] = len({vid for (vid, _) in recent})
            metric[f"recent_{w}_creator_count"] = len({ch for (_, ch) in recent})
            metric[f"stale_{w}d"] = metric[f"recent_{w}_unique_video_count"] == 0

    # Global recent windows (based on all mentions)
    global_refs = [
        (m.video_id, m.channel_namespace, published_date_by_video_id.get(m.video_id))
        for m in mentions
        if m.canonical_symbol
    ]
    global_dated_refs = [(vid, ch, pub) for (vid, ch, pub) in global_refs if pub is not None]
    for w in windows:
        recent = [
            (vid, ch)
            for (vid, ch, pub) in global_dated_refs
            if (now_date - pub).days <= w
        ]
        global_metric[f"recent_{w}_mention_count"] = len(recent)
        global_metric[f"recent_{w}_unique_video_count"] = len({vid for (vid, _) in recent})
        global_metric[f"recent_{w}_creator_count"] = len({ch for (_, ch) in recent})

    # 4.2 Enrich by_channel with transcript/summaries coverage and include channels with zero mentions
    by_channel_metrics = {m["key"]: m for m in (by_channel.get("metrics") or []) if isinstance(m, dict)}
    all_channels = sorted(set(transcripts_video_ids_by_channel.keys()) | set(summaries_video_ids_by_channel.keys()) | set(by_channel_metrics.keys()))
    enriched_metrics: list[dict[str, Any]] = []
    for channel in all_channels:
        metric = dict(by_channel_metrics.get(channel, {}))
        if not metric:
            # Keep the existing schema keys stable
            metric = {
                "key": channel,
                "unique_video_count": 0,
                "creator_count": 1,
                "mention_count": 0,
                "mentions_raw": 0,
                "mentions_unique_video": 0,
                "mentions_unique_creator": 0,
            }
        metric["transcript_video_count"] = len(transcripts_video_ids_by_channel.get(channel, set()))
        metric["summary_video_count"] = len(summaries_video_ids_by_channel.get(channel, set()))
        enriched_metrics.append(metric)
    by_channel["metrics"] = enriched_metrics

    print(f"[{time.time() - t0:.3f}s] Archiving existing reports...")
    # 5. Write outputs
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    report_date = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"

    # Try to get fingerprint from manifest
    fingerprint = "unknown"
    manifest_path = index_dir / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
                fingerprint = manifest_data.get("run_fingerprint", "unknown")[:8]
        except Exception:
            pass

    run_id = f"{timestamp}_{fingerprint}"

    if output and output.is_global_layout():
        run_dir = output.get_run_reports_path(
            timestamp, fingerprint, model_slug="aggregate"
        )
        reports_dir = run_dir / "aggregates"
    else:
        run_dir = reports_root
        archive_existing_reports(reports_root, run_id)
        reports_dir = reports_root / "aggregates"

    if output and output.is_global_layout():
        run_id = run_dir.name

    print(f"[{time.time() - t0:.3f}s] Writing JSON outputs...")

    # Lazy Creation is handled in _atomic_write_json
    _atomic_write_json(reports_dir / "by_channel.json", by_channel)
    _atomic_write_json(reports_dir / "by_symbol.json", by_symbol)
    _atomic_write_json(reports_dir / "global.json", global_stats)

    # Also write a run manifest if possible
    run_manifest = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fingerprint": fingerprint,
        "generated_from": generated_from,
        "reports_root": str(reports_root),
        "run_dir": str(run_dir),
    }
    _atomic_write_json(run_dir / "run_manifest.json", run_manifest)
    _atomic_write_json(reports_root / "run_manifest.json", run_manifest)

    print(f"[{time.time() - t0:.3f}s] Generating reports...")
    written_reports: list[Path] = []
    config = discover_config_for_run(run_dir)
    report_cfg = (config or {}).get("report", {}).get("llm")
    if report_cfg:
        try:
            written_reports = generate_reports(
                run_dir=run_dir, config=config, report_lang=report_lang
            )
        except Exception as e:
            logger.error("Failed to generate bilingual reports: %s", e)
            written_reports = []

    if not written_reports:
        try:
            markdown_report = generate_markdown_report(
                profile_root=profile_root,
                run_id=run_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                aggregates_dir=reports_dir,
                summaries_dir=summaries_dir,
                summaries_data=summaries_data,
            )

            report_path = run_dir / "report.md"
            _atomic_write_text(report_path, markdown_report)
            logger.info("Markdown report written to %s", report_path)
        except Exception as e:
            logger.error("Failed to generate markdown report: %s", e)

    # Copy current reports to reports_root with date-stamped names (global layout).
    if output and output.is_global_layout():
        reports_root.mkdir(parents=True, exist_ok=True)

        def _copy_report(src: Path, lang: str) -> None:
            dest = reports_root / f"report_{lang}_{report_date}.md"
            shutil.copy2(src, dest)

        for rpt in run_dir.glob("report_*.md"):
            if rpt.name == "report_de.md":
                _copy_report(rpt, "de")
            elif rpt.name == "report_en.md":
                _copy_report(rpt, "en")

        if (run_dir / "report.md").exists():
            if report_lang == "en":
                _copy_report(run_dir / "report.md", "en")
            elif report_lang == "both":
                _copy_report(run_dir / "report.md", "de")
                _copy_report(run_dir / "report.md", "en")
            else:
                _copy_report(run_dir / "report.md", "de")

    print(f"[{time.time() - t0:.3f}s] Aggregation completed.")
    logger.info(f"Aggregation completed. Reports written to {reports_root}")
    return 0
