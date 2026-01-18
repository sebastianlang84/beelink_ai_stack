from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TranscriptRef:
    """Reference to a transcript file within an output root."""

    output_root: str
    channel_namespace: str
    video_id: str
    transcript_path: str
    metadata_path: Optional[str] = None
    published_date: Optional[str] = None

    def to_json(self) -> dict[str, Any]:
        return {
            "output_root": self.output_root,
            "channel_namespace": self.channel_namespace,
            "video_id": self.video_id,
            "transcript_path": self.transcript_path,
            "metadata_path": self.metadata_path,
            "published_date": self.published_date,
        }


@dataclass(frozen=True)
class AnalysisManifest:
    schema_version: int
    input_roots: list[str]
    transcript_count: int
    unique_video_count: int
    run_fingerprint: str

    @staticmethod
    def create(
        *,
        input_roots: list[str],
        transcript_count: int,
        unique_video_count: int,
        run_fingerprint: str,
    ) -> "AnalysisManifest":
        return AnalysisManifest(
            schema_version=SCHEMA_VERSION,
            input_roots=input_roots,
            transcript_count=transcript_count,
            unique_video_count=unique_video_count,
            run_fingerprint=run_fingerprint,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "input_roots": self.input_roots,
            "transcript_count": self.transcript_count,
            "unique_video_count": self.unique_video_count,
            "run_fingerprint": self.run_fingerprint,
        }
