"""
Common Module.

Dieses Modul enthält gemeinsam genutzte Funktionalitäten, die von der Mining-Pipeline
und nachgelagerten Analyse-Schritten verwendet werden.
"""

from pathlib import Path

# Define project root relative to this file's location
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

__all__ = ["PROJECT_ROOT"]
