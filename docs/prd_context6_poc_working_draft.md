# PRD: context6 (PoC/Prototype) — Working Draft

## 0) Status
- Ziel: **schneller PoC**, um Integration mit Open WebUI + RooCode zu testen.
- Fokus: **Fetch → Normalize → Chunk → Serve (Search/Get)**, optional „Export für Open WebUI Collections“.
- Optional: **JS-Rendering per Playwright** für dynamische Doku-Seiten.

---

## 1) Executive Summary
`context6` ist ein selbst gehosteter Doku-Fetch/Index-Service („persönliches Context7“). Er lädt Dokumentation aus definierten Quellen (URLs, GitHub-Repos/Docs, optional lokale Files), normalisiert sie in ein einheitliches Format, chunked deterministisch und stellt sie LLM-Tools als Kontext bereit. Der PoC priorisiert tool-agnostische Nutzung (Open WebUI + RooCode) und reproduzierbare Snapshots.

---

## 2) Goals / Non-Goals (PoC)

### Goals
- **G1 Reproduzierbare Snapshots:** Quelle eindeutig referenzierbar über (`source_uri` + optional version/commit/tag).
- **G2 Idempotentes Re-Indexing:** erneutes Syncen erzeugt keine Duplikate (stabile IDs, Dedupe).
- **G3 Normalisierung:** HTML/Markdown → vereinheitlichtes Markdown/Text + Metadaten.
- **G4 Chunking:** heading/paragraph-basiert, definierte max. Chunk-Größe.
- **G5 Tool-Access:** `search` + `get_chunk`/`get_doc` über eine klar definierte Schnittstelle.
- **G6 Observability light:** Job-Status, counts, Fehlerliste, Logs.

### Non-Goals (PoC)
- Vollwertiges Web-Crawling (Sitemaps, Link-Graph, Frontier).
- PDF OCR / komplexe PDF-Extraktion (nur optional „later“).
- Keine Multi-VectorDB/Provider-Matrix im PoC (nur 1 Vektor-Backend + 1 Embedding-Provider).
- Multi-User RBAC, komplexe Auth.
- UI (nur API/Tool + minimal CLI).

---

## 3) Personas & User Stories

### Personas
- **P1 Wastolo (Power User):** will schnell neue Quellen hinzufügen und reproduzierbar syncen.
- **P2 Coding-Agent (CI/Automation):** braucht deterministische Runs, klare Status/Artifacts.

### User Stories (PoC)
- **US1:** Als User will ich eine GitHub-Repo-Doc-Quelle hinzufügen (repo + ref) und `sync` starten.
- **US2:** Als User will ich eine einzelne URL syncen.
- **US3:** Als Tool-Client will ich `search` über indizierte Chunks und anschließend `get_chunk`.
- **US4:** Als User will ich sehen, was beim letzten Sync passiert ist (counts, errors, `snapshot_id`).

---

## 4) Functional Requirements (PoC)

### MUST
- **FR-M1 Source Registry:** Quellen anlegen/ändern/löschen (type=`crawl|github|local`).
- **FR-M2 Snapshotting:** pro Sync ein Snapshot-Record (timestamp + resolved version).
- **FR-M3 Stable IDs:** `source_id` + `doc_id` + `chunk_id` stabil (hash-basiert).
- **FR-M4 Normalizer:** HTML→MD (readability + sanitize), MD passthrough.
- **FR-M5 Chunker:** heading/paragraph-basiert (semantische Grenzen vor Token-Limit). Code-Blöcke/Listen nicht mitten durchtrennen; `heading_path` als Metadatum.
  - Default PoC: `target_chunk_tokens=400`, `max_chunk_tokens=800`, `overlap_tokens=60`.
