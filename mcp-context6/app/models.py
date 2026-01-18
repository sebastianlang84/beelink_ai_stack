from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GithubSourceConfig(BaseModel):
    repo: str
    ref: str = "main"
    include: list[str] = Field(default_factory=lambda: ["**/*.md", "**/*.mdx"])
    exclude: list[str] = Field(default_factory=list)


class CrawlSourceConfig(BaseModel):
    start_urls: list[str]
    allow_domains: list[str]
    allow_path_prefixes: list[str]
    render_js: bool = False
    fetch_assets: bool = False


class LocalSourceConfig(BaseModel):
    root: str
    include: list[str] = Field(default_factory=lambda: ["**/*.md", "**/*.mdx"])
    exclude: list[str] = Field(default_factory=list)


class SourceLimits(BaseModel):
    max_pages_per_run: int = 100
    max_depth: int = 3
    delay_seconds: float = 1.0
    max_doc_size_mb: int = 10
    playwright_timeout_seconds: int = 20


class SourcesCreateRequest(BaseModel):
    type: Literal["github", "crawl", "local"]
    name: str
    config: dict[str, Any]
    limits: SourceLimits = Field(default_factory=SourceLimits)


class SourcesCreateResponse(BaseModel):
    source_id: str
    created: bool


class SourcesListResponse(BaseModel):
    sources: list[dict[str, Any]]


class SyncStartRequest(BaseModel):
    source_id: str
    mode: Literal["full", "incremental"] = "full"
    knowledge_id: str | None = Field(
        default=None,
        description="Target Open WebUI Knowledge Collection id. If omitted, no Open WebUI indexing is performed.",
    )
    knowledge_name: str | None = Field(
        default=None,
        description="Target Open WebUI Knowledge Collection name. If set, context6 resolves (and optionally creates) the Knowledge base and uses its id.",
    )
    create_knowledge_if_missing: bool = Field(
        default=False,
        description="If knowledge_name is set and no Knowledge base exists with that name, create it in Open WebUI.",
    )


class SyncStartResponse(BaseModel):
    job_id: str
    accepted: bool


class KnowledgeListRequest(BaseModel):
    query: str | None = Field(default=None, description="Optional substring filter for name")
    limit: int = Field(default=200, description="Max items returned")


class KnowledgeCreateRequest(BaseModel):
    name: str
    description: str | None = None


class SyncStatusRequest(BaseModel):
    job_id: str


class SyncStatusResponse(BaseModel):
    job_id: str
    status: str
    source_id: str
    snapshot_id: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    last_error: str | None = None


class SyncPrepareRequest(BaseModel):
    source_id: str


class SnapshotsListRequest(BaseModel):
    source_id: str
    limit: int = 10


class SearchRequest(BaseModel):
    query: str
    top_k: int = 8
    source_id: str | None = None
    snapshot_id: str | None = None


class SearchResponse(BaseModel):
    results: list[dict[str, Any]]


class GetChunkRequest(BaseModel):
    chunk_id: str


class GetChunkResponse(BaseModel):
    chunk_id: str
    doc_id: str
    url: str
    heading_path: str
    text: str
    meta: dict[str, Any]


class GetDocRequest(BaseModel):
    doc_id: str


class GetDocResponse(BaseModel):
    doc_id: str
    title: str | None
    url: str | None
    content_normalized: str
    chunks: list[dict[str, Any]]
