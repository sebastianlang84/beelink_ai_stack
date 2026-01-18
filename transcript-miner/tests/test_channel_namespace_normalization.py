from __future__ import annotations

from transcript_ai_analysis.aggregation_runner import _normalize_channel_namespace as agg_ns
from transcript_ai_analysis.llm_report_generator import _normalize_channel_namespace as report_ns


def test_normalize_channel_namespace_prefers_raw_value() -> None:
    transcript_path = (
        "/tmp/output/stocks_crypto/1_transcripts/CouchInvestor/2025-12-31_42RfznSu91o.txt"
    )
    assert agg_ns("CouchInvestor", transcript_path) == "CouchInvestor"
    assert report_ns("CouchInvestor", transcript_path) == "CouchInvestor"


def test_normalize_channel_namespace_derives_from_prd_path_when_raw_missing() -> None:
    transcript_path = (
        "/tmp/output/stocks_crypto/1_transcripts/CouchInvestor/2025-12-31_42RfznSu91o.txt"
    )
    assert agg_ns("", transcript_path) == "CouchInvestor"
    assert report_ns(None, transcript_path) == "CouchInvestor"


def test_normalize_channel_namespace_supports_legacy_channel_before_1_transcripts() -> None:
    transcript_path = "/tmp/output/stocks_crypto/CouchInvestor/1_transcripts/2025-12-31_42RfznSu91o.txt"
    assert agg_ns(None, transcript_path) == "CouchInvestor"
    assert report_ns(None, transcript_path) == "CouchInvestor"