- **FR-M6 Storage:** persistente Ablage (files + sqlite metadata).
- **FR-M7 API:** `sync.start`, `sync.status`, `search`, `get_chunk`, `get_doc`.
- **FR-M8 Controlled Crawl (URL Sources):** start_url(s) + allowlist (domain + path-prefix) + limits (max_pages, max_depth) + polite crawling (delay, UA) + **robots.txt strict**.
  - Canonicalization/De-dupe (PoC):
    - Strip fragments (`#...`)
    - Drop common tracking params: `utm_*`, `gclid`, `fbclid`, `ref`, `source`
    - Normalize trailing slash
    - Enforce allowlist before enqueue
    - Skip binaries by content-type (images/fonts) unless `fetch_assets=true`
    - Skip obvious non-doc paths by default: `/assets/`, `/static/`, `/img/`, `/css/`, `/js/`
- **FR-M9 JS Rendering (optional):** per Source `render_js=true` via Playwright; default off.
- **FR-M10 Asset Fetch Policy:** default **text-only**; optional `fetch_assets=true` per Source.
- **FR-M11 Default Limits (PoC):** `max_pages_per_run=100`, `max_depth=3`, `delay_seconds=1.0`, `max_doc_size_mb=10`, `playwright_timeout_seconds=20`.
- **FR-M12 Embeddings (PoC):** chunk embeddings in Qdrant, dedizierte Collection. Embedding-Provider: OpenRouter, Modell: `qwen/qwen3-embedding-8b`.

### SHOULD
- **FR-S1 Dedupe:** content-hash gegen gleiche Inhalte über snapshots.
- **FR-S2 Robots/Rate-limit:** polite crawling (UA + delay + max requests), **robots.txt strict**.
- **FR-S3 Export:** artifacts für Open WebUI Import (z. B. `jsonl`/`md` bundle).

### COULD
- **FR-C1 WebUI collection push (später):** direkte Integration per Open WebUI API.
- **FR-C2 PDF basic:** text extraction ohne OCR.
- **FR-C3 JS-rendered pages (Playwright):** optional pro Source (Headless Chromium) für Sites, die Inhalte clientseitig laden.

---

## 5) Architektur-Optionen (MCP vs OpenAPI vs Hybrid) + Empfehlung

### Option A — MCP Server (Streamable HTTP)
- Pros: RooCode-first, agentic tool ergonomics; Open WebUI kann MCP nutzen.
- Cons: zusätzlicher MCP Server Layer; OpenAPI ggf. trotzdem nötig für andere Clients.

### Option B — OpenAPI Tool-Server
- Pros: sehr einfach; breit kompatibel.
- Cons: Tool-Discovery/Auto-Invocation kann bei OpenAPI je nach Setup schwächer sein; Adapter für RooCode evtl. nötig.

### Option C — Hybrid (Core + Adapters)
- Pros: langfristig sauber; beide Welten.
- Cons: PoC langsamer.

### Empfehlung (PoC)
- **MCP-first (Streamable HTTP)**.
- Optional (nach PoC stabil): **OpenAPI-Adapter** als Zusatz (nicht Blocker).

---

## 6) Data Model (PoC)

### Entities
- **Source**: `source_id`, `type`, `uri`, `include_paths`, `exclude_paths`, `default_ref`, `created_at`
- **Snapshot**: `snapshot_id`, `source_id`, `resolved_ref` (commit/tag), `started_at`, `finished_at`, `status`
- **Document**: `doc_id`, `snapshot_id`, `url_or_path`, `title`, `content_hash`, `raw_format`, `norm_format`
- **Chunk**: `chunk_id`, `doc_id`, `idx`, `heading_path`, `text`, `text_hash`, `char_len`
- **Embedding**: `chunk_id`, `vector_id`, `model`, `dim`, `created_at`
- **IndexState**: `qdrant_collection`, `last_snapshot_id`, `last_success_at`
- **JobRun**: `job_id`, `args`, `logs_path`, `error_count`, `summary`

### ID Strategy
- `source_id = sha256(type + canonical_uri)`
- `snapshot_id = sha256(source_id + resolved_ref + timestamp)`
- `doc_id = sha256(snapshot_id + canonical_doc_path)`
- `chunk_id = sha256(doc_id + idx + text_hash)`

