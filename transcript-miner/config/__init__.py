# Ermöglicht die Nutzung von config als Python-Package.
# Die .yaml-Dateien bleiben weiterhin editierbar und werden nicht verändert.

import os
import yaml

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))


def load_yaml(filename):
    """Hilfsfunktion zum Laden einer YAML-Konfigurationsdatei aus dem config/-Ordner."""
    path = os.path.join(CONFIG_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Beispiel: config_data = load_yaml('config_stocks.yaml')
