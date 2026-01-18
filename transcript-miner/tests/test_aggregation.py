from __future__ import annotations

from transcript_ai_analysis.aggregation import (
    aggregate_by_channel,
    aggregate_by_symbol,
    aggregate_global,
    CanonicalMention,
)


def _mentions() -> list[CanonicalMention]:
    return [
        CanonicalMention(
            channel_namespace="chan_a",
            video_id="v1",
            canonical_symbol="AAPL",
        ),
        CanonicalMention(
            channel_namespace="chan_a",
            video_id="v1",
            canonical_symbol="AAPL",
        ),
        CanonicalMention(
            channel_namespace="chan_b",
            video_id="v2",
            canonical_symbol="MSFT",
        ),
        CanonicalMention(
            channel_namespace="chan_b",
            video_id="v3",
            canonical_symbol=None,
        ),
    ]


def test_aggregate_by_channel_counts_unique_videos_and_mentions() -> None:
    out = aggregate_by_channel(
        mentions=_mentions(),
        generated_from={"batch2_manifest_path": "x", "run_fingerprint": "y"},
    )

    assert out["schema_version"] == 1
    metrics = out["metrics"]
    assert [m["key"] for m in metrics] == ["chan_a", "chan_b"]

    chan_a = metrics[0]
    assert chan_a["unique_video_count"] == 1
    assert chan_a["creator_count"] == 1
    assert chan_a["mention_count"] == 2
    assert chan_a["mentions_raw"] == 2
    assert chan_a["mentions_unique_video"] == 1
    assert chan_a["mentions_unique_creator"] == 1

    chan_b = metrics[1]
    assert (
        chan_b["unique_video_count"] == 2
    )  # v2 + v3 (unresolved still counts by channel)
    assert chan_b["creator_count"] == 1
    assert chan_b["mention_count"] == 2
    assert chan_b["mentions_raw"] == 2
    assert chan_b["mentions_unique_video"] == 2
    assert chan_b["mentions_unique_creator"] == 1


def test_aggregate_by_symbol_excludes_unresolved_by_default() -> None:
    out = aggregate_by_symbol(
        mentions=_mentions(),
        generated_from={"batch2_manifest_path": "x", "run_fingerprint": "y"},
    )
    metrics = out["metrics"]
    assert [m["key"] for m in metrics] == ["AAPL", "MSFT"]

    aapl = metrics[0]
    assert aapl["unique_video_count"] == 1
    assert aapl["creator_count"] == 1  # only chan_a
    assert aapl["mention_count"] == 2
    assert aapl["mentions_raw"] == 2
    assert aapl["mentions_unique_video"] == 1
    assert aapl["mentions_unique_creator"] == 1


def test_aggregate_global_is_single_metric_and_excludes_unresolved_by_default() -> None:
    out = aggregate_global(
        mentions=_mentions(),
        generated_from={"batch2_manifest_path": "x", "run_fingerprint": "y"},
    )
    metrics = out["metrics"]
    assert len(metrics) == 1
    assert metrics[0]["key"] == "global"
    assert metrics[0]["unique_video_count"] == 2  # v1 + v2
    assert metrics[0]["creator_count"] == 2  # chan_a + chan_b
    assert metrics[0]["mention_count"] == 3  # m1,m2,m3
    assert metrics[0]["mentions_raw"] == 3
    assert metrics[0]["mentions_unique_video"] == 2
    assert metrics[0]["mentions_unique_creator"] == 2


def test_aggregate_by_symbol_can_include_unresolved_bucket() -> None:
    out = aggregate_by_symbol(
        mentions=_mentions(),
        generated_from={"batch2_manifest_path": "x", "run_fingerprint": "y"},
        include_unresolved=True,
    )
    keys = [m["key"] for m in out["metrics"]]
    assert keys == ["AAPL", "MSFT", "__UNRESOLVED__"]
    unresolved = out["metrics"][2]
    assert unresolved["unique_video_count"] == 1
    assert unresolved["creator_count"] == 1
    assert unresolved["mention_count"] == 1
    assert unresolved["mentions_raw"] == 1
    assert unresolved["mentions_unique_video"] == 1
    assert unresolved["mentions_unique_creator"] == 1


