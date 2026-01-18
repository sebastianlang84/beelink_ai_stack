from __future__ import annotations

from typing import Any

from .validator_core import ValidationIssue, issue


def validate_knowledge_extract_payload(
    *, parsed_obj: dict[str, Any]
) -> list[ValidationIssue]:
    """MVP Schema (PRD 9.2): video_id, channel_id, title, published_at, knowledge_items[]."""

    issues: list[ValidationIssue] = []

    for key in ["video_id", "channel_id", "title", "published_at"]:
        if not isinstance(parsed_obj.get(key), str) or not parsed_obj.get(key):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message=f"Missing or invalid top-level field: {key}",
                    path=f"$.{key}",
                )
            )

    items = parsed_obj.get("knowledge_items")
    if not isinstance(items, list):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Missing or invalid knowledge_items (must be array)",
                path="$.knowledge_items",
            )
        )
        return issues

    for i, item in enumerate(items):
        base = f"$.knowledge_items[{i}]"
        if not isinstance(item, dict):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="knowledge_items[] entry must be an object",
                    path=base,
                )
            )
            continue

        if not isinstance(item.get("text"), str) or not item.get("text"):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Missing or invalid knowledge_items[].text",
                    path=f"{base}.text",
                )
            )

        entities = item.get("entities")
        if entities is not None and not isinstance(entities, list):
            issues.append(
                issue(
                    code="llm_invalid_type",
                    message="knowledge_items[].entities must be an array if present",
                    path=f"{base}.entities",
                )
            )

    return issues
