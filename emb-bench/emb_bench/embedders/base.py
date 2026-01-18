from __future__ import annotations

from abc import ABC, abstractmethod


class Embedder(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def dim(self) -> int: ...

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
