from __future__ import annotations

import uuid

import numpy as np

from .base import IndexBackend


class QdrantIndex(IndexBackend):
    def __init__(self, *, url: str, collection: str, dim: int, distance: str = "cosine") -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.models import Distance, VectorParams
        except Exception as e:
            raise RuntimeError("QdrantIndex requires qdrant-client") from e

        self._client = QdrantClient(url=url)
        self._collection = collection
        dist = Distance.COSINE if distance.lower() == "cosine" else Distance.DOT

        if self._client.collection_exists(collection_name=collection):
            self._client.delete_collection(collection_name=collection)
        self._client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=int(dim), distance=dist),
        )

    def upsert(self, *, ids: list[str], vectors: np.ndarray) -> None:
        from qdrant_client.http.models import PointStruct

        points = []
        for doc_id, vec in zip(ids, vectors.tolist(), strict=True):
            points.append(PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, doc_id)), vector=vec, payload={"doc_id": doc_id}))
        self._client.upsert(collection_name=self._collection, points=points)

    def query(self, *, vector: np.ndarray, top_k: int) -> list[str]:
        res = self._client.search(collection_name=self._collection, query_vector=vector.tolist(), limit=int(top_k))
        out = []
        for r in res:
            payload = r.payload or {}
            if "doc_id" in payload:
                out.append(str(payload["doc_id"]))
        return out

    def close(self) -> None:
        return None

