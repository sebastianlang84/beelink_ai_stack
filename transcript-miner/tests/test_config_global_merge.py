from __future__ import annotations

from pathlib import Path

from common.config import load_config


def test_load_config_applies_global_defaults(tmp_path: Path) -> None:
    global_cfg = tmp_path / "config_global.yaml"
    topic_cfg = tmp_path / "topic.yaml"

    global_cfg.write_text(
        """
output:
  global: ../output
youtube:
  min_delay_s: 9.0
  jitter_s: 3.0
api:
  openrouter_app_title: TranscriptMiner
""".lstrip(),
        encoding="utf-8",
    )

    topic_cfg.write_text(
        """
output:
  topic: investing
youtube:
  channels: ["@CouchInvestor"]
""".lstrip(),
        encoding="utf-8",
    )

    cfg = load_config(topic_cfg, global_config_path=global_cfg)

    assert cfg.output.get_topic() == "investing"
    assert str(cfg.output.get_global_root()).endswith("/output")
    assert cfg.youtube.min_delay_s == 9.0
    assert cfg.youtube.jitter_s == 3.0
    assert cfg.api.openrouter_app_title == "TranscriptMiner"


def test_topic_overrides_global_on_conflict(tmp_path: Path) -> None:
    global_cfg = tmp_path / "config_global.yaml"
    topic_cfg = tmp_path / "topic.yaml"

    global_cfg.write_text(
        """
youtube:
  min_delay_s: 9.0
  channels: ["@GLOBAL"]
""".lstrip(),
        encoding="utf-8",
    )

    topic_cfg.write_text(
        """
youtube:
  min_delay_s: 2.0
  channels: ["@TOPIC"]
""".lstrip(),
        encoding="utf-8",
    )

    cfg = load_config(topic_cfg, global_config_path=global_cfg)

    # scalar override
    assert cfg.youtube.min_delay_s == 2.0
    # list override (topic wins; no union)
    assert cfg.youtube.channels == ["@TOPIC"]

