#!/usr/bin/env python3
"""
Move legacy per-profile outputs into the global output layout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from common.config import load_config
from common.output_migration import migrate_legacy_outputs


logger = logging.getLogger(__name__)


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _files_identical(src: Path, dest: Path) -> bool:
    try:
        if src.stat().st_size != dest.stat().st_size:
            return False
    except FileNotFoundError:
        return False
    return _sha256(src) == _sha256(dest)


def _move_file(src: Path, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if _files_identical(src, dest):
            src.unlink(missing_ok=True)
            return "deduped"
        return "conflict"
    shutil.move(str(src), str(dest))
    return "moved"


def _move_tree(src_dir: Path, dest_dir: Path) -> dict[str, int]:
    counts = {"moved": 0, "deduped": 0, "conflict": 0}
    for item in sorted(src_dir.rglob("*")):
        if item.is_dir():
            continue
        rel = item.relative_to(src_dir)
        dest = dest_dir / rel
        result = _move_file(item, dest)
        counts[result] += 1
    # Clean up empty dirs.
    for d in sorted((x for x in src_dir.rglob("*") if x.is_dir()), reverse=True):
        try:
            if any(d.iterdir()):
                continue
            d.rmdir()
        except Exception:
            pass
    return counts


def _model_slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value or "")
    cleaned = cleaned.strip("_")
    return cleaned or "model"


def _bundle_path(
    *, history_root: Path, timestamp_iso: str | None, fingerprint: str, model: str
) -> Path:
    ts = timestamp_iso or ""
    date_str = "unknown-date"
    time_str = "0000"
    if ts:
        try:
            if ts.endswith("Z"):
                ts = ts.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(ts)
            date_str = parsed.strftime("%Y-%m-%d")
            time_str = parsed.strftime("%H%M")
        except Exception:
            pass

    if date_str == "unknown-date":
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M")

    model_slug = _model_slug(model)
    fingerprint_short = (fingerprint or "unknown")[:8]
    run_dir = f"{date_str}__{time_str}__{model_slug}__{fingerprint_short}"
    return history_root / date_str / run_dir


def _extract_run_metadata(run_dir: Path) -> tuple[str | None, str, str]:
    run_manifest = run_dir / "run_manifest.json"
    manifest = run_dir / "manifest.json"
    data = _load_json(run_manifest) if run_manifest.exists() else _load_json(manifest)
    timestamp = data.get("timestamp") if isinstance(data, dict) else None
    fingerprint = ""
    model = ""
    if isinstance(data, dict):
        fingerprint = str(data.get("fingerprint") or data.get("run_fingerprint") or "")
        model = str(data.get("model") or data.get("llm", {}).get("model") or "")
    if not model:
        model = "aggregate"
    return timestamp, fingerprint, model


def _copy_current_reports(*, src_dir: Path, reports_root: Path, timestamp_iso: str | None) -> None:
    reports_root.mkdir(parents=True, exist_ok=True)
    if timestamp_iso:
        try:
            if timestamp_iso.endswith("Z"):
                timestamp_iso = timestamp_iso.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(timestamp_iso)
            date_str = parsed.strftime("%Y-%m-%d")
        except Exception:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    mapping = {
        "report_de.md": f"report_de_{date_str}.md",
        "report_en.md": f"report_en_{date_str}.md",
        "report.md": f"report_de_{date_str}.md",
    }
    for src_name, dest_name in mapping.items():
        src = src_dir / src_name
        dest = reports_root / dest_name
        if not src.exists() or dest.exists():
            continue
        shutil.copy2(src, dest)

    for aux_name in ("run_manifest.json", "run_summary.md", "timeout_budget.md"):
        src = src_dir / aux_name
        dest = reports_root / aux_name
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)


def migrate_outputs(config_path: Path) -> int:
    cfg = load_config(config_path)
    output = cfg.output

    if not output.is_global_layout():
        logger.error("Config must set output.global and output.topic for migration.")
        return 1

    legacy_root = output.get_legacy_root()
    reports_root = output.get_reports_root()
    history_root = output.get_history_root()
    index_target = output.get_index_path()

    logger.info("Migrating transcripts/summaries/skipped from %s", legacy_root)
    migrate_legacy_outputs(output)

    legacy_reports = legacy_root / "3_reports"
    legacy_index = legacy_reports / "index"
    if legacy_index.exists():
        if index_target.exists():
            logger.warning("Index target exists; skipping move: %s", index_target)
        else:
            index_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy_index), str(index_target))

    if legacy_reports.exists():
        # Migrate current run (everything except index/archive).
        timestamp_iso, fingerprint, model = _extract_run_metadata(legacy_reports)
        run_dir = _bundle_path(
            history_root=history_root,
            timestamp_iso=timestamp_iso,
            fingerprint=fingerprint,
            model=model,
        )
        run_dir.mkdir(parents=True, exist_ok=True)

        for item in sorted(legacy_reports.iterdir()):
            if item.name in {"index", "archive"}:
                continue
            dest = run_dir / item.name
            if item.is_dir():
                _move_tree(item, dest)
            else:
                _move_file(item, dest)

        _copy_current_reports(
            src_dir=run_dir, reports_root=reports_root, timestamp_iso=timestamp_iso
        )

        # Migrate archived runs.
        archive_root = legacy_reports / "archive"
        if archive_root.exists():
            for legacy_run in sorted(x for x in archive_root.iterdir() if x.is_dir()):
                ts_iso, fp, model_name = _extract_run_metadata(legacy_run)
                bundle_dir = _bundle_path(
                    history_root=history_root,
                    timestamp_iso=ts_iso,
                    fingerprint=fp,
                    model=model_name,
                )
                bundle_dir.mkdir(parents=True, exist_ok=True)
                _move_tree(legacy_run, bundle_dir)

            # Cleanup empty archive root.
            for d in sorted(
                (x for x in archive_root.rglob("*") if x.is_dir()), reverse=True
            ):
                try:
                    if any(d.iterdir()):
                        continue
                    d.rmdir()
                except Exception:
                    pass

    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Move legacy output/<topic> layout into global output layout."
    )
    p.add_argument("--config", required=True, help="Path to YAML config file.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    return migrate_outputs(Path(args.config))


if __name__ == "__main__":
    raise SystemExit(main())
