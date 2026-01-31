#!/usr/bin/env python3
"""
Human-friendly summary of extracted flows (JSON array from flow_extract.py).

Focus: what OWUI sent (system/user sizes, stream/settings) + whether streamed reasoning appeared.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="in_path", required=True, help="Input JSON array file (last_flows.json)")
    p.add_argument("--max-preview", type=int, default=220, help="Max chars for previews")
    return p.parse_args()


def _preview(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _safe_load_json(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return None


def _extract_system_and_user(payload: dict) -> tuple[str | None, str | None]:
    msgs = payload.get("messages")
    if not isinstance(msgs, list):
        return None, None
    system = None
    user = None
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role == "system" and isinstance(content, str) and system is None:
            system = content
        if role == "user" and isinstance(content, str):
            user = content
    return system, user


def _sse_has_reasoning(response_body: str) -> bool:
    # OpenRouter SSE: "data: {...json...}\n\n"
    for line in response_body.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        raw = line[len("data:") :].strip()
        if raw in ("[DONE]", ""):
            continue
        evt = _safe_load_json(raw)
        if not isinstance(evt, dict):
            continue
        # common: choices[0].delta.reasoning
        choices = evt.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
        if isinstance(delta, dict) and delta.get("reasoning"):
            return True
    return False


def main() -> int:
    args = parse_args()
    data = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("Input must be a JSON array.", file=sys.stderr)
        return 2

    for i, flow in enumerate(data, start=1):
        if not isinstance(flow, dict):
            continue
        ts = flow.get("ts")
        method = flow.get("method")
        url = flow.get("url")
        status = flow.get("status_code")

        req_body = flow.get("request_body")
        req_payload = _safe_load_json(req_body) if isinstance(req_body, str) else None

        model = req_payload.get("model") if isinstance(req_payload, dict) else None
        stream = req_payload.get("stream") if isinstance(req_payload, dict) else None
        reasoning_effort = req_payload.get("reasoning_effort") if isinstance(req_payload, dict) else None
        max_tokens = req_payload.get("max_tokens") if isinstance(req_payload, dict) else None
        tools = req_payload.get("tools") if isinstance(req_payload, dict) else None

        system, user = _extract_system_and_user(req_payload) if isinstance(req_payload, dict) else (None, None)

        resp_body = flow.get("response_body")
        resp_ct = None
        rh = flow.get("response_headers")
        if isinstance(rh, dict):
            resp_ct = rh.get("Content-Type")

        sse_reasoning = False
        if isinstance(resp_body, str) and resp_ct and "text/event-stream" in str(resp_ct):
            sse_reasoning = _sse_has_reasoning(resp_body)

        print(f"== Flow {i} ==")
        print(f"ts: {ts}")
        print(f"req: {method} {url}")
        print(f"status: {status}")
        print(f"model: {model}")
        print(f"stream: {stream}  reasoning_effort: {reasoning_effort}  max_tokens: {max_tokens}")
        print(f"tools_present: {bool(tools)}")
        if isinstance(system, str):
            print(f"system_len: {len(system)}  system_preview: {_preview(system, args.max_preview)}")
        if isinstance(user, str):
            print(f"user_len: {len(user)}  user_preview: {_preview(user, args.max_preview)}")
        if resp_ct:
            print(f"resp_content_type: {resp_ct}")
        if sse_reasoning:
            print("resp_sse_reasoning: true")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

