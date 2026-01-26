import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import uuid
from typing import Any
from xml.etree.ElementTree import ParseError

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi import Query
from pydantic import BaseModel, Field
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


def _split_languages(value: str) -> list[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


DEFAULT_LANGUAGES = _split_languages(os.getenv("TRANSCRIPT_MINER_DEFAULT_LANGUAGES", "de,en"))
FETCH_RETRIES = int(os.getenv("TRANSCRIPT_MINER_FETCH_RETRIES", "2"))
FETCH_RETRY_BACKOFF_SECONDS = float(os.getenv("TRANSCRIPT_MINER_FETCH_RETRY_BACKOFF_SECONDS", "0.5"))
CONFIG_DIR = os.getenv("TRANSCRIPT_MINER_CONFIG_DIR", "/transcript_miner_config")
OUTPUT_DIR = os.getenv("TRANSCRIPT_MINER_OUTPUT_DIR", "/transcript_miner_output")
CONFIG_BACKUP_DIR = os.getenv(
    "TRANSCRIPT_MINER_CONFIG_BACKUP_DIR",
    "/data/config_backups",
)
RUNS_DIR = os.getenv("TRANSCRIPT_MINER_RUNS_DIR", "/data/runs")
KNOWLEDGE_MAP_JSON_PATH = os.getenv("OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON_PATH", "").strip()
KNOWLEDGE_MAP_JSON = os.getenv("OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON", "").strip()
if not KNOWLEDGE_MAP_JSON and KNOWLEDGE_MAP_JSON_PATH:
    try:
        candidate = Path(KNOWLEDGE_MAP_JSON_PATH).read_text(encoding="utf-8").strip()
        if candidate:
            json.loads(candidate)
            KNOWLEDGE_MAP_JSON = candidate
    except (OSError, json.JSONDecodeError):
        KNOWLEDGE_MAP_JSON = ""
OPEN_WEBUI_BASE_URL = os.getenv("OPEN_WEBUI_BASE_URL", "http://owui:8080").rstrip("/")
OPEN_WEBUI_API_KEY = (os.getenv("OPEN_WEBUI_API_KEY", "") or os.getenv("OWUI_API_KEY", "")).strip()
DEFAULT_KNOWLEDGE_ID = os.getenv("OPEN_WEBUI_KNOWLEDGE_ID", "").strip()
POLL_INTERVAL = int(os.getenv("OPEN_WEBUI_PROCESS_POLL_INTERVAL_SECONDS", "3"))
PROCESS_TIMEOUT = int(os.getenv("OPEN_WEBUI_PROCESS_TIMEOUT_SECONDS", "900"))
INDEXER_DB_PATH = os.getenv("INDEXER_DB_PATH", "/data/indexer.sqlite3")

CAPABILITIES_MARKDOWN = """\
## Transcript Miner — Capabilities

This tool server provides:

### A) Fetch fresh YouTube transcripts (ad-hoc)
- `POST /transcript`
  - Input: `video_id`, optional `preferred_languages`, `include_timestamps`, `max_chars`
  - Output: `{ status, text, meta }`

### B) Read and update TranscriptMiner configs (YAML)
Configs:
- `GET /configs` — list available YAML configs
- `GET /configs/{config_id}` — read a YAML config
- `POST /configs/{config_id}` — validate and optionally write a YAML config (creates a backup)
  - Recommended workflow:
    1) `GET /configs/{config_id}` to read current config
    2) propose changes
    3) `POST /configs/{config_id}` with `validate_only=true` to preview diff
    4) `POST /configs/{config_id}` with `validate_only=false` to write

Run + sync:
- `POST /runs/start` — starts TranscriptMiner for a given config (async) and returns `run_id`
- `GET /runs/{run_id}` — returns status + log tail
- `POST /sync/topic/{topic}` — indexes summaries for a topic into Open WebUI Knowledge (same service)

Outputs (global layout; requires output root mounted):
- `GET /outputs/topics` — list available topics (based on `output/data/indexes/<topic>/current/manifest.json`)
- `GET /outputs/topics/{topic}/videos` — list ingested videos (from `transcripts.jsonl`, paged via `limit`/`offset`)
- `GET /outputs/videos/{video_id}/transcript` — read `output/data/transcripts/by_video_id/<video_id>.txt`
- `GET /outputs/videos/{video_id}/summary` — read `output/data/summaries/by_video_id/<video_id>.summary.md`

Indexing (Knowledge Collections):
- `POST /index/transcript` — upload Markdown, wait for processing, add to Knowledge Collection (idempotent via `source_id`)

Notes:
- If a tool call fails, reduce output size using `max_chars` and retry.
- If tools are not enabled in the current chat, the model cannot call them.
- `POST /runs/start` requires `YOUTUBE_API_KEY` and (if LLM analysis enabled) `OPENROUTER_API_KEY` in the tool container environment.
  - Example: start a run: `POST /runs/start` with `{"config_id":"config_investing.yaml"}`
  - Then poll: `GET /runs/{run_id}`
  - Then index: `POST /sync/topic/investing` (Knowledge-Name = Topic; optional mapping via `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON`)
"""

app = FastAPI(
    title="Transcript Miner",
    version="1.0.0",
    description="One unified tool server: transcript fetch + config management + run trigger + Open WebUI Knowledge indexing.",
)

RUN_PROCS: dict[str, subprocess.Popen] = {}


class TranscriptRequest(BaseModel):
    video_id: str = Field(min_length=3)
    preferred_languages: list[str] | None = None
    include_timestamps: bool = False
    max_chars: int = Field(
        default=20_000,
        ge=0,
        le=200_000,
        description="Safety limit for returned transcript text. Use 0 for unlimited.",
    )


class ConfigInfo(BaseModel):
    config_id: str
    filename: str
    bytes: int
    updated_at: int
    display_name: str
    aliases: list[str]


class ConfigListResponse(BaseModel):
    status: str
    config_dir: str
    configs: list[ConfigInfo]


class ConfigGetResponse(BaseModel):
    status: str
    config_id: str
    filename: str
    text: str


class ConfigGetRequest(BaseModel):
    config_id: str = Field(min_length=1)


class TopicListResponse(BaseModel):
    status: str
    output_dir: str
    topics: list[str]


class TopicVideosResponse(BaseModel):
    status: str
    topic: str
    count: int
    items: list[dict[str, Any]]


class OutputTextResponse(BaseModel):
    status: str
    video_id: str
    path: str
    truncated: bool
    text: str
    meta: dict[str, Any] | None = None


class CapabilitiesResponse(BaseModel):
    status: str
    markdown: str


class ConfigWriteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000, description="Full YAML content to write.")
    validate_only: bool = Field(
        default=False,
        description="If true, only validate YAML and return a diff preview; do not write.",
    )
    create_backup: bool = Field(
        default=True,
        description="If true, store a timestamped backup before writing.",
    )
    max_diff_lines: int = Field(
        default=200,
        ge=0,
        le=2000,
        description="Maximum diff lines to return in the response (0 disables diff).",
    )


