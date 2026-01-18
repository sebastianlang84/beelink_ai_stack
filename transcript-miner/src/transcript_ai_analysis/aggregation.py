from __future__ import annotations

from dataclasses import dataclass


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MentionRef:
    video_id: str
    channel_namespace: str

    def to_json(self) -> dict[str, object]:
        return {
            "video_id": self.video_id,
            "channel_namespace": self.channel_namespace,
        }


@dataclass(frozen=True)
class CanonicalMention:
    """A mention with canonicalization result attached.

    This is the minimal in-memory representation needed for deterministic
    Coverage/Aggregation (Batch 2+), per schemas in [`docs/architecture.md`](docs/architecture.md:327).
    """

    channel_namespace: str
    video_id: str
    canonical_symbol: str | None
    symbol_label: str | None = None


def _metric_json(
    *, key: str, mentions: list[MentionRef], labels: set[str] | None = None
) -> dict[str, object]:
    unique_videos = {m.video_id for m in mentions}
    unique_channels = {m.channel_namespace for m in mentions}
    out: dict[str, object] = {
        "key": key,
        "unique_video_count": len(unique_videos),
        "creator_count": len(unique_channels),
        "mention_count": len(mentions),
        "mentions_raw": len(mentions),
        "mentions_unique_video": len(unique_videos),
        "mentions_unique_creator": len(unique_channels),
    }
    if labels:
        sorted_labels = sorted(labels)
        preferred_label = sorted_labels[0]
        paren = f"({key})"
        for label in sorted_labels:
            if label.endswith(paren):
                preferred_label = label
                break
        out["preferred_label"] = preferred_label
        out["labels"] = sorted_labels
    return out


def aggregate_by_channel(
    *,
    mentions: list[CanonicalMention],
    generated_from: dict[str, str],
) -> dict[str, object]:
    """Aggregate coverage stats by `channel_namespace`.

    Determinism:
    - channels sorted lexicographically
    """

    by_channel: dict[str, list[MentionRef]] = {}
    for m in mentions:
        ref = MentionRef(
            video_id=m.video_id,
            channel_namespace=m.channel_namespace,
        )
        by_channel.setdefault(m.channel_namespace, []).append(ref)

    metrics: list[dict[str, object]] = []
    for channel in sorted(by_channel.keys()):
        metrics.append(_metric_json(key=channel, mentions=by_channel[channel]))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_from": generated_from,
        "metrics": metrics,
    }


def aggregate_by_symbol(
    *,
    mentions: list[CanonicalMention],
    generated_from: dict[str, str],
    include_unresolved: bool = False,
) -> dict[str, object]:
    """Aggregate coverage stats by canonical symbol.

    If `include_unresolved` is False, mentions with `canonical_symbol is None`
    are excluded.
    """

    by_symbol: dict[str, list[MentionRef]] = {}
    labels_by_symbol: dict[str, set[str]] = {}
    for m in mentions:
        if m.canonical_symbol is None and not include_unresolved:
            continue
        symbol = m.canonical_symbol or "__UNRESOLVED__"
        ref = MentionRef(
            video_id=m.video_id,
            channel_namespace=m.channel_namespace,
        )
        by_symbol.setdefault(symbol, []).append(ref)
        if m.symbol_label:
            labels_by_symbol.setdefault(symbol, set()).add(m.symbol_label)

    metrics: list[dict[str, object]] = []
    for symbol in sorted(by_symbol.keys()):
        metrics.append(
            _metric_json(
                key=symbol,
                mentions=by_symbol[symbol],
                labels=labels_by_symbol.get(symbol),
            )
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_from": generated_from,
        "metrics": metrics,
    }


def aggregate_global(
    *,
    mentions: list[CanonicalMention],
    generated_from: dict[str, str],
    include_unresolved: bool = False,
) -> dict[str, object]:
    """Single global metric entry (key = "global")."""

    filtered: list[CanonicalMention]
    if include_unresolved:
        filtered = mentions
    else:
        filtered = [m for m in mentions if m.canonical_symbol is not None]

    refs = [
        MentionRef(
            video_id=m.video_id,
            channel_namespace=m.channel_namespace,
        )
        for m in filtered
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_from": generated_from,
        "metrics": [_metric_json(key="global", mentions=refs)],
    }
