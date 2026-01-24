from __future__ import annotations

import re
from typing import Any

from .validator_core import ValidationIssue, issue


_RAW_HASH_RE = re.compile(r"^sha256:[0-9a-fA-F]{64}$")

_ALLOWED_EVIDENCE_ROLES = {
    "thesis",
    "risk",
    "catalyst",
    "numbers_valuation",
    "comparison",
    "other",
}

_ALLOWED_MACRO_TAGS = {
    "rates",
    "inflation",
    "liquidity",
    "credit",
    "usd",
    "commodities",
    "growth",
    "sentiment",
    "policy",
    "recession",
    "soft-landing",
}

_ALLOWED_CRYPTO_TAGS = {
    "btc",
    "eth",
    "alts",
    "stablecoins",
    "onchain",
    "derivatives",
    "regulation",
    "mining",
    "cefi",
    "defi",
    "rwa",
}


def _validate_evidence_item(
    *, ev: Any, base: str, issues: list[ValidationIssue]
) -> None:
    if not isinstance(ev, dict):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="evidence[] entry must be an object",
                path=base,
                details={"type": type(ev).__name__},
            )
        )
        return

    for key in ["video_id", "transcript_path", "quote", "role"]:
        if not isinstance(ev.get(key), str) or not ev.get(key):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message=f"Missing or invalid evidence[].{key}",
                    path=f"{base}.{key}",
                )
            )

    snippet_sha256 = ev.get("snippet_sha256")
    if not isinstance(snippet_sha256, str) or not _RAW_HASH_RE.match(snippet_sha256):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Missing or invalid evidence[].snippet_sha256 (expected 'sha256:<64hex>')",
                path=f"{base}.snippet_sha256",
            )
        )

    role = ev.get("role")
    if isinstance(role, str) and role and role not in _ALLOWED_EVIDENCE_ROLES:
        issues.append(
            issue(
                code="llm_invalid_evidence_role",
                message="Invalid evidence[].role",
                path=f"{base}.role",
                details={"role": role, "allowed": sorted(_ALLOWED_EVIDENCE_ROLES)},
            )
        )


def _validate_macro_tags(*, tags: Any, base: str, issues: list[ValidationIssue]) -> None:
    if not isinstance(tags, list) or any(not isinstance(x, str) for x in tags):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Invalid macro_insights[].tags (expected array[string])",
                path=f"{base}.tags",
            )
        )
        return

    # Policy: tag taxonomy is a 2-tuple: ["macro", "<subtag>"] or ["crypto", "<subtag>"].
    if len(tags) < 2:
        issues.append(
            issue(
                code="llm_policy_violation_macro_tags_missing_taxonomy",
                message="macro_insights[].tags must include ['macro'| 'crypto', '<subtag>']",
                path=f"{base}.tags",
                details={"tags": tags},
            )
        )
        return

    category = tags[0]
    subtag = tags[1]
    if category not in {"macro", "crypto"}:
        issues.append(
            issue(
                code="llm_policy_violation_macro_tags_invalid_category",
                message="macro_insights[].tags[0] must be 'macro' or 'crypto'",
                path=f"{base}.tags[0]",
                details={"category": category},
            )
        )
        return

    allowed = _ALLOWED_MACRO_TAGS if category == "macro" else _ALLOWED_CRYPTO_TAGS
    if subtag not in allowed:
        issues.append(
            issue(
                code="llm_policy_violation_macro_tags_invalid_subtag",
                message="macro_insights[].tags[1] must be a known taxonomy subtag",
                path=f"{base}.tags[1]",
                details={"category": category, "subtag": subtag, "allowed": sorted(allowed)},
            )
        )


