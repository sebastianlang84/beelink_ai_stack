from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]


def _schema_for(model_cls: type[BaseModel]) -> dict[str, Any]:
    return model_cls.model_json_schema()


def _simple_schema(*, props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def make_tools(*, models: dict[str, type[BaseModel]]) -> list[ToolDef]:
    return [
        ToolDef(
            name="capabilities.get",
            description="Get server capabilities (Markdown)",
            input_schema=_simple_schema(
                props={
                    "detail": {
                        "type": "string",
                        "description": "short|full (default: short)",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Max characters returned (0 = unlimited). Default: 6000",
                    },
                }
            ),
        ),
        ToolDef(
            name="configs.list",
            description="List available TranscriptMiner YAML configs",
            input_schema={"type": "object", "properties": {}},
        ),
        ToolDef(
            name="configs.get",
            description="Get a TranscriptMiner YAML config by config_id",
            input_schema=_simple_schema(props={"config_id": {"type": "string"}}, required=["config_id"]),
        ),
        ToolDef(
            name="configs.write",
            description="Validate and optionally write a TranscriptMiner YAML config",
            input_schema=_simple_schema(
                props={
                    "config_id": {"type": "string"},
                    "text": {"type": "string", "description": "Full YAML content"},
                    "validate_only": {"type": "boolean"},
                    "create_backup": {"type": "boolean"},
                    "max_diff_lines": {"type": "integer"},
                },
                required=["config_id", "text"],
            ),
        ),
        ToolDef(
            name="runs.start",
            description="Start a TranscriptMiner run (async) for a config_id",
            input_schema=_simple_schema(
                props={
                    "config_id": {"type": "string"},
                    "skip_index": {"type": "boolean"},
                    "skip_llm": {"type": "boolean"},
                    "skip_report": {"type": "boolean"},
                    "only": {"type": "array", "items": {"type": "string"}},
                    "report_lang": {"type": "string"},
                },
                required=["config_id"],
            ),
        ),
        ToolDef(
            name="runs.status",
            description="Get run status + log tail by run_id",
            input_schema=_simple_schema(props={"run_id": {"type": "string"}}, required=["run_id"]),
        ),
        ToolDef(
            name="sync.topic",
            description="Index summaries for a topic into Open WebUI Knowledge",
            input_schema=_simple_schema(
                props={"topic": {"type": "string"}, "max_videos": {"type": "integer"}, "dry_run": {"type": "boolean"}},
                required=["topic"],
            ),
        ),
        ToolDef(
            name="index.transcript",
            description="Index one Markdown transcript/summary into Open WebUI Knowledge (idempotent via source_id)",
            input_schema=_simple_schema(
                props={
                    "source_id": {"type": "string"},
                    "text": {"type": "string"},
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "channel": {"type": "string"},
                    "published_at": {"type": "string"},
                    "fetched_at": {"type": "string"},
                    "language": {"type": "string"},
                    "knowledge_id": {"type": "string"},
                },
                required=["source_id", "text"],
            ),
        ),
        ToolDef(
            name="transcript.fetch",
            description="Fetch a YouTube transcript by video_id",
            input_schema=_simple_schema(
                props={
                    "video_id": {"type": "string"},
                    "preferred_languages": {"type": "array", "items": {"type": "string"}},
                    "include_timestamps": {"type": "boolean"},
                    "max_chars": {"type": "integer"},
                },
                required=["video_id"],
            ),
        ),
    ]


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
                    "serverInfo": {"name": "transcript-miner", "version": "1.0.0"},
                    "capabilities": {"tools": {}},
                }
            )

        if method == "tools/list":
            return ok({"tools": [{"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in tools]})

        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            res = call_tool(str(name), args)
            # MCP tool result content wrapper: minimal text payload
            # If the tool already returns a plain string, avoid JSON-encoding it (saves tokens and avoids escaping).
            if isinstance(res, str):
                text = res
            else:
                text = json.dumps(res, ensure_ascii=False)
            return ok({"content": [{"type": "text", "text": text}]})

        return err(-32601, f"unknown method: {method}")
    except Exception as e:
        return err(-32000, "tool execution error", {"message": str(e)})
