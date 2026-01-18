from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class Reducer(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    def fit(self, vectors: np.ndarray) -> None:
        return None

    @abstractmethod
    def transform(self, vectors: np.ndarray) -> np.ndarray: ...
