from __future__ import annotations

import numpy as np

from .base import Reducer


class RandomProjectionReducer(Reducer):
    def __init__(self, *, input_dim: int, target_dim: int, seed: int = 42) -> None:
        self._input_dim = int(input_dim)
        self._target_dim = int(target_dim)
        self._seed = int(seed)
        self._proj: np.ndarray | None = None

    @property
    def name(self) -> str:
        return "random_projection"

    def fit(self, vectors: np.ndarray) -> None:
        if vectors.ndim != 2:
            raise ValueError("vectors must be 2D")
        if vectors.shape[1] != self._input_dim:
            raise ValueError(f"input_dim mismatch: expected {self._input_dim}, got {vectors.shape[1]}")
        rng = np.random.default_rng(self._seed)
        # Gaussian random projection
        self._proj = rng.normal(0.0, 1.0, size=(self._input_dim, self._target_dim)).astype(np.float32)

    def transform(self, vectors: np.ndarray) -> np.ndarray:
        if self._proj is None:
            raise RuntimeError("RandomProjectionReducer not fitted")
        return vectors @ self._proj
