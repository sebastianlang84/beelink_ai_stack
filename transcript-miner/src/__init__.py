"""
YouTube Transcript Miner

Ein Tool zum Herunterladen und Verarbeiten von YouTube-Transkripten.
"""

# Stelle sicher, dass die Module korrekt importiert werden
import sys
from pathlib import Path

# Füge das Projektverzeichnis zum Python-Pfad hinzu
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Exportiere die wichtigsten Komponenten
__all__ = ["common", "transcript_miner"]
