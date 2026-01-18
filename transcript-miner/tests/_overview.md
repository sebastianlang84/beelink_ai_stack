# Tests Overview

Dieses Verzeichnis enthält die Testsuite für den Transcript Miner.

## Dateien

- [`conftest.py`](conftest.py): Gemeinsame Fixtures und Konfiguration für pytest.
- [`test_aggregation.py`](test_aggregation.py): Tests für die Aggregationslogik von Analyseergebnissen.
- [`test_analysis_runner.py`](test_analysis_runner.py): Tests für den Analysis Runner (Batch 1).
- [`test_cleanup_policy.py`](test_cleanup_policy.py): **(Konsolidiert)** Tests für die Retention- und Cleanup-Logik (ersetzt `test_transcript_retention_cleanup.py` und `test_output_retention_cleanup.py`).
- [`test_config.py`](test_config.py): Tests für das Laden und Validieren der YAML-Konfiguration.
- [`test_generate_filename_base.py`](test_generate_filename_base.py): Tests für die Generierung von Dateinamen.
- [`test_llm_output_validation_policy.py`](test_llm_output_validation_policy.py): Tests für die Validierung von LLM-Outputs.
- [`test_llm_runner.py`](test_llm_runner.py): Tests für den LLM-Analyse-Runner.
- [`test_multi_config_cli_multi_run.py`](test_multi_config_cli_multi_run.py): Tests für die Multi-Config CLI Funktionalität.
- [`test_multichannel_output_validation.py`](test_multichannel_output_validation.py): Validierungstests für Multi-Channel-Konfigurationen.
- [`test_output_policy.py`](test_output_policy.py): Tests für die Pfad-Auflösungslogik (`OutputConfig`).
- [`test_process_channel_integration.py`](test_process_channel_integration.py): Integrations-Tests für das Processing eines gesamten Kanals.
- [`test_progress_handling.py`](test_progress_handling.py): **(Konsolidiert)** Tests für atomares Schreiben, Korruptions-Handling, Deduplizierung und Filesystem-Sync (ersetzt `test_progress_atomic_write.py`, `test_progress_corruption_policy.py`, `test_progress_dedup.py` und `test_sync_progress_with_filesystem.py`).
- [`test_search_keywords.py`](test_search_keywords.py): Tests für die Keyword-Suche in Transkripten.
- [`test_smoke.py`](test_smoke.py): Einfache Smoke-Tests für CLI und Imports.
- [`test_summary_check_ingest.py`](test_summary_check_ingest.py): Tests für die Ingest-Prüfung von Summaries.
- [`test_telemetry_counter.py`](test_telemetry_counter.py): Tests für die Telemetrie-Funktionen.
- [`test_transcript_handling.py`](test_transcript_handling.py): Tests für das Herunterladen und Verarbeiten einzelner Videos (inkl. Skip-Logik).

## Unterverzeichnisse

- [`fixtures/`](fixtures): Testdaten und Beispieldateien.
