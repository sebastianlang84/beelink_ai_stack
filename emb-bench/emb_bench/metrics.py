from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Metrics:
    recall_at_1: float
    recall_at_5: float
    recall_at_10: float
    recall_at_20: float
    mrr_at_10: float
    ndcg_at_10: float

    def as_dict(self) -> dict:
        return {
            "recall@1": self.recall_at_1,
            "recall@5": self.recall_at_5,
            "recall@10": self.recall_at_10,
            "recall@20": self.recall_at_20,
            "mrr@10": self.mrr_at_10,
            "ndcg@10": self.ndcg_at_10,
        }


def _dcg(rels: list[int], *, k: int) -> float:
    score = 0.0
    for i, rel in enumerate(rels[:k], start=1):
        if rel <= 0:
            continue
        score += (2.0**rel - 1.0) / math.log2(i + 1)
    return score


def compute_metrics(*, retrieved: dict[str, list[str]], qrels: dict[str, set[str]]) -> Metrics:
    ks = [1, 5, 10, 20]
    recall_sums = {k: 0.0 for k in ks}
    mrr_sum = 0.0
    ndcg_sum = 0.0
    n = 0

    for qid, rel_set in qrels.items():
        docs = retrieved.get(qid, [])
        if not rel_set:
            continue
        n += 1

        for k in ks:
            hit = any(d in rel_set for d in docs[:k])
            recall_sums[k] += 1.0 if hit else 0.0

        rr = 0.0
        for rank, d in enumerate(docs[:10], start=1):
            if d in rel_set:
                rr = 1.0 / rank
                break
        mrr_sum += rr

        rels = [1 if d in rel_set else 0 for d in docs[:10]]
        dcg = _dcg(rels, k=10)
        ideal = _dcg([1] * min(len(rel_set), 10), k=10)
        ndcg_sum += (dcg / ideal) if ideal > 0 else 0.0

    if n == 0:
        return Metrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    return Metrics(
        recall_at_1=recall_sums[1] / n,
        recall_at_5=recall_sums[5] / n,
        recall_at_10=recall_sums[10] / n,
        recall_at_20=recall_sums[20] / n,
        mrr_at_10=mrr_sum / n,
        ndcg_at_10=ndcg_sum / n,
    )

