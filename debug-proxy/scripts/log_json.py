import json
import os
from datetime import datetime, timezone

from mitmproxy import http

LOG_PATH = os.getenv("PROXY_LOG_PATH", "/data/flows.jsonl")
MAX_CHARS = int(os.getenv("PROXY_LOG_MAX_CHARS", "10000"))
MAX_BYTES = int(os.getenv("PROXY_LOG_MAX_BYTES", "10485760"))  # 10 MB
ROTATE_KEEP = int(os.getenv("PROXY_LOG_ROTATE_KEEP", "5"))

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
    _maybe_rotate()
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _maybe_rotate() -> None:
    if MAX_BYTES <= 0:
        return
    try:
        size = os.path.getsize(LOG_PATH)
    except FileNotFoundError:
        return
    except OSError:
        return
    if size < MAX_BYTES:
        return
    if ROTATE_KEEP <= 0:
        return
    # Rotate: flows.jsonl -> flows.jsonl.1, keep .1..ROTATE_KEEP
    for i in range(ROTATE_KEEP, 0, -1):
        src = f"{LOG_PATH}.{i}"
        dst = f"{LOG_PATH}.{i + 1}"
        if os.path.exists(src):
            try:
                os.replace(src, dst)
            except OSError:
                pass
    try:
        os.replace(LOG_PATH, f"{LOG_PATH}.1")
    except OSError:
        pass


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
