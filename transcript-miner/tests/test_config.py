from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from common.path_utils import _resolve_path, resolve_paths, substitute_env_vars


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


# --- Tests from test_config_validation_errors.py ---


def test_empty_youtube_channels_fails_fast_with_clear_message() -> None:
    # Must fail fast before any network calls when youtube.channels is empty/missing.
    with TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = tmp / "config.yaml"
        _write_yaml(
            cfg_path,
            """\
api:
  youtube_api_key: ${YOUTUBE_API_KEY}

youtube:
  channels: []
  num_videos: 1

output:
  path: ./out
  metadata: true

logging:
  level: INFO
  file: ./logs/test.log
  error_log_file: ./logs/test-error.log
""",
        )

        result = subprocess.run(
            [sys.executable, "-m", "transcript_miner", str(cfg_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0
        combined = (result.stdout + result.stderr).lower()
        assert "youtube.channels" in combined
        assert "at least one" in combined


def test_youtube_channels_whitespace_entry_fails_with_index() -> None:
    with TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = tmp / "config.yaml"
        _write_yaml(
            cfg_path,
            """\
api:
  youtube_api_key: ${YOUTUBE_API_KEY}

youtube:
  channels:
    - "  "
  num_videos: 1

output:
  path: ./out
  metadata: true

logging:
  level: INFO
  file: ./logs/test.log
  error_log_file: ./logs/test-error.log
""",
        )

        result = subprocess.run(
            [sys.executable, "-m", "transcript_miner", str(cfg_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "youtube.channels" in combined
        assert "index 0" in combined


# --- Tests from test_env_substitution.py ---


def test_substitute_env_vars_replaces_known_vars(monkeypatch) -> None:
    monkeypatch.setenv("FOO", "bar")
    assert substitute_env_vars("${FOO}") == "bar"
    assert substitute_env_vars("/tmp/${FOO}/x") == "/tmp/bar/x"


def test_substitute_env_vars_keeps_unknown_vars() -> None:
    # Unknown vars should not crash and should remain unchanged.
    assert substitute_env_vars("${DOES_NOT_EXIST}") == "${DOES_NOT_EXIST}"
    assert substitute_env_vars("/tmp/${DOES_NOT_EXIST}/x") == "/tmp/${DOES_NOT_EXIST}/x"


# --- Tests from test_resolve_paths.py ---


def test__resolve_path_resolves_relative_against_base_path(tmp_path: Path) -> None:
    base_path = tmp_path / "base"
    base_path.mkdir()

    resolved = _resolve_path("foo/bar.txt", base_path)
    assert resolved == (base_path / "foo/bar.txt").resolve()


def test__resolve_path_strips_leading_dot_slash(tmp_path: Path) -> None:
    base_path = tmp_path / "base"
    base_path.mkdir()

    resolved = _resolve_path("./foo", base_path)
    assert resolved == (base_path / "foo").resolve()


def test__resolve_path_applies_env_var_substitution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base_path = tmp_path / "base"
    base_path.mkdir()

    monkeypatch.setenv("MYDIR", "subdir")
    resolved = _resolve_path("${MYDIR}/x.txt", base_path)
    assert resolved == (base_path / "subdir/x.txt").resolve()


def test__resolve_path_does_not_expand_tilde_home(tmp_path: Path) -> None:
    """`_resolve_path()` implementiert kein `~`→Home-Expand, sondern behandelt es als relativen Pfad."""

    base_path = tmp_path / "base"
    base_path.mkdir()

    resolved = _resolve_path("~/.cache/app.log", base_path)
    assert resolved == (base_path / "~/.cache/app.log").resolve()
    assert "~" in resolved.parts


def test_resolve_paths_recurses_dicts_and_lists_and_only_resolves_path_keys(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "base"
    base_path.mkdir()

    config = {
        "output": {
            "root_path": "./out",
            "nested": {
                "data_dir": "data",
                "not_a_path": "keep-relative",
            },
        },
        "other": [
            {"output_dir": "results"},
            "not-touched",
        ],
    }

    resolved = resolve_paths(config, base_path)

    # Rekursion in dicts (und Path-Konvertierung)
    assert resolved["output"]["root_path"] == (base_path / "out").resolve()
    assert resolved["output"]["nested"]["data_dir"] == (base_path / "data").resolve()

    # Nicht in path_keys → unverändert
    assert resolved["output"]["nested"]["not_a_path"] == "keep-relative"

    # Listen werden nur dann traversiert, wenn der Key in `path_keys` ist.
    assert resolved["other"] == config["other"]


def test_resolve_paths_logging_file_fields_are_returned_as_strings(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "base"
    base_path.mkdir()

    config = {
        "logging": {
            "file": "logs/app.log",
            "error_log_file": "./logs/error.log",
        }
    }

    resolved = resolve_paths(config, base_path)

    assert isinstance(resolved["logging"]["file"], str)
    assert resolved["logging"]["file"] == str((base_path / "logs/app.log").resolve())

    assert isinstance(resolved["logging"]["error_log_file"], str)
    assert resolved["logging"]["error_log_file"] == str(
        (base_path / "logs/error.log").resolve()
    )


def test_resolve_paths_youtube_cookies_is_returned_as_string(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "base"
    base_path.mkdir()

    config = {"api": {"youtube_cookies": "./cookies.txt"}}

    resolved = resolve_paths(config, base_path)

    assert isinstance(resolved["api"]["youtube_cookies"], str)
    assert resolved["api"]["youtube_cookies"] == str(
        (base_path / "cookies.txt").resolve()
    )


def test_resolve_paths_additional_files_list_returns_strings_and_preserves_non_strings(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "base"
    base_path.mkdir()

    config = {
        "output": {
            "additional_files": [
                "a.txt",
                "./b.txt",
                {"already": "a-dict"},
            ]
        }
    }

    resolved = resolve_paths(config, base_path)

    additional_files = resolved["output"]["additional_files"]
    assert additional_files[0] == str((base_path / "a.txt").resolve())
    assert additional_files[1] == str((base_path / "b.txt").resolve())
    assert additional_files[2] == {"already": "a-dict"}