class ConfigWriteResponse(BaseModel):
    status: str
    config_id: str
    filename: str
    yaml_valid: bool
    yaml_error: str | None = None
    wrote: bool
    bytes_before: int | None = None
    bytes_after: int | None = None
    backup_path: str | None = None
    diff: str | None = None


class ConfigWriteMcpRequest(ConfigWriteRequest):
    config_id: str = Field(min_length=1)


class RunStartRequest(BaseModel):
    config_id: str = Field(min_length=1, description="Config filename from /configs (e.g. config_investing.yaml).")
    skip_index: bool = False
    skip_llm: bool = False
    skip_report: bool = False
    only: list[str] | None = Field(default=None, description="Optional: only run steps: mine|index|llm|report.")
    report_lang: str | None = Field(default=None, description="Optional: de|en|both")


class RunStartResponse(BaseModel):
    status: str
    run_id: str
    topic: str | None = None
    command: list[str]
    log_path: str
    summary: str | None = None


class RunStatusResponse(BaseModel):
    status: str
    run_id: str
    state: str
    pid: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    config_id: str | None = None
    topic: str | None = None
    log_tail: str | None = None
    error: str | None = None
    summary: str | None = None


class RunStatusMcpRequest(BaseModel):
    run_id: str = Field(min_length=1)


class SyncTopicRequest(BaseModel):
    max_videos: int = Field(default=0, ge=0, le=5000, description="0 = no limit.")
    dry_run: bool = False


class SyncTopicResponse(BaseModel):
    status: str
    topic: str
    knowledge_id: str | None = None
    processed: int = 0
    indexed: int = 0
    skipped: int = 0
    errors: int = 0
    last_error: str | None = None


class SyncTopicMcpRequest(SyncTopicRequest):
    topic: str = Field(min_length=1)


class IndexTranscriptRequest(BaseModel):
    source_id: str = Field(min_length=1, description="Stable idempotency key (e.g. youtube:<video_id>)")
    text: str = Field(min_length=1, description="Markdown content to index")
    title: str | None = None
    url: str | None = None
    channel: str | None = None
    published_at: str | None = None
    fetched_at: str | None = None
    language: str | None = None
    knowledge_id: str | None = None


from .mcp_rpc import handle_mcp_request, make_tools  # noqa: E402


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    mm = total // 60
    ss = total % 60
    return f"{mm:02d}:{ss:02d}"


