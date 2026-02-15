#!/usr/bin/env bash
set -euo pipefail

# Runs a reproducible Open WebUI chat baseline over a query matrix and writes
# a Markdown report with latency/status/output snippets.
#
# Usage:
#   ./scripts/owui_rag_baseline_probe.sh
#   ./scripts/owui_rag_baseline_probe.sh --limit 3
#   ./scripts/owui_rag_baseline_probe.sh --model google/gemini-3-flash-preview --output docs/owui_rag_baseline_2026-02-15.md
#
# Inputs:
#   - OPEN_WEBUI_API_KEY or OWUI_API_KEY (env) OR shared .env file in repo root
#   - config/owui_rag_baseline_queries.json (default query matrix)
#
# Output:
#   - Markdown report (default: docs/owui_rag_baseline_latest.md)

BASE_URL="${OPEN_WEBUI_BASE_URL_PUBLIC:-http://127.0.0.1:3000}"
MODEL="${OWUI_BASELINE_MODEL:-google/gemini-3-flash-preview}"
QUERIES_FILE="${OWUI_BASELINE_QUERIES_FILE:-config/owui_rag_baseline_queries.json}"
OUTPUT_FILE="${OWUI_BASELINE_OUTPUT_FILE:-docs/owui_rag_baseline_latest.md}"
LIMIT="${OWUI_BASELINE_LIMIT:-0}"
TIMEOUT_SECONDS="${OWUI_BASELINE_TIMEOUT_SECONDS:-120}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --model)
      MODEL="${2:-}"
      shift 2
      ;;
    --queries-file)
      QUERIES_FILE="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_FILE="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-0}"
      shift 2
      ;;
    --timeout-seconds)
      TIMEOUT_SECONDS="${2:-120}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$(dirname "${OUTPUT_FILE}")"

export OWUI_BASE_URL="${BASE_URL}"
export OWUI_BASELINE_MODEL_EFFECTIVE="${MODEL}"
export OWUI_BASELINE_QUERIES_FILE_EFFECTIVE="${QUERIES_FILE}"
export OWUI_BASELINE_LIMIT_EFFECTIVE="${LIMIT}"
export OWUI_BASELINE_TIMEOUT_SECONDS_EFFECTIVE="${TIMEOUT_SECONDS}"
export OWUI_BASELINE_OUTPUT_FILE_EFFECTIVE="${OUTPUT_FILE}"

uv run python - <<'PY'
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def read_env_file_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip()
    return ""


def parse_sse_body(body_text: str) -> dict:
    content_parts: list[str] = []
    usage = {}
    done = False
    chunks = 0
    tool_call_names: list[str] = []
    tool_call_count = 0

    for raw_line in body_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data:
            continue
        if data == "[DONE]":
            done = True
            break
        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            continue

        chunks += 1
        choices = obj.get("choices") or []
        if choices and isinstance(choices[0], dict):
            delta = choices[0].get("delta") or {}
            piece = delta.get("content")
            if isinstance(piece, str) and piece:
                content_parts.append(piece)
            tool_calls = delta.get("tool_calls") or []
            if isinstance(tool_calls, list):
                tool_call_count += len(tool_calls)
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    fn = (tc.get("function") or {}).get("name")
                    if isinstance(fn, str) and fn:
                        tool_call_names.append(fn)
        if isinstance(obj.get("usage"), dict):
            usage = obj["usage"]

    return {
        "text": "".join(content_parts).strip(),
        "usage": usage,
        "chunks": chunks,
        "done": done,
        "tool_call_count": tool_call_count,
        "tool_call_names": tool_call_names,
    }


