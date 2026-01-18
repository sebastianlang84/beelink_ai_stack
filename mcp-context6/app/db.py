from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  name TEXT NOT NULL,
  config_json TEXT NOT NULL,
  limits_json TEXT NOT NULL,
  created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
  snapshot_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
  resolved_ref TEXT NOT NULL,
  started_at_utc TEXT NOT NULL,
  finished_at_utc TEXT,
  status TEXT NOT NULL,
  counts_json TEXT NOT NULL,
  errors_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
  canonical_path TEXT NOT NULL,
  title TEXT,
  latest_snapshot_id TEXT,
  UNIQUE(source_id, canonical_path)
);

CREATE TABLE IF NOT EXISTS document_versions (
  snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
  doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  url_or_path TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  raw_format TEXT NOT NULL,
  norm_format TEXT NOT NULL,
  normalized_path TEXT NOT NULL,
  PRIMARY KEY (snapshot_id, doc_id)
);

CREATE TABLE IF NOT EXISTS chunks (
  chunk_id TEXT PRIMARY KEY,
  doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  text_hash TEXT NOT NULL,
  text TEXT NOT NULL,
  heading_path TEXT NOT NULL,
  char_len INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chunk_versions (
  snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
  chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL,
  url_or_path TEXT NOT NULL,
  title TEXT,
  PRIMARY KEY (snapshot_id, chunk_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  chunk_id UNINDEXED,
  doc_id UNINDEXED,
  title,
  heading_path,
  text,
  tokenize='porter'
);

CREATE TABLE IF NOT EXISTS embeddings (
  chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  created_at_utc TEXT NOT NULL,
  PRIMARY KEY(chunk_id, model, dim)
);

CREATE TABLE IF NOT EXISTS owui_uploads (
  snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
  doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  knowledge_id TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  file_id TEXT NOT NULL,
  created_at_utc TEXT NOT NULL,
  PRIMARY KEY(snapshot_id, doc_id, knowledge_id)
);

CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  snapshot_id TEXT,
  knowledge_id TEXT,
  knowledge_name TEXT,
  status TEXT NOT NULL,
  created_at_utc TEXT NOT NULL,
  started_at_utc TEXT,
  finished_at_utc TEXT,
  counts_json TEXT NOT NULL,
  errors_json TEXT NOT NULL,
  last_error TEXT
);
"""


@dataclass(frozen=True)
class Db:
    path: Path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


def init_db(db_path: str) -> Db:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    db = Db(path=p)
    conn = db.connect()
    try:
        conn.executescript(SCHEMA_SQL)
        # Lightweight migrations for existing DBs (PoC-friendly).
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "knowledge_id" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN knowledge_id TEXT")
        if "knowledge_name" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN knowledge_name TEXT")
        conn.commit()
    finally:
        conn.close()
    return db
