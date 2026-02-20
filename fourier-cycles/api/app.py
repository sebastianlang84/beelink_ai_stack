#!/usr/bin/env python3
"""Internal API for controlled fourier-cycles batch triggering."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="fourier-cycles-api", version="0.1.0")

OUTPUT_DIR = Path(os.getenv("FOURIER_OUTPUT_DIR", "/data/output"))
LOG_DIR = OUTPUT_DIR / "_trigger_logs"
MAX_RUNTIME_SECONDS = int(os.getenv("FOURIER_TRIGGER_MAX_RUNTIME_SECONDS", "5400"))
PIPELINE_PATH = os.getenv("FOURIER_TRIGGER_PIPELINE_PATH", "/app/src/fourier_cycles_pipeline.py")
PYTHON_BIN = os.getenv("FOURIER_TRIGGER_PYTHON", "python")

_state_lock = threading.Lock()
_run_state: dict[str, Any] = {
    "run_id": None,
    "state": "idle",
    "started_at": None,
    "finished_at": None,
    "exit_code": None,
    "error": None,
    "log_path": None,
    "latest_output_path": None,
}


class RunStatus(BaseModel):
    run_id: str | None
    state: str
    started_at: str | None
    finished_at: str | None
    exit_code: int | None
    error: str | None
    log_path: str | None
    latest_output_path: str | None


class TriggerRequest(BaseModel):
    confirm: bool = Field(
        default=False,
        description="Must be true to explicitly confirm the run trigger.",
    )


def _snapshot_status() -> RunStatus:
    with _state_lock:
        return RunStatus(
            run_id=_run_state["run_id"],
            state=_run_state["state"],
            started_at=_run_state["started_at"],
            finished_at=_run_state["finished_at"],
            exit_code=_run_state["exit_code"],
            error=_run_state["error"],
            log_path=_run_state["log_path"],
            latest_output_path=_run_state["latest_output_path"],
        )


def _update_state(**changes: Any) -> None:
    with _state_lock:
        _run_state.update(changes)


def _running_state() -> bool:
    with _state_lock:
        return _run_state["state"] in {"starting", "running"}


def _resolve_latest_output() -> str | None:
    latest_link = OUTPUT_DIR / "latest"
    if not latest_link.exists():
        return None
    try:
        return str(latest_link.resolve())
    except OSError:
        return str(latest_link)


def _execute_pipeline(run_id: str, log_path: Path) -> None:
    _update_state(state="running")

    cmd = [PYTHON_BIN, PIPELINE_PATH]
    env = os.environ.copy()
    start_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            log_file.write(f"[{start_utc}] starting {' '.join(cmd)}\n")
            log_file.flush()

            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd="/app",
                env=env,
                text=True,
            )

            timed_out = False
            try:
                exit_code = proc.wait(timeout=MAX_RUNTIME_SECONDS)
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                exit_code = proc.wait(timeout=30)
                log_file.write(f"\n[{dt.datetime.now(dt.timezone.utc).isoformat()}] timed out after {MAX_RUNTIME_SECONDS}s\n")
                log_file.flush()

            if timed_out:
                _update_state(
                    state="failed",
                    finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    exit_code=exit_code,
                    error=f"run exceeded max runtime ({MAX_RUNTIME_SECONDS}s)",
                    log_path=str(log_path),
                    latest_output_path=_resolve_latest_output(),
                )
                return

            if exit_code == 0:
                _update_state(
                    state="succeeded",
                    finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    exit_code=exit_code,
                    error=None,
                    log_path=str(log_path),
                    latest_output_path=_resolve_latest_output(),
                )
                return

            _update_state(
                state="failed",
                finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                exit_code=exit_code,
                error=f"pipeline exited with code {exit_code}",
                log_path=str(log_path),
                latest_output_path=_resolve_latest_output(),
            )
    except Exception as exc:  # noqa: BLE001
        _update_state(
            state="failed",
            finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            exit_code=-1,
            error=f"trigger exception: {exc}",
            log_path=str(log_path),
            latest_output_path=_resolve_latest_output(),
        )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/run/status", response_model=RunStatus)
def run_status() -> RunStatus:
    return _snapshot_status()


@app.post("/api/run", response_model=RunStatus)
def trigger_run(request: TriggerRequest) -> RunStatus:
    if not request.confirm:
        raise HTTPException(status_code=400, detail="set confirm=true to trigger a run")

    if _running_state():
        raise HTTPException(status_code=409, detail="run already in progress")

    run_id = dt.datetime.now(dt.timezone.utc).strftime("run_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    start_ts = dt.datetime.now(dt.timezone.utc).isoformat()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{run_id}.log"

    _update_state(
        run_id=run_id,
        state="starting",
        started_at=start_ts,
        finished_at=None,
        exit_code=None,
        error=None,
        log_path=str(log_path),
        latest_output_path=_resolve_latest_output(),
    )

    worker = threading.Thread(target=_execute_pipeline, args=(run_id, log_path), daemon=True)
    worker.start()
    return _snapshot_status()
