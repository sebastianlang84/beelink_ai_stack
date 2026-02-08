from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]


def _simple_schema(*, props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


TOOLS: list[ToolDef] = [
    ToolDef(
        name="capabilities.get",
        description="Get server capabilities (Markdown)",
        input_schema=_simple_schema(
            props={
                "max_chars": {"type": "integer", "description": "Max characters returned (0 = unlimited). Default: 4000"}
            }
        ),
    ),
    ToolDef(
        name="owui.knowledge.list",
        description="List Open WebUI Knowledge Collections",
        input_schema=_simple_schema(props={"query": {"type": "string"}, "limit": {"type": "integer"}}),
    ),
    ToolDef(
        name="owui.knowledge.create",
        description="Create an Open WebUI Knowledge Collection (gated)",
        input_schema=_simple_schema(
            props={"name": {"type": "string"}, "description": {"type": "string"}},
            required=["name"],
        ),
    ),
    ToolDef(
        name="owui.knowledge.files.list",
        description="List files in an Open WebUI Knowledge Collection",
        input_schema=_simple_schema(
            props={"knowledge_id": {"type": "string"}, "limit": {"type": "integer"}},
            required=["knowledge_id"],
        ),
    ),
    ToolDef(
        name="owui.knowledge.search",
        description="Search Knowledge files (optionally within a specific Knowledge Collection)",
        input_schema=_simple_schema(
            props={
                "query": {"type": "string", "description": "Search query"},
                "knowledge_id": {"type": "string", "description": "Optional Knowledge Collection ID to scope the search"},
                "limit": {"type": "integer", "description": "Max items returned (default: 20)"},
                "page": {"type": "integer", "description": "1-based page number (default: 1)"},
                "order_by": {"type": "string", "description": "Optional server-side ordering (e.g. name|created_at|updated_at)"},
                "direction": {"type": "string", "description": "Optional server-side direction (asc|desc)"},
                "view_option": {"type": "string", "description": "Optional server-side filter (e.g. created|shared)"},
            },
            required=["query"],
        ),
    ),
    ToolDef(
        name="owui.files.process.status",
        description="Get processing status for a file_id",
        input_schema=_simple_schema(props={"file_id": {"type": "string"}}, required=["file_id"]),
    ),
    ToolDef(
        name="owui.tool_servers.get",
        description="Get Open WebUI External Tools config (Admin API)",
        input_schema={"type": "object", "properties": {}},
    ),
    ToolDef(
        name="owui.tool_servers.apply_from_repo",
        description="Apply External Tools config from repo templates mounted in the container (Admin API, gated)",
        input_schema=_simple_schema(
            props={
                "imports_dir": {"type": "string", "description": "Default: OWUI_CONNECTOR_IMPORTS_DIR env"},
                "dry_run": {"type": "boolean", "description": "If true, returns payload only; no POST"},
            }
        ),
    ),
    ToolDef(
        name="owui.knowledge.upload_markdown",
        description="Upload Markdown and add it to a Knowledge Collection (gated)",
        input_schema=_simple_schema(
            props={
                "knowledge_id": {"type": "string"},
                "filename": {"type": "string", "description": "e.g. note.md"},
                "markdown": {"type": "string"},
                "wait_for_processing": {"type": "boolean", "description": "Default: true"},
            },
            required=["knowledge_id", "filename", "markdown"],
        ),
    ),
    ToolDef(
        name="owui.knowledge.file.remove",
        description="Remove a file from a Knowledge Collection (gated)",
        input_schema=_simple_schema(
            props={"knowledge_id": {"type": "string"}, "file_id": {"type": "string"}},
            required=["knowledge_id", "file_id"],
        ),
    ),
]


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    if max_chars <= 64:
        return text[:max_chars]
    return text[: max_chars - 32] + "\n\n...(truncated)"


def handle_mcp_request(
    *,
    payload: dict[str, Any],
    tools: list[ToolDef],
    call_tool: Callable[[str, dict[str, Any]], Any],
) -> dict[str, Any]:
    if payload.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": payload.get("id"), "error": {"code": -32600, "message": "invalid jsonrpc"}}

    method = payload.get("method")
    req_id = payload.get("id")
    params = payload.get("params") or {}

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code: int, message: str, data: Any | None = None) -> dict[str, Any]:
        e = {"code": code, "message": message}
        if data is not None:
            e["data"] = data
        return {"jsonrpc": "2.0", "id": req_id, "error": e}

    try:
        if method == "initialize":
            return ok(
                {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "owui-connector", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                }
            )

        if method == "tools/list":
            return ok({"tools": [{"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in tools]})

        if method == "tools/call":
            name = str((params or {}).get("name") or "").strip()
            args = (params or {}).get("arguments") or {}

            res = call_tool(name, args if isinstance(args, dict) else {})
            if isinstance(res, str):
                text = res
            else:
                text = json.dumps(res, ensure_ascii=False)
            max_chars_raw = (args or {}).get("max_chars")
            try:
                max_chars = int(max_chars_raw) if max_chars_raw is not None else 0
            except Exception:
                max_chars = 0
            return ok({"content": [{"type": "text", "text": _truncate_text(text, max_chars)}]})

        return err(-32601, f"unknown method: {method}")
    except Exception as e:
        return err(-32000, "tool execution error", {"message": str(e)})
