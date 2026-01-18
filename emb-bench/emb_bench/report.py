from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .metrics import Metrics


@dataclass(frozen=True)
class RunRow:
    phase: str
    embedder: str
    reducer: str
    target_dim: int
    normalize: bool
    metrics: Metrics
    timing: dict
    storage_bytes_est: int


def write_csv(path: str, rows: list[RunRow]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "phase",
        "embedder",
        "reducer",
        "target_dim",
        "normalize",
        "storage_bytes_est",
        "recall@1",
        "recall@5",
        "recall@10",
        "recall@20",
        "mrr@10",
        "ndcg@10",
        "embed_corpus_time_s",
        "index_build_time_s",
        "embed_queries_time_s",
        "retrieval_time_s",
        "embed_call_p50_s",
        "embed_call_p95_s",
        "query_p50_s",
        "query_p95_s",
    ]
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            row = {
                "phase": r.phase,
                "embedder": r.embedder,
                "reducer": r.reducer,
                "target_dim": r.target_dim,
                "normalize": r.normalize,
                "storage_bytes_est": r.storage_bytes_est,
            }
            row.update(r.metrics.as_dict())
            row.update(r.timing)
            w.writerow(row)


def write_markdown(path: str, rows: list[RunRow]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("# Embedding Benchmark Report\n\nNo results.\n", encoding="utf-8")
        return

    # Rank primarily by nDCG@10, then Recall@10
    ranked = sorted(rows, key=lambda r: (r.metrics.ndcg_at_10, r.metrics.recall_at_10), reverse=True)
    best = ranked[0]

    lines: list[str] = []
    lines.append("# Embedding Benchmark Report\n")
    lines.append("## Best Configuration\n")
    lines.append(
        f"- phase: `{best.phase}`\n"
        f"- embedder: `{best.embedder}`\n"
        f"- reducer: `{best.reducer}`\n"
        f"- target_dim: `{best.target_dim}`\n"
        f"- normalize: `{best.normalize}`\n"
    )
    lines.append("## Ranking (Top 10)\n")
    lines.append("| rank | phase | embedder | reducer | dim | nDCG@10 | Recall@10 | mrr@10 | embed p95 (s) | query p95 (s) |\n")
    lines.append("|---:|---|---|---|---:|---:|---:|---:|---:|---:|\n")
    for i, r in enumerate(ranked[:10], start=1):
        lines.append(
            f"| {i} | {r.phase} | {r.embedder} | {r.reducer} | {r.target_dim} | "
            f"{r.metrics.ndcg_at_10:.4f} | {r.metrics.recall_at_10:.4f} | {r.metrics.mrr_at_10:.4f} | "
            f"{(r.timing.get('embed_call_p95_s') or 0.0):.3f} | {(r.timing.get('query_p95_s') or 0.0):.3f} |\n"
        )

    p.write_text("".join(lines), encoding="utf-8")

