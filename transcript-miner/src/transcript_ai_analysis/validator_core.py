from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str
    details: dict[str, Any]


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    payload: dict[str, Any] | None
    issues: list[ValidationIssue]


def issue(
    *, code: str, message: str, path: str, details: dict[str, Any] | None = None
) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, path=path, details=details or {})
