"""
Hauptmodul für die Kommandozeilenausführung des Transcript Miners.
"""

import sys
from pathlib import Path

# Füge das Projektverzeichnis zum Python-Pfad hinzu
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Stelle sicher, dass die Umgebungsvariablen geladen werden
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv ist optional

# Starte die Hauptanwendung
if __name__ == "__main__":
    from transcript_miner.main import main

    main()