def _has_forbidden_persisted_keys(obj: Any) -> list[str]:
    """Return a list of JSON paths where forbidden 'mentions/name-drops' keys appear.

    Stocks policy: *no* mention/name-drop persistence (see
    [`docs/use-cases/stocks.md`](docs/use-cases/stocks.md)).
    """

    forbidden_substrings = [
        "mention",
        "name_drop",
        "name-drop",
        "namedrop",
        "name drop",
        "discussed",
    ]

    hits: list[str] = []

    def _walk(x: Any, path: str) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(k, str):
                    kl = k.lower()
                    if any(s in kl for s in forbidden_substrings):
                        hits.append(f"{path}.{k}" if path else f"$.{k}")
                _walk(v, f"{path}.{k}" if path else f"$.{k}")
        elif isinstance(x, list):
            for i, it in enumerate(x):
                _walk(it, f"{path}[{i}]" if path else f"$[{i}]")

    _walk(obj, "")
    return hits


def _is_name_dropping_quote(quote: str) -> bool:
    # Heuristic: list/"name dropping" patterns must not count as `covered`.
    # Baseline patterns are already called out in spec.
    q = quote.lower()

    # Explicit canonical examples.
    if "magnificent 7" in q or re.search(r"\bfaang\b", q):
        return True

    # Generic list markers + multiple comma-separated items.
    comma_count = quote.count(",")
    if comma_count >= 2:
        if re.search(r"\btickers?\b", q):
            return True
        if re.search(r"\bwatchlist\b|\bportfolio\b|\btop\s+\d+\b", q):
            return True

        # Short, list-like enumerations without any reasoning signal.
        # This is a conservative guardrail to avoid treating pure lists as Deep-Dive evidence.
        # Policy: "Reine Listen/Aufzaehlungen ohne Begruendung => nicht covered".
        if len(quote) <= 140:
            has_number = bool(re.search(r"\d|[%$]", quote))
            has_reasoning = bool(
                re.search(
                    r"\bbecause\b|\bsince\b|\bdue\s+to\b|\btherefore\b|\bso\b|\bwhy\b|"
                    r"\bvaluation\b|\brisk\b|\bcatalyst\b|\bcompare\b|\bversus\b|"
                    r"\bweil\b|\bdeshalb\b|\bwegen\b|\bgrund\b|\bvergleichen\b",
                    q,
                )
            )
            if not has_number and not has_reasoning:
                return True

    # Bullet/line list patterns.
    lines = [ln.strip() for ln in quote.splitlines() if ln.strip()]
    bullet_lines = [ln for ln in lines if re.match("^[-*\u2022]\\s+", ln)]
    if len(bullet_lines) >= 2:
        return True

    # "X: a, b, c" style.
    if ":" in quote and comma_count >= 2 and len(quote) <= 160:
        return True

    return False


def _ticker_symbol_policy_violations(symbol: str) -> list[str]:
    # Prevent obvious ticker hallucinations / regex-only resolution.
    # Note: this is deliberately conservative and does not attempt online lookups.
    s = symbol.strip().upper()
    ticker_re = re.compile(r"^[A-Z]{1,5}$")
    if not ticker_re.fullmatch(s):
        return ["invalid_format"]

    # A minimal stoplist of common short tokens that frequently appear in transcripts but are not tickers.
    # This mirrors the spirit of `stop_symbols` in canonicalization.
    suspicious = {
        "A",
        "I",
        "US",
        "EU",
        "UK",
        "IT",
        "AM",
        "PM",
        "ON",
        "IN",
        "AT",
        "AS",
        "OR",
    }
    if s in suspicious:
        return ["suspicious_stopword"]

    return []


