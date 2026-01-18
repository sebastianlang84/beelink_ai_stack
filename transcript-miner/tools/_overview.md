# Tools Overview

Dieses Verzeichnis enthält Hilfsskripte für Entwicklung, Debugging und Qualitätssicherung.

## Dateien

- [`quality_check.py`](quality_check.py): Zentrales Werkzeug zur statischen Code-Analyse (Docstrings, Type Hints, Magic Strings).
- [`repro_ip_block.py`](repro_ip_block.py): Minimales Skript zur Reproduktion von IP-Blocks/Rate-Limits durch YouTube.
- [`youtube_tool.py`](youtube_tool.py): **(Konsolidiert)** All-in-one Tool für YouTube API-Diagnose und Kanalsuche (ersetzt `youtube_api_check.py`, `youtube_find_channel.py` und `verify_paths.py`).
- [`migrate_output_layout.py`](migrate_output_layout.py): Migration von Legacy-Outputs (`output/<topic>/...`) in das globale Output-Layout.

## Nutzung

Die Tools sollten in der Regel aus dem Projekt-Root ausgeführt werden, um korrekte Pfade zu gewährleisten:

```bash
uv run python tools/quality_check.py all
uv run python tools/youtube_tool.py check --config config/config_ai_knowledge.yaml
uv run python tools/youtube_tool.py find @bravosresearch

# Doku-Hygiene: md->md Links prüfen (tracked docs)
uv run python tools/md_link_audit.py
```
