from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")


def _pct(values: list[float], p: int) -> float | None:
    if not values:
        return None
    values = sorted(values)
    idx = int(round((p / 100.0) * (len(values) - 1)))
    return values[idx]


def _fmt(val: float | None) -> str:
    if val is None:
        return "unknown"
    return f"{val:.2f}"


def parse_log(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    starts: list[datetime] = []
    ends: list[datetime] = []
    rate_waits: list[float] = []
    report_durations_ms: list[float] = []
    per_video_durations_ms: list[float] = []
    aggregate_durations_ms: list[float] = []
    llm_prepare: dict[str, int] | None = None
    channels_count_log: int | None = None

    for line in lines:
        m = _TS_RE.match(line)
        if not m:
            continue
        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")

        if "Starting mining..." in line:
            starts.append(ts)
        if "Aggregation completed." in line:
            ends.append(ts)

        m_wait = re.search(r"Rate limiting: waiting ([0-9.]+)s", line)
        if m_wait:
            try:
                rate_waits.append(float(m_wait.group(1)))
            except ValueError:
                pass

        m_report = re.search(
            r"LLM report call completed: .* duration_ms=([0-9.]+)", line
        )
        if m_report:
            try:
                report_durations_ms.append(float(m_report.group(1)))
            except ValueError:
                pass

        m_per_video = re.search(
            r"LLM per-video call completed: .* duration_ms=([0-9.]+)", line
        )
        if m_per_video:
            try:
                per_video_durations_ms.append(float(m_per_video.group(1)))
            except ValueError:
                pass

        m_agg = re.search(
            r"LLM aggregate call completed: .* duration_ms=([0-9.]+)", line
        )
        if m_agg:
            try:
                aggregate_durations_ms.append(float(m_agg.group(1)))
            except ValueError:
                pass

        m_channels = re.search(r"Starting to process (\d+) channels", line)
        if m_channels:
            channels_count_log = int(m_channels.group(1))

        m_prepare = re.search(
            r"Preparing LLM request: (\d+) transcripts, (\d+) chars, ~([0-9]+) tokens",
            line,
        )
        if m_prepare:
            llm_prepare = {
                "transcripts": int(m_prepare.group(1)),
                "chars": int(m_prepare.group(2)),
                "tokens_est": int(m_prepare.group(3)),
            }

    # Pair each start with the next end after it.
    pairs: list[float] = []
    end_idx = 0
    for s in starts:
        while end_idx < len(ends) and ends[end_idx] < s:
            end_idx += 1
        if end_idx < len(ends):
            e = ends[end_idx]
            pairs.append((e - s).total_seconds())
            end_idx += 1

    return {
        "starts": starts,
        "ends": ends,
        "run_durations_s": pairs,
        "rate_waits_s": rate_waits,
        "report_durations_ms": report_durations_ms,
        "per_video_durations_ms": per_video_durations_ms,
        "aggregate_durations_ms": aggregate_durations_ms,
        "llm_prepare": llm_prepare,
        "channels_count_log": channels_count_log,
    }


def generate_timeout_report(
    *,
    config_dict: dict[str, Any],
    log_path: Path,
    config_path: Path | None = None,
    now_utc: str | None = None,
) -> str:
    log = parse_log(log_path)

    youtube = config_dict.get("youtube", {}) or {}
    analysis = (config_dict.get("analysis", {}) or {}).get("llm", {}) or {}
    report = (config_dict.get("report", {}) or {}).get("llm", {}) or {}

    channels = youtube.get("channels", []) or []
    channels_count = len(channels) if isinstance(channels, list) else None
    num_videos = youtube.get("num_videos")
    min_delay_s = youtube.get("min_delay_s")
    jitter_s = youtube.get("jitter_s")

    per_video_concurrency = analysis.get("per_video_concurrency")
    per_video_min_delay_s = analysis.get("per_video_min_delay_s")
    per_video_jitter_s = analysis.get("per_video_jitter_s")
    analysis_timeout_s = analysis.get("timeout_s")
    max_transcripts = analysis.get("max_transcripts")

    report_timeout_s = report.get("timeout_s")

    rate_waits = log.get("rate_waits_s", [])
    report_durations_ms = log.get("report_durations_ms", [])
    per_video_durations_ms = log.get("per_video_durations_ms", [])
    aggregate_durations_ms = log.get("aggregate_durations_ms", [])
    run_durations_s = log.get("run_durations_s", [])
    llm_prepare = log.get("llm_prepare")

    rate_wait_sum = sum(rate_waits) if rate_waits else None
    rate_wait_max = max(rate_waits) if rate_waits else None
    rate_wait_avg = (rate_wait_sum / len(rate_waits)) if rate_waits else None

    report_ms_last = report_durations_ms[-1] if report_durations_ms else None
    per_video_ms_p90 = _pct(per_video_durations_ms, 90)
    aggregate_ms_p90 = _pct(aggregate_durations_ms, 90)

    run_p90 = _pct(run_durations_s, 90)
    run_median = _pct(run_durations_s, 50)

    wait_min = None
    wait_exp = None
    wait_max = None
    if channels_count and num_videos and min_delay_s is not None and jitter_s is not None:
        wait_min = channels_count * num_videos * min_delay_s
        wait_exp = channels_count * num_videos * (min_delay_s + (jitter_s / 2.0))
        wait_max = channels_count * num_videos * (min_delay_s + jitter_s)

    empirical_budget_s = None
    if rate_wait_sum is not None:
        report_s = (report_ms_last / 1000.0) if report_ms_last is not None else 0.0
        base = rate_wait_sum + report_s
        empirical_budget_s = base * 1.2 + 60.0

    config_budget_s = None
    if wait_max is not None and report_timeout_s is not None:
        config_budget_s = wait_max + report_timeout_s

    candidates = [v for v in [run_p90, empirical_budget_s, config_budget_s] if v]
    recommended_s = max(candidates) if candidates else None

    if now_utc is None:
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    lines = []
    lines.append("# Timeout Budget Report: stocks_crypto")
    lines.append("")
    lines.append(f"Generated (UTC): {now_utc}")
    lines.append("")
    lines.append("## Inputs")
    lines.append(f"- Config: {config_path if config_path else 'unknown'}")
    lines.append(f"- Log: {log_path}")
    lines.append("")
    lines.append("## Config Snapshot")
    lines.append(f"- channels_count: {channels_count}")
    lines.append(f"- num_videos: {num_videos}")
    lines.append(f"- min_delay_s: {min_delay_s}")
    lines.append(f"- jitter_s: {jitter_s}")
    lines.append(f"- per_video_concurrency: {per_video_concurrency}")
    lines.append(f"- per_video_min_delay_s: {per_video_min_delay_s}")
    lines.append(f"- per_video_jitter_s: {per_video_jitter_s}")
    lines.append(f"- analysis_llm.timeout_s: {analysis_timeout_s}")
    lines.append(f"- analysis_llm.max_transcripts: {max_transcripts}")
    lines.append(f"- report_llm.timeout_s: {report_timeout_s}")
    lines.append("")
    if llm_prepare:
        lines.append("## LLM Input Snapshot")
        lines.append(f"- transcripts: {llm_prepare.get('transcripts')}")
        lines.append(f"- chars: {llm_prepare.get('chars')}")
        lines.append(f"- tokens_est: {llm_prepare.get('tokens_est')}")
        lines.append("")
    lines.append("## Log Observations")
    lines.append(f"- runs_detected: {len(run_durations_s)}")
    lines.append(f"- run_duration_median_s: {_fmt(run_median)}")
    lines.append(f"- run_duration_p90_s: {_fmt(run_p90)}")
    lines.append(
        f"- run_duration_max_s: {_fmt(max(run_durations_s) if run_durations_s else None)}"
    )
    lines.append("")
    lines.append("### Rate Limiting Waits")
    lines.append(f"- count: {len(rate_waits)}")
    lines.append(f"- sum_s: {_fmt(rate_wait_sum)}")
    lines.append(f"- avg_s: {_fmt(rate_wait_avg)}")
    lines.append(f"- max_s: {_fmt(rate_wait_max)}")
    lines.append("")
    lines.append("### LLM Report Calls")
    lines.append(f"- count: {len(report_durations_ms)}")
    lines.append(f"- last_duration_ms: {_fmt(report_ms_last)}")
    lines.append("")
    lines.append("### LLM Per-Video Calls (if instrumented)")
    lines.append(f"- count: {len(per_video_durations_ms)}")
    lines.append(f"- p90_duration_ms: {_fmt(per_video_ms_p90)}")
    lines.append("")
    lines.append("### LLM Aggregate Calls (if instrumented)")
    lines.append(f"- count: {len(aggregate_durations_ms)}")
    lines.append(f"- p90_duration_ms: {_fmt(aggregate_ms_p90)}")
    lines.append("")
    lines.append("## Deterministic Wait Bounds (config-based)")
    lines.append(f"- wait_min_s = channels*num_videos*min_delay_s = {_fmt(wait_min)}")
    lines.append(
        f"- wait_expected_s = channels*num_videos*(min_delay_s + jitter_s/2) = {_fmt(wait_exp)}"
    )
    lines.append(
        f"- wait_max_s = channels*num_videos*(min_delay_s + jitter_s) = {_fmt(wait_max)}"
    )
    lines.append("")
    lines.append("## Empirical Budget (log-based)")
    lines.append(
        f"- empirical_budget_s = (rate_wait_sum + report_duration_s) * 1.2 + 60 = {_fmt(empirical_budget_s)}"
    )
    lines.append("")
    lines.append("## Recommended Wrapper Timeout")
    lines.append("- recommendation_s = max(run_p90, empirical_budget_s, wait_max + report_timeout_s)")
    lines.append(f"- recommendation_s = {_fmt(recommended_s)}")
    lines.append("")
    lines.append("## Notes")
    lines.append("- If per-video or aggregate call durations are missing, run a new full pipeline after instrumentation changes.")
    lines.append("- The default 10s shell timeout is insufficient when min_delay_s exceeds 10s.")
    lines.append("")

    return "\n".join(lines)


def write_timeout_report(
    *,
    config_dict: dict[str, Any],
    log_path: Path,
    out_path: Path,
    config_path: Path | None = None,
) -> Path:
    report = generate_timeout_report(
        config_dict=config_dict, log_path=log_path, config_path=config_path
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    return out_path
