from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .chunking import chunk_markdown
from .db import Db
from .ids import chunk_id as make_chunk_id
from .ids import doc_id as make_doc_id
from .ids import job_id as make_job_id
from .ids import snapshot_id as make_snapshot_id
from .ids import source_id as make_source_id
from .ids import sha256_hex
from .models import (
    CrawlSourceConfig,
    GithubSourceConfig,
    LocalSourceConfig,
    SourceLimits,
    SourcesCreateRequest,
)
from .normalize import normalize_html, normalize_markdown
from .openwebui_indexer import (
    add_to_knowledge,
    create_knowledge,
    find_knowledge_by_name,
    list_knowledge,
    list_knowledge_files,
    load_openwebui_cfg_from_env,
    poll_processing,
    render_markdown,
    upload_markdown,
)
from .search import make_snippet, rrf_fuse
from .sources import CrawlFetcher, GithubFetcher, LocalFetcher, canonicalize_url
from .time_utils import now_utc_iso


class ToolUserError(RuntimeError):
    def __init__(self, message: str, *, data: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.data = data or {}


@dataclass(frozen=True)
class Context6Paths:
    data_dir: Path
    cache_dir: Path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "context6.sqlite3"

    @property
    def docs_dir(self) -> Path:
        return self.data_dir / "docs"


def _ensure_dirs(paths: Context6Paths) -> None:
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.cache_dir.mkdir(parents=True, exist_ok=True)
    paths.docs_dir.mkdir(parents=True, exist_ok=True)

def _normalize_github_repo(value: str) -> str:
    v = (value or "").strip()
    if v.startswith("https://github.com/"):
        v = v[len("https://github.com/") :]
    if v.startswith("http://github.com/"):
        v = v[len("http://github.com/") :]
    v = v.strip("/")
    if v.endswith(".git"):
        v = v[: -len(".git")]
    return v


def _normalize_source_config(*, source_type: str, config: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize common user/LLM config variants into the canonical stored shape:
      - github: {"github": {...}}
      - crawl:  {"crawl": {...}}
      - local:  {"local": {...}}

    This makes the MCP tool more robust to slightly wrong argument shapes (e.g. `config.repo`).
    """
    cfg = config or {}

    if source_type == "github":
        gh = cfg.get("github") if isinstance(cfg.get("github"), dict) else None
        if gh is None:
            gh = dict(cfg)
        if "url" in gh and "repo" not in gh:
            gh["repo"] = _normalize_github_repo(str(gh.get("url") or ""))
        if "repo" in gh:
            gh["repo"] = _normalize_github_repo(str(gh.get("repo") or ""))

        # Apply defaults via model (keep only known keys).
        gh_model = GithubSourceConfig.model_validate(gh)
        return {"github": gh_model.model_dump()}

    if source_type == "crawl":
        cr = cfg.get("crawl") if isinstance(cfg.get("crawl"), dict) else None
        if cr is None:
            cr = dict(cfg)
        cr_model = CrawlSourceConfig.model_validate(cr)
        return {"crawl": cr_model.model_dump()}

    if source_type == "local":
        loc = cfg.get("local") if isinstance(cfg.get("local"), dict) else None
        if loc is None:
            loc = dict(cfg)
        loc_model = LocalSourceConfig.model_validate(loc)
        return {"local": loc_model.model_dump()}

    raise ValueError(f"Unknown source type: {source_type}")

def _slugify_filename_part(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    t = re.sub(r"-{2,}", "-", t).strip("-")
    return t or "doc"


def _make_owui_filename(*, canonical_path: str, doc_id: str) -> str:
    """
    Produce human-friendly but stable filenames for Open WebUI uploads.
    - derived from canonical_path (e.g. repo path or URL path)
    - includes a short doc_id suffix for uniqueness
    """
    cp = (canonical_path or "").strip().strip("/")
    cp = re.sub(r"\\.(md|mdx|html?)$", "", cp, flags=re.IGNORECASE)
    parts = [_slugify_filename_part(p) for p in re.split(r"[\\\\/]+", cp) if p]
    slug = "__".join(parts[-6:]) if parts else "doc"

    short = (doc_id or "")[:12] or "unknown"
    prefix = "context6__"
    suffix = f"__{short}.md"

    max_len = 180
    max_slug_len = max_len - len(prefix) - len(suffix)
    if max_slug_len < 8:
        max_slug_len = 8
    if len(slug) > max_slug_len:
        slug = slug[:max_slug_len].rstrip("_-")

    return f"{prefix}{slug}{suffix}"


class Context6Service:
    def __init__(self, *, db: Db, paths: Context6Paths) -> None:
        self._db = db
        self._paths = paths
        self._job_threads: dict[str, threading.Thread] = {}

    def create_source(self, req: SourcesCreateRequest) -> dict[str, Any]:
        # Validate + normalize config by type.
        config = _normalize_source_config(source_type=req.type, config=req.config)
        if req.type == "github":
            canonical_uri = f"github:{(config.get('github') or {}).get('repo','')}"
        elif req.type == "crawl":
            first = ((config.get("crawl") or {}).get("start_urls") or [""])[0]
            canonical_uri = canonicalize_url(str(first))
        elif req.type == "local":
            canonical_uri = f"local:{(config.get('local') or {}).get('root','')}"
        else:
            raise ValueError(f"Unknown source type: {req.type}")

        sid = make_source_id(type=req.type, canonical_uri=canonical_uri)
        created_at = now_utc_iso()
        name = (req.name or "").strip() or sid
        config_json = json.dumps(config, sort_keys=True)
        limits_json = req.limits.model_dump_json()

        conn = self._db.connect()
        try:
            row = conn.execute(
                "SELECT name, config_json, limits_json FROM sources WHERE source_id = ?",
                (sid,),
            ).fetchone()
            exists = row is not None
            updated = False
            if not exists:
                conn.execute(
                    "INSERT INTO sources(source_id, type, name, config_json, limits_json, created_at_utc) VALUES (?,?,?,?,?,?)",
                    (
                        sid,
                        req.type,
                        name,
                        config_json,
                        limits_json,
                        created_at,
                    ),
                )
                updated = True
            else:
                # "create" is idempotent by source_id; update stored fields in-place.
                if str(row["name"]) != name or str(row["config_json"]) != config_json or str(row["limits_json"]) != limits_json:
                    conn.execute(
                        "UPDATE sources SET name = ?, config_json = ?, limits_json = ? WHERE source_id = ?",
                        (name, config_json, limits_json, sid),
                    )
                    updated = True
            conn.commit()
            return {"source_id": sid, "created": not exists, "updated": updated}
        finally:
            conn.close()

    def list_sources(self) -> list[dict[str, Any]]:
        conn = self._db.connect()
        try:
            rows = conn.execute("SELECT source_id, type, name, created_at_utc FROM sources ORDER BY created_at_utc DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_source(self, source_id: str) -> dict[str, Any]:
        conn = self._db.connect()
        try:
            conn.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))
            conn.commit()
            return {"deleted": True}
        finally:
            conn.close()

    def _require_openwebui_cfg(self):
        cfg = load_openwebui_cfg_from_env()
        if not cfg:
            raise ToolUserError(
                "Open WebUI not configured (set OPEN_WEBUI_API_KEY / OWUI_API_KEY and optional OPEN_WEBUI_BASE_URL)"
            )
        return cfg

    def owui_list_knowledge(self, *, query: str | None = None, limit: int = 200) -> dict[str, Any]:
        cfg = self._require_openwebui_cfg()
        items = list_knowledge(cfg=cfg)
        out: list[dict[str, Any]] = []
        q = (query or "").strip().casefold()
        for kb in items:
            kid = kb.get("id") or kb.get("knowledge_id")
            name = kb.get("name")
            if not kid or not name:
                continue
            if q and q not in str(name).casefold():
                continue
            out.append({"id": str(kid), "name": str(name), "description": kb.get("description")})
            if len(out) >= int(limit):
                break
        return {"knowledge": out}

    def owui_create_knowledge(self, *, name: str, description: str | None = None) -> dict[str, Any]:
        cfg = self._require_openwebui_cfg()
        res = create_knowledge(cfg=cfg, name=name, description=description)
        kid = res.get("id") or res.get("knowledge_id")
        if not kid:
            # Fallback: lookup by name after creation.
            found = find_knowledge_by_name(cfg=cfg, name=name)
            kid = (found or {}).get("id") or (found or {}).get("knowledge_id")
        return {"id": str(kid) if kid else None, "name": name, "raw": res}

    def sync_prepare(self, *, source_id: str) -> dict[str, Any]:
        cfg = self._require_openwebui_cfg()

        conn = self._db.connect()
        try:
            row = conn.execute("SELECT name, type FROM sources WHERE source_id = ?", (source_id,)).fetchone()
        finally:
            conn.close()

        base = (row["name"] if row else source_id) if row else source_id
        suggested = str(base).strip() or "knowledge"

        # Keep it small: return only id + name for the first N.
        items = list_knowledge(cfg=cfg)
        options: list[dict[str, Any]] = []
        for kb in items:
            kid = kb.get("id") or kb.get("knowledge_id")
            name = kb.get("name")
            if not kid or not name:
                continue
            options.append({"id": str(kid), "name": str(name)})
            if len(options) >= 50:
                break

        return {"suggested_knowledge_name": suggested, "existing": options}

    def start_sync(
        self,
        *,
        source_id: str,
        mode: str,
        knowledge_id: str | None = None,
        knowledge_name: str | None = None,
        create_knowledge_if_missing: bool = False,
    ) -> dict[str, Any]:
        resolved_knowledge_id: str | None = (knowledge_id or "").strip() or None
        resolved_knowledge_name: str | None = (knowledge_name or "").strip() or None

        if resolved_knowledge_name and resolved_knowledge_id:
            raise ToolUserError("Provide either knowledge_id or knowledge_name (not both)")

        if resolved_knowledge_name:
            cfg = self._require_openwebui_cfg()
            found = find_knowledge_by_name(cfg=cfg, name=resolved_knowledge_name)
            if found:
                resolved_knowledge_id = str(found.get("id") or found.get("knowledge_id") or "")
            elif create_knowledge_if_missing:
                created = create_knowledge(cfg=cfg, name=resolved_knowledge_name)
                resolved_knowledge_id = str(created.get("id") or created.get("knowledge_id") or "")
            else:
                prep = self.sync_prepare(source_id=source_id)
                raise ToolUserError(
                    "Knowledge base not found. Pick an existing one, or set create_knowledge_if_missing=true.",
                    data=prep,
                )

        created = now_utc_iso()
        jid = make_job_id(source_id=source_id, created_at_utc=created, nonce=uuid4().hex)

        conn = self._db.connect()
        try:
            conn.execute(
                "INSERT INTO jobs(job_id, source_id, knowledge_id, knowledge_name, status, created_at_utc, counts_json, errors_json) VALUES (?,?,?,?,?,?,?,?)",
                (jid, source_id, resolved_knowledge_id, resolved_knowledge_name, "queued", created, json.dumps({}), json.dumps([])),
            )
            conn.commit()
        finally:
            conn.close()

        t = threading.Thread(target=self._run_sync_job, args=(jid, source_id, mode, resolved_knowledge_id), daemon=True)
        self._job_threads[jid] = t
        t.start()
        hint: dict[str, Any] = {"job_id": jid, "accepted": True}
        if resolved_knowledge_id:
            hint["knowledge_id"] = resolved_knowledge_id
            if resolved_knowledge_name:
                hint["knowledge_name"] = resolved_knowledge_name
            hint["next"] = (
                "Monitor progress via sync.status. "
                "In Open WebUI: Workspace → Knowledge → open the collection → Files."
            )
        else:
            hint["notice"] = (
                "No Open WebUI Knowledge target set; sync will index locally only. "
                "If you want Open WebUI Knowledge embedding, call sync.prepare and then rerun sync.start with knowledge_name/knowledge_id."
            )
        return hint

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        conn = self._db.connect()
        try:
            row = conn.execute(
                "SELECT job_id, source_id, snapshot_id, knowledge_id, knowledge_name, status, counts_json, errors_json, last_error FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if not row:
                return None
            res: dict[str, Any] = {
                "job_id": row["job_id"],
                "source_id": row["source_id"],
                "snapshot_id": row["snapshot_id"],
                "knowledge_id": row["knowledge_id"],
                "knowledge_name": row["knowledge_name"],
                "status": row["status"],
                "counts": json.loads(row["counts_json"]),
                "errors": json.loads(row["errors_json"]),
                "last_error": row["last_error"],
            }
            # Best-effort visibility: if we're syncing to Open WebUI, include current files count.
            kid = (row["knowledge_id"] or "").strip()
            if kid:
                try:
                    cfg = load_openwebui_cfg_from_env()
                    if cfg:
                        res["knowledge_files_count"] = len(list_knowledge_files(cfg=cfg, knowledge_id=kid))
                except Exception:
                    pass
            return res
        finally:
            conn.close()

    def list_snapshots(self, *, source_id: str, limit: int) -> list[dict[str, Any]]:
        conn = self._db.connect()
        try:
            rows = conn.execute(
                "SELECT snapshot_id, resolved_ref, started_at_utc, finished_at_utc, status, counts_json FROM snapshots WHERE source_id = ? ORDER BY started_at_utc DESC LIMIT ?",
                (source_id, int(limit)),
            ).fetchall()
            out = []
            for r in rows:
                out.append(
                    {
                        "snapshot_id": r["snapshot_id"],
                        "resolved_ref": r["resolved_ref"],
                        "created_at": r["started_at_utc"],
                        "status": r["status"],
                        "counts": json.loads(r["counts_json"]),
                    }
                )
            return out
        finally:
            conn.close()

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        conn = self._db.connect()
        try:
            row = conn.execute(
                "SELECT c.chunk_id, c.doc_id, c.heading_path, c.text, v.url_or_path, v.title, d.source_id, d.latest_snapshot_id, c.chunk_index "
                "FROM chunks c "
                "JOIN documents d ON d.doc_id = c.doc_id "
                "LEFT JOIN chunk_versions v ON v.chunk_id = c.chunk_id AND v.snapshot_id = d.latest_snapshot_id "
                "WHERE c.chunk_id = ?",
                (chunk_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "chunk_id": row["chunk_id"],
                "doc_id": row["doc_id"],
                "url": row["url_or_path"] or "",
                "heading_path": row["heading_path"],
                "text": row["text"],
                "meta": {
                    "source_id": row["source_id"],
                    "snapshot_id": row["latest_snapshot_id"],
                    "chunk_index": row["chunk_index"],
                    "title": row["title"],
                },
            }
        finally:
            conn.close()

    def get_doc(self, doc_id: str) -> dict[str, Any] | None:
        conn = self._db.connect()
        try:
            doc = conn.execute(
                "SELECT doc_id, title, latest_snapshot_id FROM documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
            if not doc:
                return None
            dv = conn.execute(
                "SELECT url_or_path, normalized_path FROM document_versions WHERE doc_id = ? AND snapshot_id = ?",
                (doc_id, doc["latest_snapshot_id"]),
            ).fetchone()
            if not dv:
                return None
            content = Path(dv["normalized_path"]).read_text(encoding="utf-8")
            chunks = conn.execute(
                "SELECT chunk_id, heading_path, chunk_index FROM chunks WHERE doc_id = ? ORDER BY chunk_index ASC",
                (doc_id,),
            ).fetchall()
            return {
                "doc_id": doc["doc_id"],
                "title": doc["title"],
                "url": dv["url_or_path"],
                "content_normalized": content,
                "chunks": [{"chunk_id": r["chunk_id"], "heading_path": r["heading_path"], "chunk_index": r["chunk_index"]} for r in chunks],
            }
        finally:
            conn.close()

    def search(self, *, query: str, top_k: int, source_id: str | None, snapshot_id: str | None) -> list[dict[str, Any]]:
        top_k = int(top_k)
        conn = self._db.connect()
        try:
            where: list[str] = []
            params: list[Any] = []
            if source_id:
                where.append("cv.source_id = ?")
                params.append(source_id)
            if snapshot_id:
                where.append("cv.snapshot_id = ?")
                params.append(snapshot_id)
            where.append("chunks_fts MATCH ?")
            params.append(query)
            where_sql = "WHERE " + " AND ".join(where)

            # Sparse: SQLite FTS
            sparse_rows = conn.execute(
                f"SELECT c.chunk_id AS chunk_id, bm25(chunks_fts) AS score "
                f"FROM chunks_fts "
                f"JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id "
                f"JOIN chunk_versions cv ON cv.chunk_id = c.chunk_id "
                f"{where_sql} "
                f"LIMIT ?",
                (*params, max(50, top_k * 4)),
            ).fetchall()
            # bm25 lower is better; invert by rank later
            sparse_ranked = [(r["chunk_id"], float(r["score"])) for r in sparse_rows]

            # Fuse
            fused = rrf_fuse(dense=[], sparse=sparse_ranked, k=60)
            ranked_ids = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]

            results: list[dict[str, Any]] = []
            for cid, score in ranked_ids:
                row = conn.execute(
                    "SELECT c.chunk_id, c.heading_path, c.text, cv.url_or_path, cv.title "
                    "FROM chunks c "
                    "JOIN chunk_versions cv ON cv.chunk_id = c.chunk_id "
                    "WHERE c.chunk_id = ? "
                    "ORDER BY cv.snapshot_id DESC LIMIT 1",
                    (cid,),
                ).fetchone()
                if not row:
                    continue
                results.append(
                    {
                        "chunk_id": row["chunk_id"],
                        "score": float(score),
                        "title": row["title"],
                        "url": row["url_or_path"],
                        "heading_path": row["heading_path"],
                        "snippet": make_snippet(row["text"]),
                    }
                )
            return results
        finally:
            conn.close()

    def _run_sync_job(self, job_id: str, source_id: str, mode: str, knowledge_id: str | None) -> None:
        started = now_utc_iso()
        conn = self._db.connect()
        try:
            conn.execute("UPDATE jobs SET status=?, started_at_utc=? WHERE job_id=?", ("running", started, job_id))
            source_row = conn.execute("SELECT type, config_json, limits_json FROM sources WHERE source_id=?", (source_id,)).fetchone()
            if not source_row:
                conn.execute("UPDATE jobs SET status=?, last_error=? WHERE job_id=?", ("failed", "source not found", job_id))
                conn.commit()
                return

            src_type = str(source_row["type"])
            config = json.loads(source_row["config_json"])
            config = _normalize_source_config(source_type=src_type, config=config)
            limits = SourceLimits.model_validate_json(source_row["limits_json"])

            resolved_ref = ""
            fetched_docs = []
            max_bytes = int(limits.max_doc_size_mb) * 1024 * 1024
            if src_type == "local":
                loc = LocalSourceConfig.model_validate(config.get("local") or {})
                fetched_docs = list(LocalFetcher(root=loc.root, include=loc.include, exclude=loc.exclude, max_doc_size_bytes=max_bytes).fetch())
                resolved_ref = "local"
            elif src_type == "github":
                gh = GithubSourceConfig.model_validate(config.get("github") or {})
                resolved_ref, fetched_docs = GithubFetcher(
                    repo=gh.repo,
                    ref=gh.ref,
                    include=gh.include,
                    exclude=gh.exclude,
                    max_doc_size_bytes=max_bytes,
                ).fetch()
            elif src_type == "crawl":
                cr = CrawlSourceConfig.model_validate(config.get("crawl") or {})
                fetched_docs = CrawlFetcher(
                    start_urls=cr.start_urls,
                    allow_domains=cr.allow_domains,
                    allow_path_prefixes=cr.allow_path_prefixes,
                    max_pages=limits.max_pages_per_run,
                    max_depth=limits.max_depth,
                    delay_s=limits.delay_seconds,
                    max_doc_size_bytes=max_bytes,
                ).fetch()
                resolved_ref = "crawl"
            else:
                raise ValueError(f"Unsupported source type: {src_type}")

            snap_id = make_snapshot_id(source_id=source_id, resolved_ref=resolved_ref, started_at_utc=started)
            conn.execute(
                "INSERT INTO snapshots(snapshot_id, source_id, resolved_ref, started_at_utc, status, counts_json, errors_json) VALUES (?,?,?,?,?,?,?)",
                (snap_id, source_id, resolved_ref, started, "running", json.dumps({}), json.dumps([])),
            )
            conn.execute("UPDATE jobs SET snapshot_id=? WHERE job_id=?", (snap_id, job_id))
            conn.commit()

            counts = {"docs": 0, "chunks": 0, "embedded": 0, "skipped": 0}
            errors: list[dict[str, Any]] = []

            # Open WebUI Knowledge indexing: upload normalized markdown, let Open WebUI do processing/embeddings.
            owui_cfg = load_openwebui_cfg_from_env()
            if knowledge_id and not owui_cfg:
                raise RuntimeError("OPEN_WEBUI_API_KEY/OWUI_API_KEY is not set (required for Open WebUI indexing)")

            for doc in fetched_docs:
                try:
                    did = make_doc_id(source_id=source_id, canonical_path=doc.canonical_path)
                    # Ensure document row
                    conn.execute(
                        "INSERT OR IGNORE INTO documents(doc_id, source_id, canonical_path) VALUES (?,?,?)",
                        (did, source_id, doc.canonical_path),
                    )

                    # Detect + normalize
                    raw_text = doc.raw_bytes.decode("utf-8", errors="replace")
                    if doc.content_type in ("text/markdown", "text/plain") or doc.url_or_path.endswith((".md", ".mdx")):
                        norm = normalize_markdown(raw_text)
                    else:
                        norm = normalize_html(raw_text)
                    content_hash = sha256_hex(norm.markdown)

                    # Incremental skip if unchanged vs latest snapshot
                    if mode == "incremental":
                        prev = conn.execute(
                            "SELECT dv.content_hash FROM documents d JOIN document_versions dv ON dv.doc_id = d.doc_id AND dv.snapshot_id = d.latest_snapshot_id WHERE d.doc_id = ? AND d.latest_snapshot_id IS NOT NULL",
                            (did,),
                        ).fetchone()
                        if prev and str(prev["content_hash"]) == content_hash:
                            counts["skipped"] += 1
                            continue

                    # Persist normalized
                    doc_dir = self._paths.docs_dir / snap_id
                    doc_dir.mkdir(parents=True, exist_ok=True)
                    norm_path = doc_dir / f"{did}.md"
                    norm_path.write_text(norm.markdown, encoding="utf-8")

                    conn.execute(
                        "INSERT OR REPLACE INTO document_versions(snapshot_id, doc_id, url_or_path, content_hash, raw_format, norm_format, normalized_path) VALUES (?,?,?,?,?,?,?)",
                        (snap_id, did, doc.url_or_path, content_hash, norm.raw_format, norm.norm_format, str(norm_path)),
                    )
                    conn.execute(
                        "UPDATE documents SET title = COALESCE(?, title), latest_snapshot_id = ? WHERE doc_id = ?",
                        (norm.title, snap_id, did),
                    )
                    counts["docs"] += 1

                    # Chunking
                    chunks = chunk_markdown(markdown=norm.markdown)
                    for idx, ch in enumerate(chunks):
                        th = sha256_hex(ch.text)
                        cid = make_chunk_id(doc_id=did, chunk_index=idx, text_hash=th)

                        conn.execute(
                            "INSERT OR IGNORE INTO chunks(chunk_id, doc_id, chunk_index, text_hash, text, heading_path, char_len) VALUES (?,?,?,?,?,?,?)",
                            (cid, did, idx, th, ch.text, ch.heading_path, ch.char_len),
                        )
                        conn.execute(
                            "INSERT OR REPLACE INTO chunk_versions(snapshot_id, chunk_id, source_id, url_or_path, title) VALUES (?,?,?,?,?)",
                            (snap_id, cid, source_id, doc.url_or_path, norm.title),
                        )
                        # FTS upsert
                        conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (cid,))
                        conn.execute(
                            "INSERT INTO chunks_fts(chunk_id, doc_id, title, heading_path, text) VALUES (?,?,?,?,?)",
                            (cid, did, norm.title or "", ch.heading_path, ch.text),
                        )
                        counts["chunks"] += 1

                    # Index into Open WebUI Knowledge (optional).
                    if knowledge_id:
                        assert owui_cfg is not None  # validated above
                        already = conn.execute(
                            "SELECT content_hash FROM owui_uploads WHERE snapshot_id=? AND doc_id=? AND knowledge_id=?",
                            (snap_id, did, knowledge_id),
                        ).fetchone()
                        if already and str(already["content_hash"]) == content_hash:
                            counts["skipped"] += 1
                        else:
                            md = render_markdown(
                                title=norm.title,
                                url=doc.url_or_path,
                                meta={
                                    "source_id": source_id,
                                    "snapshot_id": snap_id,
                                    "doc_id": did,
                                    "fetched_at": started,
                                },
                                markdown=norm.markdown,
                            )
                            filename = _make_owui_filename(canonical_path=doc.canonical_path, doc_id=did)
                            file_id = upload_markdown(cfg=owui_cfg, markdown=md, filename=filename)
                            process_status = poll_processing(cfg=owui_cfg, file_id=file_id)
                            if (process_status.get("status") or "").lower() == "failed":
                                raise RuntimeError(f"openwebui processing failed: {process_status}")
                            add_to_knowledge(cfg=owui_cfg, knowledge_id=knowledge_id, file_id=file_id)
                            conn.execute(
                                "INSERT OR REPLACE INTO owui_uploads (snapshot_id, doc_id, knowledge_id, content_hash, file_id, created_at_utc) VALUES (?,?,?,?,?,?)",
                                (snap_id, did, knowledge_id, content_hash, str(file_id), now_utc_iso()),
                            )
                            counts["embedded"] += 1

                except Exception as e:
                    errors.append({"kind": "process", "ref": doc.url_or_path, "message": str(e)})

            finished = now_utc_iso()
            conn.execute(
                "UPDATE snapshots SET status=?, finished_at_utc=?, counts_json=?, errors_json=? WHERE snapshot_id=?",
                ("success" if not errors else "success_with_errors", finished, json.dumps(counts), json.dumps(errors), snap_id),
            )
            conn.execute(
                "UPDATE jobs SET status=?, finished_at_utc=?, counts_json=?, errors_json=? WHERE job_id=?",
                ("success" if not errors else "success_with_errors", finished, json.dumps(counts), json.dumps(errors), job_id),
            )
            conn.commit()
        except Exception as e:
            finished = now_utc_iso()
            conn.execute(
                "UPDATE jobs SET status=?, finished_at_utc=?, last_error=? WHERE job_id=?",
                ("failed", finished, str(e), job_id),
            )
            conn.commit()
        finally:
            conn.close()
