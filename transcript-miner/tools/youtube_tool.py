#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube API & Channel Diagnostic Tool.
Kombiniert Funktionalitäten zum Prüfen des API-Keys und Finden von Kanälen.
"""

import os
import sys
import yaml
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv
from googleapiclient.discovery import build

# Projektroot für Importe setzen
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Load environment variables from .env
load_dotenv(PROJECT_ROOT / ".env")

# Import our modules
try:
    from src.common import config
except ImportError:
    # Fallback if src is not in path correctly
    sys.path.append(str(PROJECT_ROOT / "src"))
    from common import config

# Logging einrichten
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def quick_check():
    """Einfache Schnellprüfung der API-Key-Verfügbarkeit."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    logger.info(f"API Key vorhanden: {bool(api_key)}")
    if api_key:
        logger.info(f"API Key Anfang/Ende: {api_key[:4]}...{api_key[-4:]}")
    else:
        logger.warning("Kein YouTube API Key in Umgebungsvariablen gefunden!")
    return bool(api_key)


def full_test(config_path: Path):
    """Führt einen vollständigen API-Key-Test mit einer Config-Datei durch."""
    logger.info(f"=== API-Key-Test mit {config_path} ===")

    if not config_path.exists():
        logger.error(f"Config-Datei nicht gefunden: {config_path}")
        return

    # 1. Rohe YAML-Datei untersuchen
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)
        logger.info(
            f"API-Key in YAML (roh): {raw_config.get('api', {}).get('youtube_api_key')}"
        )
    except Exception as e:
        logger.error(f"Fehler beim Lesen der YAML: {e}")

    # 2. Über Konfigurationsmodul laden
    try:
        app_config = config.load_config(config_path)
        api_key = app_config.api.youtube_api_key
        logger.info(f"API-Key nach Resolution: {api_key}")

        if api_key == "${YOUTUBE_API_KEY}":
            logger.error("Umgebungsvariablen-Substitution hat nicht funktioniert!")
            api_key = os.getenv("YOUTUBE_API_KEY")
    except Exception as e:
        logger.error(f"Fehler beim Laden der Config: {e}")
        api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:
        logger.error("Kein API-Key gefunden (weder in Config noch in Environment).")
        return

    # 3. Mit YouTube API-Client testen
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        logger.info("YouTube-Client erfolgreich erstellt.")

        # Test-Abfrage
        request = (
            youtube.channels().list(part="snippet", mine=True)
            if not os.getenv("YOUTUBE_API_KEY")
            else None
        )
        # Da 'mine=True' oft fehlschlägt ohne OAuth, machen wir eine einfache Suche
        request = youtube.search().list(
            part="snippet", q="YouTube", maxResults=1, type="video"
        )
        request.execute()
        logger.info("API-Verbindung erfolgreich validiert.")
    except Exception as e:
        logger.error(f"Fehler bei API-Validierung: {e}")


def find_channel(handle: str):
    """Sucht einen Kanal anhand seines Handles."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        logger.error("YOUTUBE_API_KEY nicht gesetzt.")
        return

    logger.info(f"Suche nach Kanal: {handle}")
    try:
        youtube = build("youtube", "v3", developerKey=api_key)

        # Handle normalisieren
        search_query = handle if handle.startswith("@") else f"@{handle}"

        request = youtube.search().list(
            part="snippet", q=search_query, type="channel", maxResults=1
        )
        response = request.execute()

        if not response.get("items"):
            logger.warning(f"Kein Kanal mit Handle '{handle}' gefunden.")
            return

        item = response["items"][0]
        channel_id = item["id"]["channelId"]
        channel_title = item["snippet"]["title"]

        logger.info(f"Kanal gefunden: {channel_title}")
        logger.info(f"Kanal-ID: {channel_id}")
        print(
            f'\nKonfigurations-Snippet:\nyoutube:\n  channels: ["{handle}"] # ID: {channel_id}'
        )

    except Exception as e:
        logger.error(f"Fehler bei Kanalsuche: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="YouTube API & Channel Diagnostic Tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Kommandos")

    # Check
    check_parser = subparsers.add_parser("check", help="Prüft API-Key und Verbindung")
    check_parser.add_argument(
        "--config", type=str, help="Pfad zur Config-Datei für detaillierten Test"
    )
    check_parser.add_argument("--quick", action="store_true", help="Nur Schnellprüfung")

    # Find
    find_parser = subparsers.add_parser("find", help="Findet Kanal-ID zu einem Handle")
    find_parser.add_argument(
        "handle", type=str, help="Kanal-Handle (z.B. @bravosresearch)"
    )

    args = parser.parse_args()

    if args.command == "check":
        if args.quick or not args.config:
            quick_check()
        if args.config:
            full_test(Path(args.config))
    elif args.command == "find":
        find_channel(args.handle)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
