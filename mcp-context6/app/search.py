from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    score: float
    title: str | None
    url: str
    heading_path: str
    snippet: str


def rrf_fuse(*, dense: list[tuple[str, float]], sparse: list[tuple[str, float]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}

    def add(rank_list: list[tuple[str, float]]) -> None:
        for rank, (cid, _score) in enumerate(rank_list, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)

    add(dense)
    add(sparse)
    return scores


def make_snippet(text: str, *, max_chars: int = 220) -> str:
    t = " ".join(text.strip().split())
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1] + "…"

