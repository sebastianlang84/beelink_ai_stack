from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class OpenRouterConfig:
    base_url: str
    api_key_env: str
    timeout_s: int = 30
    max_retries: int = 5
    rpm_limit: int = 120
    batch_size: int = 16


@dataclass(frozen=True)
class RemoteModelConfig:
    name: str
    native_dim: int


@dataclass(frozen=True)
class MRLPCAConfig:
    sample_size: int = 5000
    whiten: bool = False


@dataclass(frozen=True)
class MRLPhaseConfig:
    dims: list[int]
    reducers: list[str]
    normalize: bool = True
    pca: MRLPCAConfig | None = None


@dataclass(frozen=True)
class LocalEmbedderConfig:
    id: str
    engine: str
    model: str
    batch_size: int = 32
    threads: int = 4


@dataclass(frozen=True)
class LocalPhaseConfig:
    local_embedders: list[LocalEmbedderConfig]
    compare_against_remote: bool = True
    remote_dims: list[int] | None = None
    remote_reducer: str = "mrl_prefix"
    normalize: bool = True


@dataclass(frozen=True)
class DatasetConfig:
    corpus_path: str
    queries_path: str
    qrels_path: str


@dataclass(frozen=True)
class QdrantConfig:
    url: str
    distance: str = "cosine"


@dataclass(frozen=True)
class BackendConfig:
    type: str = "in_memory"
    qdrant: QdrantConfig | None = None


@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int = 20


@dataclass(frozen=True)
class RuntimeConfig:
    seed: int = 42
    subset_docs: int | None = None
    subset_queries: int | None = None
    warmup_calls: int = 20
    concurrency: int = 1
    cache_dir: str = ".cache"


@dataclass(frozen=True)
class ReportConfig:
    output_dir: str = "runs"
    make_plots: bool = False


@dataclass(frozen=True)
class BenchConfig:
    phases: list[str]
    openrouter: OpenRouterConfig
    remote_model: RemoteModelConfig
    dataset: DatasetConfig
    backend: BackendConfig
    retrieval: RetrievalConfig
    runtime: RuntimeConfig
    report: ReportConfig
    mrl_phase: MRLPhaseConfig | None = None
    local_phase: LocalPhaseConfig | None = None


def _require(d: dict[str, Any], key: str) -> Any:
    if key not in d:
        raise ValueError(f"Missing required config key: {key}")
    return d[key]


def load_config(path: str) -> BenchConfig:
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Config must be a YAML object at the root")

    openrouter_raw = _require(raw, "openrouter")
    openrouter = OpenRouterConfig(
        base_url=str(_require(openrouter_raw, "base_url")).rstrip("/"),
        api_key_env=str(_require(openrouter_raw, "api_key_env")),
        timeout_s=int(openrouter_raw.get("timeout_s", 30)),
        max_retries=int(openrouter_raw.get("max_retries", 5)),
        rpm_limit=int(openrouter_raw.get("rpm_limit", 120)),
        batch_size=int(openrouter_raw.get("batch_size", 16)),
    )

    remote_raw = _require(raw, "remote_model")
    remote_model = RemoteModelConfig(
        name=str(_require(remote_raw, "name")),
        native_dim=int(_require(remote_raw, "native_dim")),
    )

    dataset_raw = _require(raw, "dataset")
    dataset = DatasetConfig(
        corpus_path=str(_require(dataset_raw, "corpus_path")),
        queries_path=str(_require(dataset_raw, "queries_path")),
        qrels_path=str(_require(dataset_raw, "qrels_path")),
    )

    backend_raw = raw.get("backend", {}) or {}
    qdrant_raw = backend_raw.get("qdrant")
    backend = BackendConfig(
        type=str(backend_raw.get("type", "in_memory")),
        qdrant=QdrantConfig(url=str(_require(qdrant_raw, "url")), distance=str(qdrant_raw.get("distance", "cosine")))
        if isinstance(qdrant_raw, dict)
        else None,
    )

    retrieval_raw = raw.get("retrieval", {}) or {}
    retrieval = RetrievalConfig(top_k=int(retrieval_raw.get("top_k", 20)))

    runtime_raw = raw.get("runtime", {}) or {}
    runtime = RuntimeConfig(
        seed=int(runtime_raw.get("seed", 42)),
        subset_docs=runtime_raw.get("subset_docs"),
        subset_queries=runtime_raw.get("subset_queries"),
        warmup_calls=int(runtime_raw.get("warmup_calls", 20)),
        concurrency=int(runtime_raw.get("concurrency", 1)),
        cache_dir=str(runtime_raw.get("cache_dir", ".cache")),
    )

    report_raw = raw.get("report", {}) or {}
    report = ReportConfig(
        output_dir=str(report_raw.get("output_dir", "runs")),
        make_plots=bool(report_raw.get("make_plots", False)),
    )

    mrl_phase = None
    if isinstance(raw.get("mrl_phase"), dict):
        mrl_raw = raw["mrl_phase"]
        pca_cfg = None
        if isinstance(mrl_raw.get("pca"), dict):
            pca_raw = mrl_raw["pca"]
            pca_cfg = MRLPCAConfig(
                sample_size=int(pca_raw.get("sample_size", 5000)),
                whiten=bool(pca_raw.get("whiten", False)),
            )
        mrl_phase = MRLPhaseConfig(
            dims=[int(x) for x in _require(mrl_raw, "dims")],
            reducers=[str(x) for x in _require(mrl_raw, "reducers")],
            normalize=bool(mrl_raw.get("normalize", True)),
            pca=pca_cfg,
        )

    local_phase = None
    if isinstance(raw.get("local_phase"), dict):
        local_raw = raw["local_phase"]
        embedder_list = []
        for item in _require(local_raw, "local_embedders"):
            if not isinstance(item, dict):
                raise ValueError("local_phase.local_embedders must be a list of objects")
            embedder_list.append(
                LocalEmbedderConfig(
                    id=str(_require(item, "id")),
                    engine=str(_require(item, "engine")),
                    model=str(_require(item, "model")),
                    batch_size=int(item.get("batch_size", 32)),
                    threads=int(item.get("threads", 4)),
                )
            )
        local_phase = LocalPhaseConfig(
            local_embedders=embedder_list,
            compare_against_remote=bool(local_raw.get("compare_against_remote", True)),
            remote_dims=[int(x) for x in local_raw.get("remote_dims", [])] or None,
            remote_reducer=str(local_raw.get("remote_reducer", "mrl_prefix")),
            normalize=bool(local_raw.get("normalize", True)),
        )

    phases = [str(x) for x in _require(raw, "phases")]

    return BenchConfig(
        phases=phases,
        openrouter=openrouter,
        remote_model=remote_model,
        dataset=dataset,
        backend=backend,
        retrieval=retrieval,
        runtime=runtime,
        report=report,
        mrl_phase=mrl_phase,
        local_phase=local_phase,
    )
