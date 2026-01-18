from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class IndexBackend(ABC):
    @abstractmethod
    def upsert(self, *, ids: list[str], vectors: np.ndarray) -> None: ...

    @abstractmethod
    def query(self, *, vector: np.ndarray, top_k: int) -> list[str]: ...

    @abstractmethod
    def close(self) -> None: ...
