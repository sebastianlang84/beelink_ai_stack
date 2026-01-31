"""
Pydantic models for configuration validation.
"""

from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator
import re

from .path_utils import substitute_env_vars


class ProxyConfig(BaseModel):
    """Konfiguration für Proxies."""

    mode: Literal["none", "generic", "webshare"] = Field(
        "none", description="Proxy-Modus: none, generic oder webshare"
    )
    http_url: Optional[str] = Field(None, description="HTTP Proxy URL (für generic)")
    https_url: Optional[str] = Field(None, description="HTTPS Proxy URL (für generic)")
    webshare_username: Optional[str] = Field(None, description="Webshare.io Username")
    webshare_password: Optional[str] = Field(None, description="Webshare.io Password")
    filter_ip_locations: List[str] = Field(
        default_factory=list,
        description="Liste von Länder-Codes für Proxies (z.B. ['us', 'de'])",
    )

    @field_validator("mode", mode="before")
    @classmethod
    def resolve_mode_env_vars(cls, value: Optional[str]) -> str:
        """Ersetzt Umgebungsvariablen im Proxy-Modus."""
        if not value:
            return "none"
        if isinstance(value, str):
            resolved = substitute_env_vars(value).strip().lower()
            if not resolved or re.search(r"\${[^}]+}", resolved):
                return "none"
            return resolved
        return "none"

    @field_validator("http_url", "https_url", "webshare_username", "webshare_password")
    @classmethod
    def resolve_proxy_env_vars(cls, value: Optional[str]) -> Optional[str]:
        """Ersetzt Umgebungsvariablen in Proxy-Strings."""
        if not value or not isinstance(value, str):
            return value

        resolved = substitute_env_vars(value)
        if re.search(r"\${[^}]+}", resolved):
            return None
        return resolved

    @field_validator("filter_ip_locations", mode="before")
    @classmethod
    def resolve_filter_locations(cls, value: Optional[object]) -> List[str]:
        """Erlaubt CSV-Strings oder Env-Substitution für Länder-Codes."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            resolved = substitute_env_vars(value)
            if not resolved or re.search(r"\${[^}]+}", resolved):
                return []
            return [item.strip().lower() for item in resolved.split(",") if item.strip()]
        return []


class YoutubeConfig(BaseModel):
    """YouTube-spezifische Konfiguration (Kanäle und Filteroptionen)."""

    channels: List[str] = Field(
        default_factory=list,
        description="Liste der Kanal-Handles (z.B. @handle) oder URLs",
    )

    # Filter-Optionen integriert direkt in YoutubeConfig
    num_videos: int = Field(
        10,
        ge=1,
        description="Anzahl der neuesten Videos, die verarbeitet werden sollen",
    )
    lookback_days: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "Optionales Zeitfenster (Tage) fuer die Videoauswahl. "
            "Wenn gesetzt, werden nur Videos der letzten N Tage beruecksichtigt."
        ),
    )
    max_videos_per_channel: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "Maximale Anzahl Videos pro Kanal innerhalb des Zeitfensters. "
            "Fallback: num_videos."
        ),
    )
    keywords: List[str] = Field(
        default_factory=list, description="Suchbegriffe für Titel/Transkript-Filterung"
    )
    preferred_languages: List[str] = Field(
        default_factory=lambda: ["en", "de"],
        description="Bevorzugte Sprachen für Transkripte",
    )
    force_redownload_transcripts: bool = Field(
        False,
        description="Erzwingt den erneuten Download von Transkripten, auch wenn eine Summary existiert",
    )

    # Rate Limiting & Backoff (IP-Block Prevention)
    min_delay_s: float = Field(
        2.0, ge=0.0, description="Minimale Pause vor jedem Transcript-Download"
    )
    jitter_s: float = Field(1.0, ge=0.0, description="Zufälliger Jitter für die Pause")
    max_retries: int = Field(
        5, ge=0, description="Maximale Anzahl an Retries bei 429 Fehlern"
    )
    backoff_base_s: float = Field(
        2.0, ge=1.0, description="Basis für exponentiellen Backoff"
    )
    backoff_cap_s: float = Field(
        120.0, ge=1.0, description="Maximum für exponentiellen Backoff"
    )
    cooldown_on_block_s: int = Field(
        900, ge=0, description="Cooldown-Zeit nach einem IP-Block (Sekunden)"
    )

    exclude_live_events: bool = Field(
        True,
        description="Wenn true, werden Live-Events und anstehende Streams aus der Video-Auswahl herausgefiltert"
    )

    proxy: ProxyConfig = Field(default_factory=ProxyConfig)


class OutputConfig(BaseModel):
    """Konfiguration für Ausgabepfade."""

    model_config = {"populate_by_name": True}

    global_root: Optional[Union[str, Path]] = Field(
        None,
        validation_alias=AliasChoices("global", "global_root"),
        description=(
            "Globales Output-Root (bevorzugter Key: output.global; "
            "Legacy-Alias: output.global_root)."
        ),
    )
    topic: Optional[str] = Field(
        None,
        description="Topic/Namespace für reports/history im globalen Output-Layout.",
    )
    path: Union[str, Path] = Field(
        "./output",
        description="Basispfad für Ausgabedateien (deprecated: use root_path + use_channel_subfolder)",
    )
    root_path: Optional[Union[str, Path]] = Field(
        None,
        description="Root-Pfad für Ausgabedateien (verwendet mit use_channel_subfolder)",
    )
    use_channel_subfolder: bool = Field(
        False,
        description="Automatische Erstellung von Unterordnern basierend auf Channel-Handle",
    )
    metadata: bool = Field(
        True, description="Metadaten-Generierung aktivieren/deaktivieren"
    )

    daily_report: bool = Field(
        False,
        description="Wenn true, werden Reports in tagesbasierten Ordnern (YYYY-MM-DD) abgelegt (überschreibend).",
    )
    skip_on_no_new_data: bool = Field(
        False,
        description="Wenn true, wird der Run übersprungen, wenn sich der Input-Fingerprint nicht geändert hat.",
    )
    write_timeout_report: bool = Field(
        False,
        description=(
            "Wenn true, wird ein Timeout-Report unter 3_reports/timeout_budget.md erzeugt."
        ),
    )

    retention_days: Optional[int] = Field(
        30,
        ge=0,
        description=(
            "Retention für Output-Dateien (transcripts/*.{txt,_meta.json}). "
            "Wenn gesetzt, werden Dateien gelöscht, deren mtime älter als N Tage ist. "
            "Setze null, um Cleanup zu deaktivieren."
        ),
    )

    def _resolve_path_value(self, target: Union[str, Path]) -> Path:
        """Löst einen Pfad relativ zu PROJECT_ROOT auf (falls nötig)."""
        from . import PROJECT_ROOT

        path_obj = Path(target) if isinstance(target, str) else target
        if not path_obj.is_absolute():
            return (PROJECT_ROOT / path_obj).resolve()
        return path_obj

    def is_global_layout(self) -> bool:
        """True, wenn das globale Output-Layout (output.global/topic) aktiv ist."""
        return bool(self.global_root or self.topic)

    def _clean_topic(self, topic: str) -> str:
        return topic.strip().replace("/", "_").replace("\\", "_")

    def get_topic(self) -> str:
        if isinstance(self.topic, str) and self.topic.strip():
            return self._clean_topic(self.topic)
        if self.is_global_layout():
            fallback = self.root_path if self.root_path is not None else self.path
            return self._clean_topic(Path(fallback).name)
        return ""

    def get_global_root(self) -> Path:
        """Gibt das globale Output-Root zurück (output.global / output.global_root)."""
        target = self.global_root
        if target is None:
            target = self.root_path if self.root_path is not None else self.path
        return self._resolve_path_value(target)

    def get_data_root(self) -> Path:
        return self.get_global_root() / "data"

    def get_reports_root(self) -> Path:
        topic = self.get_topic()
        if not topic:
            raise ValueError("output.topic is required when using output.global layout")
        return self.get_global_root() / "reports" / topic

    def get_history_root(self) -> Path:
        topic = self.get_topic()
        if not topic:
            raise ValueError("output.topic is required when using output.global layout")
        return self.get_global_root() / "history" / topic

    def get_path(self, channel_handle: Optional[str] = None) -> Path:
        """
        Gibt den Basis-Pfad für das Profil zurück (Legacy-Layout).

        Args:
            channel_handle: Wird im Legacy-Layout auf dieser Ebene ignoriert.

        Returns:
            Absoluter Pfad für die Profil-Ausgabe
        """
        if self.is_global_layout():
            return self.get_global_root()

        # Fallback auf altes Verhalten mit path/root_path
        target_path = self.root_path if self.root_path else self.path
        return self._resolve_path_value(target_path)

    def get_legacy_root(self) -> Path:
        """Gibt den Legacy-Profile-Root zurück (output.root_path / output.path)."""
        if self.root_path is not None:
            return self._resolve_path_value(self.root_path)
        if not self.is_global_layout():
            return self._resolve_path_value(self.path)
        return self.get_global_root() / self.get_topic()

    def _get_clean_handle(self, channel_handle: str) -> str:
        """Normalisiert das Channel-Handle für Ordnernamen."""
        return channel_handle.lstrip("@").replace("/", "_").replace("\\", "_")

    def get_transcripts_path(self, channel_handle: Optional[str] = None) -> Path:
        """Gibt den Pfad für Transkripte zurück (immer kanonisch)."""
        if self.is_global_layout():
            return self.get_data_root() / "transcripts" / "by_video_id"
        
        base = self.get_path() / "1_transcripts"
        if self.use_channel_subfolder and channel_handle:
            return base / self._get_clean_handle(channel_handle)
        return base

    def get_transcript_path(
        self, video_id: str, channel_handle: Optional[str] = None
    ) -> Path:
        """Gibt den Pfad für eine Transkript-Datei zurück (immer kanonisch)."""
        return self.get_transcripts_path(channel_handle) / f"{video_id}.txt"

    def get_transcript_meta_path(
        self, video_id: str, channel_handle: Optional[str] = None
    ) -> Path:
        """Gibt den Pfad für eine Transkript-Metadaten-Datei zurück (immer kanonisch)."""
        return self.get_transcripts_path(channel_handle) / f"{video_id}.meta.json"

    def get_transcripts_skipped_path(self, channel_handle: Optional[str] = None) -> Path:
        """Gibt den Pfad für die Liste übersprungener Videos zurück (immer kanonisch)."""
        if self.is_global_layout():
            return self.get_data_root() / "transcripts" / "skipped.json"
        # In legacy mode, skipped.json is in the 1_transcripts root
        return self.get_path() / "1_transcripts" / "skipped.json"

    def get_summaries_path(self, channel_handle: Optional[str] = None) -> Path:
        """Gibt den Pfad für Summaries zurück (immer kanonisch)."""
        if self.is_global_layout():
            return self.get_data_root() / "summaries" / "by_video_id"
        
        base = self.get_path() / "2_summaries"
        if self.use_channel_subfolder and channel_handle:
            return base / self._get_clean_handle(channel_handle)
        return base

    def get_summary_path(
        self, video_id: str, channel_handle: Optional[str] = None
    ) -> Path:
        """Gibt den Pfad für eine Summary-Datei zurück (immer kanonisch)."""
        if self.is_global_layout():
            return self.get_summaries_path(channel_handle) / f"{video_id}.summary.md"
        return self.get_summaries_path(channel_handle) / f"{video_id}.md"

    def get_reports_path(self, channel_handle: Optional[str] = None) -> Path:
        """Gibt den Pfad für Reports zurück."""
        if self.is_global_layout():
            return self.get_reports_root()
        return self.get_path() / "3_reports"

    def get_timeout_report_path(self) -> Path:
        """Gibt den Pfad für den Timeout-Report zurück."""
        return self.get_reports_path() / "timeout_budget.md"

    def get_error_history_path(self) -> Path:
        """Gibt den Pfad für die Fehler-History zurück."""
        if self.is_global_layout():
            return self.get_data_root() / "diagnostics" / "errors.jsonl"
        return self.get_path() / "diagnostics" / "errors.jsonl"

    def get_run_reports_path(
        self,
        timestamp: str,
        config_hash: Optional[str] = None,
        channel_handle: Optional[str] = None,
        model_slug: Optional[str] = None,
    ) -> Path:
        """
        Gibt den Pfad für einen spezifischen Run zurück.

        Flat-First Policy: Standardmäßig wird der Basis-Pfad (3_reports/) zurückgegeben.
        Die Historie wird bei Bedarf in den Unterordner 'archive/' verschoben.
        """

        if self.is_global_layout():
            date_part = timestamp.split("_")[0] if timestamp else ""
            time_part = timestamp.split("_")[1] if "_" in timestamp else ""
            try:
                date_dir = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
            except Exception:
                date_dir = "unknown-date"
            time_label = time_part[:4] if time_part else "0000"
            model_part = (model_slug or "unknown").replace("/", "_")
            fingerprint = config_hash or "unknown"
            run_dir = f"{date_dir}__{time_label}__{model_part}__{fingerprint}"
            return self.get_history_root() / date_dir / run_dir

        if self.daily_report:
            # Timestamp format expected: YYYYMMDD_HHMMSSZ
            try:
                date_part = timestamp.split("_")[0]
                # Format YYYYMMDD -> YYYY-MM-DD
                formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                return self.get_reports_path() / formatted_date
            except Exception:
                # Fallback if timestamp format is unexpected
                return self.get_reports_path() / f"daily_{timestamp}"

        # Standardmäßig flache Struktur
        return self.get_reports_path()

    def get_archive_run_path(
        self, timestamp: str, config_hash: Optional[str] = None
    ) -> Path:
        """Gibt den Pfad für die Archivierung eines Runs zurück."""
        if self.is_global_layout():
            return self.get_run_reports_path(timestamp, config_hash)
        run_id = f"run_{timestamp}"
        if config_hash:
            run_id = f"{run_id}_{config_hash}"
        return self.get_reports_path() / "archive" / run_id

    def get_index_path(self, channel_handle: Optional[str] = None) -> Path:
        """Gibt den Pfad für den Index zurück."""
        if self.is_global_layout():
            return self.get_data_root() / "indexes" / self.get_topic() / "current"
        return self.get_reports_path() / "index"

    def _get_absolute_root(self) -> Path:
        """Hilfsmethode für den absoluten Root-Pfad."""
        from . import PROJECT_ROOT

        target = self.root_path if self.root_path else self.path
        path_obj = Path(target) if isinstance(target, str) else target
        if not path_obj.is_absolute():
            return (PROJECT_ROOT / path_obj).resolve()
        return path_obj


class LoggingConfig(BaseModel):
    """Logging-Konfiguration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    file: str = "logs/miner.log"
    error_log_file: str = "logs/error.log"
    llm_request_json: bool = Field(
        False,
        description=(
            "Wenn true, werden LLM-Request-Metadaten als JSON nach logs/llm_requests.json geschrieben."
        ),
    )

    # Rotation-Einstellungen direkt eingebettet
    rotation_enabled: bool = False
    rotation_when: str = "D"
    rotation_interval: int = 1
    rotation_backup_count: int = 7

    @field_validator("level")
    @classmethod
    def validate_level(cls, v):
        """Validiert das Logging-Level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"Logging level must be one of {valid_levels}")
        return v

    def get_log_file_path(self) -> str:
        """Konvertiert zu absolutem Pfad für die Log-Datei."""
        from . import PROJECT_ROOT

        path_obj = Path(self.file)
        if not path_obj.is_absolute():
            return str((PROJECT_ROOT / path_obj).resolve())
        return str(path_obj)

    def get_error_log_file_path(self) -> str:
        """Konvertiert zu absolutem Pfad für die Error-Log-Datei."""
        from . import PROJECT_ROOT

        path_obj = Path(self.error_log_file)
        if not path_obj.is_absolute():
            return str((PROJECT_ROOT / path_obj).resolve())
        return str(path_obj)


class ApiConfig(BaseModel):
    """Konfiguration für externe APIs."""

    youtube_api_key: Optional[str] = Field(None, description="YouTube Data API v3 Key")
    youtube_cookies: Optional[str] = Field(
        None,
        description="Pfad zur cookies.txt für YouTube (HINWEIS: Derzeit aufgrund von YouTube-Änderungen oft nicht funktionsfähig)",
    )
    openrouter_api_key: Optional[str] = Field(None, description="OpenRouter API key")
    openrouter_app_title: Optional[str] = Field(
        None,
        description="OpenRouter app title for attribution (X-Title header)",
    )
    openrouter_http_referer: Optional[str] = Field(
        None,
        description="OpenRouter app/site URL for attribution (HTTP-Referer header)",
    )
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")

    @field_validator("youtube_api_key")
    @classmethod
    def resolve_api_key_env_vars(cls, value: Optional[str]) -> Optional[str]:
        """Ersetzt Umgebungsvariablen im API-Key."""
        if not value or not isinstance(value, str):
            return value

        resolved = substitute_env_vars(value)

        # Wenn `${VAR}` nicht aufgelöst werden konnte, behandeln wir den Key als "missing".
        # Rationale: Ein literal `${YOUTUBE_API_KEY}` ist kein gültiger API-Key und soll
        # nicht verhindern, dass wir auf Environment/CLI-Fallbacks zurückfallen.
        if re.search(r"\${[^}]+}", resolved):
            return None

        return resolved

    @field_validator("youtube_cookies")
    @classmethod
    def resolve_cookies_env_vars(cls, value: Optional[str]) -> Optional[str]:
        """Ersetzt Umgebungsvariablen im Cookie-Pfad."""
        if not value or not isinstance(value, str):
            return value
        resolved = substitute_env_vars(value)
        # Wenn `${VAR}` nicht aufgelöst werden konnte, behandeln wir den Pfad als "missing".
        if re.search(r"\${[^}]+}", resolved):
            return None
        return resolved

    @field_validator("openai_api_key")
    @classmethod
    def resolve_openai_key_env_vars(cls, value: Optional[str]) -> Optional[str]:
        """Ersetzt Umgebungsvariablen im OpenAI API-Key."""
        if not value or not isinstance(value, str):
            return value

        resolved = substitute_env_vars(value)

        # Wenn `${VAR}` nicht aufgelöst werden konnte, behandeln wir den Key als "missing".
        if re.search(r"\${[^}]+}", resolved):
            return None

        return resolved

    @field_validator("openrouter_api_key")
    @classmethod
    def resolve_openrouter_key_env_vars(cls, value: Optional[str]) -> Optional[str]:
        """Ersetzt Umgebungsvariablen im OpenRouter API-Key."""
        if not value or not isinstance(value, str):
            return value

        resolved = substitute_env_vars(value)

        # Wenn `${VAR}` nicht aufgelöst werden konnte, behandeln wir den Key als "missing".
        if re.search(r"\${[^}]+}", resolved):
            return None

        return resolved

    @field_validator("openrouter_app_title")
    @classmethod
    def resolve_openrouter_app_title_env_vars(
        cls, value: Optional[str]
    ) -> Optional[str]:
        """Ersetzt Umgebungsvariablen im OpenRouter App-Titel."""
        if not value or not isinstance(value, str):
            return value

        resolved = substitute_env_vars(value).strip()
        if not resolved:
            return None
        if re.search(r"\${[^}]+}", resolved):
            return None

        return resolved

    @field_validator("openrouter_http_referer")
    @classmethod
    def resolve_openrouter_http_referer_env_vars(
        cls, value: Optional[str]
    ) -> Optional[str]:
        """Ersetzt Umgebungsvariablen im OpenRouter HTTP-Referer."""
        if not value or not isinstance(value, str):
            return value

        resolved = substitute_env_vars(value).strip()
        if not resolved:
            return None
        if re.search(r"\${[^}]+}", resolved):
            return None

        return resolved


class LlmAnalysisConfig(BaseModel):
    """Konfiguration für LLM-gestützte Analyse (ein Job pro Run)."""

    enabled: bool = Field(False, description="Wenn true, wird LLM-Analyse ausgeführt")
    mode: Literal["aggregate", "per_video"] = Field(
        "aggregate",
        description=(
            "Ausführungsmodus für LLM-Analyse: aggregate (ein Report über alle Transkripte) "
            "oder per_video (ein Call pro Transcript)."
        ),
    )
    model: Optional[str] = Field(
        None,
        description="Model-Name (z.B. gpt-5.2). Muss gesetzt sein, wenn enabled=true.",
    )
    system_prompt: Optional[str] = Field(
        None,
        description="System-Prompt für das LLM. Muss gesetzt sein, wenn enabled=true.",
    )
    user_prompt_template: Optional[str] = Field(
        None,
        description=(
            "User-Prompt Template. Platzhalter: {transcripts}, {transcript_count}. "
            "Muss gesetzt sein, wenn enabled=true."
        ),
    )

    max_transcripts: int = Field(
        20,
        ge=1,
        description="Max. Anzahl Transkripte, die in den Prompt aufgenommen werden.",
    )
    max_chars_per_transcript: int = Field(
        4000,
        ge=200,
        description="Max. Zeichen pro Transcript (Prefix), um Prompt-Größe zu begrenzen.",
    )
    max_total_chars: int = Field(
        50000,
        ge=1000,
        description="Max. Gesamtzeichen über alle Transkripte im Prompt.",
    )
    max_input_tokens: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "Hartes Token-Limit für System+User Prompt. "
            "None deaktiviert das Token-Limit."
        ),
    )
    max_output_tokens: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "Hartes Token-Limit für LLM-Output. "
            "None deaktiviert das Token-Limit."
        ),
    )
    per_video_concurrency: int = Field(
        1,
        ge=1,
        description="Max. parallele LLM Calls im per_video Modus.",
    )
    per_video_min_delay_s: float = Field(
        0.0,
        ge=0.0,
        description="Globales Mindest-Delay zwischen per_video LLM Calls (Sekunden).",
    )
    per_video_jitter_s: float = Field(
        0.0,
        ge=0.0,
        description="Maximaler Jitter (Sekunden) für per_video Rate-Limit.",
    )
    stream_summaries: bool = Field(
        False,
        description="Wenn true, startet per-video Summaries parallel zum Transcript-Download (Streaming).",
    )
    stream_worker_concurrency: int = Field(
        1,
        ge=1,
        description="Anzahl paralleler Streaming-Worker für per-video Summaries.",
    )
    stream_queue_size: int = Field(
        100,
        ge=1,
        description="Maximale Queue-Größe für Streaming-Summaries (Backpressure).",
    )
    temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Optional: Sampling temperature (Provider-spezifisch).",
    )
    reasoning_effort: Optional[Literal["low", "medium", "high"]] = Field(
        "high",
        description="Optional: Reasoning effort for compatible providers (low|medium|high).",
    )

    @model_validator(mode="after")
    def _validate_required_fields_when_enabled(self) -> "LlmAnalysisConfig":
        if self.enabled:
            missing: list[str] = []
            if not self.model:
                missing.append("analysis.llm.model")
            if not self.system_prompt:
                missing.append("analysis.llm.system_prompt")
            if not self.user_prompt_template:
                missing.append("analysis.llm.user_prompt_template")
            if missing:
                raise ValueError(
                    "Missing required fields when analysis.llm.enabled=true: "
                    + ", ".join(missing)
                )
        return self


class AnalysisConfig(BaseModel):
    """Konfiguration für Analyse-Module (offline + optional LLM)."""

    llm: LlmAnalysisConfig = Field(default_factory=LlmAnalysisConfig)


class Config(BaseModel):
    """Haupt-Konfigurationsmodell."""

    api: ApiConfig = Field(default_factory=ApiConfig)
    youtube: YoutubeConfig = Field(default_factory=YoutubeConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)

    model_config = {"arbitrary_types_allowed": True, "json_encoders": {Path: str}}
