from __future__ import annotations

import hashlib


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_id(*, type: str, canonical_uri: str) -> str:
    return sha256_hex(f"{type}:{canonical_uri}")


def doc_id(*, source_id: str, canonical_path: str) -> str:
    return sha256_hex(f"{source_id}:{canonical_path}")


def chunk_id(*, doc_id: str, chunk_index: int, text_hash: str) -> str:
    return sha256_hex(f"{doc_id}:{chunk_index}:{text_hash}")


def snapshot_id(*, source_id: str, resolved_ref: str, started_at_utc: str) -> str:
    return sha256_hex(f"{source_id}:{resolved_ref}:{started_at_utc}")


def job_id(*, source_id: str, created_at_utc: str, nonce: str) -> str:
    return sha256_hex(f"{source_id}:{created_at_utc}:{nonce}")