def validate_stock_coverage_payload(*, parsed_obj: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    schema_version = parsed_obj.get("schema_version")
    if not isinstance(schema_version, int):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Missing or invalid schema_version (must be int)",
                path="$.schema_version",
            )
        )
    elif schema_version != 1:
        issues.append(
            issue(
                code="llm_unknown_schema_version",
                message="Unknown schema_version (expected 1)",
                path="$.schema_version",
                details={"schema_version": schema_version},
            )
        )

    results = parsed_obj.get("results")
    if not isinstance(results, list):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Missing or invalid results (must be array)",
                path="$.results",
            )
        )
        results = []

    errors = parsed_obj.get("errors")
    if not isinstance(errors, list):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Missing or invalid errors (must be array)",
                path="$.errors",
            )
        )

    for i, item in enumerate(results):
        base = f"$.results[{i}]"
        if not isinstance(item, dict):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="results[] entry must be an object",
                    path=base,
                    details={"type": type(item).__name__},
                )
            )
            continue

        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Missing or invalid symbol",
                    path=f"{base}.symbol",
                )
            )
            symbol = ""
        else:
            for v in _ticker_symbol_policy_violations(symbol):
                if v == "invalid_format":
                    issues.append(
                        issue(
                            code="llm_invalid_symbol_format",
                            message="symbol must look like a ticker (A-Z{1,5})",
                            path=f"{base}.symbol",
                            details={"symbol": symbol},
                        )
                    )
                elif v == "suspicious_stopword":
                    issues.append(
                        issue(
                            code="llm_policy_violation_suspicious_ticker",
                            message="symbol is a common stopword/ambiguous token and must not be asserted as covered",
                            path=f"{base}.symbol",
                            details={"symbol": symbol},
                        )
                    )

        if not isinstance(item.get("channel_namespace"), str) or not item.get(
            "channel_namespace"
        ):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Missing or invalid channel_namespace",
                    path=f"{base}.channel_namespace",
                )
            )

        covered = item.get("covered")
        if not isinstance(covered, dict):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Missing or invalid covered object",
                    path=f"{base}.covered",
                )
            )
            continue

        status = covered.get("status")
        if status not in {"covered", "not_covered", "ambiguous"}:
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Invalid covered.status (expected 'covered'|'not_covered'|'ambiguous')",
                    path=f"{base}.covered.status",
                    details={"status": status},
                )
            )
            continue

    return issues


