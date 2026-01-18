from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from .models import (
    GetChunkRequest,
    GetDocRequest,
    KnowledgeCreateRequest,
    KnowledgeListRequest,
    SearchRequest,
    SnapshotsListRequest,
    SourcesCreateRequest,
    SyncPrepareRequest,
    SyncStartRequest,
    SyncStatusRequest,
)
from .service import Context6Service, ToolUserError


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


def _capabilities_markdown() -> str:
    return "\n".join(
        [
            "# context6 (MCP)",
            "",
            "Doku-Fetch/Normalize/Chunk/Search Service (PoC).",
            "",
            "## Tools",
            "- `capabilities.get` — Kurzüberblick",
            "- `sources.create` — Source anlegen/ändern (github|crawl|local)",
            "- `sources.list` — Sources auflisten",
            "- `sources.delete` — Source löschen",
            "- `sync.start` / `sync.status` — Sync Job starten/Status",
            "- `sync.prepare` — Vorschläge/Optionen für Open WebUI Knowledge Target",
            "- `owui.knowledge.list` — Open WebUI Knowledge Bases anzeigen",
            "- `owui.knowledge.create` — Open WebUI Knowledge Base anlegen",
            "- `snapshots.list` — Snapshots anzeigen",
            "- `search` — Suche über Chunks",
            "- `get_chunk` / `get_doc` — Inhalte holen",
            "",
            "Hinweis:",
            "- Volltexte bleiben SSOT in SQLite/Files.",
            "- `search` ist lokale SQLite-FTS Suche (keine Vektor-DB).",
            "- Optional kann `sync.start` mit `knowledge_id` oder `knowledge_name` die Docs in Open WebUI Knowledge hochladen (Open WebUI übernimmt Processing/Embeddings).",
        ]
    )

def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    if max_chars <= 64:
        return text[:max_chars]
    return text[: max_chars - 32] + "\n\n...(truncated)"


TOOLS: list[ToolDef] = [
    ToolDef(
        name="capabilities.get",
        description="Get server capabilities (Markdown)",
        input_schema=_simple_schema(
            props={
                "max_chars": {
                    "type": "integer",
                    "description": "Max characters returned (0 = unlimited). Default: 2000",
                }
            }
        ),
    ),
    ToolDef(
        name="sources.create",
        description="Create/update a source (github|crawl|local)",
        input_schema=_simple_schema(
            props={
                "type": {"type": "string", "description": "github|crawl|local"},
                "name": {"type": "string"},
                "config": {
                    "type": "object",
                    "description": (
                        "Source config. Recommended canonical shapes:\n"
                        "- github: {\"github\": {\"repo\":\"owner/repo\",\"ref\":\"main\",\"include\":[\"**/*.md\"],\"exclude\":[]}}\n"
                        "- crawl:  {\"crawl\":  {\"start_urls\":[\"https://...\"],\"allow_domains\":[\"...\"],\"allow_path_prefixes\":[\"/...\"],\"render_js\":false,\"fetch_assets\":false}}\n"
                        "- local:  {\"local\":  {\"root\":\"/path\",\"include\":[\"**/*.md\"],\"exclude\":[]}}\n"
                        "Compat: for github also accepts {\"repo\":\"owner/repo\"} or {\"url\":\"https://github.com/owner/repo\"}."
                    ),
                },
                "limits": {"type": "object"},
            },
            required=["type", "name", "config"],
        ),
    ),
    ToolDef(name="sources.list", description="List sources", input_schema={"type": "object", "properties": {}}),
    ToolDef(
        name="sources.delete",
        description="Delete a source by source_id",
        input_schema={"type": "object", "properties": {"source_id": {"type": "string"}}, "required": ["source_id"]},
    ),
    ToolDef(
        name="sync.prepare",
        description="Prepare Open WebUI Knowledge selection (suggest name + list existing)",
        input_schema=_simple_schema(
            props={"source_id": {"type": "string"}},
            required=["source_id"],
        ),
    ),
    ToolDef(
        name="sync.start",
        description="Start a sync job for a source",
        input_schema=_simple_schema(
            props={
                "source_id": {"type": "string"},
                "mode": {"type": "string", "description": "full|incremental"},
                "knowledge_id": {"type": "string", "description": "Open WebUI Knowledge Collection id (optional)"},
                "knowledge_name": {"type": "string", "description": "Open WebUI Knowledge Collection name (optional)"},
                "create_knowledge_if_missing": {
                    "type": "boolean",
                    "description": "If knowledge_name doesn't exist, create it in Open WebUI",
                },
            },
            required=["source_id"],
        ),
    ),
    ToolDef(
        name="sync.status",
        description="Get sync job status",
        input_schema=_simple_schema(props={"job_id": {"type": "string"}}, required=["job_id"]),
    ),
    ToolDef(
        name="owui.knowledge.list",
        description="List Open WebUI Knowledge Bases",
        input_schema=_simple_schema(
            props={"query": {"type": "string"}, "limit": {"type": "integer"}},
        ),
    ),
    ToolDef(
        name="owui.knowledge.create",
        description="Create an Open WebUI Knowledge Base",
        input_schema=_simple_schema(
            props={"name": {"type": "string"}, "description": {"type": "string"}},
            required=["name"],
        ),
    ),
    ToolDef(
        name="snapshots.list",
        description="List snapshots for a source",
        input_schema=_simple_schema(props={"source_id": {"type": "string"}, "limit": {"type": "integer"}}, required=["source_id"]),
    ),
    ToolDef(
        name="search",
        description="Search over indexed chunks (SQLite FTS)",
        input_schema=_simple_schema(
            props={
                "query": {"type": "string"},
                "top_k": {"type": "integer"},
                "source_id": {"type": "string"},
                "snapshot_id": {"type": "string"},
            },
            required=["query"],
        ),
    ),
    ToolDef(
        name="get_chunk",
        description="Get a chunk by chunk_id",
        input_schema=_simple_schema(props={"chunk_id": {"type": "string"}}, required=["chunk_id"]),
    ),
    ToolDef(
        name="get_doc",
        description="Get a document by doc_id",
        input_schema=_simple_schema(props={"doc_id": {"type": "string"}}, required=["doc_id"]),
    ),
]