def test_aggregation_empty_input_is_well_formed() -> None:
    generated_from = {"batch2_manifest_path": "x", "run_fingerprint": "y"}

    by_channel = aggregate_by_channel(mentions=[], generated_from=generated_from)
    assert by_channel["metrics"] == []

    by_symbol = aggregate_by_symbol(mentions=[], generated_from=generated_from)
    assert by_symbol["metrics"] == []

    global_out = aggregate_global(mentions=[], generated_from=generated_from)
    metrics = global_out["metrics"]
    assert len(metrics) == 1
    assert metrics[0]["key"] == "global"
    assert metrics[0]["unique_video_count"] == 0
    assert metrics[0]["creator_count"] == 0
    assert metrics[0]["mention_count"] == 0
    assert metrics[0]["mentions_raw"] == 0
    assert metrics[0]["mentions_unique_video"] == 0
    assert metrics[0]["mentions_unique_creator"] == 0


def test_aggregate_by_channel_includes_generated_from_verbatim_and_schema_version() -> (
    None
):
    generated_from = {"batch2_manifest_path": "p", "run_fingerprint": "f"}
    out = aggregate_by_channel(mentions=_mentions(), generated_from=generated_from)
    assert out["generated_from"] == generated_from
    assert out["schema_version"] == 1


def test_aggregate_global_include_unresolved_changes_counts() -> None:
    generated_from = {"batch2_manifest_path": "x", "run_fingerprint": "y"}
    out = aggregate_global(
        mentions=_mentions(), generated_from=generated_from, include_unresolved=True
    )
    metric = out["metrics"][0]
    assert metric["unique_video_count"] == 3  # v1,v2,v3
    assert metric["creator_count"] == 2  # chan_a, chan_b
    assert metric["mention_count"] == 4
    assert metric["mentions_raw"] == 4
    assert metric["mentions_unique_video"] == 3
    assert metric["mentions_unique_creator"] == 2


def test_aggregate_by_symbol_creator_count_multiple_channels() -> None:
    mentions = [
        CanonicalMention(
            channel_namespace="chan_a",
            video_id="v1",
            canonical_symbol="AAPL",
        ),
        CanonicalMention(
            channel_namespace="chan_b",
            video_id="v2",
            canonical_symbol="AAPL",
        ),
    ]
    out = aggregate_by_symbol(
        mentions=mentions,
        generated_from={"batch2_manifest_path": "x", "run_fingerprint": "y"},
    )
    aapl = out["metrics"][0]
    assert aapl["key"] == "AAPL"
    assert aapl["creator_count"] == 2
    assert aapl["unique_video_count"] == 2
    assert aapl["mention_count"] == 2
    assert aapl["mentions_raw"] == 2
    assert aapl["mentions_unique_video"] == 2
    assert aapl["mentions_unique_creator"] == 2


def test_aggregate_by_symbol_emits_labels_and_preferred_label_when_available() -> None:
    mentions = [
        CanonicalMention(
            channel_namespace="chan_a",
            video_id="v1",
            canonical_symbol="TSLA",
            symbol_label="Tesla (TSLA)",
        ),
        CanonicalMention(
            channel_namespace="chan_b",
            video_id="v2",
            canonical_symbol="TSLA",
            symbol_label="Tesla, Inc. (TSLA)",
        ),
    ]
    out = aggregate_by_symbol(
        mentions=mentions,
        generated_from={"batch2_manifest_path": "x", "run_fingerprint": "y"},
    )
    metric = out["metrics"][0]
    assert metric["key"] == "TSLA"
    assert metric["labels"] == ["Tesla (TSLA)", "Tesla, Inc. (TSLA)"]
    assert metric["preferred_label"] == "Tesla (TSLA)"
