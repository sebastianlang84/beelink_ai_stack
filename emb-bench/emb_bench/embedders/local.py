from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LocalEmbedderConfig:
    engine: str
    model: str
    batch_size: int
    threads: int


class LocalEmbedder:
    def __init__(self, *, engine: str, model: str, batch_size: int = 32, threads: int = 4) -> None:
        self._engine = engine
        self._model = model
        self._batch_size = int(batch_size)
        self._threads = int(threads)

        os.environ.setdefault("OMP_NUM_THREADS", str(self._threads))
        os.environ.setdefault("MKL_NUM_THREADS", str(self._threads))

        self._st_model = None
        self._fastembed = None
        self._dim: int | None = None

        if self._engine == "sentence_transformers":
            try:
                from sentence_transformers import SentenceTransformer
            except Exception as e:
                raise RuntimeError("engine=sentence_transformers requires sentence-transformers") from e
            self._st_model = SentenceTransformer(self._model, device="cpu")
            self._dim = int(self._st_model.get_sentence_embedding_dimension())
        elif self._engine == "onnxruntime":
            try:
                from fastembed import TextEmbedding
            except Exception as e:
                raise RuntimeError("engine=onnxruntime requires fastembed (onnxruntime backend)") from e
            self._fastembed = TextEmbedding(model_name=self._model)
            # Probe dim
            vec = next(self._fastembed.embed(["dim probe"]))
            self._dim = int(len(vec))
        else:
            raise ValueError(f"Unknown local embedder engine: {self._engine}")

    @property
    def name(self) -> str:
        return f"local:{self._engine}:{self._model}"

    @property
    def dim(self) -> int:
        assert self._dim is not None
        return self._dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self._st_model is not None:
            vecs = self._st_model.encode(
                texts,
                batch_size=self._batch_size,
                show_progress_bar=False,
                normalize_embeddings=False,
            )
            arr = np.asarray(vecs, dtype=np.float32)
            return arr.tolist()

        if self._fastembed is not None:
            out: list[list[float]] = []
            for vec in self._fastembed.embed(texts):
                out.append([float(x) for x in vec])
            return out

        raise RuntimeError("LocalEmbedder not initialized")

