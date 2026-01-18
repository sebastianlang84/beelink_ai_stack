from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .validator_ai_knowledge import validate_knowledge_extract_payload
from .validator_core import ValidationIssue, ValidationResult, issue
from .validator_stocks import (
    validate_stock_coverage_payload,
    validate_stocks_per_video_extract_payload,
)


_ISO_UTC_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


_SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _read_text_best_effort(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_bytes().decode("utf-8", errors="replace")
        except Exception:
            return None
    except Exception:
        return None


def _issue(
    *, code: str, message: str, path: str, details: dict[str, Any] | None = None
) -> ValidationIssue:
    return issue(code=code, message=message, path=path, details=details)


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def _sha256_hex_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def validate_llm_report_artefacts(*, llm_dir: Path) -> ValidationResult:
    """Offline validator for the LLM artefact bundle in a single `analysis/llm` dir.

    Validates:
    - `metadata.json` required fields + basic type checks + ISO-UTC timestamps
    - hash/pointer consistency between `metadata.json` and `report.json`
    - derived report file is byte-identical to `report.json.output.content`
    - optional rolling-window guardrails if represented in metadata:
      * no self-referential loops
      * max 1 hop in inherited sources chain
      * inherited items must not be marked as evidence
    """

    issues: list[ValidationIssue] = []

    report_path = llm_dir / "report.json"
    metadata_path = llm_dir / "metadata.json"
    if not report_path.exists():
        return ValidationResult(
            ok=False,
            payload=None,
            issues=[
                _issue(
                    code="llm_missing_artefact",
                    message="missing report.json",
                    path=str(report_path),
                )
            ],
        )
    if not metadata_path.exists():
        return ValidationResult(
            ok=False,
            payload=None,
            issues=[
                _issue(
                    code="llm_missing_artefact",
                    message="missing metadata.json",
                    path=str(metadata_path),
                )
            ],
        )

    try:
        report_bytes = report_path.read_bytes()
        report = json.loads(report_bytes.decode("utf-8"))
    except Exception as e:
        return ValidationResult(
            ok=False,
            payload=None,
            issues=[
                _issue(
                    code="llm_invalid_report_json",
                    message=f"failed to parse report.json: {e}",
                    path=str(report_path),
                )
            ],
        )
    if not isinstance(report, dict):
        return ValidationResult(
            ok=False,
            payload=None,
            issues=[
                _issue(
                    code="llm_invalid_report_json",
                    message="report.json must be a JSON object",
                    path=str(report_path),
                    details={"type": type(report).__name__},
                )
            ],
        )

    try:
        metadata = _read_json(metadata_path)
    except Exception as e:
        return ValidationResult(
            ok=False,
            payload=None,
            issues=[
                _issue(
                    code="llm_invalid_metadata_json",
                    message=f"failed to parse metadata.json: {e}",
                    path=str(metadata_path),
                )
            ],
        )

    # --- metadata required fields ---
    if metadata.get("schema_version") != 1:
        issues.append(
            _issue(
                code="llm_invalid_metadata",
                message="invalid metadata schema_version (expected 1)",
                path="$.schema_version",
                details={"schema_version": metadata.get("schema_version")},
            )
        )

    for key in ["batch", "run_fingerprint", "model", "created_at_utc"]:
        if not isinstance(metadata.get(key), str) or not metadata.get(key):
            issues.append(
                _issue(
                    code="llm_invalid_metadata",
                    message=f"missing or invalid metadata.{key}",
                    path=f"$.{key}",
                )
            )

    created_at_utc = metadata.get("created_at_utc")
    if (
        isinstance(created_at_utc, str)
        and created_at_utc
        and not _ISO_UTC_Z_RE.match(created_at_utc)
    ):
        issues.append(
            _issue(
                code="llm_invalid_metadata",
                message="created_at_utc must be ISO-8601 UTC with trailing 'Z'",
                path="$.created_at_utc",
                details={"created_at_utc": created_at_utc},
            )
        )

    # --- report required fields (minimum for cross-checks) ---
    if not isinstance(report.get("schema_version"), int):
        issues.append(
            _issue(
                code="llm_invalid_report_json",
                message="missing or invalid report.schema_version (expected int)",
                path="$.schema_version",
            )
        )

    if not isinstance(report.get("run_fingerprint"), str) or not report.get(
        "run_fingerprint"
    ):
        issues.append(
            _issue(
                code="llm_invalid_report_json",
                message="missing or invalid report.run_fingerprint",
                path="$.run_fingerprint",
            )
        )

    output = report.get("output")
    content = output.get("content") if isinstance(output, dict) else None
    if not isinstance(content, str):
        issues.append(
            _issue(
                code="llm_invalid_report_json",
                message="missing or invalid report.output.content",
                path="$.output.content",
            )
        )
        content = ""

    # --- hash/pointer consistency ---
    source = metadata.get("source")
    if not isinstance(source, dict):
        issues.append(
            _issue(
                code="llm_invalid_metadata",
                message="missing or invalid metadata.source object",
                path="$.source",
            )
        )
        source = {}

    if source.get("report_json") != "report.json":
        issues.append(
            _issue(
                code="llm_invalid_metadata",
                message="metadata.source.report_json must be 'report.json'",
                path="$.source.report_json",
                details={"report_json": source.get("report_json")},
            )
        )

    report_json_sha256 = source.get("report_json_sha256")
    if not isinstance(report_json_sha256, str) or not _SHA256_HEX_RE.match(
        report_json_sha256
    ):
        issues.append(
            _issue(
                code="llm_invalid_metadata",
                message="missing or invalid metadata.source.report_json_sha256",
                path="$.source.report_json_sha256",
            )
        )
    else:
        expected = _sha256_hex_bytes(report_bytes)
        if report_json_sha256.lower() != expected.lower():
            issues.append(
                _issue(
                    code="llm_hash_mismatch",
                    message="metadata.source.report_json_sha256 does not match report.json bytes",
                    path="$.source.report_json_sha256",
                    details={"expected": expected, "actual": report_json_sha256},
                )
            )

    derived = metadata.get("derived")
    if not isinstance(derived, dict):
        issues.append(
            _issue(
                code="llm_invalid_metadata",
                message="missing or invalid metadata.derived object",
                path="$.derived",
            )
        )
        derived = {}

    derived_report_name = derived.get("report")
    if not isinstance(derived_report_name, str) or not derived_report_name:
        issues.append(
            _issue(
                code="llm_invalid_metadata",
                message="missing or invalid metadata.derived.report",
                path="$.derived.report",
            )
        )
        derived_report_name = ""

    output_content_sha256 = derived.get("output_content_sha256")
    if not isinstance(output_content_sha256, str) or not _SHA256_HEX_RE.match(
        output_content_sha256
    ):
        issues.append(
            _issue(
                code="llm_invalid_metadata",
                message="missing or invalid metadata.derived.output_content_sha256",
                path="$.derived.output_content_sha256",
            )
        )
    else:
        expected = _sha256_hex_bytes(content.encode("utf-8"))
        if output_content_sha256.lower() != expected.lower():
            issues.append(
                _issue(
                    code="llm_hash_mismatch",
                    message="metadata.derived.output_content_sha256 does not match report.output.content",
                    path="$.derived.output_content_sha256",
                    details={"expected": expected, "actual": output_content_sha256},
                )
            )

    # Derived report byte identity.
    if derived_report_name:
        derived_path = llm_dir / derived_report_name
        if not derived_path.exists():
            issues.append(
                _issue(
                    code="llm_missing_artefact",
                    message="derived report file missing",
                    path=str(derived_path),
                )
            )
        else:
            derived_bytes = derived_path.read_bytes()
            expected_bytes = content.encode("utf-8")
            if derived_bytes != expected_bytes:
                issues.append(
                    _issue(
                        code="llm_derived_report_mismatch",
                        message="derived report file is not byte-identical to report.output.content",
                        path=str(derived_path),
                        details={
                            "expected_len": len(expected_bytes),
                            "actual_len": len(derived_bytes),
                        },
                    )
                )

    # Cross-check basic identity fields (best-effort, no hard fail on report parse issues).
    if isinstance(report.get("batch"), str) and isinstance(metadata.get("batch"), str):
        if (
            metadata.get("batch")
            and report.get("batch")
            and metadata.get("batch") != report.get("batch")
        ):
            issues.append(
                _issue(
                    code="llm_invalid_metadata",
                    message="metadata.batch must match report.batch",
                    path="$.batch",
                    details={
                        "metadata": metadata.get("batch"),
                        "report": report.get("batch"),
                    },
                )
            )

    if isinstance(report.get("model"), str) and isinstance(metadata.get("model"), str):
        if (
            metadata.get("model")
            and report.get("model")
            and metadata.get("model") != report.get("model")
        ):
            issues.append(
                _issue(
                    code="llm_invalid_metadata",
                    message="metadata.model must match report.model",
                    path="$.model",
                    details={
                        "metadata": metadata.get("model"),
                        "report": report.get("model"),
                    },
                )
            )

    if isinstance(report.get("run_fingerprint"), str) and isinstance(
        metadata.get("run_fingerprint"), str
    ):
        if (
            metadata.get("run_fingerprint")
            and report.get("run_fingerprint")
            and metadata.get("run_fingerprint") != report.get("run_fingerprint")
        ):
            issues.append(
                _issue(
                    code="llm_invalid_metadata",
                    message="metadata.run_fingerprint must match report.run_fingerprint",
                    path="$.run_fingerprint",
                )
            )

    if isinstance(metadata.get("report_schema_version"), int) and isinstance(
        report.get("schema_version"), int
    ):
        if metadata.get("report_schema_version") != report.get("schema_version"):
            issues.append(
                _issue(
                    code="llm_invalid_metadata",
                    message="metadata.report_schema_version must match report.schema_version",
                    path="$.report_schema_version",
                    details={
                        "metadata": metadata.get("report_schema_version"),
                        "report": report.get("schema_version"),
                    },
                )
            )

    if isinstance(metadata.get("created_at_utc"), str) and isinstance(
        report.get("created_at_utc"), str
    ):
        if (
            metadata.get("created_at_utc")
            and report.get("created_at_utc")
            and metadata.get("created_at_utc") != report.get("created_at_utc")
        ):
            issues.append(
                _issue(
                    code="llm_invalid_metadata",
                    message="metadata.created_at_utc must match report.created_at_utc",
                    path="$.created_at_utc",
                )
            )

    # --- optional: rolling-window guardrails (only enforced if metadata includes it) ---
    rolling_window = metadata.get("rolling_window")
    if rolling_window is not None:
        if not isinstance(rolling_window, dict):
            issues.append(
                _issue(
                    code="llm_invalid_metadata",
                    message="metadata.rolling_window must be an object",
                    path="$.rolling_window",
                )
            )
        else:
            inherited_sources = rolling_window.get("inherited_sources")
            if inherited_sources is not None:
                if not isinstance(inherited_sources, list):
                    issues.append(
                        _issue(
                            code="llm_invalid_metadata",
                            message="rolling_window.inherited_sources must be an array",
                            path="$.rolling_window.inherited_sources",
                        )
                    )
                else:
                    if len(inherited_sources) > 1:
                        issues.append(
                            _issue(
                                code="llm_rolling_window_max_hop_exceeded",
                                message="max 1 inherited source is allowed (max 1 hop)",
                                path="$.rolling_window.inherited_sources",
                                details={"count": len(inherited_sources)},
                            )
                        )
                    if len(inherited_sources) == 1:
                        src0 = inherited_sources[0]
                        if not isinstance(src0, dict):
                            issues.append(
                                _issue(
                                    code="llm_invalid_metadata",
                                    message="rolling_window.inherited_sources[0] must be an object",
                                    path="$.rolling_window.inherited_sources[0]",
                                )
                            )
                        else:
                            src_meta = src0.get("metadata_path")
                            if not isinstance(src_meta, str) or not src_meta:
                                issues.append(
                                    _issue(
                                        code="llm_invalid_metadata",
                                        message="inherited source requires metadata_path",
                                        path="$.rolling_window.inherited_sources[0].metadata_path",
                                    )
                                )
                            else:
                                src_meta_path = (llm_dir / src_meta).resolve()
                                if src_meta_path == metadata_path.resolve():
                                    issues.append(
                                        _issue(
                                            code="llm_rolling_window_loop",
                                            message="inherited source metadata_path must not self-reference",
                                            path="$.rolling_window.inherited_sources[0].metadata_path",
                                            details={"metadata_path": src_meta},
                                        )
                                    )
                                elif not src_meta_path.exists():
                                    issues.append(
                                        _issue(
                                            code="llm_invalid_metadata",
                                            message="inherited source metadata_path does not exist",
                                            path="$.rolling_window.inherited_sources[0].metadata_path",
                                            details={"metadata_path": src_meta},
                                        )
                                    )
                                else:
                                    try:
                                        src_meta_obj = _read_json(src_meta_path)
                                    except Exception as e:
                                        issues.append(
                                            _issue(
                                                code="llm_invalid_metadata",
                                                message=f"failed to parse inherited source metadata: {e}",
                                                path="$.rolling_window.inherited_sources[0].metadata_path",
                                                details={"metadata_path": src_meta},
                                            )
                                        )
                                    else:
                                        nested = src_meta_obj.get("rolling_window")
                                        if isinstance(nested, dict) and nested.get(
                                            "inherited_sources"
                                        ):
                                            issues.append(
                                                _issue(
                                                    code="llm_rolling_window_max_hop_exceeded",
                                                    message="inherited source itself has inherited_sources (would exceed max 1 hop)",
                                                    path="$.rolling_window.inherited_sources[0].metadata_path",
                                                    details={"metadata_path": src_meta},
                                                )
                                            )

            evidence_items = rolling_window.get("evidence_items")
            if evidence_items is not None:
                if not isinstance(evidence_items, list):
                    issues.append(
                        _issue(
                            code="llm_invalid_metadata",
                            message="rolling_window.evidence_items must be an array",
                            path="$.rolling_window.evidence_items",
                        )
                    )
                else:
                    for i, ev in enumerate(evidence_items):
                        if not isinstance(ev, dict):
                            issues.append(
                                _issue(
                                    code="llm_invalid_metadata",
                                    message="evidence_items[] entries must be objects",
                                    path=f"$.rolling_window.evidence_items[{i}]",
                                )
                            )
                            continue
                        prov = ev.get("provenance")
                        if prov == "inherited":
                            issues.append(
                                _issue(
                                    code="llm_inherited_marked_as_evidence",
                                    message="inherited items must not be marked as evidence",
                                    path=f"$.rolling_window.evidence_items[{i}].provenance",
                                )
                            )

    return ValidationResult(
        ok=(len(issues) == 0),
        payload={"report": report, "metadata": metadata},
        issues=issues,
    )


def validate_llm_output_content(*, content: str) -> ValidationResult:
    """Validate `output.content` against the strict JSON + evidence policy.

    Supported payloads (task-dispatched):
    - Legacy: `task == "stock_coverage"` (schema_version=1)
    - Stocks policy (no name-drops persisted): `task == "stocks_per_video_extract"` (schema_version=1)

    Spec source: [`docs/analysis/llm_prompt_spec_strict_json_evidence.md`](docs/analysis/llm_prompt_spec_strict_json_evidence.md:1)

    Additional offline quality policy (see [`TODO.md`](../../TODO.md:54)) enforced here:
    - Apple ambiguity guardrail: block `symbol=AAPL` covered when evidence quote lacks company context
    - List/name-dropping guardrails beyond the explicit examples
    - Low transcript quality guardrail (placeholder markers)
    - Ticker-fakes guardrail: reject suspicious/invalid ticker symbols (no regex-only decision)
    """

    issues: list[ValidationIssue] = []
    raw = content.strip()

    # 1) Strict JSON: exactly one JSON object, no fences/prose.
    if not raw.startswith("{") or not raw.endswith("}"):
        return ValidationResult(
            ok=False,
            payload=None,
            issues=[
                _issue(
                    code="llm_invalid_json",
                    message="LLM output is not strict JSON object (must start with '{' and end with '}')",
                    path="$",
                    details={"prefix": raw[:40], "suffix": raw[-40:]},
                )
            ],
        )

    try:
        parsed = json.loads(raw)
    except Exception as e:
        return ValidationResult(
            ok=False,
            payload=None,
            issues=[
                _issue(
                    code="llm_invalid_json",
                    message=f"LLM output JSON parse failed: {e}",
                    path="$",
                )
            ],
        )

    if not isinstance(parsed, dict):
        return ValidationResult(
            ok=False,
            payload=None,
            issues=[
                _issue(
                    code="llm_missing_required_fields",
                    message="LLM output JSON must be an object",
                    path="$",
                    details={"type": type(parsed).__name__},
                )
            ],
        )

    # 2) Task dispatch.
    task = parsed.get("task")
    if task == "stock_coverage":
        issues.extend(validate_stock_coverage_payload(parsed_obj=parsed))
    elif task == "stocks_per_video_extract":
        issues.extend(validate_stocks_per_video_extract_payload(parsed_obj=parsed))
    elif task == "knowledge_extract":
        issues.extend(validate_knowledge_extract_payload(parsed_obj=parsed))
    else:
        issues.append(
            _issue(
                code="llm_missing_required_fields",
                message="Invalid task (expected 'stock_coverage', 'stocks_per_video_extract' or 'knowledge_extract')",
                path="$.task",
                details={"task": task},
            )
        )

    return ValidationResult(ok=(len(issues) == 0), payload=parsed, issues=issues)