base_url = os.environ.get("OWUI_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
model = os.environ.get("OWUI_BASELINE_MODEL_EFFECTIVE", "google/gemini-3-flash-preview")
queries_file = Path(os.environ.get("OWUI_BASELINE_QUERIES_FILE_EFFECTIVE", "config/owui_rag_baseline_queries.json"))
limit = int(os.environ.get("OWUI_BASELINE_LIMIT_EFFECTIVE", "0") or "0")
timeout_seconds = int(os.environ.get("OWUI_BASELINE_TIMEOUT_SECONDS_EFFECTIVE", "120") or "120")
output_file = Path(os.environ.get("OWUI_BASELINE_OUTPUT_FILE_EFFECTIVE", "docs/owui_rag_baseline_latest.md"))

token = (
    os.environ.get("OPEN_WEBUI_API_KEY", "").strip()
    or os.environ.get("OWUI_API_KEY", "").strip()
    or read_env_file_value(Path(".env"), "OPEN_WEBUI_API_KEY")
    or read_env_file_value(Path(".env"), "OWUI_API_KEY")
)
if not token:
    raise SystemExit("Missing OPEN_WEBUI_API_KEY/OWUI_API_KEY (env or .env)")

queries = json.loads(queries_file.read_text(encoding="utf-8"))
if not isinstance(queries, list) or not queries:
    raise SystemExit(f"Invalid or empty query matrix: {queries_file}")
if limit > 0:
    queries = queries[:limit]

endpoints = ["/api/chat/completions", "/api/v1/chat/completions"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

results = []
for item in queries:
    qid = str(item.get("id", "")).strip() or f"q{len(results) + 1}"
    query = str(item.get("query", "")).strip()
    focus = str(item.get("focus", "")).strip()
    if not query:
        continue

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": query}],
        "stream": True,
    }
    body = json.dumps(payload).encode("utf-8")

    endpoint_used = ""
    status = 0
    response_text = ""
    error_text = ""
    elapsed_ms = 0
    parsed = {"text": "", "usage": {}, "chunks": 0, "done": False}

    for endpoint in endpoints:
        endpoint_used = endpoint
        req = urllib.request.Request(f"{base_url}{endpoint}", data=body, headers=headers, method="POST")
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                status = int(resp.status)
                response_text = resp.read().decode("utf-8", "replace")
                elapsed_ms = int((time.perf_counter() - started) * 1000)
            parsed = parse_sse_body(response_text)
            break
        except urllib.error.HTTPError as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            status = int(exc.code)
            error_text = exc.read().decode("utf-8", "replace")[:500]
            if endpoint == endpoints[-1]:
                break
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            status = -1
            error_text = f"{type(exc).__name__}: {exc}"
            if endpoint == endpoints[-1]:
                break

    usage = parsed.get("usage") or {}
    preview = parsed.get("text", "")
    if len(preview) > 220:
        preview = preview[:220] + "..."

    results.append(
        {
            "id": qid,
            "focus": focus,
            "query": query,
            "endpoint": endpoint_used,
            "status": status,
            "latency_ms": elapsed_ms,
            "chunks": parsed.get("chunks", 0),
            "done": parsed.get("done", False),
            "tool_call_count": parsed.get("tool_call_count", 0),
            "tool_call_names": parsed.get("tool_call_names", []),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "preview": preview,
            "full_text": parsed.get("text", ""),
            "error": error_text,
        }
    )

generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
ok_count = sum(1 for r in results if r["status"] == 200 and r["done"])
fail_count = len(results) - ok_count

lines = [
    "# Open WebUI RAG Baseline Report",
    "",
    f"- generated_at_utc: `{generated_at}`",
    f"- base_url: `{base_url}`",
    f"- model: `{model}`",
    f"- query_matrix: `{queries_file}`",
    f"- total_queries: `{len(results)}`",
    f"- ok_done: `{ok_count}`",
    f"- failed_or_incomplete: `{fail_count}`",
    "",
    "## Summary",
    "",
    "| id | status | latency_ms | chunks | done | tool_calls | total_tokens | preview |",
    "| --- | --- | --- | --- | --- | --- | --- |",
]

for r in results:
    preview = (r["preview"] or "").replace("\n", " ").replace("|", "\\|")
    tokens = r["total_tokens"] if r["total_tokens"] is not None else ""
    lines.append(
        f"| `{r['id']}` | `{r['status']}` | `{r['latency_ms']}` | `{r['chunks']}` | `{str(r['done']).lower()}` | `{r['tool_call_count']}` | `{tokens}` | {preview} |"
    )

lines.extend(["", "## Details", ""])
for r in results:
    lines.append(f"### `{r['id']}`")
    lines.append(f"- focus: `{r['focus']}`")
    lines.append(f"- endpoint: `{r['endpoint']}`")
    lines.append(f"- status: `{r['status']}`")
    lines.append(f"- latency_ms: `{r['latency_ms']}`")
    lines.append(f"- chunks: `{r['chunks']}`")
    lines.append(f"- done: `{str(r['done']).lower()}`")
    lines.append(f"- tool_call_count: `{r['tool_call_count']}`")
    if r["tool_call_names"]:
        lines.append(f"- tool_call_names: `{', '.join(sorted(set(r['tool_call_names']))[:12])}`")
    lines.append(f"- prompt_tokens: `{r['prompt_tokens']}`")
    lines.append(f"- completion_tokens: `{r['completion_tokens']}`")
    lines.append(f"- total_tokens: `{r['total_tokens']}`")
    if r["error"]:
        lines.append("- error:")
        lines.append("```text")
        lines.append(r["error"])
        lines.append("```")
    lines.append("- query:")
    lines.append("```text")
    lines.append(r["query"])
    lines.append("```")
    lines.append("- response:")
    lines.append("```text")
    lines.append((r["full_text"] or "").strip())
    lines.append("```")
    lines.append("")

output_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
print(f"Wrote baseline report: {output_file}")
print(f"queries={len(results)} ok_done={ok_count} failed_or_incomplete={fail_count}")
PY
