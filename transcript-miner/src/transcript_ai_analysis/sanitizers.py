from __future__ import annotations

import re
from typing import Any


# Matches common bullet/numbered list prefixes.
_BULLET_LINE_RE = re.compile(r"^\s*(?:[-*•]|\d+[\.)])\s+", re.UNICODE)


def _looks_like_bullets(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    bulletish = sum(1 for ln in lines if _BULLET_LINE_RE.match(ln))
    return bulletish >= 2


def _flatten_bullets(text: str) -> str:
    parts: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        s = _BULLET_LINE_RE.sub("", s).strip()
        if s:
            parts.append(s)
    return "; ".join(parts)


def sanitize_stocks_per_video_extract_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Deterministically sanitize *format only* for stocks_per_video_extract.

    Policy:
    - Repair only the *shape/format* of fields (no new facts).
    - Intended to reduce run failures on minor formatting deviations.
    """

    repairs: list[dict[str, Any]] = []
    stocks = payload.get("stocks_covered")
    if not isinstance(stocks, list):
        return payload, repairs

    for i, item in enumerate(stocks):
        if not isinstance(item, dict):
            continue
        if "why_covered" not in item:
            continue

        path = f"$.stocks_covered[{i}].why_covered"
        v = item.get("why_covered")

        # Case 1: list -> string
        if isinstance(v, list):
            parts = [str(x).strip() for x in v if str(x).strip()]
            new_v = "; ".join(parts).strip()
            item["why_covered"] = new_v
            repairs.append(
                {
                    "path": path,
                    "kind": "list_to_string",
                    "before_type": "list",
                    "after_len": len(new_v),
                }
            )
            continue

        # Case 2: bullet-ish string -> flattened string
        if isinstance(v, str):
            s = v.strip()
            if _looks_like_bullets(s):
                new_v = _flatten_bullets(s).strip()
                item["why_covered"] = new_v
                repairs.append(
                    {
                        "path": path,
                        "kind": "bullets_to_sentence",
                        "before_type": "str",
                        "after_len": len(new_v),
                    }
                )
                continue

            # Case 3: whitespace normalization (harmless)
            new_v = re.sub(r"\s+", " ", s).strip()
            if new_v != v:
                item["why_covered"] = new_v
                repairs.append(
                    {
                        "path": path,
                        "kind": "whitespace_normalized",
                        "before_type": "str",
                        "after_len": len(new_v),
                    }
                )

    return payload, repairs