### Vector Storage (PoC)
- nutzt **bestehende Qdrant-Instanz** mit **dedizierter Collection**: `context6_chunks`
- Embedding-Modell: OpenRouter `qwen/qwen3-embedding-8b`

---

## 7) APIs / Tool Interface (PoC skeleton)

### Output-Entscheidung (PoC)
- Pflicht: **Tool-Responses** (`search`/`get`) — *kein* direktes Push in Open WebUI Collections.

### MCP Tool Surface (PoC)
- `sources.create` / `sources.list` / `sources.delete` (optional)
- `sync.start` / `sync.status`
- `snapshots.list`
- `search`
- `get_chunk`
- `get_doc`

### MCP Schemas (PoC) — Request/Response

#### `sources.create`

Request:
```json
{
  "type": "github|crawl|local",
  "name": "string",
  "config": {
    "github": {"repo": "owner/name", "ref": "main|tag|commit", "include": ["**/*.md", "**/*.mdx"], "exclude": []},
    "crawl": {"start_urls": ["https://example.com/docs"], "allow_domains": ["example.com"], "allow_path_prefixes": ["/docs"], "render_js": false, "fetch_assets": false},
    "local": {"root": "/mnt/local_docs", "include": ["**/*.md", "**/*.mdx"], "exclude": []}
  },
  "limits": {"max_pages_per_run": 100, "max_depth": 3, "delay_seconds": 1.0, "max_doc_size_mb": 10, "playwright_timeout_seconds": 20}
}
```

Response:
```json
{"source_id":"sha256...","created":true}
```

#### `sources.list`

Response:
```json
{"sources":[{"source_id":"...","type":"github","name":"...","created_at":"..."}]}
```

#### `sync.start`

Request:
```json
{"source_id":"...","mode":"full|incremental"}
```

Response:
```json
{"job_id":"...","accepted":true}
```

#### `sync.status`

Request:
```json
{"job_id":"..."}
```

Response:
```json
{
  "job_id":"...",
  "status":"queued|running|success|failed",
  "source_id":"...",
  "snapshot_id":"...",
  "counts":{"docs":12,"chunks":340,"embedded":340,"skipped":2},
  "errors":[{"kind":"fetch|parse|embed","ref":"url/path","message":"..."}]
}
```

#### `snapshots.list`

Request:
```json
{"source_id":"...","limit":10}
```

Response:
```json
{"snapshots":[{"snapshot_id":"...","resolved_ref":"commit/tag","created_at":"...","status":"success","counts":{"docs":12,"chunks":340}}]}
```

#### `search`

Request:
```json
{"query":"...","top_k":8,"source_id":"...","snapshot_id":null}
```

Response:
```json
{"results":[{"chunk_id":"...","score":0.78,"title":"...","url":"...","heading_path":"H1 > H2","snippet":"..."}]}
```

#### `get_chunk`

Request:
```json
{"chunk_id":"..."}
```

Response:
```json
{"chunk_id":"...","doc_id":"...","url":"...","heading_path":"...","text":"...","meta":{"source_id":"...","snapshot_id":"...","chunk_index":12}}
```

#### `get_doc`

Request:
```json
{"doc_id":"..."}
```

Response:
```json
{"doc_id":"...","title":"...","url":"...","content_normalized":"...","chunks":[{"chunk_id":"...","heading_path":"..."}]}
```

### REST (OpenAPI) (optional später)
- `POST /sources` create source
- `GET /sources` list sources
- `POST /sync` start sync job `{source_id}` → `{job_id}`
- `GET /jobs/{job_id}` job status + summary
- `GET /snapshots?source_id=` list snapshots
- `POST /search` `{query, source_id?, snapshot_id?, top_k}` → results (chunk refs + snippets)
- `GET /chunks/{chunk_id}` full chunk + metadata
- `GET /docs/{doc_id}` normalized doc + chunk list (optional)
- `GET /healthz`

---

