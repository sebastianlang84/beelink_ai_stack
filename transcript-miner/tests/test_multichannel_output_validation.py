import subprocess
import sys
from pathlib import Path


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_multi_channel_requires_root_path_and_channel_subfolder() -> None:
    # The miner must fail fast for multi-channel configs unless:
    # - output.root_path is set AND
    # - output.use_channel_subfolder is true
    # Otherwise channels would share the same output dir (progress.json/transcripts collision).
    from tempfile import TemporaryDirectory

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
    - "@A"
    - "@B"
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
        assert "multi-channel" in combined.lower()
        assert "output.global" in combined or "output.root_path" in combined
        assert "output.topic" in combined or "use_channel_subfolder" in combined
