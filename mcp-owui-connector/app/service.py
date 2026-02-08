from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class OwuiConnectorConfig:
    open_webui_base_url: str
    open_webui_api_key: str
    allow_knowledge_write: bool
    allow_admin_write: bool
    imports_dir: str
    request_timeout_seconds: int
    process_poll_interval_seconds: int
    process_timeout_seconds: int
    max_tool_text_chars: int


class OwuiConnectorService:
    def __init__(self, cfg: OwuiConnectorConfig) -> None:
        self.cfg = cfg

    @classmethod
    def from_env(cls) -> "OwuiConnectorService":
        base_url = (os.getenv("OPEN_WEBUI_BASE_URL", "http://owui:8080") or "").rstrip("/")
        api_key = (os.getenv("OPEN_WEBUI_API_KEY", "") or os.getenv("OWUI_API_KEY", "") or "").strip()
        cfg = OwuiConnectorConfig(
            open_webui_base_url=base_url,
            open_webui_api_key=api_key,
            allow_knowledge_write=_env_bool("OWUI_CONNECTOR_ALLOW_KNOWLEDGE_WRITE", False),
            allow_admin_write=_env_bool("OWUI_CONNECTOR_ALLOW_ADMIN_WRITE", False),
            imports_dir=(os.getenv("OWUI_CONNECTOR_IMPORTS_DIR", "/imports") or "/imports").strip(),
            request_timeout_seconds=max(1, int(os.getenv("OWUI_CONNECTOR_REQUEST_TIMEOUT_SECONDS", "60"))),
            process_poll_interval_seconds=max(1, int(os.getenv("OWUI_CONNECTOR_PROCESS_POLL_INTERVAL_SECONDS", "3"))),
            process_timeout_seconds=max(5, int(os.getenv("OWUI_CONNECTOR_PROCESS_TIMEOUT_SECONDS", "900"))),
            max_tool_text_chars=max(1000, int(os.getenv("OWUI_CONNECTOR_MAX_TOOL_TEXT_CHARS", "12000"))),
        )
        return cls(cfg)

    def _auth_headers(self) -> dict[str, str]:
        if not self.cfg.open_webui_api_key:
            raise RuntimeError("OPEN_WEBUI_API_KEY/OWUI_API_KEY is not set")
        return {"Authorization": f"Bearer {self.cfg.open_webui_api_key}", "Accept": "application/json"}

    def _capabilities_markdown(self) -> str:
        lines = [
            "# owui-connector (MCP)",
            "",
            "Expose selected Open WebUI APIs as MCP tools.",
            "",
            "## Config",
            f"- OPEN_WEBUI_BASE_URL: `{self.cfg.open_webui_base_url}`",
            f"- OWUI_CONNECTOR_ALLOW_KNOWLEDGE_WRITE: `{str(self.cfg.allow_knowledge_write).lower()}`",
            f"- OWUI_CONNECTOR_ALLOW_ADMIN_WRITE: `{str(self.cfg.allow_admin_write).lower()}`",
            "",
            "## Tools",
            "- `owui.knowledge.list`",
            "- `owui.knowledge.create` (gated)",
            "- `owui.knowledge.files.list`",
            "- `owui.files.process.status`",
            "- `owui.tool_servers.get`",
            "- `owui.tool_servers.apply_from_repo` (gated)",
            "- `owui.knowledge.upload_markdown` (gated)",
            "- `owui.knowledge.file.remove` (gated)",
        ]
        return "\n".join(lines)

    def _truncate_payload(self, obj: Any) -> Any:
        """
        Avoid returning huge payloads into the LLM: this service is a connector, not a bulk export API.
        """
        try:
            raw = json.dumps(obj, ensure_ascii=False)
        except Exception:
            return obj
        if len(raw) <= self.cfg.max_tool_text_chars:
            return obj
        return {"status": "truncated", "max_chars": self.cfg.max_tool_text_chars, "preview": raw[: self.cfg.max_tool_text_chars]}

    # ---------- Open WebUI APIs ----------
    def owui_tool_servers_get(self) -> Any:
        url = f"{self.cfg.open_webui_base_url}/api/v1/configs/tool_servers"
        resp = requests.get(url, headers=self._auth_headers(), timeout=self.cfg.request_timeout_seconds)
        if resp.status_code >= 400:
            raise RuntimeError(f"tool_servers get failed: {resp.status_code} {resp.text}")
        return resp.json()

    def owui_tool_servers_apply(self, connections: list[dict[str, Any]]) -> Any:
        if not self.cfg.allow_admin_write:
            raise RuntimeError("Admin writes disabled (set OWUI_CONNECTOR_ALLOW_ADMIN_WRITE=true)")
        url = f"{self.cfg.open_webui_base_url}/api/v1/configs/tool_servers"
        headers = self._auth_headers() | {"Content-Type": "application/json"}
        payload = {"TOOL_SERVER_CONNECTIONS": connections}
        resp = requests.post(url, headers=headers, json=payload, timeout=self.cfg.request_timeout_seconds)
        if resp.status_code >= 400:
            raise RuntimeError(f"tool_servers apply failed: {resp.status_code} {resp.text}")
        return {"status": "ok"}

    def _read_repo_imports(self, imports_dir: str) -> list[dict[str, Any]]:
        p = Path(imports_dir)
        if not p.is_dir():
            raise RuntimeError(f"imports_dir not found: {imports_dir}")
        files = sorted([x for x in p.glob("*.json") if not x.name.startswith("backup_tool_servers__")])
        if not files:
            raise RuntimeError(f"no import json files found under: {imports_dir}")
        connections: list[dict[str, Any]] = []
        for f in files:
            text = f.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, list):
                raise RuntimeError(f"import file must be JSON array: {f}")
            for item in data:
                if isinstance(item, dict):
                    connections.append(item)
        return connections

    def owui_tool_servers_apply_from_repo(self, *, imports_dir: str | None, dry_run: bool) -> Any:
        if not self.cfg.allow_admin_write:
            raise RuntimeError("Admin writes disabled (set OWUI_CONNECTOR_ALLOW_ADMIN_WRITE=true)")
        imp_dir = (imports_dir or self.cfg.imports_dir).strip() or self.cfg.imports_dir
        connections = self._read_repo_imports(imp_dir)

        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        backup_path = Path("/data") / f"backup_tool_servers__{ts}.json"
        try:
            backup = self.owui_tool_servers_get()
            backup_path.write_text(json.dumps(backup, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            # Best-effort backup; do not block apply.
            backup_path.write_text(
                json.dumps({"note": "backup failed", "error": str(e)}, ensure_ascii=False),
                encoding="utf-8",
            )

        if dry_run:
            return {"dry_run": True, "imports_dir": imp_dir, "count": len(connections), "payload": {"TOOL_SERVER_CONNECTIONS": connections}}

        res = self.owui_tool_servers_apply(connections)
        return {"imports_dir": imp_dir, "count": len(connections), "backup_path": str(backup_path), **res}

    def owui_knowledge_list(self) -> list[dict[str, Any]]:
        url = f"{self.cfg.open_webui_base_url}/api/v1/knowledge/"
        resp = requests.get(url, headers=self._auth_headers(), timeout=self.cfg.request_timeout_seconds)
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

    def owui_knowledge_create(self, *, name: str, description: str) -> dict[str, Any]:
        if not self.cfg.allow_knowledge_write:
            raise RuntimeError("Knowledge writes disabled (set OWUI_CONNECTOR_ALLOW_KNOWLEDGE_WRITE=true)")
        nm = (name or "").strip()
        if not nm:
            raise RuntimeError("name is required")
        url = f"{self.cfg.open_webui_base_url}/api/v1/knowledge/create"
        headers = self._auth_headers() | {"Content-Type": "application/json"}
        payload = {"name": nm, "description": (description or "")}
        resp = requests.post(url, headers=headers, json=payload, timeout=self.cfg.request_timeout_seconds)
        if resp.status_code >= 400:
            raise RuntimeError(f"knowledge create failed: {resp.status_code} {resp.text}")
        data = resp.json() if resp.content else {"status": "ok"}
        return data if isinstance(data, dict) else {"status": "ok", "raw": data}

    def owui_knowledge_files_list(self, *, knowledge_id: str, limit: int) -> list[dict[str, Any]]:
        kid = (knowledge_id or "").strip()
        if not kid:
            raise RuntimeError("knowledge_id is required")
        url = f"{self.cfg.open_webui_base_url}/api/v1/knowledge/{kid}/files"
        headers = self._auth_headers()
        page = 0
        page_limit = 200
        files: list[dict[str, Any]] = []
        while True:
            resp = requests.get(
                url,
                headers=headers,
                params={"page": page, "limit": page_limit},
                timeout=self.cfg.request_timeout_seconds,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"knowledge files failed: {resp.status_code} {resp.text}")
            data = resp.json()
            batch = data.get("items") or data.get("files") or []
            if not batch:
                break
            for item in batch:
                if isinstance(item, dict):
                    files.append(item)
                    if limit > 0 and len(files) >= limit:
                        return files
            if len(batch) < page_limit:
                break
            page += 1
        return files

    def owui_files_process_status(self, *, file_id: str) -> dict[str, Any]:
        fid = (file_id or "").strip()
        if not fid:
            raise RuntimeError("file_id is required")
        url = f"{self.cfg.open_webui_base_url}/api/v1/files/{fid}/process/status"
        resp = requests.get(url, headers=self._auth_headers(), timeout=self.cfg.request_timeout_seconds)
        if resp.status_code >= 400:
            raise RuntimeError(f"process status failed: {resp.status_code} {resp.text}")
        data = resp.json()
        return data if isinstance(data, dict) else {"status": "unknown", "raw": data}

    def owui_upload_markdown_to_knowledge(
        self,
        *,
        knowledge_id: str,
        filename: str,
        markdown: str,
        wait_for_processing: bool,
    ) -> dict[str, Any]:
        if not self.cfg.allow_knowledge_write:
            raise RuntimeError("Knowledge writes disabled (set OWUI_CONNECTOR_ALLOW_KNOWLEDGE_WRITE=true)")
        kid = (knowledge_id or "").strip()
        if not kid:
            raise RuntimeError("knowledge_id is required")
        fname = (filename or "").strip()
        if not fname:
            raise RuntimeError("filename is required")

        # 1) upload file
        file_id = self._owui_upload_file(markdown=markdown, filename=fname)
        status: dict[str, Any] | None = None
        if wait_for_processing:
            status = self._owui_poll_processing(file_id)

        # 2) add to knowledge
        add_res = self._owui_add_to_knowledge(kid, file_id)
        out: dict[str, Any] = {"file_id": file_id, "knowledge_id": kid, "add_result": add_res}
        if status is not None:
            out["process_status"] = status
        return out

    def owui_knowledge_file_remove(self, *, knowledge_id: str, file_id: str) -> dict[str, Any]:
        if not self.cfg.allow_knowledge_write:
            raise RuntimeError("Knowledge writes disabled (set OWUI_CONNECTOR_ALLOW_KNOWLEDGE_WRITE=true)")
        kid = (knowledge_id or "").strip()
        fid = (file_id or "").strip()
        if not kid or not fid:
            raise RuntimeError("knowledge_id and file_id are required")
        url = f"{self.cfg.open_webui_base_url}/api/v1/knowledge/{kid}/file/remove"
        headers = self._auth_headers() | {"Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, json={"file_id": fid}, timeout=self.cfg.request_timeout_seconds)
        if resp.status_code >= 400:
            raise RuntimeError(f"knowledge remove failed: {resp.status_code} {resp.text}")
        return resp.json() if resp.content else {"status": "ok"}

    def _owui_upload_file(self, *, markdown: str, filename: str) -> str:
        import tempfile

        url = f"{self.cfg.open_webui_base_url}/api/v1/files/"
        params = {"process": "true", "process_in_background": "true"}
        headers = self._auth_headers()
        with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=True) as tmp:
            tmp.write(markdown)
            tmp.flush()
            with open(tmp.name, "rb") as fh:
                resp = requests.post(
                    url,
                    params=params,
                    headers=headers,
                    files={"file": (filename, fh, "text/markdown")},
                    timeout=self.cfg.request_timeout_seconds,
                )
        if resp.status_code >= 400:
            raise RuntimeError(f"upload failed: {resp.status_code} {resp.text}")
        data = resp.json()
        file_id = data.get("id") or data.get("file_id")
        if not file_id:
            raise RuntimeError(f"upload response missing id: {data}")
        return str(file_id)

    def _owui_poll_processing(self, file_id: str) -> dict[str, Any]:
        url = f"{self.cfg.open_webui_base_url}/api/v1/files/{file_id}/process/status"
        headers = self._auth_headers()
        deadline = time.time() + self.cfg.process_timeout_seconds
        last: dict[str, Any] = {}
        while time.time() < deadline:
            resp = requests.get(url, headers=headers, timeout=self.cfg.request_timeout_seconds)
            if resp.status_code >= 400:
                raise RuntimeError(f"process status failed: {resp.status_code} {resp.text}")
            last = resp.json()
            status = (last.get("status") or "").lower()
            if status in {"completed", "failed"}:
                return last
            time.sleep(self.cfg.process_poll_interval_seconds)
        raise RuntimeError(f"process status timeout: {last}")

    def _owui_add_to_knowledge(self, knowledge_id: str, file_id: str) -> dict[str, Any]:
        url = f"{self.cfg.open_webui_base_url}/api/v1/knowledge/{knowledge_id}/file/add"
        headers = self._auth_headers() | {"Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, json={"file_id": file_id}, timeout=self.cfg.request_timeout_seconds)
        if resp.status_code >= 400:
            raise RuntimeError(f"knowledge add failed: {resp.status_code} {resp.text}")
        return resp.json() if resp.content else {"status": "ok"}

    # ---------- MCP dispatcher ----------
    def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        name = (name or "").strip()
        if name == "capabilities.get":
            max_chars_raw = (args or {}).get("max_chars")
            try:
                max_chars = int(max_chars_raw) if max_chars_raw is not None else 4000
            except Exception:
                max_chars = 4000
            text = self._capabilities_markdown()
            if max_chars > 0 and len(text) > max_chars:
                return text[: max_chars - 32] + "\n\n...(truncated)"
            return text

        if name == "owui.knowledge.list":
            q = str((args or {}).get("query") or "").strip().casefold()
            limit_raw = (args or {}).get("limit")
            try:
                limit = int(limit_raw) if limit_raw is not None else 50
            except Exception:
                limit = 50
            items = self.owui_knowledge_list()
            if q:
                items = [x for x in items if q in str(x.get("name") or "").strip().casefold()]
            if limit > 0:
                items = items[:limit]
            return {"items": items, "count": len(items)}

        if name == "owui.knowledge.create":
            nm = str((args or {}).get("name") or "").strip()
            desc = str((args or {}).get("description") or "")
            return self._truncate_payload(self.owui_knowledge_create(name=nm, description=desc))

        if name == "owui.knowledge.files.list":
            kid = str((args or {}).get("knowledge_id") or "").strip()
            limit_raw = (args or {}).get("limit")
            try:
                limit = int(limit_raw) if limit_raw is not None else 50
            except Exception:
                limit = 50
            raw_items = self.owui_knowledge_files_list(knowledge_id=kid, limit=limit)
            items = [self._slim_knowledge_file_item(x) for x in raw_items if isinstance(x, dict)]
            return {"knowledge_id": kid, "count": len(items), "items": items}

        if name == "owui.files.process.status":
            fid = str((args or {}).get("file_id") or "").strip()
            return self.owui_files_process_status(file_id=fid)

        if name == "owui.tool_servers.get":
            return self._truncate_payload(self.owui_tool_servers_get())

        if name == "owui.tool_servers.apply_from_repo":
            imp = (args or {}).get("imports_dir")
            imports_dir = str(imp).strip() if isinstance(imp, str) and imp.strip() else None
            dry = bool((args or {}).get("dry_run") is True)
            return self._truncate_payload(self.owui_tool_servers_apply_from_repo(imports_dir=imports_dir, dry_run=dry))

        if name == "owui.knowledge.upload_markdown":
            kid = str((args or {}).get("knowledge_id") or "").strip()
            filename = str((args or {}).get("filename") or "").strip()
            markdown = str((args or {}).get("markdown") or "")
            wait_raw = (args or {}).get("wait_for_processing")
            wait = True if wait_raw is None else bool(wait_raw)
            return self._truncate_payload(
                self.owui_upload_markdown_to_knowledge(
                    knowledge_id=kid,
                    filename=filename,
                    markdown=markdown,
                    wait_for_processing=wait,
                )
            )

        if name == "owui.knowledge.file.remove":
            kid = str((args or {}).get("knowledge_id") or "").strip()
            fid = str((args or {}).get("file_id") or "").strip()
            return self._truncate_payload(self.owui_knowledge_file_remove(knowledge_id=kid, file_id=fid))

        raise RuntimeError(f"unknown tool: {name}")

    def _slim_knowledge_file_item(self, item: dict[str, Any]) -> dict[str, Any]:
        # Open WebUI can include large processed content in `data.content`; never return full content here.
        out: dict[str, Any] = {}
        for key in ("id", "file_id", "name", "filename", "title", "created_at", "updated_at", "status"):
            if key in item and item[key] is not None:
                out[key] = item[key]
        if "data" in item and isinstance(item["data"], dict):
            data = item["data"]
            for key in ("source", "source_id", "url", "content_type"):
                if key in data and data[key] is not None:
                    out.setdefault("data", {})[key] = data[key]
        return out
