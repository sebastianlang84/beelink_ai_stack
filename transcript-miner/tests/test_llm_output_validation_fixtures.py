from __future__ import annotations

from pathlib import Path

from transcript_ai_analysis.llm_output_validator import validate_llm_output_content


FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "llm_validator"


def _load_fixture(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _fixture_paths(kind: str) -> list[Path]:
    root = FIXTURES_ROOT / kind
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def test_llm_output_fixtures_ok() -> None:
    for path in _fixture_paths("ok"):
        result = validate_llm_output_content(content=_load_fixture(path))
        assert result.ok, f"{path} failed: {result.issues}"


def test_llm_output_fixtures_bad() -> None:
    for path in _fixture_paths("bad"):
        result = validate_llm_output_content(content=_load_fixture(path))
        assert not result.ok, f"{path} unexpectedly passed"
