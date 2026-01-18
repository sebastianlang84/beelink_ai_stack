from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Dict, Iterable

from .config_models import OutputConfig

logger = logging.getLogger(__name__)

_LEGACY_VIDEO_ID_RE = re.compile(r"_([a-zA-Z0-9_-]{11})\.txt$")


def _iter_legacy_transcript_files(legacy_root: Path) -> Iterable[Path]:
    transcripts_root = legacy_root / "1_transcripts"
    if not transcripts_root.exists():
        return []
    return transcripts_root.glob("**/*.txt")


def _legacy_channel_from_path(path: Path) -> str | None:
    try:
        parts = path.parts
        if "1_transcripts" in parts:
            idx = parts.index("1_transcripts")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    except Exception:
        pass
    return None


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _files_identical(src: Path, dest: Path) -> bool:
    try:
        if src.stat().st_size != dest.stat().st_size:
            return False
    except FileNotFoundError:
        return False
    return _sha256(src) == _sha256(dest)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def migrate_legacy_transcripts(output: OutputConfig) -> dict[str, int]:
    legacy_root = output.get_legacy_root()
    canonical_dir = output.get_transcripts_path()
    canonical_dir.mkdir(parents=True, exist_ok=True)

    migrated_txt = 0
    migrated_meta = 0

    for txt_path in _iter_legacy_transcript_files(legacy_root):
        match = _LEGACY_VIDEO_ID_RE.search(txt_path.name)
        if not match:
            continue
        video_id = match.group(1)
        target_txt = output.get_transcript_path(video_id)
        if not target_txt.exists():
            target_txt.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(txt_path), str(target_txt))
            migrated_txt += 1
        else:
            if _files_identical(txt_path, target_txt):
                txt_path.unlink(missing_ok=True)

        legacy_meta = txt_path.with_name(
            txt_path.name.replace(f"_{video_id}.txt", f"_{video_id}_meta.json")
        )
        target_meta = output.get_transcript_meta_path(video_id)
        if legacy_meta.exists() and not target_meta.exists():
            meta = _load_json(legacy_meta)
            channel_handle = _legacy_channel_from_path(txt_path)
            if channel_handle:
                meta.setdefault("channel_handle", channel_handle)
                meta.setdefault("channel_handle_raw", f"@{channel_handle}")
            _write_json(target_meta, meta)
            legacy_meta.unlink(missing_ok=True)
            migrated_meta += 1
        elif legacy_meta.exists() and target_meta.exists():
            if _files_identical(legacy_meta, target_meta):
                legacy_meta.unlink(missing_ok=True)

    if migrated_txt or migrated_meta:
        logger.info(
            "Migrated legacy transcripts: txt=%s meta=%s",
            migrated_txt,
            migrated_meta,
        )

    return {"transcripts": migrated_txt, "metadata": migrated_meta}


