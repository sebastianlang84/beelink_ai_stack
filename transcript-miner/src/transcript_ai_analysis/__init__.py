"""Transcript AI Analysis (Batch 2+).

Dieses Package ist das Ziel-„Zuhause“ für die Batch-2+-Analyse (Extraktion →
Aggregation), siehe Zielbild in [`docs/architecture.md`](docs/architecture.md:115).
"""

from .aggregation import (
    CanonicalMention,
    aggregate_by_channel,
    aggregate_by_symbol,
    aggregate_global,
)

__all__ = [
    "CanonicalMention",
    "aggregate_by_channel",
    "aggregate_by_symbol",
    "aggregate_global",
]
