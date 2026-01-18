from __future__ import annotations

import argparse
import json
from pathlib import Path


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + len("\n---\n") :]
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if k:
            meta[k] = v
    return meta, body


def _render_md(*, video_id: str, payload: dict) -> str:
    task = str(payload.get("task") or "unknown").strip() or "unknown"
    title = str(payload.get("title") or payload.get("video_title") or "unknown").strip() or "unknown"
    published_at = str(payload.get("published_at") or "unknown").strip() or "unknown"
    channel_id = str(payload.get("channel_id") or "unknown").strip() or "unknown"

    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    channel_namespace = str(source.get("channel_namespace") or "unknown").strip() or "unknown"
    transcript_path = str(source.get("transcript_path") or "").strip()
    raw_hash = str(payload.get("raw_hash") or "").strip()

    lines: list[str] = []
    lines.append("---")
    schema_version = payload.get("schema_version")
    lines.append(f"schema_version: {schema_version}" if isinstance(schema_version, int) else "schema_version: 1")
    lines.append(f"task: {task}")
    lines.append(f"video_id: {video_id}")
    lines.append(f"title: {title}")
    lines.append(f"channel_namespace: {channel_namespace}")
    lines.append(f"channel_id: {channel_id}")
    lines.append(f"published_at: {published_at}")
    lines.append(f"transcript_path: {transcript_path}")
    lines.append(f"raw_hash: {raw_hash}")
    lines.append("---")
    lines.append("")

    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Source")
    lines.append(f"- video_id: `{video_id}`")
    lines.append(f"- channel_namespace: `{channel_namespace}`")
    lines.append(f"- published_at: `{published_at}`")
    lines.append("")

    macro = payload.get("macro_insights")
    if isinstance(macro, list):
        items = [x for x in macro if isinstance(x, dict)]
        if items:
            lines.append("## Macro Insights")
            for item in items:
                claim = str(item.get("claim") or "").strip()
                if not claim:
                    continue
                tags = item.get("tags")
                if isinstance(tags, list):
                    cleaned = [str(t).strip() for t in tags if str(t).strip()]
                else:
                    cleaned = []
                if cleaned:
                    lines.append(f"- {claim} (tags: {', '.join(cleaned)})")
                else:
                    lines.append(f"- {claim}")
            lines.append("")

    stocks = payload.get("stocks_covered")
    if isinstance(stocks, list):
        items = [x for x in stocks if isinstance(x, dict)]
        if items:
            lines.append("## Stocks Covered")
            for item in items:
                canonical = str(item.get("canonical") or "").strip()
                why = str(item.get("why_covered") or "").strip()
                if not canonical:
                    continue
                lines.append(f"- {canonical}: {why}" if why else f"- {canonical}")
            lines.append("")

    knowledge = payload.get("knowledge_items")
    if isinstance(knowledge, list):
        items = [x for x in knowledge if isinstance(x, dict)]
        if items:
            lines.append("## Knowledge Items")
            for item in items:
                text_value = str(item.get("text") or "").strip()
                if not text_value:
                    continue
                entities = item.get("entities")
                if isinstance(entities, list):
                    cleaned = [str(e).strip() for e in entities if str(e).strip()]
                else:
                    cleaned = []
                if cleaned:
                    lines.append(f"- {text_value} (entities: {', '.join(cleaned)})")
                else:
                    lines.append(f"- {text_value}")
            lines.append("")

    errors = payload.get("errors")
    if isinstance(errors, list):
        cleaned = [str(e).strip() for e in errors if str(e).strip()]
        if cleaned:
            lines.append("## Errors")
            for e in cleaned:
                lines.append(f"- {e}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="One-shot migration: per-video .summary.json -> .summary.md (global layout).")
    p.add_argument("--output-root", required=True, help="Path to the TranscriptMiner global output root (the folder that contains data/).")
    p.add_argument("--delete-json", action="store_true", help="Delete the original .summary.json after successful conversion.")
    args = p.parse_args()

    output_root = Path(args.output_root).expanduser().resolve()
    summaries_dir = output_root / "data" / "summaries" / "by_video_id"
    if not summaries_dir.exists():
        raise SystemExit(f"missing summaries dir: {summaries_dir}")

    converted = 0
    skipped = 0
    for json_path in sorted(summaries_dir.glob("*.summary.json")):
        video_id = json_path.name[: -len(".summary.json")]
        md_path = summaries_dir / f"{video_id}.summary.md"

        if md_path.exists():
            skipped += 1
            if args.delete_json:
                json_path.unlink(missing_ok=True)
            continue

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            print(f"skip (not a json object): {json_path}")
            continue

        md = _render_md(video_id=video_id, payload=payload)
        md_path.write_text(md, encoding="utf-8")
        converted += 1
        if args.delete_json:
            json_path.unlink(missing_ok=True)

    print(f"converted={converted} skipped_existing_md={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

