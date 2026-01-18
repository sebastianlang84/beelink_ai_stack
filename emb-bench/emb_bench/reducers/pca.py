from __future__ import annotations

import numpy as np

from .base import Reducer


class PCAReducer(Reducer):
    def __init__(self, *, target_dim: int, whiten: bool = False, seed: int = 42) -> None:
        self._target_dim = int(target_dim)
        self._whiten = bool(whiten)
        self._seed = int(seed)
        self._pca = None

    @property
    def name(self) -> str:
        return "pca"

    def fit(self, vectors: np.ndarray) -> None:
        try:
            from sklearn.decomposition import PCA
        except Exception as e:
            raise RuntimeError("PCAReducer requires scikit-learn") from e

        if vectors.ndim != 2:
            raise ValueError("vectors must be 2D")
        if self._target_dim <= 0 or self._target_dim > vectors.shape[1]:
            raise ValueError(f"target_dim {self._target_dim} out of range for dim={vectors.shape[1]}")

        self._pca = PCA(n_components=self._target_dim, whiten=self._whiten, random_state=self._seed)
        self._pca.fit(vectors)

    def transform(self, vectors: np.ndarray) -> np.ndarray:
        if self._pca is None:
            raise RuntimeError("PCAReducer not fitted")
        return self._pca.transform(vectors)
