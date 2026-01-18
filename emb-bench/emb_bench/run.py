from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import numpy as np

from .config import BenchConfig, load_config
from .dataset import load_dataset, subset_dataset
from .embedders.local import LocalEmbedder
from .embedders.openrouter import OpenRouterEmbedder
from .index.in_memory import InMemoryIndex
from .index.qdrant_backend import QdrantIndex
from .metrics import compute_metrics
from .reducers.mrl_prefix import MRLPrefixReducer
from .reducers.pca import PCAReducer
from .reducers.random_projection import RandomProjectionReducer
from .report import RunRow, write_csv, write_markdown
from .timing import StageTimings, Timer
from .utils import ensure_dir, env_snapshot, sha256_text, write_text


def _utc_ts() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _l2_normalize(v: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    norm = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.maximum(norm, eps)


def _storage_estimate_bytes(*, num_vectors: int, dim: int) -> int:
    return int(num_vectors) * int(dim) * 4


def _cache_path(cache_dir: str, *, key: str) -> Path:
    return Path(cache_dir) / f"{key}.npy"


def _embed_with_cache(
    *,
    embedder,
    texts: list[str],
    cache_dir: str,
    cache_key_prefix: str,
    batch_size: int,
    timings: StageTimings,
) -> np.ndarray:
    ensure_dir(cache_dir)
    prefix_hash = sha256_text(cache_key_prefix)
    out: list[np.ndarray | None] = [None] * len(texts)
    missing: list[tuple[int, str, Path]] = []
    for i, text in enumerate(texts):
        h = sha256_text(text)
        p = _cache_path(cache_dir, key=f"{prefix_hash}__{h}")
        if p.exists():
            out[i] = np.load(p)
        else:
            missing.append((i, text, p))

    # Embed missing in batches
    for start in range(0, len(missing), max(1, int(batch_size))):
        chunk = missing[start : start + int(batch_size)]
        chunk_texts = [t for _, t, _ in chunk]
        with Timer() as t:
            vecs = embedder.embed_texts(chunk_texts)
        timings.embed_call_latencies_s.append(t.elapsed_s)
        for (i, _t, p), vec in zip(chunk, vecs, strict=True):
            arr = np.array(vec, dtype=np.float32)
            np.save(p, arr)
            out[i] = arr

    stacked = np.stack([v for v in out if v is not None], axis=0)
    if stacked.shape[0] != len(texts):
        raise RuntimeError("embedding cache mismatch")
    return stacked


@dataclass(frozen=True)
class ExperimentSpec:
    phase: str
    embedder_id: str
    reducer: str
    target_dim: int
    normalize: bool


def _build_reducer(spec: ExperimentSpec, *, input_dim: int, seed: int, pca_whiten: bool) -> object | None:
    if spec.reducer == "none":
        return None
    if spec.reducer == "mrl_prefix":
        return MRLPrefixReducer(target_dim=spec.target_dim)
    if spec.reducer == "pca":
        return PCAReducer(target_dim=spec.target_dim, whiten=pca_whiten, seed=seed)
    if spec.reducer == "random_projection":
        return RandomProjectionReducer(input_dim=input_dim, target_dim=spec.target_dim, seed=seed)
    raise ValueError(f"Unknown reducer: {spec.reducer}")


def _apply_reducer(*, reducer, vectors: np.ndarray, fit_vectors: np.ndarray | None) -> np.ndarray:
    if reducer is None:
        return vectors
    if hasattr(reducer, "fit") and fit_vectors is not None:
        reducer.fit(fit_vectors)
    return reducer.transform(vectors)


def _build_index(cfg: BenchConfig, *, dim: int, normalize: bool, collection: str):
    if cfg.backend.type == "in_memory":
        return InMemoryIndex(normalize=normalize)
    if cfg.backend.type == "qdrant":
        if not cfg.backend.qdrant:
            raise ValueError("backend.qdrant is required for backend.type=qdrant")
        return QdrantIndex(
            url=cfg.backend.qdrant.url,
            collection=collection,
            dim=dim,
            distance=cfg.backend.qdrant.distance,
        )
    raise ValueError(f"Unknown backend.type: {cfg.backend.type}")


def _run_one(cfg: BenchConfig, *, ds, spec: ExperimentSpec, embedder, pca_sample_size: int | None, pca_whiten: bool) -> RunRow:
    timings = StageTimings()
    cache_dir = cfg.runtime.cache_dir
    cache_prefix = f"{embedder.name}__{spec.reducer}__{spec.target_dim}"

    corpus_texts = [d.text for d in ds.corpus]
    query_texts = [q.text for q in ds.queries]
    qrels = {q.query_id: ds.qrels_by_query_id[q.query_id].relevant for q in ds.queries}

    with Timer() as t:
        corpus_vecs = _embed_with_cache(
            embedder=embedder,
            texts=corpus_texts,
            cache_dir=cache_dir,
            cache_key_prefix=cache_prefix + "__corpus",
            batch_size=cfg.openrouter.batch_size if spec.embedder_id == "remote" else 64,
            timings=timings,
        )
    timings.embed_corpus_time_s = t.elapsed_s

    reducer = _build_reducer(spec, input_dim=corpus_vecs.shape[1], seed=cfg.runtime.seed, pca_whiten=pca_whiten)
    fit_vecs = None
    if reducer is not None and spec.reducer in ("pca", "random_projection"):
        if pca_sample_size:
            fit_vecs = corpus_vecs[: min(pca_sample_size, corpus_vecs.shape[0])]
        else:
            fit_vecs = corpus_vecs

    if reducer is not None:
        corpus_vecs = _apply_reducer(reducer=reducer, vectors=corpus_vecs, fit_vectors=fit_vecs)

    if spec.normalize:
        corpus_vecs = _l2_normalize(corpus_vecs)

    with Timer() as t:
        index = _build_index(cfg, dim=corpus_vecs.shape[1], normalize=False, collection=f"emb_bench_{_utc_ts()}_{uuid4().hex}")
        index.upsert(ids=[d.doc_id for d in ds.corpus], vectors=corpus_vecs)
    timings.index_build_time_s = t.elapsed_s

    with Timer() as t:
        query_vecs = _embed_with_cache(
            embedder=embedder,
            texts=query_texts,
            cache_dir=cache_dir,
            cache_key_prefix=cache_prefix + "__queries",
            batch_size=cfg.openrouter.batch_size if spec.embedder_id == "remote" else 64,
            timings=timings,
        )
    timings.embed_queries_time_s = t.elapsed_s

    if reducer is not None:
        query_vecs = reducer.transform(query_vecs)
    if spec.normalize:
        query_vecs = _l2_normalize(query_vecs)

    retrieved: dict[str, list[str]] = {}
    with Timer() as t:
        for q, qvec in zip(ds.queries, query_vecs, strict=True):
            with Timer() as qt:
                retrieved[q.query_id] = index.query(vector=qvec, top_k=cfg.retrieval.top_k)
            timings.query_latencies_s.append(qt.elapsed_s)
    timings.retrieval_time_s = t.elapsed_s
    index.close()

    metrics = compute_metrics(retrieved=retrieved, qrels=qrels)
    storage_est = _storage_estimate_bytes(num_vectors=len(ds.corpus), dim=int(corpus_vecs.shape[1]))

    return RunRow(
        phase=spec.phase,
        embedder=embedder.name,
        reducer=spec.reducer,
        target_dim=int(corpus_vecs.shape[1]),
        normalize=spec.normalize,
        metrics=metrics,
        timing=timings.summary(),
        storage_bytes_est=storage_est,
    )


def _phase_mrl(cfg: BenchConfig, *, ds) -> list[RunRow]:
    assert cfg.mrl_phase is not None
    rows: list[RunRow] = []

    timings_sink: list[float] = []
    remote = OpenRouterEmbedder(
        base_url=cfg.openrouter.base_url,
        api_key_env=cfg.openrouter.api_key_env,
        model=cfg.remote_model.name,
        native_dim=cfg.remote_model.native_dim,
        timeout_s=cfg.openrouter.timeout_s,
        max_retries=cfg.openrouter.max_retries,
        rpm_limit=cfg.openrouter.rpm_limit,
        call_latencies_sink=timings_sink,
    )

    reducers = cfg.mrl_phase.reducers
    dims = cfg.mrl_phase.dims
    for target_dim in dims:
        for reducer_name in reducers:
            if reducer_name == "none" and target_dim != cfg.remote_model.native_dim:
                continue
            if reducer_name != "none" and target_dim == cfg.remote_model.native_dim:
                # allow, but it is a no-op only for prefix. Still keep for explicitness.
                pass
            spec = ExperimentSpec(
                phase="mrl",
                embedder_id="remote",
                reducer=reducer_name if reducer_name != "none" else "none",
                target_dim=int(target_dim),
                normalize=cfg.mrl_phase.normalize,
            )
            pca_sample = cfg.mrl_phase.pca.sample_size if cfg.mrl_phase.pca else None
            pca_whiten = cfg.mrl_phase.pca.whiten if cfg.mrl_phase.pca else False
            row = _run_one(cfg, ds=ds, spec=spec, embedder=remote, pca_sample_size=pca_sample, pca_whiten=pca_whiten)
            rows.append(row)
    return rows


def _phase_local_vs_remote(cfg: BenchConfig, *, ds) -> list[RunRow]:
    assert cfg.local_phase is not None
    rows: list[RunRow] = []

    # Local embedders (baseline: no reducer, keep native dim)
    for emb_cfg in cfg.local_phase.local_embedders:
        local = LocalEmbedder(
            engine=emb_cfg.engine,
            model=emb_cfg.model,
            batch_size=emb_cfg.batch_size,
            threads=emb_cfg.threads,
        )
        spec = ExperimentSpec(
            phase="local_vs_remote",
            embedder_id=emb_cfg.id,
            reducer="none",
            target_dim=local.dim,
            normalize=cfg.local_phase.normalize,
        )
        rows.append(_run_one(cfg, ds=ds, spec=spec, embedder=local, pca_sample_size=None, pca_whiten=False))

    if cfg.local_phase.compare_against_remote:
        remote_dims = cfg.local_phase.remote_dims or [cfg.remote_model.native_dim]
        remote = OpenRouterEmbedder(
            base_url=cfg.openrouter.base_url,
            api_key_env=cfg.openrouter.api_key_env,
            model=cfg.remote_model.name,
            native_dim=cfg.remote_model.native_dim,
            timeout_s=cfg.openrouter.timeout_s,
            max_retries=cfg.openrouter.max_retries,
            rpm_limit=cfg.openrouter.rpm_limit,
        )
        for d in remote_dims:
            spec = ExperimentSpec(
                phase="local_vs_remote",
                embedder_id="remote",
                reducer=cfg.local_phase.remote_reducer,
                target_dim=int(d),
                normalize=cfg.local_phase.normalize,
            )
            rows.append(_run_one(cfg, ds=ds, spec=spec, embedder=remote, pca_sample_size=None, pca_whiten=False))

    return rows


def run_benchmark(
    *,
    config_path: str,
    phase: str,
    subset_docs: int | None,
    subset_queries: int | None,
    warmup_calls: int | None,
    concurrency: int | None,
) -> None:
    cfg = load_config(config_path)

    # Override runtime knobs from CLI (optional)
    runtime = cfg.runtime
    runtime_subset_docs = subset_docs if subset_docs is not None else runtime.subset_docs
    runtime_subset_queries = subset_queries if subset_queries is not None else runtime.subset_queries
    _ = warmup_calls if warmup_calls is not None else runtime.warmup_calls
    _ = concurrency if concurrency is not None else runtime.concurrency

    ds = load_dataset(
        corpus_path=str(Path(config_path).parent / cfg.dataset.corpus_path),
        queries_path=str(Path(config_path).parent / cfg.dataset.queries_path),
        qrels_path=str(Path(config_path).parent / cfg.dataset.qrels_path),
    )
    ds = subset_dataset(ds, subset_docs=runtime_subset_docs, subset_queries=runtime_subset_queries)

    run_id = _utc_ts()
    out_dir = Path(Path(config_path).parent / cfg.report.output_dir / run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    write_text(str(out_dir / "seed.txt"), f"{cfg.runtime.seed}\n")
    write_text(str(out_dir / "env.txt"), env_snapshot())
    # Resolved config snapshot (JSON; no secrets included)
    write_text(str(out_dir / "config_resolved.json"), json.dumps(cfg, default=lambda o: o.__dict__, indent=2) + "\n")

    if phase == "mrl":
        if cfg.mrl_phase is None:
            raise ValueError("mrl_phase config missing")
        rows = _phase_mrl(cfg, ds=ds)
    elif phase == "local_vs_remote":
        if cfg.local_phase is None:
            raise ValueError("local_phase config missing")
        rows = _phase_local_vs_remote(cfg, ds=ds)
    else:
        raise ValueError(f"Unknown phase: {phase}")

    write_csv(str(out_dir / "results.csv"), rows)
    write_markdown(str(out_dir / "report.md"), rows)