def migrate_legacy_summaries(output: OutputConfig) -> dict[str, int]:
    legacy_root = output.get_legacy_root() / "2_summaries"
    canonical_dir = output.get_summaries_path()
    canonical_dir.mkdir(parents=True, exist_ok=True)

    migrated = 0
    if legacy_root.exists():
        for summary_file in legacy_root.rglob("*.json"):
            if summary_file.name in {"report.json", "manifest.json", "metadata.json"}:
                continue
            video_id = summary_file.stem
            target_path = output.get_summary_path(video_id)
            if target_path.exists():
                summary_file.unlink(missing_ok=True)
                continue
            try:
                payload = _load_json(summary_file)
                task = str(payload.get("task") or "unknown").strip() or "unknown"
                title = str(payload.get("title") or payload.get("video_title") or "unknown").strip() or "unknown"
                published_at = str(payload.get("published_at") or "unknown").strip() or "unknown"
                channel_id = str(payload.get("channel_id") or "unknown").strip() or "unknown"

                source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
                channel_namespace = str(source.get("channel_namespace") or "unknown").strip() or "unknown"
                transcript_path = str(source.get("transcript_path") or "").strip()
                raw_hash = str(payload.get("raw_hash") or "").strip()

                lines = [
                    "---",
                    f"schema_version: {payload.get('schema_version')}"
                    if isinstance(payload.get("schema_version"), int)
                    else "schema_version: 1",
                    f"task: {task}",
                    f"topic: {output.get_topic()}" if output.is_global_layout() else "topic: legacy",
                    f"video_id: {video_id}",
                    f"title: {title}",
                    f"channel_namespace: {channel_namespace}",
                    f"channel_id: {channel_id}",
                    f"published_at: {published_at}",
                    f"transcript_path: {transcript_path}",
                    f"raw_hash: {raw_hash}",
                    "---",
                    "",
                    f"# {title}",
                    "",
                    "## Source",
                    f"- video_id: `{video_id}`",
                    f"- channel_namespace: `{channel_namespace}`",
                    f"- published_at: `{published_at}`",
                    "",
                ]

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
                            lines.append(f"- {canonical}: {why}" if why else f"- {canonical}")
                        lines.append("")

                knowledge = payload.get("knowledge_items")
                if isinstance(knowledge, list):
                    items = [x for x in knowledge if isinstance(x, dict)]
                    if items:
                        lines.append("## Knowledge Items")
                        for item in items:
                            text_value = str(item.get("text") or "").strip()
                            if not text_value:
                                continue
                            entities = item.get("entities")
                            if isinstance(entities, list):
                                cleaned = [str(e).strip() for e in entities if str(e).strip()]
                            else:
                                cleaned = []
                            if cleaned:
                                lines.append(f"- {text_value} (entities: {', '.join(cleaned)})")
                            else:
                                lines.append(f"- {text_value}")
                        lines.append("")

                errors = payload.get("errors")
                if isinstance(errors, list):
                    cleaned = [str(e).strip() for e in errors if str(e).strip()]
                    if cleaned:
                        lines.append("## Errors")
                        for e in cleaned:
                            lines.append(f"- {e}")
                        lines.append("")

                target_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = target_path.with_suffix(target_path.suffix + ".tmp")
                tmp.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
                tmp.replace(target_path)
                summary_file.unlink(missing_ok=True)
                migrated += 1
            except Exception:
                logger.exception("Failed to migrate legacy summary: %s", summary_file)

    if migrated:
        logger.info("Migrated legacy summaries: %s", migrated)
    return {"summaries": migrated}


def migrate_legacy_skipped(output: OutputConfig) -> dict[str, int]:
    legacy_skipped = output.get_legacy_root() / "1_transcripts" / "skipped.json"
    target = output.get_transcripts_skipped_path()

    if not legacy_skipped.exists():
        return {"skipped": 0}

    existing = _load_json(target)
    existing_skipped = existing.get("skipped") if isinstance(existing, dict) else None
    if not isinstance(existing_skipped, dict):
        existing_skipped = {}

    legacy_data = _load_json(legacy_skipped)
    migrated = 0
    if isinstance(legacy_data, dict):
        for channel_id, entries in legacy_data.items():
            if not isinstance(entries, dict):
                continue
            for video_id, info in entries.items():
                if video_id in existing_skipped:
                    continue
                payload = info if isinstance(info, dict) else {}
                payload.setdefault("channel_id", channel_id)
                existing_skipped[video_id] = payload
                migrated += 1

    if migrated:
        _write_json(
            target,
            {"schema_version": 1, "skipped": existing_skipped},
        )
        legacy_skipped.unlink(missing_ok=True)
        logger.info("Migrated legacy skipped entries: %s", migrated)

    return {"skipped": migrated}


def migrate_legacy_outputs(output: OutputConfig) -> dict[str, int]:
    """One-shot migration from legacy output/<topic> layout into global data layer."""
    counts: Dict[str, int] = {}
    counts.update(migrate_legacy_transcripts(output))
    counts.update(migrate_legacy_summaries(output))
    counts.update(migrate_legacy_skipped(output))
    return counts
