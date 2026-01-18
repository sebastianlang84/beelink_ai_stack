from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import AnalysisManifest
from .scanner import load_metadata_fields, scan_output_roots


def _atomic_write_text(path: Path, content: str) -> None:
    """Write file content atomically via a .tmp + replace."""

    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    tmp.replace(path)


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def _compute_run_fingerprint(
    *, transcripts_jsonl_lines: list[str], errors: list[str]
) -> str:
    """Compute a deterministic fingerprint over the scan result.

    This is used instead of timestamps so reruns with identical inputs generate
    identical `manifest.json` bytes.
    """

    h = hashlib.sha256()
    for line in transcripts_jsonl_lines:
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    for err in errors:
        h.update(err.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def write_analysis_index(*, output_dir: Path, input_roots: list[Path]) -> int:
    """Scan transcript outputs and write analysis artefacts.

    Artefact layout (Batch 1):
    - {output_dir}/manifest.json
    - {output_dir}/transcripts.jsonl
    - {output_dir}/audit.jsonl
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    scan = scan_output_roots(input_roots)

    transcripts_path = output_dir / "transcripts.jsonl"
    audit_path = output_dir / "audit.jsonl"

    unique_video_ids: set[str] = set()
    transcripts_lines: list[str] = []
    audit_lines: list[str] = []

    for ref in scan.transcripts:
        unique_video_ids.add(ref.video_id)
        transcripts_lines.append(json.dumps(ref.to_json(), ensure_ascii=False))

        audit_event: dict = {
            "kind": "transcript_discovered",
            "video_id": ref.video_id,
            "channel_namespace": ref.channel_namespace,
            "transcript_path": ref.transcript_path,
            "metadata_path": ref.metadata_path,
            "published_date": ref.published_date,
        }

        if ref.metadata_path:
            md = load_metadata_fields(Path(ref.metadata_path))
            # Only include a small, stable subset (best-effort).
            for key in [
                "channel_id",
                "channel_name",
                "video_title",
                "published_at",
                "transcript_status",
                "transcript_reason",
            ]:
                if key in md:
                    audit_event[key] = md.get(key)

        audit_lines.append(json.dumps(audit_event, ensure_ascii=False))

    for err in scan.errors:
        audit_lines.append(
            json.dumps({"kind": "scan_error", "error": err}, ensure_ascii=False)
        )

    _atomic_write_text(
        transcripts_path,
        "\n".join(transcripts_lines) + ("\n" if transcripts_lines else ""),
    )
    _atomic_write_text(
        audit_path, "\n".join(audit_lines) + ("\n" if audit_lines else "")
    )

    run_fingerprint = _compute_run_fingerprint(
        transcripts_jsonl_lines=transcripts_lines, errors=scan.errors
    )
    manifest = AnalysisManifest.create(
        input_roots=sorted([str(p.resolve()) for p in input_roots]),
        transcript_count=len(scan.transcripts),
        unique_video_count=len(unique_video_ids),
        run_fingerprint=run_fingerprint,
    )
    _atomic_write_json(output_dir / "manifest.json", manifest.to_json())

    return 0 if not scan.errors else 1
