import subprocess
import sys


def test_import_transcript_miner() -> None:
    # Offline smoke-check: Import must not require network or API keys.
    import transcript_miner  # noqa: F401


def test_cli_help_does_not_crash() -> None:
    # Offline smoke-check: `--help` must succeed without requiring environment variables.
    result = subprocess.run(
        [sys.executable, "-m", "transcript_miner", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "YouTube Transcript Miner" in (result.stdout + result.stderr)


def test_cli_help_with_positional_config_does_not_crash() -> None:
    # Regression: `--help` must also work when a positional config path is provided.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "transcript_miner",
            "config/config_ai_knowledge.yaml",
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "YouTube Transcript Miner" in (result.stdout + result.stderr)

