# ADR: Qdrant Indexing Boundaries

Date: 2026-02-18  
Status: accepted

## Context
Qdrant is used as vector index infrastructure across multiple services (`context6`, optional later `transcript-miner`, optional benchmark runs).  
Without a shared boundary, indexing scope and payload conventions drift quickly.

## Decision
1. Qdrant stores vectors and filter metadata only; full text stays in service-local storage (files/SQLite).
2. Indexing unit is chunk-level, not full documents/repos.
3. Point IDs must be stable and idempotent (`point_id = chunk_id` where possible).
4. Collections are segmented by embedding model/dimension (or explicitly fixed to one model/dim in PoC mode).
5. Payload keeps retrieval filters/traceability (`source_id`, `snapshot_id`, `doc_id`, `chunk_id`), not full content blobs.
6. Index scope is controlled by upstream indexers/source rules, not by Qdrant itself.

## Consequences
- Retrieval quality and dedupe behavior stay predictable across re-indexing.
- Model/dimension migrations are explicit via collection naming, not hidden in-place.
- Debug/trace is possible without duplicating the full corpus inside Qdrant.

## Alternatives considered
- Single monolithic collection for all models/dimensions: rejected due to schema mismatch and migration risk.
- Storing full text in payload: rejected due to duplication/performance and SSOT violations.
