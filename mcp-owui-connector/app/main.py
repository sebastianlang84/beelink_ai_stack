from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .mcp_rpc import TOOLS, handle_mcp_request
from .service import OwuiConnectorService


def _make_app() -> FastAPI:
    svc = OwuiConnectorService.from_env()
    app = FastAPI(title="owui-connector", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"ok": True}

    @app.post("/mcp")
    async def mcp(payload: dict[str, Any]) -> JSONResponse:
        res = handle_mcp_request(payload=payload, tools=TOOLS, call_tool=svc.call_tool)
        return JSONResponse(res)

    return app


app = _make_app()
