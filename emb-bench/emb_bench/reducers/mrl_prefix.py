from __future__ import annotations

import numpy as np

from .base import Reducer


class MRLPrefixReducer(Reducer):
    def __init__(self, *, target_dim: int) -> None:
        self._target_dim = int(target_dim)

    @property
    def name(self) -> str:
        return "mrl_prefix"

    def transform(self, vectors: np.ndarray) -> np.ndarray:
        if vectors.ndim != 2:
            raise ValueError("vectors must be 2D")
        if self._target_dim <= 0 or self._target_dim > vectors.shape[1]:
            raise ValueError(f"target_dim {self._target_dim} out of range for dim={vectors.shape[1]}")
        return vectors[:, : self._target_dim]
