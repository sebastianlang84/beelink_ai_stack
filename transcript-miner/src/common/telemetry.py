"""
Telemetrie-Modul für das YouTube Transcript Miner Projekt.

Dieses Modul stellt Metriken und Telemetrie-Funktionen bereit, die von der Mining-Pipeline
und nachgelagerten Analyse-Schritten verwendet werden können.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Mapping, Optional

try:
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.resources import Resource

    # Initialize MeterProvider and exporter
    resource = Resource.create({"service.name": "youtube-transcript-miner"})

    # Pytest captures/tears down stdout/stderr which can lead to background
    # exporter threads writing to closed file handles. Avoid periodic export
    # during tests.
    is_test = bool(os.getenv("PYTEST_CURRENT_TEST")) or ("pytest" in sys.modules)
    enable_console = os.getenv("ENABLE_TELEMETRY_CONSOLE", "false").lower() == "true"

    if is_test or not enable_console:
        provider = MeterProvider(resource=resource)
    else:
        exporter = ConsoleMetricExporter()
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=5000)
        provider = MeterProvider(metric_readers=[reader], resource=resource)
    metrics.set_meter_provider(provider)
    meter = metrics.get_meter("youtube-transcript-miner")

    # Metrics instruments
    llm_prompt_tokens_counter = meter.create_counter(
        "llm_prompt_tokens", unit="1", description="Number of prompt tokens sent to LLM"
    )
    pipeline_duration_histogram = meter.create_histogram(
        "pipeline_duration_seconds",
        unit="s",
        description="Duration of the transcript mining pipeline",
    )
    pipeline_errors_counter = meter.create_counter(
        "pipeline_errors_total", unit="1", description="Total number of pipeline errors"
    )
except ImportError:
    # Fallback: dummy metrics objects
    class DummyMetric:
        def add(self, *args, **kwargs):
            pass

        def record(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass  # Added for compatibility

    llm_prompt_tokens_counter = DummyMetric()
    pipeline_duration_histogram = DummyMetric()
    pipeline_errors_counter = DummyMetric()


def counter_add(
    counter: Any,
    amount: int | float = 1,
    attributes: Optional[Mapping[str, Any]] = None,
) -> None:
    """Best-effort counter increment across OpenTelemetry and fallback metrics.

    Evidence:
    - OpenTelemetry Counters use `add(amount, attributes)` (see usage in
      [`process_channel()`](src/transcript_miner/main.py:57)).
    - Fallback DummyMetric implements `.inc(...)` for compatibility.
    """

    if counter is None:
        return

    # OpenTelemetry API
    add = getattr(counter, "add", None)
    if callable(add):
        if attributes is None:
            add(amount)
        else:
            add(amount, dict(attributes))
        return

    # Legacy / fallback compatibility
    inc = getattr(counter, "inc", None)
    if callable(inc):
        inc(amount)


def record_pipeline_error(*, error_type: str, where: str | None = None) -> None:
    """Inkrementiert den Pipeline-Fehlerzähler mit stabilen Attributen."""

    attrs: dict[str, Any] = {"error_type": error_type}
    if where:
        attrs["where"] = where
    counter_add(pipeline_errors_counter, 1, attrs)


def record_llm_prompt_tokens(prompt_tokens: int) -> None:
    """Inkrementiert den LLM-Prompt-Token Counter (best-effort)."""

    if prompt_tokens <= 0:
        return
    counter_add(llm_prompt_tokens_counter, int(prompt_tokens), {"kind": "prompt"})
