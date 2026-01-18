from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpenWebUIConfig:
    base_url: str
    api_key: str
    poll_interval_s: int = 3
    process_timeout_s: int = 900


def load_openwebui_cfg_from_env() -> OpenWebUIConfig | None:
    base_url = os.getenv("OPEN_WEBUI_BASE_URL", "http://open-webui:8080").strip().rstrip("/")
    api_key = (os.getenv("OPEN_WEBUI_API_KEY", "") or os.getenv("OWUI_API_KEY", "")).strip()
    if not api_key:
        return None
    poll_interval_s = int(os.getenv("OPEN_WEBUI_PROCESS_POLL_INTERVAL_SECONDS", "3"))
    process_timeout_s = int(os.getenv("OPEN_WEBUI_PROCESS_TIMEOUT_SECONDS", "900"))
    return OpenWebUIConfig(
        base_url=base_url,
        api_key=api_key,
        poll_interval_s=poll_interval_s,
        process_timeout_s=process_timeout_s,
    )


def _auth_headers(cfg: OpenWebUIConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {cfg.api_key}", "Accept": "application/json"}


def render_markdown(*, title: str | None, url: str, meta: dict[str, Any], markdown: str) -> str:
    meta_clean = {k: v for k, v in (meta or {}).items() if v not in (None, "", [])}
    if title:
        meta_clean = {"title": title, **meta_clean}
    if url:
        meta_clean = {"url": url, **meta_clean}

    def yaml_value(v: Any) -> str:
        if v is None:
            return "null"
        if isinstance(v, (int, float)):
            return str(v)
        return json.dumps(str(v), ensure_ascii=False)

    frontmatter = "\n".join([f"{k}: {yaml_value(v)}" for k, v in meta_clean.items()])
    body = markdown.strip() + "\n"
    if frontmatter:
        return f"---\n{frontmatter}\n---\n\n{body}"
    return body


def upload_markdown(*, cfg: OpenWebUIConfig, markdown: str, filename: str) -> str:
    import tempfile

    import requests

    url = f"{cfg.base_url}/api/v1/files/"
    params = {"process": "true", "process_in_background": "true"}
    headers = _auth_headers(cfg)
    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=True, encoding="utf-8") as tmp:
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
        raise RuntimeError(f"openwebui upload failed: {resp.status_code} {resp.text}")
    data = resp.json()
    file_id = data.get("id") or data.get("file_id")
    if not file_id:
        raise RuntimeError(f"openwebui upload response missing id: {data}")
    return str(file_id)


def poll_processing(*, cfg: OpenWebUIConfig, file_id: str) -> dict[str, Any]:
    import requests

    url = f"{cfg.base_url}/api/v1/files/{file_id}/process/status"
    headers = _auth_headers(cfg)
    deadline = time.time() + cfg.process_timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code >= 400:
            raise RuntimeError(f"openwebui process status failed: {resp.status_code} {resp.text}")
        last = resp.json()
        status = (last.get("status") or "").lower()
        if status in {"completed", "failed"}:
            return last
        time.sleep(cfg.poll_interval_s)
    raise RuntimeError(f"openwebui process status timeout: {last}")


def add_to_knowledge(*, cfg: OpenWebUIConfig, knowledge_id: str, file_id: str) -> dict[str, Any]:
    import requests

    url = f"{cfg.base_url}/api/v1/knowledge/{knowledge_id}/file/add"
    headers = _auth_headers(cfg) | {"Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={"file_id": file_id}, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"openwebui knowledge add failed: {resp.status_code} {resp.text}")
    return resp.json() if resp.content else {"status": "ok"}


def list_knowledge(*, cfg: OpenWebUIConfig) -> list[dict[str, Any]]:
    import requests

    url = f"{cfg.base_url}/api/v1/knowledge/"
    headers = _auth_headers(cfg)
    resp = requests.get(url, headers=headers, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"openwebui knowledge list failed: {resp.status_code} {resp.text}")
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


def find_knowledge_by_name(*, cfg: OpenWebUIConfig, name: str) -> dict[str, Any] | None:
    name_norm = (name or "").strip().casefold()
    if not name_norm:
        return None
    for kb in list_knowledge(cfg=cfg):
        kb_name = str(kb.get("name") or "").strip().casefold()
        if kb_name == name_norm:
            return kb
    return None


def create_knowledge(*, cfg: OpenWebUIConfig, name: str, description: str | None = None) -> dict[str, Any]:
    import requests

    url = f"{cfg.base_url}/api/v1/knowledge/create"
    headers = _auth_headers(cfg) | {"Content-Type": "application/json"}
    payload: dict[str, Any] = {"name": name}
    if description is not None:
        payload["description"] = description
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"openwebui knowledge create failed: {resp.status_code} {resp.text}")
    return resp.json() if resp.content else {"status": "ok"}


def list_knowledge_files(*, cfg: OpenWebUIConfig, knowledge_id: str) -> list[dict[str, Any]]:
    import requests

    url = f"{cfg.base_url}/api/v1/knowledge/{knowledge_id}/files"
    headers = _auth_headers(cfg)
    resp = requests.get(url, headers=headers, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"openwebui knowledge files list failed: {resp.status_code} {resp.text}")
    data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("files"), list):
        return list(data["files"])
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return list(data["data"])
    return []
