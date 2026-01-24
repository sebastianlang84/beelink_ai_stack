#!/usr/bin/env python3
"""
Probe YouTube transcript fetch settings to reduce blocking.

Runs a small matrix over min_delay/jitter/retries and records results to JSONL.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from common.config import load_config
from transcript_miner.transcript_downloader import download_transcript_result
from transcript_miner.transcript_models import TranscriptDownloadResult


@dataclass(frozen=True)
class Scenario:
    min_delay_s: float
    jitter_s: float
    max_retries: int
    backoff_base_s: float
    backoff_cap_s: float


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_list(value: str, cast):
    return [cast(item.strip()) for item in value.split(",") if item.strip()]


def iter_video_ids(args: argparse.Namespace) -> list[str]:
    ids: list[str] = []
    if args.videos:
        ids.extend(parse_list(args.videos, str))
    if args.videos_file:
        path = Path(args.videos_file)
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            ids.append(line)
    deduped: list[str] = []
    seen = set()
    for vid in ids:
        if vid not in seen:
            deduped.append(vid)
            seen.add(vid)
    return deduped


def build_scenarios(args: argparse.Namespace, cfg) -> list[Scenario]:
    min_delays = parse_list(args.min_delay_s, float) if args.min_delay_s else None
    jitters = parse_list(args.jitter_s, float) if args.jitter_s else None
    max_retries = parse_list(args.max_retries, int) if args.max_retries else None
    backoff_base = parse_list(args.backoff_base_s, float) if args.backoff_base_s else None
    backoff_cap = parse_list(args.backoff_cap_s, float) if args.backoff_cap_s else None

    if min_delays is None:
        min_delays = [float(cfg.youtube.min_delay_s)]
    if jitters is None:
        jitters = [float(cfg.youtube.jitter_s)]
    if max_retries is None:
        max_retries = [int(cfg.youtube.max_retries)]
    if backoff_base is None:
        backoff_base = [float(cfg.youtube.backoff_base_s)]
    if backoff_cap is None:
        backoff_cap = [float(cfg.youtube.backoff_cap_s)]

    scenarios: list[Scenario] = []
    for values in itertools.product(min_delays, jitters, max_retries, backoff_base, backoff_cap):
        scenarios.append(Scenario(*values))
    return scenarios


def write_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")


def result_to_record(
    result: TranscriptDownloadResult,
    *,
    scenario: Scenario,
    video_id: str,
    duration_s: float,
) -> dict:
    return {
        "ts": now_iso(),
        "video_id": video_id,
        "scenario": asdict(scenario),
        "duration_s": round(duration_s, 3),
        "status": result.status.value,
        "reason": result.reason,
        "error_type": result.error_type,
        "error_message": (result.error_message or "")[:300],
    }


def summarize(records: Iterable[dict]) -> dict:
    summary: dict[str, int] = {}
    for rec in records:
        key = rec.get("status") or "unknown"
        summary[key] = summary.get(key, 0) + 1
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        required=True,
        help="Path to topic config (e.g. transcript-miner/config/config_stocks_crypto.yaml)",
    )
    parser.add_argument("--videos", help="Comma-separated video IDs.")
    parser.add_argument("--videos-file", help="File with one video ID per line.")
    parser.add_argument("--languages", help="Comma-separated preferred languages.")
    parser.add_argument("--cookie-file", help="Override cookie file path (optional).")
    parser.add_argument("--min-delay-s", help="Comma-separated min_delay_s values.")
    parser.add_argument("--jitter-s", help="Comma-separated jitter_s values.")
    parser.add_argument("--max-retries", help="Comma-separated max_retries values.")
    parser.add_argument("--backoff-base-s", help="Comma-separated backoff_base_s values.")
    parser.add_argument("--backoff-cap-s", help="Comma-separated backoff_cap_s values.")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat each video N times.")
    parser.add_argument(
        "--sleep-between-s",
        type=float,
        default=0.0,
        help="Sleep between video requests (seconds).",
    )
    parser.add_argument(
        "--out",
        help="JSONL output path (default: ./output/diagnostics/youtube_block_probe_<ts>.jsonl)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    video_ids = iter_video_ids(args)
    if not video_ids:
        raise SystemExit("No video IDs provided. Use --videos or --videos-file.")

    scenarios = build_scenarios(args, cfg)
    languages = (
        parse_list(args.languages, str) if args.languages else None
    )
    cookie_file = args.cookie_file or cfg.api.youtube_cookies

    out_path = (
        Path(args.out)
        if args.out
        else Path("output")
        / "diagnostics"
        / f"youtube_block_probe_{int(time.time())}.jsonl"
    )

    all_records: list[dict] = []
    for scenario in scenarios:
        for _ in range(max(args.repeat, 1)):
            for video_id in video_ids:
                start = time.time()
                result = download_transcript_result(
                    video_id=video_id,
                    preferred_languages=languages,
                    cookie_file=cookie_file,
                    proxy_settings=cfg.youtube.proxy,
                    min_delay=scenario.min_delay_s,
                    jitter=scenario.jitter_s,
                    max_retries=scenario.max_retries,
                    backoff_base=scenario.backoff_base_s,
                    backoff_cap=scenario.backoff_cap_s,
                )
                duration_s = time.time() - start
                record = result_to_record(
                    result,
                    scenario=scenario,
                    video_id=video_id,
                    duration_s=duration_s,
                )
                write_jsonl(out_path, record)
                all_records.append(record)
                if args.sleep_between_s > 0:
                    time.sleep(args.sleep_between_s)

    summary = summarize(all_records)
    print(f"output: {out_path}")
    print(f"videos: {len(video_ids)} scenarios: {len(scenarios)} repeat: {args.repeat}")
    print(f"summary: {json.dumps(summary, ensure_ascii=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