## 8) Security & Compliance (PoC)
- Secrets repo-lokal (gitignored): `.env` (secrets-only); Non-Secrets: `.config.env` + `mcp-context6/.config.env`.
- Robots/Rate limit: **robots.txt strict**, UA + delay + max pages per run.
- Auth: PoC ohne Auth möglich (nur Tailnet/LAN). Upgrade-Pfad: Bearer Token / Reverse Proxy / mTLS.

---

## 9) Operations (PoC)
- Deployment: läuft auf demselben Host wie Open WebUI/Qdrant.
- MCP Endpoint (PoC): `http://<server-ip>:8816/mcp` (LAN/Tailnet).
- Ports (PoC): `8816/tcp` (Host) → `context6:8816` (Container).
- Host-Verzeichnisse (Vorschlag PoC):
  - Persistenz: `/srv/mcp-context6/data` → Container `/data`
  - Raw-Cache: `/srv/mcp-context6/cache` → Container `/cache` (optional)
  - Local Docs (read-only): `/srv/mcp-context6/local_docs` → Container `/mnt/local_docs`
- Logging: stdout + job logs unter `/data/jobs/<job_id>.log`
- Backup: tar/rsync von `/srv/mcp-context6/data`

---

## 10) MVP Scope & Phases

### MVP (PoC)
- Sources (MUST):
  - **C1 GitHub repo docs** (repo + ref + include/exclude paths)
  - **C3 Controlled crawl** (start_url(s) + allowlist domain/path + limits)
  - **C4 Local folders/files** (bind-mount; primär Markdown)
- Sync pipeline: fetch → normalize → chunk → persist
- Search/Get: Hybrid Search (SQLite FTS/BM25 + Vector via Qdrant) + `get_chunk`
  - Ranking: **Reciprocal Rank Fusion (RRF)**, `k=60`
- Job status

### v1
- OpenAPI Adapter
- Export-to-OpenWebUI artifacts + optional auto-import
- Better dedupe + incremental sync

### v2
- PDF extraction
- Multi-source federated search
- Platform-Connectors (ReadTheDocs/Confluence/GitBook etc.)

---

## 11) Acceptance Criteria / Test Plan (PoC)
- AC1: Sync GitHub repo docs (fixed commit) produces snapshot with deterministic chunk IDs.
- AC2: Re-sync same ref creates new snapshot but **no duplicate chunks** under stable IDs (oder Dedupe-Report).
- AC3: `search` returns relevante chunks; `get_chunk` liefert exakten Text.
- AC4: Job status shows counts + errors; failure does not corrupt prior snapshot.
- AC5: Default: keine Host-Port Exponierung notwendig (nur Docker-Netz oder Tailscale), Host-Port nur wenn bewusst aktiviert.

---

## 12) Open Questions / Risks (initial)
- Q1: Open WebUI Version + MCP Streamable HTTP support.
- Q2: Deployment exposure: internal only vs client reachable (Reverse Proxy/Tailscale).
- Q3: MVP sources (GitHub/crawl/local) — genaue Priorisierung.
- Q4: Output integration: Tool-responses vs Indexing vs beides.
- Q5: Embedding/Vector Strategy (PoC ohne Embeddings ok?).
- Q6: Limits: max pages/run, max size, refresh cadence.

---

## 13) Next: Prioritized Questions (A–F)
1. **A — Open WebUI Version + MCP:** Welche Open WebUI Version nutzt du und ist MCP Streamable HTTP dort aktiv nutzbar?
2. **B — Exposure:** Soll context6 nur im Docker-Netz laufen (no host port) oder auch direkt erreichbar sein (Reverse Proxy/Tailscale)?
3. **C — Quellen MVP:** GitHub Docs + einzelne URLs + lokale Ordner: was ist MUST für PoC?
4. **D — Output:** (1) Tool-responses search/get, (2) Indexing in Open WebUI Collections, (3) beides — was ist für PoC Pflicht?
5. **E — Embeddings:** PoC ohne Embeddings ok? Später: Open WebUI Knowledge vs Qdrant vs SQLite/FTS only?
6. **F — Limits:** grobe Grenzen (max pages/run, max MB/doc, refresh manuell vs cron)?