def _render_text(items: list[dict[str, Any]], include_timestamps: bool) -> str:
    lines: list[str] = []
    for item in items:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        if include_timestamps:
            ts = _format_timestamp(float(item.get("start", 0.0)))
            lines.append(f"[{ts}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines).strip()


def _safe_config_id(value: str) -> str:
    value = (value or "").strip()
    if not value or "/" in value or "\\" in value or value.startswith("."):
        raise ValueError("invalid config_id")
    return value


def _resolve_config_path(config_id: str) -> str:
    cid = _safe_config_id(config_id)
    if not (cid.endswith(".yml") or cid.endswith(".yaml")):
        cid = f"{cid}.yml"
    candidate = os.path.abspath(os.path.join(CONFIG_DIR, cid))
    base = os.path.abspath(CONFIG_DIR) + os.sep
    if not candidate.startswith(base):
        raise ValueError("invalid config_id")
    return candidate


def _safe_id(value: str, *, label: str) -> str:
    value = (value or "").strip()
    if not value or "/" in value or "\\" in value or value.startswith("."):
        raise ValueError(f"invalid {label}")
    if len(value) > 200:
        raise ValueError(f"invalid {label}")
    return value


def _list_configs() -> list[ConfigInfo]:
    out: list[ConfigInfo] = []
    try:
        entries = os.listdir(CONFIG_DIR)
    except FileNotFoundError:
        return []
    for name in sorted(entries):
        if not (name.endswith(".yml") or name.endswith(".yaml")):
            continue
        path = os.path.join(CONFIG_DIR, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        config_id = name
        base = name.rsplit(".", 1)[0]
        display = base
        if display.startswith("config_"):
            display = display[len("config_") :]
        aliases = {display, display.replace("_", "-"), base, config_id}
        out.append(
            ConfigInfo(
                config_id=config_id,
                filename=name,
                bytes=int(st.st_size),
                updated_at=int(st.st_mtime),
                display_name=display,
                aliases=sorted(a for a in aliases if a),
            )
        )
    return out


def _read_config_text(config_id: str) -> tuple[str, str]:
    path = _resolve_config_path(config_id)
    cid = os.path.basename(path)
    with open(path, "r", encoding="utf-8") as fh:
        return cid, fh.read()


def _indexes_root() -> str:
    return os.path.join(OUTPUT_DIR, "data", "indexes")


def _list_topics() -> list[str]:
    root = _indexes_root()
    try:
        entries = os.listdir(root)
    except FileNotFoundError:
        return []
    topics: list[str] = []
    for name in sorted(entries):
        if not name or name.startswith("."):
            continue
        path = os.path.join(root, name, "current", "manifest.json")
        if os.path.isfile(path):
            topics.append(name)
    return topics


def _read_jsonl(path: str, *, limit: int, offset: int) -> tuple[int, list[dict[str, Any]]]:
    total = 0
    items: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if total >= offset and len(items) < limit:
                items.append(obj)
            total += 1
    return total, items


def _load_knowledge_map() -> dict[str, str]:
    if not KNOWLEDGE_MAP_JSON:
        return {}
    try:
        data = json.loads(KNOWLEDGE_MAP_JSON)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip():
            out[k.strip()] = v.strip()
    return out


def _list_knowledge() -> list[dict[str, Any]]:
    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/knowledge/"
    resp = requests.get(url, headers=_auth_headers(), timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"knowledge list failed: {resp.status_code} {resp.text}")
    data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return list(data["items"])
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return list(data["data"])
    if isinstance(data, dict) and isinstance(data.get("knowledge"), list):
        return list(data["knowledge"])
    return []


def _find_knowledge_by_name(name: str) -> dict[str, Any] | None:
    name_norm = (name or "").strip().casefold()
    if not name_norm:
        return None
    for kb in _list_knowledge():
        kb_name = str(kb.get("name") or "").strip().casefold()
        if kb_name == name_norm:
            return kb
    return None


def _resolve_knowledge_id_for_topic(topic: str) -> str | None:
    knowledge_map = _load_knowledge_map()
    mapped = knowledge_map.get(topic)
    if mapped:
        return mapped
    kb = _find_knowledge_by_name(topic)
    if not kb:
        return None
    kid = str(kb.get("id") or "").strip()
    return kid or None


def _db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(INDEXER_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(INDEXER_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS uploads (
          source_id TEXT PRIMARY KEY,
          sha256 TEXT NOT NULL,
          file_id TEXT NOT NULL,
          knowledge_id TEXT NOT NULL,
          created_at INTEGER NOT NULL
        )
        """
    )
    return conn


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _auth_headers() -> dict[str, str]:
    if not OPEN_WEBUI_API_KEY:
        raise RuntimeError("OPEN_WEBUI_API_KEY/OWUI_API_KEY is not set")
    return {"Authorization": f"Bearer {OPEN_WEBUI_API_KEY}", "Accept": "application/json"}


def _render_markdown(req: IndexTranscriptRequest) -> str:
    meta: dict[str, Any] = {
        "source_id": req.source_id,
        "title": req.title,
        "url": req.url,
        "channel": req.channel,
        "published_at": req.published_at,
        "fetched_at": req.fetched_at,
        "language": req.language,
    }
    meta_clean = {k: v for k, v in meta.items() if v}

    def yaml_value(v: Any) -> str:
        if v is None:
            return "null"
        if isinstance(v, (int, float)):
            return str(v)
        return json.dumps(str(v), ensure_ascii=False)

    frontmatter = "\n".join([f"{k}: {yaml_value(v)}" for k, v in meta_clean.items()])
    if frontmatter:
        return f"---\n{frontmatter}\n---\n\n{req.text.strip()}\n"
    return f"{req.text.strip()}\n"


def _upload_file(markdown: str, filename: str) -> str:
    import tempfile

    import requests

    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/files/"
    params = {"process": "true", "process_in_background": "true"}
    headers = _auth_headers()
    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=True) as tmp:
        tmp.write(markdown)
        tmp.flush()
        with open(tmp.name, "rb") as fh:
            resp = requests.post(
                url,
                params=params,
                headers=headers,
                files={"file": (filename, fh, "text/markdown")},
                timeout=60,
            )
    if resp.status_code >= 400:
        raise RuntimeError(f"upload failed: {resp.status_code} {resp.text}")
    data = resp.json()
    file_id = data.get("id") or data.get("file_id")
    if not file_id:
        raise RuntimeError(f"upload response missing id: {data}")
    return str(file_id)


def _poll_processing(file_id: str) -> dict[str, Any]:
    import requests

    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/files/{file_id}/process/status"
    headers = _auth_headers()
    deadline = time.time() + PROCESS_TIMEOUT
    last: dict[str, Any] = {}
    while time.time() < deadline:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code >= 400:
            raise RuntimeError(f"process status failed: {resp.status_code} {resp.text}")
        last = resp.json()
        status = (last.get("status") or "").lower()
        if status in {"completed", "failed"}:
            return last
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"process status timeout: {last}")


def _add_to_knowledge(knowledge_id: str, file_id: str) -> dict[str, Any]:
    import requests

    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/knowledge/{knowledge_id}/file/add"
    headers = _auth_headers() | {"Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={"file_id": file_id}, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"knowledge add failed: {resp.status_code} {resp.text}")
    return resp.json() if resp.content else {"status": "ok"}


def _index_markdown(req: IndexTranscriptRequest) -> dict[str, Any]:
    knowledge_id = (req.knowledge_id or DEFAULT_KNOWLEDGE_ID or "").strip()
    if not knowledge_id:
        return {"status": "error", "error": "knowledge_id is required (or set OPEN_WEBUI_KNOWLEDGE_ID)"}

    sha = _sha256(req.text)
    conn = _db()
    try:
        row = conn.execute(
            "SELECT sha256, file_id, knowledge_id FROM uploads WHERE source_id = ?",
            (req.source_id,),
        ).fetchone()
        if row and row[0] == sha and row[2] == knowledge_id:
            return {"status": "skipped", "reason": "same_sha256", "source_id": req.source_id, "file_id": row[1], "knowledge_id": row[2]}

        filename = f"{req.source_id.replace(':', '_')}.md"
        markdown = _render_markdown(req)
        file_id = _upload_file(markdown, filename=filename)

        process_status = _poll_processing(file_id)
        if (process_status.get("status") or "").lower() == "failed":
            return {"status": "failed", "step": "process", "file_id": file_id, "process": process_status}

        add_result = _add_to_knowledge(knowledge_id=knowledge_id, file_id=file_id)

        conn.execute(
            "INSERT OR REPLACE INTO uploads (source_id, sha256, file_id, knowledge_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (req.source_id, sha, file_id, knowledge_id, int(time.time())),
        )
        conn.commit()
        return {
            "status": "indexed",
            "source_id": req.source_id,
            "file_id": file_id,
            "knowledge_id": knowledge_id,
            "process": process_status,
            "knowledge_add": add_result,
        }
    finally:
        conn.close()


def _strip_frontmatter(markdown: str) -> str:
    text = markdown.lstrip()
    if not text.startswith("---"):
        return markdown
    lines = markdown.splitlines(keepends=True)
    if not lines:
        return markdown
    if not lines[0].strip() == "---":
        return markdown
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return markdown
    return "".join(lines[end + 1 :]).lstrip()


def _read_text_file(path: str, *, max_chars: int) -> tuple[bool, str]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if max_chars and len(text) > max_chars:
        return True, text[:max_chars].rstrip() + "\n\n[...truncated...]\n"
    return False, text


def _validate_yaml(text: str) -> tuple[bool, str | None]:
    try:
        import yaml  # type: ignore
    except Exception:
        # If PyYAML isn't available (should be installed), do not block edits.
        return True, None
    try:
        yaml.safe_load(text)
        return True, None
    except Exception as e:
        msg = str(e)
        if len(msg) > 500:
            msg = msg[:500] + "…"
        return False, msg


def _unified_diff(old: str, new: str, *, filename: str, max_lines: int) -> str | None:
    if max_lines <= 0:
        return None
    import difflib

    lines = list(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"{filename} (before)",
            tofile=f"{filename} (after)",
        )
    )
    if not lines:
        return ""
    if len(lines) > max_lines:
        truncated = lines[:max_lines] + ["\n...diff truncated...\n"]
        return "".join(truncated)
    return "".join(lines)


def _atomic_write(path: str, text: str) -> None:
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _write_config(config_id: str, text: str, *, create_backup: bool) -> tuple[str, int | None, int, str | None]:
    path = _resolve_config_path(config_id)
    filename = os.path.basename(path)
    bytes_before: int | None = None
    if os.path.isfile(path):
        try:
            bytes_before = int(os.stat(path).st_size)
        except OSError:
            bytes_before = None

    backup_path: str | None = None
    if create_backup and os.path.isfile(path):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
        os.makedirs(CONFIG_BACKUP_DIR, exist_ok=True)
        backup_path = os.path.join(CONFIG_BACKUP_DIR, f"{filename}.{ts}.bak")
        with open(path, "rb") as src, open(backup_path, "wb") as dst:
            dst.write(src.read())

    _atomic_write(path, text)
    bytes_after = int(os.stat(path).st_size)
    return filename, bytes_before, bytes_after, backup_path


def _run_meta_path(run_id: str) -> str:
    return os.path.join(RUNS_DIR, f"{run_id}.json")


def _run_log_path(run_id: str) -> str:
    return os.path.join(RUNS_DIR, f"{run_id}.log")


def _write_run_meta(run_id: str, meta: dict[str, Any]) -> None:
    os.makedirs(RUNS_DIR, exist_ok=True)
    path = _run_meta_path(run_id)
    _atomic_write(path, json.dumps(meta, ensure_ascii=False, indent=2) + "\n")


def _read_run_meta(run_id: str) -> dict[str, Any] | None:
    path = _run_meta_path(run_id)
    if not os.path.isfile(path):
        return None
    try:
        return json.loads(open(path, "r", encoding="utf-8").read())
    except Exception:
        return None


def _tail_file(path: str, *, max_bytes: int = 50_000) -> str:
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        start = max(0, size - max_bytes)
        fh.seek(start)
        data = fh.read()
    return data.decode("utf-8", errors="replace")


def _proc_state(pid: int) -> str | None:
    try:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("State:"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        return None
    return None


def _reap_if_zombie(pid: int) -> int | None:
    state = _proc_state(pid) or ""
    if not state.startswith("Z"):
        return None
    try:
        waited_pid, status = os.waitpid(pid, os.WNOHANG)
    except Exception:
        return None
    if waited_pid != pid:
        return None
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return None


def _rewrite_config_for_container(config_text: str) -> tuple[str, str | None]:
    try:
        import yaml  # type: ignore
    except Exception:
        return config_text, None

    obj = yaml.safe_load(config_text) or {}
    if not isinstance(obj, dict):
        return config_text, None

    output_cfg = obj.get("output")
    if isinstance(output_cfg, dict):
        topic = output_cfg.get("topic")
        topic_str = str(topic).strip() if topic is not None else None
        output_cfg["global"] = OUTPUT_DIR
    else:
        topic_str = None

    logging_cfg = obj.get("logging")
    if isinstance(logging_cfg, dict):
        logs_dir = os.path.join(OUTPUT_DIR, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        base = topic_str or "transcript-miner"
        logging_cfg["file"] = os.path.join(logs_dir, f"{base}.log")
        logging_cfg["error_log_file"] = os.path.join(logs_dir, f"{base}-error.log")

    rewritten = yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)
    return rewritten, topic_str


def _fetch_with_retries(transcript_obj: Any, retries: int) -> list[dict[str, Any]]:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return transcript_obj.fetch()
        except ParseError as e:
            last_exc = e
        except CouldNotRetrieveTranscript as e:
            last_exc = e
        except Exception as e:
            last_exc = e
        if attempt < retries:
            time.sleep(FETCH_RETRY_BACKOFF_SECONDS * (2**attempt))
    assert last_exc is not None
    raise last_exc


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


_MCP_MODELS = {
    "TranscriptRequest": TranscriptRequest,
    "ConfigGetRequest": ConfigGetRequest,
    "ConfigWriteMcpRequest": ConfigWriteMcpRequest,
    "RunStartRequest": RunStartRequest,
    "RunStatusMcpRequest": RunStatusMcpRequest,
    "SyncTopicMcpRequest": SyncTopicMcpRequest,
    "IndexTranscriptRequest": IndexTranscriptRequest,
}
_MCP_TOOLS = make_tools(models=_MCP_MODELS)

def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0:
        return text, False
    if len(text) <= max_chars:
        return text, False
    if max_chars <= 64:
        return text[:max_chars], True
    return text[: max_chars - 32] + "\n\n...(truncated)", True


def _capabilities_markdown_short() -> str:
    lines: list[str] = [
        "## Transcript Miner (MCP)",
        "",
        "Tools:",
    ]
    for t in _MCP_TOOLS:
        lines.append(f"- `{t.name}` — {t.description}")
    lines += [
        "",
        "Tip: call `capabilities.get` with `{ \"detail\": \"full\" }` for a longer overview.",
    ]
    return "\n".join(lines)


def _mcp_call_tool(name: str, args: dict[str, Any]) -> Any:
    if name == "capabilities.get":
        detail = str((args or {}).get("detail") or "short").strip().lower()
        max_chars_raw = (args or {}).get("max_chars")
        try:
            max_chars = int(max_chars_raw) if max_chars_raw is not None else 6000
        except Exception:
            max_chars = 6000

        text = CAPABILITIES_MARKDOWN if detail in {"full", "long", "detailed"} else _capabilities_markdown_short()
        text, _ = _truncate_text(text, max_chars)
        return text
    if name == "configs.list":
        return list_configs().model_dump()
    if name == "configs.get":
        req = ConfigGetRequest.model_validate(args)
        return get_config(req.config_id).model_dump()
    if name == "configs.write":
        req = ConfigWriteMcpRequest.model_validate(args)
        return write_config(req.config_id, req).model_dump()
    if name == "runs.start":
        req = RunStartRequest.model_validate(args)
        return start_run(req).model_dump()
    if name == "runs.status":
        req = RunStatusMcpRequest.model_validate(args)
        return get_run(req.run_id).model_dump()
    if name == "sync.topic":
        req = SyncTopicMcpRequest.model_validate(args)
        return sync_topic(req.topic, req).model_dump()
    if name == "index.transcript":
        req = IndexTranscriptRequest.model_validate(args)
        return index_transcript(req)
    if name == "transcript.fetch":
        req = TranscriptRequest.model_validate(args)
        return transcript(req)
    raise ValueError(f"Unknown tool: {name}")


@app.post("/mcp", include_in_schema=False)
async def mcp(payload: dict[str, Any]) -> JSONResponse:
    res = handle_mcp_request(payload=payload, tools=_MCP_TOOLS, call_tool=_mcp_call_tool)
    return JSONResponse(res)

@app.get("/capabilities", summary="Describe tool capabilities", operation_id="capabilities")
def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(status="success", markdown=CAPABILITIES_MARKDOWN)

@app.get("/configs", operation_id="configs_list")
def list_configs() -> ConfigListResponse:
    return ConfigListResponse(status="success", config_dir=CONFIG_DIR, configs=_list_configs())


@app.get("/configs/{config_id}", operation_id="configs_get")
def get_config(config_id: str) -> ConfigGetResponse:
    try:
        filename, text = _read_config_text(config_id)
    except FileNotFoundError:
        return ConfigGetResponse(status="not_found", config_id=config_id, filename="", text="")
    except ValueError:
        return ConfigGetResponse(status="error", config_id=config_id, filename="", text="invalid config_id")
    return ConfigGetResponse(status="success", config_id=config_id, filename=filename, text=text)


@app.post("/configs/{config_id}", summary="Validate and optionally write a config", operation_id="configs_write")
def write_config(config_id: str, req: ConfigWriteRequest) -> ConfigWriteResponse:
    try:
        filename, current_text = _read_config_text(config_id)
    except FileNotFoundError:
        filename = ""
        current_text = ""
    except ValueError:
        return ConfigWriteResponse(
            status="error",
            config_id=config_id,
            filename="",
            yaml_valid=False,
            yaml_error="invalid config_id",
            wrote=False,
        )

    yaml_valid, yaml_error = _validate_yaml(req.text)
    diff = _unified_diff(current_text, req.text, filename=(filename or config_id), max_lines=req.max_diff_lines)
    if not yaml_valid:
        return ConfigWriteResponse(
            status="error",
            config_id=config_id,
            filename=filename or config_id,
            yaml_valid=False,
            yaml_error=yaml_error,
            wrote=False,
            diff=diff,
        )

    if req.validate_only:
        return ConfigWriteResponse(
            status="validated",
            config_id=config_id,
            filename=filename or config_id,
            yaml_valid=True,
            yaml_error=None,
            wrote=False,
            diff=diff,
        )

    try:
        filename_written, bytes_before, bytes_after, backup_path = _write_config(
            config_id, req.text, create_backup=req.create_backup
        )
    except Exception as e:
        msg = str(e)
        if len(msg) > 500:
            msg = msg[:500] + "…"
        return ConfigWriteResponse(
            status="error",
            config_id=config_id,
            filename=filename or config_id,
            yaml_valid=True,
            yaml_error=msg,
            wrote=False,
            diff=diff,
        )

    return ConfigWriteResponse(
        status="success",
        config_id=config_id,
        filename=filename_written,
        yaml_valid=True,
        yaml_error=None,
        wrote=True,
        bytes_before=bytes_before,
        bytes_after=bytes_after,
        backup_path=backup_path,
        diff=diff,
    )


@app.post("/runs/start", summary="Start TranscriptMiner run (async)", operation_id="runs_start")
def start_run(req: RunStartRequest) -> RunStartResponse:
    try:
        config_filename, config_text = _read_config_text(req.config_id)
    except Exception:
        config_filename = req.config_id
        config_text = ""
        try:
            config_filename, config_text = _read_config_text(f"{req.config_id}.yaml")
        except Exception:
            pass

    rewritten, topic = _rewrite_config_for_container(config_text or "")
    run_id = uuid.uuid4().hex
    tmp_cfg = f"/tmp/{run_id}.yaml"
    _atomic_write(tmp_cfg, rewritten)

    cmd: list[str] = ["python", "-m", "transcript_miner", "--config", tmp_cfg]
    if req.only:
        for item in req.only:
            cmd.extend(["--only", str(item)])
    else:
        if req.skip_index:
            cmd.append("--skip-index")
        if req.skip_llm:
            cmd.append("--skip-llm")
        if req.skip_report:
            cmd.append("--skip-report")
    if req.report_lang:
        cmd.extend(["--report-lang", req.report_lang])

    os.makedirs(RUNS_DIR, exist_ok=True)
    log_path = _run_log_path(run_id)
    log_fh = open(log_path, "ab", buffering=0)
    proc = subprocess.Popen(
        cmd,
        cwd="/",
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
    )
    RUN_PROCS[run_id] = proc
    meta = {
        "run_id": run_id,
        "state": "running",
        "pid": proc.pid,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "exit_code": None,
        "config_id": config_filename,
        "topic": topic,
        "command": cmd,
        "log_path": log_path,
        "tmp_config_path": tmp_cfg,
    }
    _write_run_meta(run_id, meta)
    summary = f"Run gestartet. ID: {run_id}. Config: {config_filename}."
    return RunStartResponse(
        status="started",
        run_id=run_id,
        topic=topic,
        command=cmd,
        log_path=log_path,
        summary=summary,
    )


@app.get("/runs/{run_id}", summary="Get run status + log tail", operation_id="runs_get")
def get_run(run_id: str) -> RunStatusResponse:
    meta = _read_run_meta(run_id)
    if not meta:
        return RunStatusResponse(status="not_found", run_id=run_id, state="not_found")

    pid = meta.get("pid")
    state = meta.get("state") or "unknown"
    exit_code = meta.get("exit_code")
    finished_at = meta.get("finished_at")

    if isinstance(pid, int) and state == "running":
        proc = RUN_PROCS.get(run_id)
        if proc is not None:
            polled = proc.poll()
            if polled is not None:
                try:
                    proc.wait(timeout=0)
                except Exception:
                    pass
                RUN_PROCS.pop(run_id, None)
                meta["exit_code"] = int(polled)
                meta["finished_at"] = meta.get("finished_at") or datetime.now(timezone.utc).isoformat()
                meta["state"] = "finished"
        else:
            reaped = _reap_if_zombie(pid)
            if reaped is not None:
                meta["exit_code"] = int(reaped)
                meta["finished_at"] = meta.get("finished_at") or datetime.now(timezone.utc).isoformat()
                meta["state"] = "finished"
            else:
                alive = True
                try:
                    os.kill(pid, 0)
                except Exception:
                    alive = False
                if not alive:
                    meta["finished_at"] = meta.get("finished_at") or datetime.now(timezone.utc).isoformat()
                    meta["state"] = "finished"

        if meta.get("state") == "finished":
            _write_run_meta(run_id, meta)
            state = meta["state"]
            finished_at = meta.get("finished_at")
            exit_code = meta.get("exit_code")

    log_tail = _tail_file(_run_log_path(run_id))
    summary = None
    if state == "finished":
        summary = f"Run beendet. ID: {run_id}. Exit-Code: {exit_code}."
    elif state == "running":
        summary = f"Run läuft. ID: {run_id}."
    elif state == "queued":
        summary = f"Run queued. ID: {run_id}."
    return RunStatusResponse(
        status="success",
        run_id=run_id,
        state=str(state),
        pid=pid if isinstance(pid, int) else None,
        started_at=meta.get("started_at"),
        finished_at=finished_at,
        exit_code=exit_code if isinstance(exit_code, int) else None,
        config_id=meta.get("config_id"),
        topic=meta.get("topic"),
        log_tail=log_tail,
        error=meta.get("error"),
        summary=summary,
    )


@app.post("/sync/topic/{topic}", summary="Index summaries for a topic into Open WebUI Knowledge", operation_id="sync_topic")
def sync_topic(topic: str, req: SyncTopicRequest) -> SyncTopicResponse:
    try:
        safe_topic = _safe_id(topic, label="topic")
    except ValueError:
        return SyncTopicResponse(status="error", topic=topic, last_error="invalid topic")

    try:
        knowledge_id = _resolve_knowledge_id_for_topic(safe_topic)
    except Exception as exc:
        return SyncTopicResponse(status="error", topic=safe_topic, last_error=str(exc))
    if not knowledge_id:
        return SyncTopicResponse(
            status="error",
            topic=safe_topic,
            last_error="knowledge not found (expected Knowledge name = topic, or set OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON)",
        )

    index_dir = os.path.join(_indexes_root(), safe_topic, "current")
    transcripts_jsonl = os.path.join(index_dir, "transcripts.jsonl")
    if not os.path.isfile(transcripts_jsonl):
        return SyncTopicResponse(status="not_found", topic=safe_topic, knowledge_id=knowledge_id, last_error="missing transcripts.jsonl")

    processed = indexed = skipped = errors = 0
    last_error: str | None = None

    with open(transcripts_jsonl, "r", encoding="utf-8") as fh:
        for line in fh:
            if req.max_videos and processed >= req.max_videos:
                break
            line = line.strip()
            if not line:
                continue
            try:
                ref = json.loads(line)
            except Exception:
                continue
            if not isinstance(ref, dict):
                continue

            video_id = str(ref.get("video_id") or "").strip()
            if not video_id:
                continue

            summary_path = os.path.join(OUTPUT_DIR, "data", "summaries", "by_video_id", f"{video_id}.summary.md")
            if not os.path.isfile(summary_path):
                skipped += 1
                continue

            summary_text = open(summary_path, "r", encoding="utf-8", errors="replace").read()
            body = _strip_frontmatter(summary_text).strip()
            if not body:
                skipped += 1
                continue

            payload = {
                "source_id": f"youtube:{video_id}",
                "text": body,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "knowledge_id": knowledge_id,
            }

            processed += 1
            if req.dry_run:
                indexed += 1
                continue

            try:
                res = _index_markdown(
                    IndexTranscriptRequest(
                        source_id=payload["source_id"],
                        text=payload["text"],
                        url=payload.get("url"),
                        knowledge_id=payload.get("knowledge_id"),
                    )
                )
                status = str(res.get("status") or "")
                if status in {"indexed", "skipped"}:
                    indexed += 1
                else:
                    errors += 1
                    last_error = json.dumps(res, ensure_ascii=False)[:5000]
            except Exception as e:
                errors += 1
                msg = str(e)
                last_error = msg[:5000]

    return SyncTopicResponse(
        status="success" if errors == 0 else "partial",
        topic=safe_topic,
        knowledge_id=knowledge_id,
        processed=processed,
        indexed=indexed,
        skipped=skipped,
        errors=errors,
        last_error=last_error,
    )


@app.post("/index/transcript", summary="Upload Markdown and add to Knowledge Collection", operation_id="knowledge_index")
def index_transcript(req: IndexTranscriptRequest) -> dict[str, Any]:
    try:
        return _index_markdown(req)
    except Exception as e:
        msg = str(e)
        if len(msg) > 2000:
            msg = msg[:2000] + "…"
        return {"status": "error", "error": msg}


@app.get("/outputs/topics", operation_id="outputs_topics")
def list_output_topics() -> TopicListResponse:
    return TopicListResponse(status="success", output_dir=OUTPUT_DIR, topics=_list_topics())


@app.get("/outputs/topics/{topic}/videos", operation_id="outputs_topic_videos")
def list_topic_videos(
    topic: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=1_000_000),
) -> TopicVideosResponse:
    try:
        safe_topic = _safe_id(topic, label="topic")
    except ValueError:
        return TopicVideosResponse(status="error", topic=topic, count=0, items=[])

    transcripts_path = os.path.join(_indexes_root(), safe_topic, "current", "transcripts.jsonl")
    if not os.path.isfile(transcripts_path):
        return TopicVideosResponse(status="not_found", topic=safe_topic, count=0, items=[])

    count, items = _read_jsonl(transcripts_path, limit=limit, offset=offset)
    return TopicVideosResponse(status="success", topic=safe_topic, count=count, items=items)


@app.get("/outputs/videos/{video_id}/transcript", operation_id="outputs_video_transcript")
def get_output_transcript(
    video_id: str,
    max_chars: int = Query(default=20_000, ge=0, le=500_000),
) -> OutputTextResponse:
    try:
        vid = _safe_id(video_id, label="video_id")
    except ValueError:
        return OutputTextResponse(status="error", video_id=video_id, path="", truncated=False, text="", meta=None)

    transcript_path = os.path.join(OUTPUT_DIR, "data", "transcripts", "by_video_id", f"{vid}.txt")
    if not os.path.isfile(transcript_path):
        return OutputTextResponse(status="not_found", video_id=vid, path=transcript_path, truncated=False, text="", meta=None)

    truncated, text = _read_text_file(transcript_path, max_chars=max_chars)
    meta_path = os.path.join(OUTPUT_DIR, "data", "transcripts", "by_video_id", f"{vid}.meta.json")
    meta: dict[str, Any] | None = None
    if os.path.isfile(meta_path):
        try:
            meta_obj = json.loads(open(meta_path, "r", encoding="utf-8").read())
            if isinstance(meta_obj, dict):
                meta = meta_obj
        except Exception:
            meta = None

    return OutputTextResponse(
        status="success",
        video_id=vid,
        path=transcript_path,
        truncated=truncated,
        text=text,
        meta=meta,
    )


@app.get("/outputs/videos/{video_id}/summary", operation_id="outputs_video_summary")
def get_output_summary(
    video_id: str,
    max_chars: int = Query(default=30_000, ge=0, le=500_000),
) -> OutputTextResponse:
    try:
        vid = _safe_id(video_id, label="video_id")
    except ValueError:
        return OutputTextResponse(status="error", video_id=video_id, path="", truncated=False, text="", meta=None)

    summary_path = os.path.join(OUTPUT_DIR, "data", "summaries", "by_video_id", f"{vid}.summary.md")
    if not os.path.isfile(summary_path):
        return OutputTextResponse(status="not_found", video_id=vid, path=summary_path, truncated=False, text="", meta=None)

    truncated, text = _read_text_file(summary_path, max_chars=max_chars)
    return OutputTextResponse(
        status="success",
        video_id=vid,
        path=summary_path,
        truncated=truncated,
        text=text,
        meta=None,
    )


@app.post("/transcript")
def transcript(req: TranscriptRequest) -> dict[str, Any]:
    preferred = req.preferred_languages or DEFAULT_LANGUAGES
    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(req.video_id)

        items: list[dict[str, Any]] | None = None
        last_exc: Exception | None = None

        for lang in preferred:
            for finder in ("manual", "generated"):
                try:
                    if finder == "manual":
                        chosen = transcripts.find_manually_created_transcript([lang])
                    else:
                        chosen = transcripts.find_generated_transcript([lang])
                    items = _fetch_with_retries(chosen, retries=FETCH_RETRIES)
                    if items:
                        break
                except Exception as e:
                    last_exc = e
                    items = None
            if items:
                break

        if not items:
            try:
                chosen = transcripts.find_transcript(preferred)
                items = _fetch_with_retries(chosen, retries=FETCH_RETRIES)
            except Exception as e:
                last_exc = e
                items = None

        if not items:
            if isinstance(last_exc, (NoTranscriptFound, TranscriptsDisabled)):
                return {"status": "no_transcript", "reason": "no_transcript_found"}
            if isinstance(last_exc, VideoUnavailable):
                return {"status": "error", "error_type": "VideoUnavailable", "error_message": "video unavailable"}
            if isinstance(last_exc, ParseError):
                return {"status": "error", "error_type": "TranscriptParseError", "error_message": str(last_exc)}
            if isinstance(last_exc, CouldNotRetrieveTranscript):
                return {"status": "error", "error_type": "CouldNotRetrieveTranscript", "error_message": str(last_exc)}
            if last_exc is not None:
                msg = str(last_exc)
                if len(msg) > 500:
                    msg = msg[:500] + "…"
                return {"status": "error", "error_type": type(last_exc).__name__, "error_message": msg}
            return {"status": "no_transcript", "reason": "no_transcript_found"}

        text = _render_text(items, include_timestamps=req.include_timestamps)
        if not text:
            return {"status": "no_transcript", "reason": "empty_transcript"}

        truncated = False
        if req.max_chars and len(text) > req.max_chars:
            text = text[: req.max_chars].rstrip() + "\n\n[...truncated...]\n"
            truncated = True

        sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return {
            "status": "success",
            "text": text,
            "meta": {
                "language": getattr(chosen, "language_code", None),  # type: ignore[name-defined]
                "is_generated": getattr(chosen, "is_generated", None),  # type: ignore[name-defined]
                "sha256": sha256,
                "truncated": truncated,
                "max_chars": req.max_chars,
            },
        }
    except (NoTranscriptFound, TranscriptsDisabled):
        return {"status": "no_transcript", "reason": "no_transcript_found"}
    except VideoUnavailable:
        return {"status": "error", "error_type": "VideoUnavailable", "error_message": "video unavailable"}
    except CouldNotRetrieveTranscript as e:
        return {
            "status": "error",
            "error_type": "CouldNotRetrieveTranscript",
            "error_message": str(e),
        }
    except ParseError as e:
        return {
            "status": "error",
            "error_type": "TranscriptParseError",
            "error_message": str(e),
        }
    except Exception as e:
        message = str(e)
        if len(message) > 500:
            message = message[:500] + "…"
        return {"status": "error", "error_type": type(e).__name__, "error_message": message}
