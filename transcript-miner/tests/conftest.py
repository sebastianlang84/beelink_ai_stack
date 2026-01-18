"""Konfiguration für Tests.

Wichtig: Keine globalen Monkeypatches auf optionale Dependencies.
Sonst brechen Tests in Minimal-Installationen (ohne `google-api-python-client`).
"""

import pytest


@pytest.fixture(autouse=True)
def _block_external_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blockiert unbeabsichtigte externe Calls in Tests (offline-sicher).

    Wichtig: Nur gezielte Monkeypatches (kein sys.modules-Hacking), damit Tests,
    die bewusst einzelne Funktionen überschreiben (z.B. download_transcript_result
    in [`tests/test_transcript_handling.py`](tests/test_transcript_handling.py:1)),
    weiterhin funktionieren.
    """

    def _blocked(*_args, **_kwargs):
        raise RuntimeError("Network call blocked in tests")

    # YouTube Data API (googleapiclient) Einstiegspunkte
    monkeypatch.setattr("transcript_miner.youtube_client.get_youtube_client", _blocked)
    monkeypatch.setattr(
        "transcript_miner.youtube_client._execute_with_retries", _blocked
    )

    # YouTube Transcript API (youtube_transcript_api) Zugriff
    monkeypatch.setattr(
        "transcript_miner.transcript_downloader._list_transcripts", _blocked
    )

    # Optional: OpenAI Wrapper blockieren
    monkeypatch.setattr("common.utils.call_openai_with_retry", _blocked)


@pytest.fixture(autouse=True)
def _allow_explicit_llm_runner_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lässt Tests gezielt LLM-Calls stubben.

    Default: Der zentrale Offline-Guard blockiert `common.utils.call_openai_with_retry`.
    Für Tests, die bewusst ein LLM-Modul via Stub testen, überschreiben wir hier
    nichts zusätzlich; dieser Fixture existiert nur als Dokumentation/Anchor für
    künftige Anpassungen.
    """

    # no-op by design
    return None
