from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class TranscriptStatus(str, Enum):
    SUCCESS = "success"
    NO_TRANSCRIPT = "no_transcript"
    TRANSCRIPTS_DISABLED = "transcripts_disabled"
    ERROR = "error"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class TranscriptDownloadResult:
    status: TranscriptStatus
    text: Optional[str] = None
    reason: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    def is_success(self) -> bool:
        return self.status == TranscriptStatus.SUCCESS and bool(self.text)

    def to_metadata_fields(self) -> dict[str, Any]:
        """Stable, JSON-serializable fields for metadata/skipped logs."""

        return {
            "transcript_status": self.status.value,
            "transcript_reason": self.reason,
            "transcript_error_type": self.error_type,
            "transcript_error_message": self.error_message,
        }
