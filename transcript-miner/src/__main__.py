#!/usr/bin/env python3
"""Hauptmodul für die Ausführung des YouTube Transcript Miners."""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Füge das Projektverzeichnis zum Python-Pfad hinzu
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Stelle sicher, dass die Umgebungsvariablen geladen werden
load_dotenv()

# Starte die Hauptanwendung
if __name__ == "__main__":
    from transcript_miner.main import main

    main()