def handle_mcp_request(*, svc: Context6Service, payload: dict[str, Any]) -> dict[str, Any]:
    jsonrpc = payload.get("jsonrpc")
    if jsonrpc != "2.0":
        raise HTTPException(status_code=400, detail="invalid jsonrpc")
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
                    "serverInfo": {"name": "context6", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                }
            )

        if method == "tools/list":
            return ok(
                {
                    "tools": [
                        {"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in TOOLS
                    ]
                }
            )

        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}

            if name == "capabilities.get":
                max_chars_raw = (args or {}).get("max_chars")
                try:
                    max_chars = int(max_chars_raw) if max_chars_raw is not None else 2000
                except Exception:
                    max_chars = 2000
                return ok({"content": [{"type": "text", "text": _truncate_text(_capabilities_markdown(), max_chars)}]})
            if name == "sources.create":
                req = SourcesCreateRequest.model_validate(args)
                res = svc.create_source(req)
                return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            if name == "sources.list":
                res = {"sources": svc.list_sources()}
                return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            if name == "sources.delete":
                sid = str(args.get("source_id", "")).strip()
                if not sid:
                    raise ValueError("source_id required")
                res = svc.delete_source(sid)
                return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            if name == "sync.start":
                req = SyncStartRequest.model_validate(args)
                res = svc.start_sync(
                    source_id=req.source_id,
                    mode=req.mode,
                    knowledge_id=req.knowledge_id,
                    knowledge_name=req.knowledge_name,
                    create_knowledge_if_missing=req.create_knowledge_if_missing,
                )
                return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            if name == "sync.prepare":
                req = SyncPrepareRequest.model_validate(args)
                res = svc.sync_prepare(source_id=req.source_id)
                return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            if name == "sync.status":
                req = SyncStatusRequest.model_validate(args)
                res = svc.get_job(req.job_id)
                if not res:
                    return ok({"content": [{"type": "text", "text": json.dumps({"error": "job not found"})}]})
                return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            if name == "owui.knowledge.list":
                req = KnowledgeListRequest.model_validate(args)
                res = svc.owui_list_knowledge(query=req.query, limit=req.limit)
                return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            if name == "owui.knowledge.create":
                req = KnowledgeCreateRequest.model_validate(args)
                res = svc.owui_create_knowledge(name=req.name, description=req.description)
                return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            if name == "snapshots.list":
                req = SnapshotsListRequest.model_validate(args)
                res = {"snapshots": svc.list_snapshots(source_id=req.source_id, limit=req.limit)}
                return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            if name == "search":
                req = SearchRequest.model_validate(args)
                res = {"results": svc.search(query=req.query, top_k=req.top_k, source_id=req.source_id, snapshot_id=req.snapshot_id)}
                return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            if name == "get_chunk":
                req = GetChunkRequest.model_validate(args)
                res = svc.get_chunk(req.chunk_id)
                return ok({"content": [{"type": "text", "text": json.dumps(res or {"error": "not found"}, ensure_ascii=False)}]})
            if name == "get_doc":
                req = GetDocRequest.model_validate(args)
                res = svc.get_doc(req.doc_id)
                return ok({"content": [{"type": "text", "text": json.dumps(res or {"error": "not found"}, ensure_ascii=False)}]})

            return err(-32601, f"unknown tool: {name}")

        return err(-32601, f"unknown method: {method}")
    except ToolUserError as e:
        return err(-32000, "tool user error", {"message": str(e), "data": getattr(e, "data", {})})
    except Exception as e:
        return err(-32000, "tool execution error", {"message": str(e)})
