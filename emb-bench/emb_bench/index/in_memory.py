from __future__ import annotations

import numpy as np

from .base import IndexBackend


def _l2_normalize(v: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    norm = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.maximum(norm, eps)


class InMemoryIndex(IndexBackend):
    def __init__(self, *, normalize: bool = True) -> None:
        self._normalize = normalize
        self._ids: list[str] = []
        self._vectors: np.ndarray | None = None

    def upsert(self, *, ids: list[str], vectors: np.ndarray) -> None:
        if vectors.ndim != 2:
            raise ValueError("vectors must be 2D")
        if len(ids) != vectors.shape[0]:
            raise ValueError("ids/vectors length mismatch")
        vecs = vectors.astype(np.float32, copy=False)
        if self._normalize:
            vecs = _l2_normalize(vecs)
        self._ids = list(ids)
        self._vectors = vecs

    def query(self, *, vector: np.ndarray, top_k: int) -> list[str]:
        if self._vectors is None:
            raise RuntimeError("index is empty")
        q = vector.astype(np.float32, copy=False).reshape(1, -1)
        if self._normalize:
            q = _l2_normalize(q)
        sims = (self._vectors @ q.T).reshape(-1)
        k = min(int(top_k), sims.shape[0])
        if k <= 0:
            return []
        idx = np.argpartition(-sims, kth=k - 1)[:k]
        idx_sorted = idx[np.argsort(-sims[idx])]
        return [self._ids[i] for i in idx_sorted.tolist()]

    def close(self) -> None:
        return None

