from pathlib import Path
from transcript_ai_analysis.report_generator import ReportGenerator, ReportContext


def test_report_generator_formats_timestamp_nicely(tmp_path: Path):
    ctx = ReportContext(
        run_id="run_123",
        timestamp="2025-12-29T22:10:20.548000+00:00",
        profile_root=tmp_path,
        aggregates_dir=tmp_path / "aggregates",
        summaries_dir=tmp_path / "summaries",
    )
    generator = ReportGenerator(ctx)
    header = generator._generate_header()

    # Check if the timestamp is formatted nicely
    # Expected: 2025-12-29 22:10:20 UTC
    assert "2025-12-29 22:10:20 UTC" in header
    assert "2025-12-29T22:10:20.548000+00:00" not in header
