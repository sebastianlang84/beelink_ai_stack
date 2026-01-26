"""
Konfigurationsmodul für das YouTube Transcript Miner Projekt.

Lädt und validiert Konfigurationen aus YAML-Dateien.
"""

from __future__ import annotations

import logging
import yaml
import os
from pathlib import Path
from typing import Any, Optional, Union

from .config_models import Config
from .path_utils import resolve_paths, substitute_env_vars


# Define project root relative to this file's location
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_GLOBAL_CONFIG_PATH = PROJECT_ROOT / "config" / "config_global.yaml"

# Konfiguriere Logger für detaillierteres Debugging
log = logging.getLogger(__name__)


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _deep_merge_global_then_topic(global_cfg: Any, topic_cfg: Any) -> Any:
    """Deep-merge global config into topic config.

    Policy (deterministic):
    - dict + dict: merge keys recursively.
    - otherwise (scalars, lists, type mismatch): topic wins if not None, else global.

    Rationale: global config is for cross-topic defaults, but topic config may override.
    """

    if isinstance(global_cfg, dict) and isinstance(topic_cfg, dict):
        merged: dict[str, Any] = dict(global_cfg)
        for k, v_topic in topic_cfg.items():
            if k in merged:
                merged[k] = _deep_merge_global_then_topic(merged[k], v_topic)
            else:
                merged[k] = v_topic
        return merged

    return topic_cfg if topic_cfg is not None else global_cfg


def _apply_proxy_env_overrides(config_data: dict[str, Any]) -> dict[str, Any]:
    """Override youtube.proxy via env vars (global across all configs)."""
    proxy_mode = os.environ.get("YOUTUBE_PROXY_MODE", "").strip()
    http_url = os.environ.get("YOUTUBE_PROXY_HTTP_URL", "").strip()
    https_url = os.environ.get("YOUTUBE_PROXY_HTTPS_URL", "").strip()
    ws_user = os.environ.get("WEBSHARE_USERNAME", "").strip()
    ws_pass = os.environ.get("WEBSHARE_PASSWORD", "").strip()
    locations = os.environ.get("YOUTUBE_PROXY_FILTER_IP_LOCATIONS", "").strip()

    if not any([proxy_mode, http_url, https_url, ws_user, ws_pass, locations]):
        return config_data

    youtube_cfg = config_data.setdefault("youtube", {})
    proxy_cfg = youtube_cfg.setdefault("proxy", {})

    if proxy_mode:
        proxy_cfg["mode"] = substitute_env_vars(proxy_mode)
    if http_url:
        proxy_cfg["http_url"] = substitute_env_vars(http_url)
    if https_url:
        proxy_cfg["https_url"] = substitute_env_vars(https_url)
    if ws_user:
        proxy_cfg["webshare_username"] = substitute_env_vars(ws_user)
    if ws_pass:
        proxy_cfg["webshare_password"] = substitute_env_vars(ws_pass)
    if locations:
        proxy_cfg["filter_ip_locations"] = [
            item.strip().lower() for item in locations.split(",") if item.strip()
        ]

    return config_data


def load_config(
    config_path: Optional[Union[str, Path]] = None,
    *,
    global_config_path: Optional[Union[str, Path]] = None,
) -> Config:
    """Lädt die Konfiguration aus einer YAML-Datei.

    Args:
        config_path: Pfad zur Topic-Konfigurationsdatei (optional)
        global_config_path: Optionaler Pfad zur globalen Konfiguration.
            - Wenn None: default ist `config/config_global.yaml` im Repo-Root.
            - Wenn gesetzt und Datei fehlt: es wird ohne globale Defaults geladen.

    Returns:
        Config-Objekt mit geladenen oder Standardwerten

    Raises:
        FileNotFoundError: Wenn die Konfigurationsdatei nicht existiert
        ValidationError: Bei ungültigen Konfigurationswerten
    """
    # Wenn kein Pfad angegeben, Standard-Config zurückgeben
    if config_path is None:
        return Config()

    # Pfad-Objekt erstellen
    if isinstance(config_path, str):
        config_path = Path(config_path)

    # Basisverzeichnis für relative Pfade bestimmen
    base_dir = config_path.parent.resolve()

    # Default global-config auto-loading is intentionally conservative:
    # only apply it for repo-managed configs under `<repo>/config/`.
    # Rationale: tests and ad-hoc configs (e.g. /tmp/config.yaml) should not
    # accidentally inherit repo-local global defaults.
    if global_config_path is None:
        try:
            in_repo_config_dir = config_path.resolve().is_relative_to(
                (PROJECT_ROOT / "config").resolve()
            )
        except Exception:
            in_repo_config_dir = False

        global_path = DEFAULT_GLOBAL_CONFIG_PATH if in_repo_config_dir else None
    else:
        global_path = (
            Path(global_config_path)
            if isinstance(global_config_path, str)
            else global_config_path
        )

    try:
        global_data: dict[str, Any] = {}
        if global_path is not None and global_path.exists():
            global_base_dir = global_path.parent.resolve()
            global_data = resolve_paths(_load_yaml_dict(global_path), global_base_dir)

        # YAML-Datei laden (Topic)
        topic_data = _load_yaml_dict(config_path)

        # Pfade auflösen
        topic_data = resolve_paths(topic_data, base_dir)

        # Merge: global -> topic (topic wins on conflicts)
        config_data = _deep_merge_global_then_topic(global_data, topic_data)
        # Env overrides (global across configs)
        config_data = _apply_proxy_env_overrides(config_data)

        # Config-Objekt erstellen und zurückgeben
        return Config(**config_data)

    except FileNotFoundError:
        log.error(f"Konfigurationsdatei nicht gefunden: {config_path}")
        raise
    except yaml.YAMLError as e:
        log.error(f"Fehler beim Parsen der YAML-Datei: {e}")
        raise
    except Exception as e:
        log.error(f"Fehler beim Laden der Konfiguration: {e}")
        raise


# Beispielcode für Tests
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    config = load_config(PROJECT_ROOT / "config" / "config_test.yaml")
    print(f"Geladene Konfiguration: {config}")
