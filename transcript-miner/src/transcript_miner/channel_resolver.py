"""
Channel Resolver Service

Dieser Service verwaltet die Zuordnung von YouTube-Kanalhandles zu Kanal-IDs
und bietet eine höhere Abstraktionsebene für die Interaktion mit der YouTube API.
Verwendet eine JSON-Datei als persistenten Speicher für die Mappings.
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, TypedDict, TypeVar, TYPE_CHECKING

# Vermeide zirkuläre Imports
if TYPE_CHECKING:
    from .youtube_client import VideoDetails

# Typ für den Google API-Client
Resource = TypeVar("Resource")

# Späte Importe zur Vermeidung von Zirkelimporten
try:
    from .youtube_client import (
        get_channel_by_handle,
        get_channel_videos,
        get_youtube_client,
    )
    from .youtube_client import VideoDetails as VideoDetailsType

    VideoDetails = VideoDetailsType  # Typalias für Rückwärtskompatibilität
except ImportError:
    # Fallback für den Fall, dass der Import fehlschlägt
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src.transcript_miner.youtube_client import (
        get_channel_by_handle,
        get_channel_videos,
        get_youtube_client,
        VideoDetails as VideoDetailsType,
    )

    VideoDetails = VideoDetailsType


# Typdefinitionen
class ChannelInfo(TypedDict):
    """Datenstruktur für Kanalinformationen."""

    id: str
    last_verified: str
    display_name: str


class ChannelMapping(TypedDict):
    """Datenstruktur für die gesamte Mapping-Datei."""

    version: int
    last_updated: str
    channels: Dict[str, ChannelInfo]


class ChannelResolver:
    """
    Verwaltet die Zuordnung von YouTube-Kanalhandles zu Kanal-IDs.

    Bietet eine höhere Abstraktionsebene für die Interaktion mit der YouTube API
    und verwaltet das Caching der Kanal-Informationen.
    """

    # Standardwerte
    DEFAULT_MAPPING_FILE = Path("output/_cache/channel_mapping.json")
    LEGACY_MAPPING_FILE = Path("config/channel_mapping.json")
    CACHE_VALID_DAYS = 30

    def __init__(self, youtube_client=None, mapping_file: Optional[Path] = None):
        """
        Initialisiert den ChannelResolver.

        Args:
            youtube_client: Optionaler YouTube API-Client. Falls nicht angegeben,
                         wird ein neuer erstellt.
            mapping_file:   Pfad zur Mapping-Datei. Falls nicht angegeben, wird
                         DEFAULT_MAPPING_FILE verwendet.
        """
        self.youtube = youtube_client or get_youtube_client()
        self.logger = logging.getLogger(__name__)

        # Setze den Pfad zur Mapping-Datei
        self._mapping_file = None
        self.set_mapping_file(mapping_file or self._get_default_mapping_file())

    def set_mapping_file(self, mapping_file: Path) -> None:
        """
        Setzt den Pfad zur Mapping-Datei und lädt ggf. vorhandene Mappings.

        Args:
            mapping_file: Pfad zur Mapping-Datei (kann auch String oder Path-ähnlich sein)
        """
        self._mapping_file = Path(mapping_file).resolve()
        self._mapping_file.parent.mkdir(parents=True, exist_ok=True)
        self._mapping = self._load_mapping()
        logging.info(f"Using channel mapping file: {self._mapping_file}")

    def _get_default_mapping_file(self) -> Path:
        """Gibt den Pfad zur Standard-Mapping-Datei zurück."""
        default_path = self.DEFAULT_MAPPING_FILE
        legacy_path = self.LEGACY_MAPPING_FILE

        if default_path.exists():
            return default_path

        if legacy_path.exists():
            try:
                default_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_path, default_path)
                logging.info(
                    "Migrated channel mapping cache from %s to %s",
                    legacy_path,
                    default_path,
                )
                return default_path
            except OSError as exc:
                logging.warning(
                    "Failed to migrate channel mapping cache from %s to %s: %s",
                    legacy_path,
                    default_path,
                    exc,
                )
                return legacy_path

        return default_path

    def _create_new_mapping(self) -> ChannelMapping:
        """Erstellt ein neues, leeres Mapping."""
        return {
            "version": 1,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "channels": {},
        }

    def _load_mapping(self) -> ChannelMapping:
        """Lädt die Mapping-Datei oder erstellt eine neue, falls nicht vorhanden."""
        if not self._mapping_file.exists():
            return self._create_new_mapping()

        try:
            with open(self._mapping_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validiere das Format der geladenen Daten
            if (
                not isinstance(data, dict)
                or "version" not in data
                or "channels" not in data
            ):
                logging.warning("Ungültiges Format der Mapping-Datei. Erstelle neue.")
                return self._create_new_mapping()

            return data

        except (json.JSONDecodeError, IOError) as e:
            logging.error(
                f"Fehler beim Lesen der Mapping-Datei {self._mapping_file}: {e}"
            )
            return self._create_new_mapping()

    def _save_mapping(self) -> None:
        """Speichert die aktuellen Mappings in die Datei."""
        try:
            with open(self._mapping_file, "w", encoding="utf-8") as f:
                json.dump(self._mapping, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logging.error(
                f"Fehler beim Speichern der Mapping-Datei {self._mapping_file}: {e}"
            )

    def resolve_channel_id(self, channel_input: str) -> Optional[str]:
        """
        Löst einen Kanal-Input (Handle, URL oder ID) in eine Kanal-ID auf.

        Args:
            channel_input: Kanal-Handle (mit oder ohne @), URL oder ID

        Returns:
            Die Kanal-ID oder None, wenn der Kanal nicht gefunden wurde.
        """
        # Normalisiere die Eingabe
        channel_input = channel_input.strip()

        # Prüfe, ob die Eingabe bereits eine Kanal-ID ist
        if channel_input.startswith("UC") and len(channel_input) == 24:
            return channel_input

        # Prüfe, ob die Eingabe eine URL ist
        if "youtube.com" in channel_input or "youtu.be" in channel_input:
            from urllib.parse import urlparse, parse_qs

            # Extrahiere die Video-ID oder Kanal-ID aus der URL
            parsed = urlparse(channel_input)

            if "youtube.com" in parsed.netloc:
                if parsed.path == "/channel" or parsed.path.startswith("/channel/"):
                    # Kanal-URL: https://www.youtube.com/channel/UCxxx
                    return parsed.path.split("/")[-1]
                elif "v=" in parsed.query:
                    # Video-URL: https://www.youtube.com/watch?v=xxx
                    video_id = parse_qs(parsed.query).get("v", [""])[0]
                    if video_id:
                        return self._get_channel_id_from_video(video_id)
            elif "youtu.be" in parsed.netloc:
                # Kurz-URL: https://youtu.be/xxx
                video_id = parsed.path.lstrip("/")
                if video_id:
                    return self._get_channel_id_from_video(video_id)

        # Prüfe, ob der Kanal bereits im Cache ist
        cache_key = channel_input.lower().lstrip("@")
        if cache_key in self._mapping["channels"]:
            channel_info = self._mapping["channels"][cache_key]
            last_verified = datetime.fromisoformat(channel_info["last_verified"])

            # Prüfe, ob der Cache-Eintrag noch gültig ist
            if (
                datetime.now(timezone.utc) - last_verified
            ).days < self.CACHE_VALID_DAYS:
                return channel_info["id"]

        # Versuche, die Kanal-ID über die API zu ermitteln
        channel_info = get_channel_by_handle(self.youtube, channel_input)
        if channel_info:
            # Aktualisiere den Cache
            self._mapping["channels"][cache_key] = {
                "id": channel_info["id"],
                "display_name": channel_info.get("title", channel_input),
                "last_verified": datetime.now(timezone.utc).isoformat(),
            }
            self._save_mapping()
            return channel_info["id"]

        return None

    def _get_channel_id_from_video(self, video_id: str) -> Optional[str]:
        """
        Ermittelt die Kanal-ID anhand einer Video-ID.

        Args:
            video_id: Die YouTube-Video-ID

        Returns:
            Die Kanal-ID oder None, wenn das Video nicht gefunden wurde.
        """
        try:
            video_response = (
                self.youtube.videos()
                .list(part="snippet", id=video_id, maxResults=1)
                .execute()
            )

            if not video_response.get("items"):
                return None

            return video_response["items"][0]["snippet"]["channelId"]

        except Exception as e:
            logging.error(f"Fehler beim Abrufen des Kanals für Video {video_id}: {e}")
            return None

    def _resolve_handle(self, channel_input: str) -> Optional[Dict[str, str]]:
        """Resolve a channel handle to channel info."""
        channel_id = self.resolve_channel_id(channel_input)
        if not channel_id:
            return None

        # Get channel info from cache or API
        channel_info = self.get_channel_info(channel_input)
        if channel_info:
            return {
                "id": channel_id,
                "display_name": channel_info.get("title", channel_input),
            }
        return None

    def get_channel_info(self, channel_input: str) -> Optional[Dict[str, Any]]:
        """
        Gibt Kanalinformationen für einen Kanal zurück.

        Args:
            channel_input: Kanal-Handle, URL oder ID

        Returns:
            Dict mit Kanalinformationen oder None, wenn der Kanal nicht gefunden wurde
        """
        channel_id = self.resolve_channel_id(channel_input)
        if not channel_id:
            return None

        # Prüfe, ob der Kanal bereits im Cache ist
        cache_key = channel_input.lower().lstrip("@")
        if cache_key in self._mapping["channels"]:
            return self._mapping["channels"][cache_key]

        # Wenn nicht im Cache, rufe die Kanalinformationen ab
        try:
            response = (
                self.youtube.channels()
                .list(part="snippet,contentDetails", id=channel_id, maxResults=1)
                .execute()
            )

            if not response.get("items"):
                return None

            channel = response["items"][0]
            channel_info = {
                "id": channel_id,
                "title": channel["snippet"]["title"],
                "description": channel["snippet"].get("description", ""),
                "published_at": channel["snippet"]["publishedAt"],
                "last_verified": datetime.now(timezone.utc).isoformat(),
                "thumbnail": channel["snippet"]["thumbnails"]["default"]["url"],
            }

            # Aktualisiere den Cache
            self._mapping["channels"][cache_key] = channel_info
            self._save_mapping()

            return channel_info

        except Exception as e:
            logging.error(
                f"Fehler beim Abrufen der Kanalinformationen für {channel_id}: {e}"
            )
            return None

    def get_channel_videos(
        self,
        channel_input: str,
        *,
        max_results: int = 50,
        published_after: Optional[datetime] = None,
        exclude_live_events: bool = True,
    ) -> List[VideoDetails]:
        """
        Holt die neuesten Videos eines Kanals.

        Args:
            channel_input: Kanal-Handle, URL oder ID
            max_results: Maximale Anzahl der zurückzugebenden Videos
            published_after: Nur Videos nach diesem Datum berücksichtigen
            exclude_live_events: Wenn true, werden Live-Events herausgefiltert

        Returns:
            Liste von VideoDetails-Objekten
        """
        channel_id = self.resolve_channel_id(channel_input)
        if not channel_id:
            return []

        videos = get_channel_videos(
            self.youtube,
            channel_id,
            max_results=max_results,
            published_after=published_after,
        )

        # Filter live events if requested
        if exclude_live_events:
            filtered_videos = [v for v in videos if not v.get("is_live_event", False)]
            excluded_count = len(videos) - len(filtered_videos)
            if excluded_count > 0:
                logging.info(
                    f"Excluded {excluded_count} live events from channel {channel_input}"
                )
            return filtered_videos

        return videos


# Globale Instanzen für einfache Verwendung
_youtube_client = None
_channel_resolver = None


def get_channel_resolver(youtube_client=None, mapping_file: Optional[Path] = None):
    """
    Gibt eine globale ChannelResolver-Instanz zurück.

    Args:
        youtube_client: Optionaler YouTube-Client. Falls nicht angegeben, wird eine neue Instanz erstellt.
        mapping_file:   Optionaler Pfad zur Mapping-Datei. Falls nicht angegeben, wird die Standarddatei verwendet.

    Returns:
        ChannelResolver-Instanz
    """
    global _youtube_client, _channel_resolver

    needs_update = (
        _channel_resolver is None
        or (youtube_client and youtube_client != _youtube_client)
        or (
            mapping_file
            and getattr(_channel_resolver, "_mapping_file", None) != mapping_file
        )
    )

    if needs_update:
        _youtube_client = youtube_client or get_youtube_client()
        _channel_resolver = ChannelResolver(youtube_client=_youtube_client)
        if mapping_file:
            _channel_resolver.set_mapping_file(mapping_file)

    return _channel_resolver


def get_videos_for_channel_with_client(
    youtube_client,
    channel_id: str,
    num_videos: int = 10,
    published_after: Optional[datetime] = None,
    exclude_live_events: bool = True,
) -> List[Dict]:
    """
    Convenience function to get videos for a channel using an existing client.

    Args:
        youtube_client: Existing YouTube API client
        channel_id: The channel ID
        num_videos: Number of videos to retrieve
        published_after: Only include videos after this timestamp (UTC, naive)
        exclude_live_events: Wenn true, werden Live-Events herausgefiltert

    Returns:
        List of video dictionaries
    """
    try:
        videos = get_channel_videos(
            youtube_client,
            channel_id,
            max_results=num_videos,
            published_after=published_after,
        )
        
        # Filter live events if requested
        if exclude_live_events:
            filtered_videos = [v for v in videos if not v.get("is_live_event", False)]
            excluded_count = len(videos) - len(filtered_videos)
            if excluded_count > 0:
                logging.info(
                    f"Excluded {excluded_count} live events from channel {channel_id}"
                )
            return filtered_videos
        
        return videos
    except Exception as e:
        logging.error(f"Error getting videos for channel {channel_id}: {e}")
        return []
