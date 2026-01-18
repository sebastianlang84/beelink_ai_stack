"""
Utilities for path resolution and manipulation.
"""

import copy
import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Union, Optional


logger = logging.getLogger(__name__)


def resolve_paths(config_data: Dict, base_path: Path) -> Dict:
    """Löst relative Pfade in der Konfiguration auf."""
    # Kopie erstellen, um die Originaldaten nicht zu verändern
    resolved_data = (
        copy.deepcopy(config_data) if isinstance(config_data, dict) else config_data
    )

    if not isinstance(resolved_data, dict):
        return resolved_data

    # Bekannte Pfad-Keys aus Konfigurationsmodellen
    path_keys = [
        "file",
        "error_log_file",
        "global",
        "global_root",
        "path",
        "root_path",
        "data_dir",
        "output_dir",
        "transcript_raw_dir",
        "transcript_output_dir",
        "prompt_file",
        "knowledge_dir",
        "backup_dir",
        "dlq_dir",
        "additional_files",
        "youtube_cookies",
    ]
    string_path_keys = {"file", "error_log_file", "youtube_cookies"}

    # Hauptverarbeitung
    for key, value in resolved_data.items():
        if isinstance(value, dict):
            resolved_data[key] = resolve_paths(value, base_path)
        elif isinstance(value, str) and key in path_keys:
            # String zu Path konvertieren mit korrekter Behandlung
            path_obj = _resolve_path(value, base_path)

            # Für Logging-Felder String zurückgeben
            if key in string_path_keys:
                resolved_data[key] = str(path_obj)
            else:
                resolved_data[key] = path_obj

        elif isinstance(value, list) and key in path_keys:
            # Listen von Pfaden verarbeiten
            resolved_list = []
            for item in value:
                if isinstance(item, str):
                    path_obj = _resolve_path(item, base_path)
                    # Für bestimmte Felder Strings zurückgeben
                    if key in string_path_keys or key == "additional_files":
                        resolved_list.append(str(path_obj))
                    else:
                        resolved_list.append(path_obj)
                else:
                    resolved_list.append(item)
            resolved_data[key] = resolved_list

    return resolved_data


def substitute_env_vars(value: str) -> str:
    """Ersetzt `${VAR}`-Platzhalter in Strings durch Umgebungsvariablen.

    Policy:
    - Wenn `${VAR}` vorkommt und `VAR` ist gesetzt → ersetzen.
    - Wenn `VAR` nicht gesetzt ist → Platzhalter bleibt unverändert (keine Exception).
    """
    if not value or not isinstance(value, str):
        return value

    if "${" not in value or "}" not in value:
        return value

    for var in re.findall(r"\${([^}]+)}", value):
        if var in os.environ:
            value = value.replace(f"${{{var}}}", os.environ[var])
    return value


def _resolve_path(path_str: str, base_path: Path) -> Path:
    """
    Resolve a single path string with environment variable expansion.

    Args:
        path_str: The path string to resolve
        base_path: Base path for resolving relative paths

    Returns:
        Resolved Path object
    """
    if not path_str or not isinstance(path_str, str):
        return Path(path_str) if path_str else Path()

    # Umgebungsvariablen ersetzen
    path_str = path_str.strip().strip('"').strip("'")
    path_str = substitute_env_vars(path_str)

    # Pfad normalisieren
    path_str = os.path.normpath(path_str)
    path_obj = Path(path_str)

    # Relative Pfade auflösen
    if not path_obj.is_absolute():
        # Führende ./ oder .\ entfernen
        if path_str.startswith("./") or path_str.startswith(".\\"):
            path_str = path_str[2:]
            path_obj = Path(path_str)

        return (base_path / path_obj).resolve()
    return path_obj


def ensure_parent_exists(file_path: Union[str, Path]) -> Path:
    """
    Stellt sicher, dass das Elternverzeichnis einer Datei existiert (Lazy Creation).
    Gibt das Path-Objekt der Datei zurück.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def archive_existing_reports(reports_dir: Path, run_id: str) -> Optional[Path]:
    """
    Verschiebt existierende Berichtsdateien in einen Archiv-Unterordner.

    Args:
        reports_dir: Das Verzeichnis, das die Berichte enthält (z.B. 3_reports/)
        run_id: Eine eindeutige ID für den Archiv-Ordner (z.B. run_TIMESTAMP_HASH)

    Returns:
        Der Pfad zum Archiv-Verzeichnis, wenn etwas archiviert wurde, sonst None.
    """
    if not reports_dir.exists():
        return None

    # Use the existing run_manifest.json only if it looks like an LLM manifest.
    resolved_run_id = run_id
    run_manifest_path = reports_dir / "run_manifest.json"
    if run_manifest_path.exists():
        try:
            manifest_data = json.loads(run_manifest_path.read_text(encoding="utf-8"))
            manifest_kind = str(manifest_data.get("kind", "")).strip().lower()
            manifest_run_id = str(manifest_data.get("run_id", "")).strip()
            is_llm_manifest = manifest_kind == "llm" or (
                not manifest_kind
                and manifest_data.get("run_fingerprint")
                and manifest_data.get("llm_dir")
            )
            if is_llm_manifest and manifest_run_id:
                if run_id and run_id != manifest_run_id:
                    logger.info(
                        "Archive run_id mismatch (expected): using run_manifest run_id=%s instead of provided run_id=%s",
                        manifest_run_id,
                        run_id,
                    )
                resolved_run_id = manifest_run_id
            elif manifest_kind or manifest_run_id:
                logger.info(
                    "Archive run_manifest ignored for archive naming (kind=%s run_id=%s)",
                    manifest_kind if manifest_kind else "<none>",
                    manifest_run_id if manifest_run_id else "<none>",
                )
        except Exception as exc:
            logger.warning(
                "Failed to read run_manifest.json for archive naming: %s", exc
            )

    # Dateien und Ordner, die archiviert werden sollen
    to_archive = [
        "report.json",
        "report.md",
        "report.txt",
        "report_de.md",
        "report_en.md",
        "run_summary.md",
        "metadata.json",
        "manifest.json",
        "run_manifest.json",
        "audit.jsonl",
        "system_prompt.txt",
        "user_prompt.txt",
        "raw_transcripts",
        "aggregates",
    ]

    # Prüfen, was davon tatsächlich existiert
    existing = [f for f in to_archive if (reports_dir / f).exists()]
    if not existing:
        return None

    archive_dir = reports_dir / "archive" / resolved_run_id
    archive_dir.mkdir(parents=True, exist_ok=True)

    for item in existing:
        src = reports_dir / item
        dst = archive_dir / item

        # Falls das Ziel bereits existiert (unwahrscheinlich bei Zeitstempel), löschen wir es
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()

        # Verschieben
        shutil.move(str(src), str(dst))

    return archive_dir
