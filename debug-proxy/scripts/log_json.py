import json
import os
from datetime import datetime, timezone

from mitmproxy import http

LOG_PATH = os.getenv("PROXY_LOG_PATH", "/data/flows.jsonl")
MAX_CHARS = int(os.getenv("PROXY_LOG_MAX_CHARS", "2000"))
MAX_TOTAL_CHARS = int(os.getenv("PROXY_LOG_MAX_TOTAL_CHARS", "100000"))

_REDACT_HEADERS = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "openai-api-key",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(value: str | None) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    if len(value) <= MAX_CHARS:
        return value, False
    return value[-MAX_CHARS:], True


def _decode_body(body: bytes | None) -> str:
    if not body:
        return ""
    return body.decode("utf-8", errors="replace")


def _headers_to_dict(headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in headers.items():
        key = str(k)
        if key.lower() in _REDACT_HEADERS:
            out[key] = "***"
        else:
            out[key] = str(v)
    return out


def _write_log(entry: dict[str, object]) -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _enforce_max_total_chars()


def _enforce_max_total_chars() -> None:
    if MAX_TOTAL_CHARS <= 0:
        return
    try:
        with open(LOG_PATH, "r+", encoding="utf-8") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            if size <= MAX_TOTAL_CHARS:
                return
            # Keep only the last MAX_TOTAL_CHARS characters
            keep = min(size, MAX_TOTAL_CHARS)
            fh.seek(size - keep)
            tail = fh.read(keep)
            fh.seek(0)
            fh.write(tail)
            fh.truncate()
    except OSError:
        return


def response(flow: http.HTTPFlow) -> None:
    req = flow.request
    resp = flow.response
    req_body, req_trunc = _truncate(_decode_body(req.raw_content))
    resp_body, resp_trunc = _truncate(_decode_body(resp.raw_content))

    entry = {
        "ts": _now_iso(),
        "flow_id": flow.id,
        "method": req.method,
        "url": req.pretty_url,
        "host": req.host,
        "path": req.path,
        "request_headers": _headers_to_dict(req.headers),
        "request_body": req_body,
        "request_body_truncated": req_trunc,
        "status_code": resp.status_code,
        "response_headers": _headers_to_dict(resp.headers),
        "response_body": resp_body,
        "response_body_truncated": resp_trunc,
    }
    _write_log(entry)
