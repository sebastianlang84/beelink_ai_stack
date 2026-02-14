from transcript_ai_analysis.llm_report_generator import (
    _effective_report_model_for_backend,
    _resolve_llm_backend,
)


def test_report_backend_resolves_gemini_cli(monkeypatch):
    monkeypatch.setenv("TM_LLM_BACKEND", "gemini_cli")
    assert _resolve_llm_backend(model="openai/gpt-5.2") == "gemini_cli"


def test_report_model_falls_back_for_gemini_cli(monkeypatch):
    monkeypatch.delenv("TM_GEMINI_CLI_MODEL", raising=False)
    model = _effective_report_model_for_backend(
        model="openai/gpt-5.2",
        backend="gemini_cli",
    )
    assert model == "gemini-3-flash-preview"


def test_report_model_keeps_gemini_model_for_gemini_cli(monkeypatch):
    monkeypatch.setenv("TM_GEMINI_CLI_MODEL", "gemini-2.5-flash")
    model = _effective_report_model_for_backend(
        model="google/gemini-3-flash-preview",
        backend="gemini_cli",
    )
    # explicit report config model wins; TM_GEMINI_CLI_MODEL is only used as fallback
    assert model == "google/gemini-3-flash-preview"


def test_report_model_unchanged_for_openrouter(monkeypatch):
    monkeypatch.setenv("TM_GEMINI_CLI_MODEL", "gemini-2.5-flash")
    model = _effective_report_model_for_backend(
        model="openai/gpt-5.2",
        backend="openrouter",
    )
    assert model == "openai/gpt-5.2"
