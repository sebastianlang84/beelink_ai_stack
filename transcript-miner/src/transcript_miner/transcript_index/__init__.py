"""Offline analysis utilities.

Batch 1 (MVP): scan existing transcript outputs under an output-root and write
deterministic analysis artefacts (manifest + transcript index + audit log).
"""

from .models import AnalysisManifest, TranscriptRef
from .runner import write_analysis_index
from .scanner import ScanResult, scan_output_roots

__all__ = [
    "AnalysisManifest",
    "TranscriptRef",
    "ScanResult",
    "scan_output_roots",
    "write_analysis_index",
]
