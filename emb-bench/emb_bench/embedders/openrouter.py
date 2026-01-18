from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class OpenRouterResult:
    vectors: list[list[float]]
    request_latency_s: float


class OpenRouterEmbedder:
    def __init__(
        self,
        *,
        base_url: str,
        api_key_env: str,
        model: str,
        native_dim: int,
        timeout_s: int = 30,
        max_retries: int = 5,
        rpm_limit: int = 120,
        request_dimensions: int | None = None,
        call_latencies_sink: list[float] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = os.getenv(api_key_env, "").strip()
        self._model = model
        self._native_dim = int(native_dim)
        self._timeout_s = int(timeout_s)
        self._max_retries = int(max_retries)
        self._rpm_limit = int(rpm_limit)
        self._request_dimensions = request_dimensions
        self._sink = call_latencies_sink
        if not self._api_key:
            raise RuntimeError(f"Missing OpenRouter API key in env var: {api_key_env}")

        self._session = requests.Session()
        self._last_call_ts = 0.0

    @property
    def name(self) -> str:
        return f"openrouter:{self._model}"

    @property
    def dim(self) -> int:
        return self._native_dim

    def _rate_limit_sleep(self) -> None:
        if self._rpm_limit <= 0:
            return
        min_interval = 60.0 / float(self._rpm_limit)
        now = time.monotonic()
        delta = now - self._last_call_ts
        if delta < min_interval:
            time.sleep(min_interval - delta)

    def _post_embeddings(self, payload: dict[str, Any]) -> OpenRouterResult:
        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        for attempt in range(1, self._max_retries + 2):
            self._rate_limit_sleep()
            t0 = time.perf_counter()
            try:
                resp = self._session.post(url, headers=headers, json=payload, timeout=self._timeout_s)
            except Exception as e:
                if attempt > self._max_retries + 1:
                    raise
                time.sleep(min(10.0, 0.5 * attempt))
                continue
            latency = time.perf_counter() - t0
            self._last_call_ts = time.monotonic()
            if self._sink is not None:
                self._sink.append(latency)

            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt > self._max_retries + 1:
                    resp.raise_for_status()
                retry_after = resp.headers.get("Retry-After")
                sleep_s = float(retry_after) if retry_after and retry_after.isdigit() else min(20.0, 0.5 * attempt)
                time.sleep(sleep_s)
                continue

            resp.raise_for_status()
            data = resp.json()
            items = data.get("data")
            if not isinstance(items, list):
                raise RuntimeError("OpenRouter embeddings response missing 'data' list")
            vectors = []
            for item in items:
                emb = item.get("embedding")
                if not isinstance(emb, list):
                    raise RuntimeError("Invalid embedding in response")
                vectors.append([float(x) for x in emb])
            return OpenRouterResult(vectors=vectors, request_latency_s=latency)

        raise RuntimeError("unreachable")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, Any] = {"model": self._model, "input": texts}
        if self._request_dimensions is not None:
            payload["dimensions"] = int(self._request_dimensions)
        vectors = self._post_embeddings(payload).vectors
        expected = self._request_dimensions or self._native_dim
        for v in vectors:
            if len(v) != expected:
                raise RuntimeError(f"Embedding dim mismatch: expected {expected}, got {len(v)}")
        return vectors
