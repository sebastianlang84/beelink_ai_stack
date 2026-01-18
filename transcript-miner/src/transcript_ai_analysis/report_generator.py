from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReportContext:
    run_id: str
    timestamp: str
    profile_root: Path
    aggregates_dir: Path
    summaries_dir: Path
    summaries_data: list[dict[str, Any]] | None = None


class ReportGenerator:
    def __init__(self, context: ReportContext):
        self.ctx = context
        self._summaries = context.summaries_data

    def generate(self) -> str:
        """Generate the full markdown report."""
        sections = []

        # Header
        sections.append(self._generate_header())

        # Global Stats
        sections.append(self._generate_global_stats())

        # Top Entities/Topics
        sections.append(self._generate_top_entities())

        # Channel Coverage
        sections.append(self._generate_channel_coverage())

        # Highlights / Knowledge Items
        sections.append(self._generate_highlights())

        return "\n\n".join(sections)

    def _generate_header(self) -> str:
        # Try to format timestamp nicely
        ts_str = self.ctx.timestamp
        try:
            dt = datetime.fromisoformat(ts_str)
            # If it has timezone info, convert to UTC explicitly
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc)
            ts_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except ValueError:
            pass

        return f"""# Analysis Report

**Run ID:** `{self.ctx.run_id}`
**Date:** {ts_str}
"""

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
            return {}

    def _generate_global_stats(self) -> str:
        data = self._load_json(self.ctx.aggregates_dir / "global.json")
        metrics = data.get("metrics", [])
        if not metrics:
            return "## Global Stats\n\nNo global stats available."

        m = metrics[0]
        covered_period = data.get("covered_period") or {}
        freshness = data.get("freshness") or {}

        extra_lines: list[str] = []
        if isinstance(covered_period, dict):
            min_d = covered_period.get("min_published_date")
            max_d = covered_period.get("max_published_date")
            if min_d or max_d:
                extra_lines.append(f"- **Covered Period:** {min_d} .. {max_d}")
        if isinstance(freshness, dict):
            median_age = freshness.get("median_age_days")
            if median_age is not None:
                extra_lines.append(f"- **Median Age (days):** {median_age}")
        recent_30 = m.get("recent_30_unique_video_count")
        if recent_30 is not None:
            extra_lines.append(f"- **Recent 30d (videos):** {recent_30}")

        extra = "\n".join(extra_lines)
        return f"""## Global Stats

- **Videos Analyzed:** {m.get("unique_video_count", 0)}
- **Channels Covered:** {m.get("creator_count", 0)}
- **Total Mentions/Items:** {m.get("mention_count", 0)}
{extra}
"""

    def _generate_top_entities(self) -> str:
        data = self._load_json(self.ctx.aggregates_dir / "by_symbol.json")
        metrics = data.get("metrics", [])
        if not metrics:
            return ""

        # Sort by mention count desc
        sorted_metrics = sorted(
            metrics, key=lambda x: x.get("mention_count", 0), reverse=True
        )
        top_10 = sorted_metrics[:20]

        lines = [
            "## Top Entities / Topics",
            "",
            "| Topic/Entity | Mentions | Videos | Channels | Recent30 Videos | Stale Days |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for m in top_10:
            key = m.get("preferred_label") or m.get("key", "N/A")
            mentions = m.get("mention_count", 0)
            videos = m.get("unique_video_count", 0)
            channels = m.get("creator_count", 0)
            recent_30 = m.get("recent_30_unique_video_count", 0)
            stale_days = m.get("stale_days", "")
            lines.append(
                f"| **{key}** | {mentions} | {videos} | {channels} | {recent_30} | {stale_days} |"
            )

        return "\n".join(lines)

    def _generate_channel_coverage(self) -> str:
        data = self._load_json(self.ctx.aggregates_dir / "by_channel.json")
        metrics = data.get("metrics", [])
        if not metrics:
            return ""

        lines = [
            "## Channel Coverage",
            "",
            "| Channel | Transcripts | Summaries | Videos w/ Mentions | Mentions |",
            "|---|---:|---:|---:|---:|",
        ]
        for m in metrics:
            key = m.get("key", "N/A")
            transcripts = m.get("transcript_video_count", 0)
            summaries = m.get("summary_video_count", 0)
            videos = m.get("unique_video_count", 0)
            mentions = m.get("mention_count", 0)
            lines.append(f"| {key} | {transcripts} | {summaries} | {videos} | {mentions} |")

        return "\n".join(lines)

    def _generate_highlights(self) -> str:
        """Extract highlights from summaries."""
        highlights = []

        if self._summaries is not None:
            # Use pre-loaded data
            for data in self._summaries:
                highlights.append(self._process_single_highlight(data))
        else:
            # Fallback to reading from disk
            if not self.ctx.summaries_dir.exists():
                return ""

            for summary_file in self.ctx.summaries_dir.glob("*.json"):
                if summary_file.name in (
                    "report.json",
                    "manifest.json",
                    "metadata.json",
                ):
                    continue

                data = self._load_json(summary_file)
                highlights.append(
                    self._process_single_highlight(data, summary_file.stem)
                )

        # Filter empty
        highlights = [h for h in highlights if h]

        if not highlights:
            return ""

        return "## Key Highlights\n\n" + "\n\n".join(highlights)

    def _process_single_highlight(
        self, data: dict[str, Any], file_stem: str = "Unknown"
    ) -> str:
        """Extract items from a single summary data dictionary."""
        # Try to get video title/channel
        title = data.get("title") or data.get("video_title") or file_stem
        channel = (
            data.get("channel_id")
            or data.get("channel_name")
            or data.get("source", {}).get("channel_namespace")
            or "?"
        )
        video_id = (
            data.get("video_id")
            or data.get("source", {}).get("video_id")
            or file_stem
        )

        # Extract items
        items = []

        # 1. Knowledge Items (Generic)
        k_items = data.get("knowledge_items", [])
        for item in k_items:
            text = item.get("text")
            if text:
                items.append(f"- {text}")

        # 2. Stocks Covered (Stock Specific)
        stocks = data.get("stocks_covered", [])
        for stock in stocks:
            symbol = stock.get("canonical")
            why = stock.get("why_covered")
            if symbol and why:
                items.append(f"- **{symbol}**: {why}")

        # 3. Macro Insights (Stock Specific)
        macro = data.get("macro_insights", [])
        for m in macro:
            claim = m.get("claim")
            if claim:
                items.append(f"- *Macro*: {claim}")

        if items:
            # Limit items per video to avoid huge reports
            display_items = items[:5]
            if len(items) > 5:
                display_items.append(f"- ... ({len(items) - 5} more)")

            return (
                f"### {channel} — {title} (Video {video_id})\n\n"
                + "\n".join(display_items)
            )
        return ""


def generate_markdown_report(
    profile_root: Path,
    run_id: str,
    timestamp: str,
    aggregates_dir: Path,
    summaries_dir: Path,
    summaries_data: list[dict[str, Any]] | None = None,
) -> str:
    ctx = ReportContext(
        run_id=run_id,
        timestamp=timestamp,
        profile_root=profile_root,
        aggregates_dir=aggregates_dir,
        summaries_dir=summaries_dir,
        summaries_data=summaries_data,
    )
    generator = ReportGenerator(ctx)
    return generator.generate()
