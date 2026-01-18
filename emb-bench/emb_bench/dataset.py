from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Doc:
    doc_id: str
    text: str
    meta: dict


@dataclass(frozen=True)
class Query:
    query_id: str
    text: str


@dataclass(frozen=True)
class Qrels:
    query_id: str
    relevant: set[str]


@dataclass(frozen=True)
class Dataset:
    corpus: list[Doc]
    queries: list[Query]
    qrels_by_query_id: dict[str, Qrels]


def _read_jsonl(path: str) -> list[dict]:
    p = Path(path)
    items: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception as e:
                raise ValueError(f"Invalid JSONL in {path}:{line_no}: {e}") from e
    return items


def load_dataset(*, corpus_path: str, queries_path: str, qrels_path: str) -> Dataset:
    corpus_raw = _read_jsonl(corpus_path)
    queries_raw = _read_jsonl(queries_path)
    qrels_raw = _read_jsonl(qrels_path)

    corpus: list[Doc] = []
    for item in corpus_raw:
        doc_id = str(item.get("doc_id", "")).strip()
        text = str(item.get("text", "")).strip()
        if not doc_id or not text:
            raise ValueError("corpus.jsonl items require non-empty doc_id and text")
        meta = item.get("meta") or {}
        if not isinstance(meta, dict):
            raise ValueError("corpus.jsonl meta must be an object")
        corpus.append(Doc(doc_id=doc_id, text=text, meta=meta))

    queries: list[Query] = []
    for item in queries_raw:
        query_id = str(item.get("query_id", "")).strip()
        text = str(item.get("text", "")).strip()
        if not query_id or not text:
            raise ValueError("queries.jsonl items require non-empty query_id and text")
        queries.append(Query(query_id=query_id, text=text))

    qrels_by_query_id: dict[str, Qrels] = {}
    for item in qrels_raw:
        query_id = str(item.get("query_id", "")).strip()
        relevant = item.get("relevant")
        if not query_id or not isinstance(relevant, list):
            raise ValueError("qrels.jsonl items require query_id and relevant list")
        qrels_by_query_id[query_id] = Qrels(query_id=query_id, relevant=set(str(x) for x in relevant))

    corpus_ids = {d.doc_id for d in corpus}
    for q in queries:
        if q.query_id not in qrels_by_query_id:
            raise ValueError(f"Missing qrels for query_id={q.query_id}")
        missing = qrels_by_query_id[q.query_id].relevant - corpus_ids
        if missing:
            raise ValueError(f"qrels for query_id={q.query_id} reference unknown doc_ids: {sorted(missing)[:5]}")

    return Dataset(corpus=corpus, queries=queries, qrels_by_query_id=qrels_by_query_id)


def subset_dataset(ds: Dataset, *, subset_docs: int | None, subset_queries: int | None) -> Dataset:
    corpus = ds.corpus[:subset_docs] if subset_docs else ds.corpus
    corpus_ids = {d.doc_id for d in corpus}
    queries = ds.queries[:subset_queries] if subset_queries else ds.queries
    qrels_by_query_id = {}
    for q in queries:
        qrels = ds.qrels_by_query_id[q.query_id]
        rel = qrels.relevant & corpus_ids
        if not rel:
            continue
        qrels_by_query_id[q.query_id] = Qrels(query_id=q.query_id, relevant=rel)

    queries = [q for q in queries if q.query_id in qrels_by_query_id]
    return Dataset(corpus=corpus, queries=queries, qrels_by_query_id=qrels_by_query_id)

