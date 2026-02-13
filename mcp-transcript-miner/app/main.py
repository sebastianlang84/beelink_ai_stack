import hashlib
import json
import os
import time
import requests
import re
import sqlite3
import threading
from dataclasses import dataclass
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

import yaml


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
INDEX_MAX_ATTEMPTS = max(1, int(os.getenv("OPEN_WEBUI_INDEX_MAX_ATTEMPTS", "3")))
INDEX_RETRY_BACKOFF_SECONDS = max(0.0, float(os.getenv("OPEN_WEBUI_INDEX_RETRY_BACKOFF_SECONDS", "5")))
INDEXER_DB_PATH = os.getenv("INDEXER_DB_PATH", "/data/indexer.sqlite3")
AUTO_SYNC_AFTER_RUN = os.getenv("OPEN_WEBUI_AUTO_SYNC_AFTER_RUN", "").strip().lower() in {"1", "true", "yes"}
AUTO_CREATE_KNOWLEDGE = os.getenv("OPEN_WEBUI_CREATE_KNOWLEDGE_IF_MISSING", "").strip().lower() in {"1", "true", "yes"}
AUTO_CREATE_KNOWLEDGE_ALLOWLIST = {
    t.strip().lower()
    for t in os.getenv("OPEN_WEBUI_CREATE_KNOWLEDGE_ALLOWLIST", "").split(",")
    if t.strip()
}
KNOWLEDGE_DEDUP_PRECHECK = os.getenv("OPEN_WEBUI_KNOWLEDGE_DEDUP_PRECHECK", "true").strip().lower() in {
    "1",
    "true",
    "yes",
}
KNOWLEDGE_DEDUP_CACHE_TTL = int(os.getenv("OPEN_WEBUI_KNOWLEDGE_DEDUP_CACHE_TTL_SECONDS", "900"))


@dataclass(frozen=True)
class OwuiCollectionsConfig:
    enabled: bool
    new_suffix: str
    archive_suffix: str
    newest_per_channel: int
    new_max_age_days: int
    archive_max_age_days: int
    cold_enabled: bool
    cold_dir: str
    excluded_topics: set[str]


_OWUI_COLLECTIONS_CFG: OwuiCollectionsConfig | None = None


def _load_owui_collections_config() -> OwuiCollectionsConfig:
    global _OWUI_COLLECTIONS_CFG
    if _OWUI_COLLECTIONS_CFG is not None:
        return _OWUI_COLLECTIONS_CFG

    # Defaults (must be safe even if YAML is missing/invalid).
    enabled = True
    new_suffix = "_new"
    archive_suffix = "_archive"
    newest_per_channel = 2
    new_max_age_days = 0
    archive_max_age_days = 15
    excluded_topics: set[str] = {"company_dossiers"}
    cold_enabled = True
    cold_dir = os.path.join(OUTPUT_DIR, "data", "summaries", "cold", "by_video_id")

    # Source of truth: transcript-miner/config/config_global.yaml (mounted into tm container).
    cfg_path = os.getenv(
        "OPEN_WEBUI_COLLECTIONS_CONFIG_PATH",
        os.path.join(CONFIG_DIR, "config_global.yaml"),
    ).strip()
    if cfg_path:
        try:
            raw = Path(cfg_path).read_text(encoding="utf-8")
            obj = yaml.safe_load(raw) or {}
            if isinstance(obj, dict):
                section = obj.get("owui_collections") or {}
                if isinstance(section, dict):
                    enabled = bool(section.get("enabled", enabled))
                    if isinstance(section.get("new_suffix"), str) and section["new_suffix"]:
                        new_suffix = str(section["new_suffix"]).strip()
                    if isinstance(section.get("archive_suffix"), str) and section["archive_suffix"]:
                        archive_suffix = str(section["archive_suffix"]).strip()
                    try:
                        newest_per_channel = max(1, int(section.get("newest_per_channel", newest_per_channel)))
                    except Exception:
                        pass
                    try:
                        # 0 = no limit (allow old videos into _new if channel is stale)
                        new_max_age_days = max(0, int(section.get("new_max_age_days", new_max_age_days)))
                    except Exception:
                        pass
                    try:
                        archive_max_age_days = max(1, int(section.get("archive_max_age_days", archive_max_age_days)))
                    except Exception:
                        pass
                    excl = section.get("excluded_topics")
                    if isinstance(excl, list):
                        excluded_topics = {str(x).strip().lower() for x in excl if str(x).strip()}
                    cold = section.get("cold") or {}
                    if isinstance(cold, dict):
                        cold_enabled = bool(cold.get("enabled", cold_enabled))
                        cdir = cold.get("dir")
                        if isinstance(cdir, str) and cdir.strip():
                            cdir_s = cdir.strip()
                            cold_dir = cdir_s if os.path.isabs(cdir_s) else os.path.join(OUTPUT_DIR, cdir_s)
        except Exception:
            # Fail closed to defaults; do not crash the tool server.
            pass

    # Normalize suffixes (no spaces).
    new_suffix = new_suffix.strip()
    archive_suffix = archive_suffix.strip()
    if not new_suffix.startswith("_"):
        new_suffix = "_" + new_suffix
    if not archive_suffix.startswith("_"):
        archive_suffix = "_" + archive_suffix

    _OWUI_COLLECTIONS_CFG = OwuiCollectionsConfig(
        enabled=enabled,
        new_suffix=new_suffix,
        archive_suffix=archive_suffix,
        newest_per_channel=newest_per_channel,
        new_max_age_days=new_max_age_days,
        archive_max_age_days=archive_max_age_days,
        cold_enabled=cold_enabled,
        cold_dir=cold_dir,
        excluded_topics=excluded_topics,
    )
    return _OWUI_COLLECTIONS_CFG

