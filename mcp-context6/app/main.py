from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .db import init_db
from .mcp_rpc import handle_mcp_request
from .service import Context6Paths, Context6Service


def _make_app() -> FastAPI:
    data_dir = Path(os.getenv("CONTEXT6_DATA_DIR", "/data"))
    cache_dir = Path(os.getenv("CONTEXT6_CACHE_DIR", "/cache"))
    paths = Context6Paths(data_dir=data_dir, cache_dir=cache_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    db = init_db(str(paths.db_path))
    svc = Context6Service(db=db, paths=paths)

    app = FastAPI(title="context6", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"ok": True}

    @app.post("/mcp")
    async def mcp(payload: dict[str, Any]) -> JSONResponse:
        res = handle_mcp_request(svc=svc, payload=payload)
        return JSONResponse(res)

    return app


app = _make_app()

