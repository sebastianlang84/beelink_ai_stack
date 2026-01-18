from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class StageTimings:
    embed_corpus_time_s: float = 0.0
    index_build_time_s: float = 0.0
    embed_queries_time_s: float = 0.0
    retrieval_time_s: float = 0.0
    embed_call_latencies_s: list[float] = field(default_factory=list)
    query_latencies_s: list[float] = field(default_factory=list)

    def summary(self) -> dict:
        def pct(values: list[float], p: float) -> float | None:
            if not values:
                return None
            return float(np.quantile(np.array(values, dtype=np.float64), p))

        return {
            "embed_corpus_time_s": self.embed_corpus_time_s,
            "index_build_time_s": self.index_build_time_s,
            "embed_queries_time_s": self.embed_queries_time_s,
            "retrieval_time_s": self.retrieval_time_s,
            "embed_call_p50_s": pct(self.embed_call_latencies_s, 0.50),
            "embed_call_p95_s": pct(self.embed_call_latencies_s, 0.95),
            "query_p50_s": pct(self.query_latencies_s, 0.50),
            "query_p95_s": pct(self.query_latencies_s, 0.95),
        }


class Timer:
    def __init__(self) -> None:
        self._t0: float | None = None

    def __enter__(self) -> "Timer":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    @property
    def elapsed_s(self) -> float:
        if self._t0 is None:
            return 0.0
        return time.perf_counter() - self._t0