_KNOWLEDGE_FILE_CACHE: dict[str, dict[str, Any]] = {}
_SYNC_TOPIC_GUARD_LOCK = threading.Lock()
_SYNC_TOPIC_ACTIVE: set[str] = set()


def _sync_topic_guard_acquire(topic: str) -> bool:
    with _SYNC_TOPIC_GUARD_LOCK:
        if topic in _SYNC_TOPIC_ACTIVE:
            return False
        _SYNC_TOPIC_ACTIVE.add(topic)
        return True


def _sync_topic_guard_release(topic: str) -> None:
    with _SYNC_TOPIC_GUARD_LOCK:
        _SYNC_TOPIC_ACTIVE.discard(topic)

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
  - Default: lifecycle routing to derived collections:
    - targets: `<topic>_new` (per channel max N newest) and `<topic>_archive` (rest up to max age)
    - rules come from `transcript-miner/config/config_global.yaml` (`owui_collections.*`)
    - excluded topics (e.g. `company_dossiers`) keep direct sync to `<topic>` (no suffix routing).
    Summaries older than archive window are moved to `output/data/summaries/cold/by_video_id`.
- `POST /sync/lifecycle/{topic}` — explicit lifecycle sync endpoint (same behavior as above)
  - Backwards compatible alias: `POST /sync/investing/lifecycle`

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
- `POST /runs/start` requires `YOUTUBE_API_KEY` and, with LLM enabled, backend-specific auth:
  - `TM_LLM_BACKEND=openrouter`: `OPENROUTER_API_KEY`
  - `TM_LLM_BACKEND=gemini_cli`: one-time `gemini` login inside the `tm` container (`docker exec -it tm gemini`)
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
    auto_sync: bool = False


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
    auto_sync: bool = False
    auto_sync_state: str | None = None
    auto_sync_started_at: str | None = None
    auto_sync_finished_at: str | None = None
    auto_sync_error: str | None = None
    auto_sync_result: dict[str, Any] | None = None


class RunStatusMcpRequest(BaseModel):
    run_id: str = Field(min_length=1)


class SyncTopicRequest(BaseModel):
    max_videos: int = Field(default=0, ge=0, le=5000, description="0 = no limit.")
    dry_run: bool = False
    run_id: str | None = None
    heal_missing_summaries: bool = Field(
        default=True,
        description="Wenn true, wird vor dem Sync ein LLM-Healing-Lauf gestartet, falls Summaries fehlen.",
    )
    heal_timeout_s: int = Field(
        default=900,
        ge=30,
        le=3600,
        description="Maximale Wartezeit für Healing (Sekunden).",
    )
    heal_poll_s: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Polling-Intervall für Healing-Status (Sekunden).",
    )
    create_knowledge_if_missing: bool = Field(
        default=False,
        description="Erstellt eine Knowledge Collection nur, wenn explizit gesetzt (und Allowlist passt).",
    )


class SyncTopicResponse(BaseModel):
    status: str
    topic: str
    knowledge_id: str | None = None
    processed: int = 0
    indexed: int = 0
    skipped: int = 0
    errors: int = 0
    last_error: str | None = None
    run_id: str | None = None


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


def _resolve_config_id(requested: str) -> str | None:
    req = (requested or "").strip()
    if not req:
        return None
    configs = _list_configs()
    # Exact match on config_id/filename first.
    for cfg in configs:
        if req == cfg.config_id or req == cfg.filename:
            return cfg.config_id
    # Match display_name/aliases (case-insensitive).
    req_norm = req.casefold()
    for cfg in configs:
        if req_norm == cfg.display_name.casefold():
            return cfg.config_id
        for alias in cfg.aliases:
            if req_norm == alias.casefold():
                return cfg.config_id
    return None


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


def _get_knowledge_by_id(knowledge_id: str) -> dict[str, Any] | None:
    knowledge_id = (knowledge_id or "").strip()
    if not knowledge_id:
        return None
    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/knowledge/{knowledge_id}"
    resp = requests.get(url, headers=_auth_headers(), timeout=30)
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise RuntimeError(f"knowledge get failed: {resp.status_code} {resp.text}")
    data = resp.json()
    return data if isinstance(data, dict) else None


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
        if _get_knowledge_by_id(mapped):
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
        detail = resp.text or ""
        if resp.status_code == 400 and "Duplicate content" in detail:
            return {"status": "skipped", "reason": "duplicate_content", "detail": detail}
        raise RuntimeError(f"knowledge add failed: {resp.status_code} {detail}")
    return resp.json() if resp.content else {"status": "ok"}


def _remove_from_knowledge(knowledge_id: str, file_id: str) -> dict[str, Any]:
    import requests

    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/knowledge/{knowledge_id}/file/remove"
    headers = _auth_headers() | {"Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={"file_id": file_id}, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"knowledge remove failed: {resp.status_code} {resp.text}")
    return resp.json() if resp.content else {"status": "ok"}


def _create_knowledge(name: str) -> dict[str, Any]:
    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/knowledge/create"
    headers = _auth_headers() | {"Content-Type": "application/json"}
    payload = {"name": name, "description": ""}
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"knowledge create failed: {resp.status_code} {resp.text}")
    return resp.json() if resp.content else {"status": "ok"}


def _fetch_knowledge_files(knowledge_id: str) -> list[dict[str, Any]]:
    import requests

    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/knowledge/{knowledge_id}/files"
    headers = _auth_headers()
    page = 0
    limit = 200
    files: list[dict[str, Any]] = []
    while True:
        resp = requests.get(
            url,
            headers=headers,
            params={"page": page, "limit": limit},
            timeout=60,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"knowledge files failed: {resp.status_code} {resp.text}")
        data = resp.json()
        batch = data.get("items") or data.get("files") or []
        total = data.get("total")
        if not batch:
            break
        files.extend(batch)
        if total is not None and len(files) >= total:
            break
        if len(batch) < limit:
            break
        page += 1
    return files