def validate_stocks_per_video_extract_payload(
    *, parsed_obj: dict[str, Any]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    schema_version = parsed_obj.get("schema_version")
    if schema_version != 1:
        issues.append(
            issue(
                code="llm_unknown_schema_version",
                message="Unknown schema_version (expected 1)",
                path="$.schema_version",
                details={"schema_version": schema_version},
            )
        )

    forbidden_key_paths = _has_forbidden_persisted_keys(parsed_obj)
    if forbidden_key_paths:
        issues.append(
            issue(
                code="llm_policy_violation_mentions_persisted",
                message="Mentions/name-drops must not be persisted in stocks_per_video_extract outputs",
                path="$",
                details={"paths": forbidden_key_paths},
            )
        )

    source = parsed_obj.get("source")
    if not isinstance(source, dict):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Missing or invalid source (must be object)",
                path="$.source",
            )
        )
        source = {}

    for key in ["channel_namespace", "video_id", "transcript_path"]:
        if not isinstance(source.get(key), str) or not source.get(key):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message=f"Missing or invalid source.{key}",
                    path=f"$.source.{key}",
                )
            )

    raw_hash = parsed_obj.get("raw_hash")
    if not isinstance(raw_hash, str) or not _RAW_HASH_RE.match(raw_hash):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Missing or invalid raw_hash (expected 'sha256:<64hex>')",
                path="$.raw_hash",
            )
        )

    tq = parsed_obj.get("transcript_quality")
    if not isinstance(tq, dict):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Missing or invalid transcript_quality (must be object)",
                path="$.transcript_quality",
            )
        )
        tq = {}
    else:
        grade = tq.get("grade")
        if grade not in {"ok", "low", "unknown"}:
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Invalid transcript_quality.grade (expected 'ok'|'low'|'unknown')",
                    path="$.transcript_quality.grade",
                    details={"grade": grade},
                )
            )
        reasons = tq.get("reasons")
        if not isinstance(reasons, list) or any(not isinstance(x, str) for x in reasons):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Invalid transcript_quality.reasons (expected array[string])",
                    path="$.transcript_quality.reasons",
                )
            )

    macro = parsed_obj.get("macro_insights")
    if not isinstance(macro, list):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Missing or invalid macro_insights (must be array)",
                path="$.macro_insights",
            )
        )
        macro = []
    for i, item in enumerate(macro):
        base = f"$.macro_insights[{i}]"
        if not isinstance(item, dict):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="macro_insights[] entry must be an object",
                    path=base,
                )
            )
            continue
        if not isinstance(item.get("claim"), str) or not item.get("claim"):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Missing or invalid macro_insights[].claim",
                    path=f"{base}.claim",
                )
            )
        tags = item.get("tags")
        if tags is None:
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Missing macro_insights[].tags (required for taxonomy)",
                    path=f"{base}.tags",
                )
            )
        else:
            _validate_macro_tags(tags=tags, base=base, issues=issues)

        evidence = item.get("evidence")
        if evidence is not None:
            if not isinstance(evidence, list):
                issues.append(
                    issue(
                        code="llm_missing_required_fields",
                        message="Invalid macro_insights[].evidence (expected array[object])",
                        path=f"{base}.evidence",
                    )
                )
            else:
                for j, ev in enumerate(evidence):
                    _validate_evidence_item(ev=ev, base=f"{base}.evidence[{j}]", issues=issues)

    covered = parsed_obj.get("stocks_covered")
    if not isinstance(covered, list):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Missing or invalid stocks_covered (must be array)",
                path="$.stocks_covered",
            )
        )
        covered = []

    for i, item in enumerate(covered):
        base = f"$.stocks_covered[{i}]"
        if not isinstance(item, dict):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="stocks_covered[] entry must be an object",
                    path=base,
                )
            )
            continue
        canonical = item.get("canonical")
        if not isinstance(canonical, str) or not canonical:
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Missing or invalid stocks_covered[].canonical",
                    path=f"{base}.canonical",
                )
            )
        why = item.get("why_covered")
        if not isinstance(why, str) or not why:
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Missing or invalid stocks_covered[].why_covered",
                    path=f"{base}.why_covered",
                )
            )
        else:
            if _is_name_dropping_quote(why):
                issues.append(
                    issue(
                        code="llm_policy_violation_why_covered_is_list",
                        message="why_covered must be a justification, not a pure list/enumeration",
                        path=f"{base}.why_covered",
                    )
                )

        evidence = item.get("evidence")
        if not isinstance(evidence, list):
            issues.append(
                issue(
                    code="llm_missing_required_fields",
                    message="Missing or invalid stocks_covered[].evidence (must be array)",
                    path=f"{base}.evidence",
                )
            )
            evidence = []
        elif len(evidence) < 2:
            issues.append(
                issue(
                    code="llm_policy_violation_stock_not_deep_dive",
                    message="stocks_covered[] must include at least 2 evidence items (deep-dive policy)",
                    path=f"{base}.evidence",
                    details={"evidence_count": len(evidence)},
                )
            )

        roles: list[str] = []
        for j, ev in enumerate(evidence):
            _validate_evidence_item(ev=ev, base=f"{base}.evidence[{j}]", issues=issues)
            if isinstance(ev, dict) and isinstance(ev.get("role"), str):
                roles.append(ev["role"])

        if evidence:
            has_thesis = any(r == "thesis" for r in roles)
            has_supporting = any(
                r in {"risk", "catalyst", "numbers_valuation", "comparison"} for r in roles
            )
            if not has_thesis or not has_supporting:
                issues.append(
                    issue(
                        code="llm_policy_violation_stock_not_deep_dive",
                        message=(
                            "stocks_covered[] must include role='thesis' and at least one supporting role "
                            "(risk|catalyst|numbers_valuation|comparison)"
                        ),
                        path=f"{base}.evidence",
                        details={"roles": roles},
                    )
                )

    errors = parsed_obj.get("errors")
    if not isinstance(errors, list):
        issues.append(
            issue(
                code="llm_missing_required_fields",
                message="Missing or invalid errors (must be array)",
                path="$.errors",
            )
        )

    return issues
