from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import TranscriptRef


_VIDEO_ID_SUFFIX_RE = re.compile(r"_([a-zA-Z0-9_-]{11})\.txt$")
_VIDEO_ID_PLAIN_RE = re.compile(r"^([a-zA-Z0-9_-]{11})\.txt$")
_PUBLISHED_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_")


@dataclass(frozen=True)
class ScanResult:
    transcripts: list[TranscriptRef]
    errors: list[str]


def _iter_transcript_files(output_root: Path) -> Iterable[Path]:
    # Layout reference: see output structure in [`README.md`](README.md:223).
    # PRD: output/<profile>/1_transcripts/
    # Legacy: {output_root}/**/transcripts/*.txt
    # Global (proposal): output/data/transcripts/by_video_id/<video_id>.txt
    yield from output_root.glob("data/transcripts/by_video_id/*.txt")
    yield from output_root.glob("**/1_transcripts/**/*.txt")
    yield from output_root.glob("**/transcripts/*.txt")


def _channel_namespace_for_transcripts_dir(
    output_root: Path, transcripts_dir: Path
) -> str:
    """Derive a stable channel namespace from a transcripts directory.

    With multi-channel output policy, we have:
    - Legacy: {root_path}/{clean_handle}/transcripts
    - PRD: {root_path}/1_transcripts/{clean_handle}
    """

    try:
        # PRD: .../1_transcripts/<channel>
        if transcripts_dir.parent.name == "1_transcripts":
            return transcripts_dir.name

        # Legacy: .../<channel>/transcripts
        if transcripts_dir.name == "transcripts":
            parent = transcripts_dir.parent
            rel = parent.relative_to(output_root)
            return "default" if str(rel) in {".", ""} else str(rel)

        # Fallback
        rel = transcripts_dir.relative_to(output_root)
        return "default" if str(rel) in {".", ""} else str(rel)
    except Exception:
        return "default"


def _normalize_channel_handle(value: str) -> str:
    return value.strip().lstrip("@").replace("/", "_").replace("\\", "_")


def _extract_video_id(filename: str) -> str | None:
    plain = _VIDEO_ID_PLAIN_RE.match(filename)
    if plain:
        return plain.group(1)
    suffix = _VIDEO_ID_SUFFIX_RE.search(filename)
    if suffix:
        return suffix.group(1)
    return None


def _published_date_from_metadata(meta: dict) -> str | None:
    value = meta.get("published_at") or meta.get("published_date")
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if "T" in value:
        return value.split("T")[0]
    if len(value) >= 10:
        return value[:10]
    return None


def _channel_namespace_from_metadata(meta: dict) -> str | None:
    for key in ("channel_handle", "channel_handle_raw"):
        raw = meta.get(key)
        if isinstance(raw, str) and raw.strip():
            return _normalize_channel_handle(raw)
    return None


def scan_output_roots(output_roots: list[Path]) -> ScanResult:
    transcripts: list[TranscriptRef] = []
    errors: list[str] = []

    # Deterministic scan order regardless of CLI argument ordering.
    for root in sorted(output_roots, key=lambda p: str(p)):
        root = root.resolve()
        if not root.exists() or not root.is_dir():
            errors.append(f"output root does not exist or is not a directory: {root}")
            continue

        for txt_path in sorted(_iter_transcript_files(root)):
            video_id = _extract_video_id(txt_path.name)
            if not video_id:
                errors.append(
                    f"could not parse video_id from transcript filename: {txt_path}"
                )
                continue

            transcripts_dir = txt_path.parent

            if txt_path.name == f"{video_id}.txt":
                meta_path = txt_path.with_suffix(".meta.json")
            else:
                meta_path = txt_path.with_name(
                    txt_path.name.replace(
                        f"_{video_id}.txt", f"_{video_id}_meta.json"
                    )
                )
            metadata_path = str(meta_path) if meta_path.exists() else None

            channel_ns = None
            published_date = None
            if meta_path.exists():
                meta = load_metadata_fields(meta_path)
                channel_ns = _channel_namespace_from_metadata(meta)
                published_date = _published_date_from_metadata(meta)

            if not published_date:
                date_match = _PUBLISHED_DATE_RE.search(txt_path.name)
                published_date = date_match.group(1) if date_match else None

            if not channel_ns:
                channel_ns = _channel_namespace_for_transcripts_dir(
                    root, transcripts_dir
                )

            transcripts.append(
                TranscriptRef(
                    output_root=str(root),
                    channel_namespace=channel_ns,
                    video_id=video_id,
                    transcript_path=str(txt_path),
                    metadata_path=metadata_path,
                    published_date=published_date,
                )
            )

    # Deterministic output order for downstream writers.
    transcripts_sorted = sorted(
        transcripts,
        key=lambda r: (
            r.output_root,
            r.channel_namespace,
            r.video_id,
            r.transcript_path,
        ),
    )

    return ScanResult(transcripts=transcripts_sorted, errors=errors)


def load_metadata_fields(metadata_path: Path) -> dict:
    """Best-effort load of metadata JSON."""

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