def _extract_source_id_from_knowledge_file(item: dict[str, Any]) -> str | None:
    # OWUI returns processed content including our YAML frontmatter; prefer that over parsing filename.
    data = item.get("data") or {}
    content = data.get("content") if isinstance(data, dict) else None
    if isinstance(content, str) and content:
        head = content[:3000]
        m = re.search(r'(?m)^source_id:\\s*"?([^"\\n]+)"?\\s*$', head)
        if m:
            src = str(m.group(1)).strip()
            return src or None
    return None


def _uploads_move_knowledge(*, source_id: str, knowledge_id: str, file_id: str | None = None) -> None:
    # Keep local indexer DB consistent so future syncs don't re-upload moved files.
    conn = _db()
    try:
        row = conn.execute(
            "SELECT sha256, file_id FROM uploads WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        if not row:
            return
        sha, fid = row[0], row[1]
        conn.execute(
            "INSERT OR REPLACE INTO uploads (source_id, sha256, file_id, knowledge_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (source_id, sha, (file_id or fid), knowledge_id, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def _knowledge_file_cache_get(knowledge_id: str) -> dict[str, Any] | None:
    entry = _KNOWLEDGE_FILE_CACHE.get(knowledge_id)
    if not entry:
        return None
    if (time.time() - entry.get("ts", 0)) > KNOWLEDGE_DEDUP_CACHE_TTL:
        return None
    return entry


def _knowledge_file_cache_set(knowledge_id: str, hashes: set[str], filenames: set[str]) -> None:
    _KNOWLEDGE_FILE_CACHE[knowledge_id] = {"ts": time.time(), "hashes": hashes, "filenames": filenames}


def _knowledge_file_cache_add(knowledge_id: str, sha: str | None, filename: str | None) -> None:
    entry = _knowledge_file_cache_get(knowledge_id)
    if not entry:
        return
    if sha:
        entry["hashes"].add(sha)
    if filename:
        entry["filenames"].add(filename)


def _knowledge_has_duplicate(knowledge_id: str, sha: str | None, filename: str | None) -> bool:
    if not KNOWLEDGE_DEDUP_PRECHECK:
        return False
    entry = _knowledge_file_cache_get(knowledge_id)
    if not entry:
        try:
            files = _fetch_knowledge_files(knowledge_id)
        except Exception:
            return False
        hashes = {str(f.get("hash") or "") for f in files if f.get("hash")}
        filenames = {
            str(f.get("filename") or f.get("name") or "")
            for f in files
            if (f.get("filename") or f.get("name"))
        }
        _knowledge_file_cache_set(knowledge_id, hashes=hashes, filenames=filenames)
        entry = _knowledge_file_cache_get(knowledge_id)
        if not entry:
            return False
    hashes = entry.get("hashes") or set()
    filenames = entry.get("filenames") or set()
    if sha and sha in hashes:
        return True
    if filename and filename in filenames:
        return True
    return False


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

        def _slug(s: str, max_len: int = 80) -> str:
            s = re.sub(r"[^A-Za-z0-9]+", "_", s.strip())
            s = re.sub(r"_+", "_", s).strip("_")
            if not s:
                return "na"
            return s[:max_len]

        def _video_id_from_source(src: str) -> str:
            if src.startswith("youtube:"):
                return src.split(":", 1)[1]
            return src

        vid = _video_id_from_source(req.source_id)
        parts = ["youtube"]
        if req.published_at:
            parts.append(_slug(req.published_at[:10]))
        if req.channel:
            parts.append(_slug(req.channel, 32))
        if req.title:
            parts.append(_slug(req.title, 80))
        parts.append(_slug(vid, 16))
        filename = "__".join(parts) + ".md"
        markdown = _render_markdown(req)

        if _knowledge_has_duplicate(knowledge_id, sha=sha, filename=filename):
            return {
                "status": "skipped",
                "reason": "duplicate_remote",
                "source_id": req.source_id,
                "knowledge_id": knowledge_id,
                "filename": filename,
            }

        last_failure: dict[str, Any] | None = None
        for attempt in range(1, INDEX_MAX_ATTEMPTS + 1):
            try:
                file_id = _upload_file(markdown, filename=filename)
                process_status = _poll_processing(file_id)
                if (process_status.get("status") or "").lower() == "failed":
                    last_failure = {
                        "status": "failed",
                        "step": "process",
                        "file_id": file_id,
                        "process": process_status,
                        "attempt": attempt,
                        "attempts": INDEX_MAX_ATTEMPTS,
                    }
                    if attempt < INDEX_MAX_ATTEMPTS:
                        time.sleep(INDEX_RETRY_BACKOFF_SECONDS * attempt)
                    continue

                add_result = _add_to_knowledge(knowledge_id=knowledge_id, file_id=file_id)
                add_status = str(add_result.get("status") or "indexed")

                conn.execute(
                    "INSERT OR REPLACE INTO uploads (source_id, sha256, file_id, knowledge_id, created_at) VALUES (?, ?, ?, ?, ?)",
                    (req.source_id, sha, file_id, knowledge_id, int(time.time())),
                )
                conn.commit()
                if add_status != "skipped":
                    _knowledge_file_cache_add(knowledge_id, sha=sha, filename=filename)
                return {
                    "status": "skipped" if add_status == "skipped" else "indexed",
                    "source_id": req.source_id,
                    "file_id": file_id,
                    "knowledge_id": knowledge_id,
                    "process": process_status,
                    "knowledge_add": add_result,
                    "attempt": attempt,
                    "attempts": INDEX_MAX_ATTEMPTS,
                }
            except Exception as exc:
                last_failure = {
                    "status": "failed",
                    "step": "upload_or_add",
                    "error": str(exc),
                    "attempt": attempt,
                    "attempts": INDEX_MAX_ATTEMPTS,
                }
                if attempt < INDEX_MAX_ATTEMPTS:
                    time.sleep(INDEX_RETRY_BACKOFF_SECONDS * attempt)
                continue
        return last_failure or {"status": "failed", "step": "unknown"}
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


def _load_metadata(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            obj = json.load(fh)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _parse_datetime_utc(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except Exception:
        dt = None
    if dt is None:
        for fmt in ("%Y-%m-%d %H:%M UTC", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except Exception:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _allow_create_knowledge(*, topic: str, create_flag: bool) -> bool:
    if not create_flag:
        return False
    if not AUTO_CREATE_KNOWLEDGE:
        return False
    return (not AUTO_CREATE_KNOWLEDGE_ALLOWLIST) or (topic.lower() in AUTO_CREATE_KNOWLEDGE_ALLOWLIST)


def _resolve_or_create_knowledge_id(*, topic: str, create_flag: bool) -> tuple[str | None, str | None]:
    try:
        knowledge_id = _resolve_knowledge_id_for_topic(topic)
    except Exception as exc:
        return None, str(exc)
    if knowledge_id:
        return knowledge_id, None
    if _allow_create_knowledge(topic=topic, create_flag=create_flag):
        try:
            _create_knowledge(topic)
            knowledge_id = _resolve_knowledge_id_for_topic(topic)
        except Exception as exc:
            return None, str(exc)
    if not knowledge_id:
        return None, "knowledge not found"
    return knowledge_id, None


def _active_summary_path(video_id: str) -> str:
    return os.path.join(OUTPUT_DIR, "data", "summaries", "by_video_id", f"{video_id}.summary.md")


def _cold_summary_path(video_id: str) -> str:
    cfg = _load_owui_collections_config()
    return os.path.join(cfg.cold_dir, f"{video_id}.summary.md")


def _move_old_summaries_to_cold(
    *,
    entries: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    cfg = _load_owui_collections_config()
    info: dict[str, Any] = {
        "cold_enabled": cfg.cold_enabled,
        "cold_dir": cfg.cold_dir,
        "old_candidates": 0,
        "cold_moved": 0,
        "cold_move_errors": 0,
    }
    if not cfg.cold_enabled:
        return info

    video_ids = {str(entry.get("video_id") or "").strip() for entry in entries if str(entry.get("video_id") or "").strip()}
    info["old_candidates"] = len(video_ids)
    if not video_ids:
        return info

    if not dry_run:
        try:
            os.makedirs(cfg.cold_dir, exist_ok=True)
        except Exception:
            info["cold_move_errors"] = len(video_ids)
            return info

    for video_id in sorted(video_ids):
        src = _active_summary_path(video_id)
        if not os.path.isfile(src):
            continue
        dst = _cold_summary_path(video_id)
        try:
            if not dry_run:
                os.replace(src, dst)
            info["cold_moved"] += 1
        except Exception:
            info["cold_move_errors"] += 1
    return info


def _delete_knowledge_collection(knowledge_id: str) -> None:
    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/knowledge/{knowledge_id}/delete"
    resp = requests.delete(url, headers=_auth_headers(), timeout=60)
    if resp.status_code == 404:
        return
    if resp.status_code >= 400:
        raise RuntimeError(f"knowledge delete failed: {resp.status_code} {resp.text}")
    _KNOWLEDGE_FILE_CACHE.pop(knowledge_id, None)


def _collect_sync_entries(topic: str) -> list[dict[str, Any]]:
    index_dir = os.path.join(_indexes_root(), topic, "current")
    transcripts_jsonl = os.path.join(index_dir, "transcripts.jsonl")
    if not os.path.isfile(transcripts_jsonl):
        return []

    out: list[dict[str, Any]] = []
    with open(transcripts_jsonl, "r", encoding="utf-8") as fh:
        for line in fh:
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
            summary_path = _active_summary_path(video_id)
            if not os.path.isfile(summary_path):
                continue
            summary_text = open(summary_path, "r", encoding="utf-8", errors="replace").read()
            body = _strip_frontmatter(summary_text).strip()
            if not body:
                continue

            meta = {}
            meta_path = str(ref.get("metadata_path") or "")
            if meta_path:
                meta = _load_metadata(meta_path)

            channel = (
                str(meta.get("channel_name") or "").strip()
                or str(meta.get("channel_handle") or "").strip()
                or str(ref.get("channel_namespace") or "").strip()
                or "unknown"
            )
            published_raw = (
                meta.get("published_at")
                or ref.get("published_date")
                or ref.get("published_at")
            )
            published_dt = _parse_datetime_utc(published_raw)
            out.append(
                {
                    "video_id": video_id,
                    "source_id": f"youtube:{video_id}",
                    "text": body,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "title": meta.get("video_title"),
                    "channel": channel,
                    "published_at": str(published_raw or "").strip() or None,
                    "published_dt": published_dt,
                }
            )

    dedup: dict[str, dict[str, Any]] = {}
    for entry in out:
        vid = entry["video_id"]
        prev = dedup.get(vid)
        if prev is None:
            dedup[vid] = entry
            continue
        prev_dt = prev.get("published_dt")
        cur_dt = entry.get("published_dt")
        if cur_dt and (not prev_dt or cur_dt > prev_dt):
            dedup[vid] = entry
    return list(dedup.values())


def _index_entries_to_knowledge(
    *,
    entries: list[dict[str, Any]],
    knowledge_id: str,
    dry_run: bool,
    max_videos: int,
) -> tuple[int, int, int, int, str | None]:
    processed = indexed = skipped = errors = 0
    last_error: str | None = None
    for entry in entries:
        if max_videos and processed >= max_videos:
            break
        processed += 1
        if dry_run:
            indexed += 1
            continue
        try:
            res = _index_markdown(
                IndexTranscriptRequest(
                    source_id=str(entry["source_id"]),
                    text=str(entry["text"]),
                    url=entry.get("url"),
                    title=entry.get("title"),
                    channel=entry.get("channel"),
                    published_at=entry.get("published_at"),
                    knowledge_id=knowledge_id,
                )
            )
            status = str(res.get("status") or "")
            if status in {"indexed", "skipped"}:
                indexed += 1
            else:
                errors += 1
                last_error = json.dumps(res, ensure_ascii=False)[:5000]
        except Exception as exc:
            errors += 1
            last_error = str(exc)[:5000]
    return processed, indexed, skipped, errors, last_error


def _sync_topic_lifecycle(*, topic: str, req: SyncTopicRequest) -> SyncTopicResponse:
    cfg = _load_owui_collections_config()
    try:
        source_topic = _safe_id(topic, label="topic")
    except ValueError:
        return SyncTopicResponse(status="error", topic=topic, last_error="invalid topic", run_id=req.run_id)

    # Guard: lifecycle expects base topics, not already-suffixed derived targets.
    if source_topic.endswith(cfg.new_suffix) or source_topic.endswith(cfg.archive_suffix):
        return SyncTopicResponse(
            status="error",
            topic=source_topic,
            last_error=f"refusing to lifecycle-sync derived topic; use base topic without suffix (suffixes: {cfg.new_suffix},{cfg.archive_suffix})",
            run_id=req.run_id,
        )

    new_topic = _safe_id(f"{source_topic}{cfg.new_suffix}", label="topic")
    archive_topic = _safe_id(f"{source_topic}{cfg.archive_suffix}", label="topic")

    entries = _collect_sync_entries(source_topic)
    if not entries:
        return SyncTopicResponse(
            status="not_found",
            topic=source_topic,
            last_error=f"missing or empty source topic index: {source_topic}",
            run_id=req.run_id,
        )

    by_channel: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_channel.setdefault(str(entry.get("channel") or "unknown"), []).append(entry)

    keep_new: list[dict[str, Any]] = []
    now_utc = datetime.now(timezone.utc)
    for _, items in by_channel.items():
        # "new" means "recent enough" + newest per channel.
        eligible: list[dict[str, Any]] = []
        for it in items:
            published_dt = it.get("published_dt")
            if not isinstance(published_dt, datetime):
                continue
            if cfg.new_max_age_days > 0:
                age_s = (now_utc - published_dt).total_seconds()
                if age_s > (cfg.new_max_age_days * 86400):
                    continue
            eligible.append(it)

        items_sorted = sorted(
            eligible,
            key=lambda x: (
                x.get("published_dt") is not None,
                x.get("published_dt") or datetime(1970, 1, 1, tzinfo=timezone.utc),
                x.get("video_id") or "",
            ),
            reverse=True,
        )
        keep_new.extend(items_sorted[: cfg.newest_per_channel])

    keep_new_ids = {str(x.get("video_id")) for x in keep_new}
    keep_archive: list[dict[str, Any]] = []
    drop_old: list[dict[str, Any]] = []
    for entry in entries:
        vid = str(entry.get("video_id") or "")
        if not vid or vid in keep_new_ids:
            continue
        published_dt = entry.get("published_dt")
        if not isinstance(published_dt, datetime):
            continue
        age_s = (now_utc - published_dt).total_seconds()
        if age_s <= (cfg.archive_max_age_days * 86400):
            keep_archive.append(entry)
        else:
            drop_old.append(entry)

    new_id, err_new = _resolve_or_create_knowledge_id(topic=new_topic, create_flag=req.create_knowledge_if_missing)
    if not new_id:
        hint = " (auto-create requires OPEN_WEBUI_CREATE_KNOWLEDGE_IF_MISSING=true and allowlist match)"
        return SyncTopicResponse(status="error", topic=new_topic, last_error=f"{err_new or 'knowledge not found'}{hint}", run_id=req.run_id)
    archive_id, err_archive = _resolve_or_create_knowledge_id(topic=archive_topic, create_flag=req.create_knowledge_if_missing)
    if not archive_id:
        hint = " (auto-create requires OPEN_WEBUI_CREATE_KNOWLEDGE_IF_MISSING=true and allowlist match)"
        return SyncTopicResponse(status="error", topic=new_topic, last_error=f"{err_archive or 'archive knowledge not found'}{hint}", run_id=req.run_id)

    desired_new_source_ids = {f"youtube:{str(x.get('video_id') or '').strip()}" for x in keep_new if str(x.get("video_id") or "").strip()}
    desired_archive_source_ids = {f"youtube:{str(x.get('video_id') or '').strip()}" for x in keep_archive if str(x.get("video_id") or "").strip()}

    moved_to_new = 0
    moved_to_archive = 0
    removed_from_new = 0
    removed_from_archive = 0
    unknown_new = 0
    unknown_archive = 0

    # Reconcile in-place to keep Knowledge IDs stable (Folder bindings stay intact in OWUI).
    # Strategy:
    # 1) Move files between knowledges if already uploaded elsewhere.
    # 2) Remove files not in desired sets.
    # 3) Upload missing files.
    try:
        files_new = _fetch_knowledge_files(new_id)
        files_archive = _fetch_knowledge_files(archive_id)
    except Exception as exc:
        return SyncTopicResponse(status="error", topic=source_topic, last_error=str(exc), run_id=req.run_id)

    cur_new: dict[str, dict[str, Any]] = {}
    for it in files_new:
        sid = _extract_source_id_from_knowledge_file(it)
        if not sid:
            unknown_new += 1
            continue
        cur_new[sid] = it
    cur_archive: dict[str, dict[str, Any]] = {}
    for it in files_archive:
        sid = _extract_source_id_from_knowledge_file(it)
        if not sid:
            unknown_archive += 1
            continue
        cur_archive[sid] = it

    def _file_id(item: dict[str, Any]) -> str:
        fid = item.get("id") or item.get("file_id")
        return str(fid or "").strip()

    if not req.dry_run:
        # Move: archive -> new
        for sid in sorted(desired_new_source_ids.intersection(cur_archive.keys())):
            item = cur_archive.get(sid) or {}
            fid = _file_id(item)
            if not fid:
                continue
            try:
                _add_to_knowledge(new_id, fid)
                _remove_from_knowledge(archive_id, fid)
                moved_to_new += 1
                _uploads_move_knowledge(source_id=sid, knowledge_id=new_id, file_id=fid)
            except Exception as exc:
                return SyncTopicResponse(status="error", topic=source_topic, last_error=str(exc), run_id=req.run_id)

        # Move: new -> archive
        for sid in sorted(desired_archive_source_ids.intersection(cur_new.keys())):
            item = cur_new.get(sid) or {}
            fid = _file_id(item)
            if not fid:
                continue
            try:
                _add_to_knowledge(archive_id, fid)
                _remove_from_knowledge(new_id, fid)
                moved_to_archive += 1
                _uploads_move_knowledge(source_id=sid, knowledge_id=archive_id, file_id=fid)
            except Exception as exc:
                return SyncTopicResponse(status="error", topic=source_topic, last_error=str(exc), run_id=req.run_id)

        # Invalidate cache because we mutated membership.
        _KNOWLEDGE_FILE_CACHE.pop(new_id, None)
        _KNOWLEDGE_FILE_CACHE.pop(archive_id, None)

        # Remove: anything not desired anymore (including items that aged out of archive window).
        for sid, item in cur_new.items():
            if sid in desired_new_source_ids:
                continue
            if sid in desired_archive_source_ids:
                continue
            fid = _file_id(item)
            if not fid:
                continue
            try:
                _remove_from_knowledge(new_id, fid)
                removed_from_new += 1
            except Exception as exc:
                return SyncTopicResponse(status="error", topic=source_topic, last_error=str(exc), run_id=req.run_id)

        for sid, item in cur_archive.items():
            if sid in desired_archive_source_ids:
                continue
            if sid in desired_new_source_ids:
                continue
            fid = _file_id(item)
            if not fid:
                continue
            try:
                _remove_from_knowledge(archive_id, fid)
                removed_from_archive += 1
            except Exception as exc:
                return SyncTopicResponse(status="error", topic=source_topic, last_error=str(exc), run_id=req.run_id)

        _KNOWLEDGE_FILE_CACHE.pop(new_id, None)
        _KNOWLEDGE_FILE_CACHE.pop(archive_id, None)

    p1, i1, s1, e1, le1 = _index_entries_to_knowledge(
        entries=keep_new,
        knowledge_id=new_id,
        dry_run=req.dry_run,
        max_videos=req.max_videos,
    )
    p2, i2, s2, e2, le2 = _index_entries_to_knowledge(
        entries=keep_archive,
        knowledge_id=archive_id,
        dry_run=req.dry_run,
        max_videos=req.max_videos,
    )

    status = "success" if (e1 + e2) == 0 else "partial"
    cold_info = _move_old_summaries_to_cold(entries=drop_old, dry_run=req.dry_run)
    if int(cold_info.get("cold_move_errors") or 0) > 0 and status == "success":
        status = "partial"
    lifecycle_info = {
        "source_topic": source_topic,
        "new_topic": new_topic,
        "archive_topic": archive_topic,
        "new_kept": len(keep_new),
        "archive_kept": len(keep_archive),
        "moved_to_new": moved_to_new,
        "moved_to_archive": moved_to_archive,
        "removed_from_new": removed_from_new,
        "removed_from_archive": removed_from_archive,
        "unknown_files_new": unknown_new,
        "unknown_files_archive": unknown_archive,
        "new_knowledge_id": new_id,
        "archive_knowledge_id": archive_id,
        **cold_info,
    }
    last_error = le1 or le2
    if status == "success":
        last_error = json.dumps(lifecycle_info, ensure_ascii=False)

    return SyncTopicResponse(
        status=status,
        topic=source_topic,
        knowledge_id=None,
        processed=p1 + p2,
        indexed=i1 + i2,
        skipped=s1 + s2,
        errors=e1 + e2,
        last_error=last_error,
        run_id=req.run_id,
    )


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


def _append_run_log(run_id: str, message: str) -> None:
    try:
        path = _run_log_path(run_id)
        ts = datetime.now(timezone.utc).isoformat()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"[auto-sync {ts}] {message}\n")
    except Exception:
        pass


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


def _find_config_id_for_topic(topic: str) -> str | None:
    try:
        import yaml  # type: ignore
    except Exception:
        return None

    for cfg in _list_configs():
        try:
            _, cfg_text = _read_config_text(cfg.config_id)
            obj = yaml.safe_load(cfg_text or "") or {}
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        output_cfg = obj.get("output")
        if not isinstance(output_cfg, dict):
            continue
        cfg_topic = output_cfg.get("topic")
        if cfg_topic is None:
            continue
        if str(cfg_topic).strip() == topic:
            return cfg.config_id
    return None


def _list_missing_summaries(transcripts_jsonl: str) -> list[str]:
    missing: list[str] = []
    try:
        with open(transcripts_jsonl, "r", encoding="utf-8") as fh:
            for line in fh:
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
                summary_path = os.path.join(
                    OUTPUT_DIR, "data", "summaries", "by_video_id", f"{video_id}.summary.md"
                )
                if (not os.path.isfile(summary_path)) and (not os.path.isfile(_cold_summary_path(video_id))):
                    missing.append(video_id)
    except Exception:
        return missing
    return missing


def _heal_missing_summaries(
    *,
    topic: str,
    timeout_s: int,
    poll_s: int,
) -> tuple[bool, str | None]:
    config_id = _find_config_id_for_topic(topic)
    if not config_id:
        return False, f"no config found for topic: {topic}"

    resp = start_run(RunStartRequest(config_id=config_id, only=["llm"]))
    if resp.status != "started" or not resp.run_id:
        return False, resp.summary or "failed to start healing run"

    deadline = time.time() + max(30, int(timeout_s))
    while time.time() < deadline:
        status = get_run(resp.run_id)
        if status.state in ("finished", "failed"):
            if status.exit_code == 0:
                return True, None
            return False, status.summary or status.error or f"healing exit_code={status.exit_code}"
        time.sleep(max(1, int(poll_s)))

    return False, "healing timeout"


def _queue_auto_sync(run_id: str, topic: str) -> None:
    def _worker() -> None:
        try:
            meta = _read_run_meta(run_id) or {}
            if meta.get("auto_sync_state") in {"running", "finished", "failed"}:
                return
            meta["auto_sync_state"] = "running"
            meta["auto_sync_started_at"] = datetime.now(timezone.utc).isoformat()
            _write_run_meta(run_id, meta)
            _append_run_log(run_id, f"auto-sync start (topic={topic})")

            req = SyncTopicRequest(run_id=run_id)
            res = sync_topic(topic, req)
            result = res.model_dump()

            meta = _read_run_meta(run_id) or meta
            meta["auto_sync_state"] = "finished" if res.status == "success" else "failed"
            meta["auto_sync_finished_at"] = datetime.now(timezone.utc).isoformat()
            meta["auto_sync_result"] = result
            meta["auto_sync_error"] = None if res.status == "success" else (res.last_error or res.status)
            meta["auto_synced"] = True
            _write_run_meta(run_id, meta)
            _append_run_log(run_id, f"auto-sync done status={res.status} processed={res.processed} indexed={res.indexed} skipped={res.skipped} errors={res.errors}")
        except Exception as exc:
            meta = _read_run_meta(run_id) or {}
            meta["auto_sync_state"] = "failed"
            meta["auto_sync_finished_at"] = datetime.now(timezone.utc).isoformat()
            meta["auto_sync_error"] = str(exc)[:2000]
            _write_run_meta(run_id, meta)
            _append_run_log(run_id, f"auto-sync failed: {exc}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def _watch_run_for_autosync(run_id: str, proc: subprocess.Popen[Any], topic: str | None) -> None:
    def _worker() -> None:
        exit_code = proc.wait()
        meta = _read_run_meta(run_id) or {}
        meta["exit_code"] = int(exit_code)
        meta["finished_at"] = meta.get("finished_at") or datetime.now(timezone.utc).isoformat()
        meta["state"] = "finished"
        _write_run_meta(run_id, meta)
        if AUTO_SYNC_AFTER_RUN and topic:
            if meta.get("auto_sync_state") not in {"running", "finished", "failed"}:
                meta["auto_sync_state"] = "queued"
                _write_run_meta(run_id, meta)
                if exit_code != 0:
                    _append_run_log(run_id, f"auto-sync queued despite non-zero exit (exit_code={exit_code})")
                _queue_auto_sync(run_id, topic)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


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
    resolved = _resolve_config_id(req.config_id)
    if not resolved:
        return RunStartResponse(
            status="error",
            run_id="",
            topic=None,
            command=[],
            log_path="",
            summary=f"Config nicht gefunden: {req.config_id}. Bitte configs.list verwenden.",
        )
    try:
        config_filename, config_text = _read_config_text(resolved)
    except Exception:
        return RunStartResponse(
            status="error",
            run_id="",
            topic=None,
            command=[],
            log_path="",
            summary=f"Config konnte nicht gelesen werden: {resolved}.",
        )

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
    _watch_run_for_autosync(run_id, proc, topic)
    summary = f"Run gestartet. ID: {run_id}. Config: {config_filename}."
    return RunStartResponse(
        status="started",
        run_id=run_id,
        topic=topic,
        command=cmd,
        log_path=log_path,
        summary=summary,
        auto_sync=AUTO_SYNC_AFTER_RUN,
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
        if (
            AUTO_SYNC_AFTER_RUN
            and exit_code == 0
            and meta.get("topic")
            and meta.get("auto_sync_state") not in {"queued", "running", "finished", "failed"}
        ):
            meta["auto_sync_state"] = "queued"
            _write_run_meta(run_id, meta)
            _queue_auto_sync(run_id, str(meta.get("topic")))

    log_tail = _tail_file(_run_log_path(run_id))
    block_alert = None
    if log_tail:
        if "YouTube IP Block detected" in log_tail or "YouTube blocked the request" in log_tail:
            block_alert = "YouTube IP Block detected (check proxy/credentials)."
    summary = None
    if state == "finished":
        summary = f"Run beendet. ID: {run_id}. Exit-Code: {exit_code}."
        if block_alert:
            summary = f"{summary} ALERT: {block_alert}"
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
        error=block_alert or meta.get("error"),
        summary=summary,
        auto_sync=AUTO_SYNC_AFTER_RUN,
        auto_sync_state=meta.get("auto_sync_state"),
        auto_sync_started_at=meta.get("auto_sync_started_at"),
        auto_sync_finished_at=meta.get("auto_sync_finished_at"),
        auto_sync_error=meta.get("auto_sync_error"),
        auto_sync_result=meta.get("auto_sync_result"),
    )


def _sync_topic_impl(safe_topic: str, req: SyncTopicRequest) -> SyncTopicResponse:
    cfg = _load_owui_collections_config()
    # Guard: lifecycle expects base topics, not already-suffixed derived targets.
    # Without this, callers get a confusing "missing transcripts.jsonl" (because indexes exist only for base topics).
    if safe_topic.endswith(cfg.new_suffix) or safe_topic.endswith(cfg.archive_suffix):
        return SyncTopicResponse(
            status="error",
            topic=safe_topic,
            last_error=f"refusing to sync derived topic; use base topic without suffix (suffixes: {cfg.new_suffix},{cfg.archive_suffix})",
            run_id=req.run_id,
        )
    if cfg.enabled and safe_topic.lower() not in cfg.excluded_topics:
        # Lifecycle routing: base topic -> <topic>_new + <topic>_archive
        # (No legacy "sync into <topic>" for lifecycle-enabled topics.)
        # Note: healing is still allowed but treats cold summaries as present.
        index_dir = os.path.join(_indexes_root(), safe_topic, "current")
        transcripts_jsonl = os.path.join(index_dir, "transcripts.jsonl")
        if not os.path.isfile(transcripts_jsonl):
            return SyncTopicResponse(status="not_found", topic=safe_topic, last_error="missing transcripts.jsonl", run_id=req.run_id)
        if not req.dry_run and req.heal_missing_summaries:
            missing = _list_missing_summaries(transcripts_jsonl)
            if missing:
                ok, err = _heal_missing_summaries(
                    topic=safe_topic,
                    timeout_s=req.heal_timeout_s,
                    poll_s=req.heal_poll_s,
                )
                if not ok:
                    return SyncTopicResponse(
                        status="error",
                        topic=safe_topic,
                        last_error=f"healing failed: {err}",
                        run_id=req.run_id,
                    )
        return _sync_topic_lifecycle(topic=safe_topic, req=req)

    knowledge_id, resolve_error = _resolve_or_create_knowledge_id(
        topic=safe_topic,
        create_flag=req.create_knowledge_if_missing,
    )
    if not knowledge_id:
        detail = resolve_error or "knowledge not found"
        return SyncTopicResponse(
            status="error",
            topic=safe_topic,
            last_error=f"{detail} (expected Knowledge name = topic, or set OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON; auto-create requires OPEN_WEBUI_CREATE_KNOWLEDGE_IF_MISSING=true and allowlist match)",
            run_id=req.run_id,
        )

    index_dir = os.path.join(_indexes_root(), safe_topic, "current")
    transcripts_jsonl = os.path.join(index_dir, "transcripts.jsonl")
    if not os.path.isfile(transcripts_jsonl):
        return SyncTopicResponse(status="not_found", topic=safe_topic, knowledge_id=knowledge_id, last_error="missing transcripts.jsonl", run_id=req.run_id)

    if not req.dry_run and req.heal_missing_summaries:
        missing = _list_missing_summaries(transcripts_jsonl)
        if missing:
            ok, err = _heal_missing_summaries(
                topic=safe_topic,
                timeout_s=req.heal_timeout_s,
                poll_s=req.heal_poll_s,
            )
            if not ok:
                return SyncTopicResponse(
                    status="error",
                    topic=safe_topic,
                    knowledge_id=knowledge_id,
                    last_error=f"healing failed: {err}",
                    run_id=req.run_id,
                )

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

            meta = {}
            meta_path = str(ref.get("metadata_path") or "")
            if meta_path:
                meta = _load_metadata(meta_path)

            payload = {
                "source_id": f"youtube:{video_id}",
                "text": body,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "knowledge_id": knowledge_id,
                "title": meta.get("video_title"),
                "channel": meta.get("channel_name") or meta.get("channel_handle") or ref.get("channel_namespace"),
                "published_at": meta.get("published_at") or ref.get("published_date"),
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
                        title=payload.get("title"),
                        channel=payload.get("channel"),
                        published_at=payload.get("published_at"),
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
        run_id=req.run_id,
    )


@app.post("/sync/topic/{topic}", summary="Index summaries for a topic into Open WebUI Knowledge", operation_id="sync_topic")
def sync_topic(topic: str, req: SyncTopicRequest) -> SyncTopicResponse:
    try:
        safe_topic = _safe_id(topic, label="topic")
    except ValueError:
        return SyncTopicResponse(status="error", topic=topic, last_error="invalid topic", run_id=req.run_id)

    guard_acquired = False
    if not req.dry_run:
        guard_acquired = _sync_topic_guard_acquire(safe_topic)
        if not guard_acquired:
            return SyncTopicResponse(
                status="busy",
                topic=safe_topic,
                last_error="sync already running for topic; wait for completion and retry",
                run_id=req.run_id,
            )
    try:
        return _sync_topic_impl(safe_topic, req)
    finally:
        if guard_acquired:
            _sync_topic_guard_release(safe_topic)


@app.post(
    "/sync/investing/lifecycle",
    summary="Rebuild investing_new/investing_archive from source topic with recency rules",
    operation_id="sync_investing_lifecycle",
)
def sync_investing_lifecycle(req: SyncTopicRequest) -> SyncTopicResponse:
    # Backwards-compatible alias; prefer /sync/lifecycle/{topic}.
    return _sync_topic_lifecycle(topic="investing", req=req)


@app.post(
    "/sync/lifecycle/{topic}",
    summary="Rebuild <topic>_new/<topic>_archive from source topic with global lifecycle rules",
    operation_id="sync_lifecycle",
)
def sync_lifecycle(topic: str, req: SyncTopicRequest) -> SyncTopicResponse:
    try:
        safe_topic = _safe_id(topic, label="topic")
    except ValueError:
        return SyncTopicResponse(status="error", topic=topic, last_error="invalid topic", run_id=req.run_id)
    cfg = _load_owui_collections_config()
    if safe_topic.lower() in cfg.excluded_topics:
        return SyncTopicResponse(
            status="error",
            topic=safe_topic,
            last_error=f"topic excluded from lifecycle routing: {safe_topic}",
            run_id=req.run_id,
        )
    return _sync_topic_lifecycle(topic=safe_topic, req=req)


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
