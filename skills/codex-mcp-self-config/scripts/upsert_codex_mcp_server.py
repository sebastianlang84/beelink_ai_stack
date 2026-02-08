#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning, message=r"Possible nested set.*")


def _slugify(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "custom-server"


def _toml_quote(s: str) -> str:
    # Minimal TOML string escaping for our config values.
    return '"' + (s or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


# Match TOML table headers like:
#   [mcp_servers.context7]
#   [projects."/home/user/repo"]  # optional comment
_SECTION_HEADER_RE = re.compile(r"(?m)^[[]([^]]+)[]]\s*(?:#.*)?$")


def _upsert_section(*, text: str, header: str, body_lines: list[str]) -> str:
    """
    Upsert a TOML table section by raw text manipulation.
    - header: without brackets, e.g. 'mcp_servers.context7'
    - body_lines: lines after the header, no trailing newline
    """
    hdr_line = f"[{header}]"
    section_text = hdr_line + "\n" + "\n".join(body_lines).rstrip() + "\n"

    # Index all section headers so we can remove duplicates safely.
    matches = list(_SECTION_HEADER_RE.finditer(text))
    sections: list[tuple[str, int, int]] = []
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.start()
        end = matches[i + 1].start() if (i + 1) < len(matches) else len(text)
        sections.append((name, start, end))

    target_name = header.strip()
    target_sections = [(s, e) for (n, s, e) in sections if n == target_name]

    if not target_sections:
        out = text
        if out and not out.endswith("\n"):
            out += "\n"
        if out and not out.endswith("\n\n"):
            out += "\n"
        return out + section_text

    # Remove all existing occurrences of the target section and insert a single one at the first position.
    first_start = min(s for (s, _) in target_sections)
    cut_ranges = sorted(target_sections, key=lambda t: t[0])
    rebuilt_parts: list[str] = []
    cursor = 0
    for s, e in cut_ranges:
        rebuilt_parts.append(text[cursor:s])
        cursor = e
    rebuilt_parts.append(text[cursor:])
    without = "".join(rebuilt_parts)

    before = without[:first_start].rstrip("\n")
    after = without[first_start:].lstrip("\n")
    out = before + "\n\n" + section_text
    if after:
        out += "\n" + after
    if not out.endswith("\n"):
        out += "\n"
    return out


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write_text(path: Path, text: str) -> None:
    _ensure_parent_dir(path)
    path.write_text(text, encoding="utf-8")


def _parse_bool(raw: str) -> bool:
    v = (raw or "").strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean: {raw!r}")


def _ensure_project_trusted(*, project_dir: Path) -> None:
    global_cfg = Path.home() / ".codex" / "config.toml"
    key = str(project_dir)
    header = f'projects.{_toml_quote(key)}'
    body = ['trust_level = "trusted"']
    text = _read_text(global_cfg)
    text2 = _upsert_section(text=text, header=header, body_lines=body)
    if text2 != text:
        _write_text(global_cfg, text2)
    # Validate that we did not create a broken global config (duplicate tables, etc).
    import tomllib  # noqa: PLC0415

    tomllib.loads(_read_text(global_cfg) or "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Upsert a Codex MCP server into .codex/config.toml (streamable-http).")
    ap.add_argument("--project-dir", default=os.getcwd(), help="Project root that contains .codex/config.toml")
    ap.add_argument("--name", required=True, help="Server name (e.g. owui-connector)")
    ap.add_argument("--url", required=True, help="Streamable HTTP MCP endpoint URL (e.g. http://127.0.0.1:8877/mcp)")
    ap.add_argument("--enabled", default="true", help="true|false (default: true)")
    ap.add_argument("--ensure-trusted", action="store_true", help="Ensure ~/.codex/config.toml trusts this project")
    args = ap.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    server_key = _slugify(args.name)
    enabled = _parse_bool(args.enabled)

    if args.ensure_trusted:
        _ensure_project_trusted(project_dir=project_dir)

    cfg_path = project_dir / ".codex" / "config.toml"
    text = _read_text(cfg_path)
    body = [
        f'enabled = {"true" if enabled else "false"}',
        'type = "streamable-http"',
        f"url = {_toml_quote(args.url)}",
    ]
    text2 = _upsert_section(text=text, header=f"mcp_servers.{server_key}", body_lines=body)
    if text2 != text:
        _write_text(cfg_path, text2)

    # Validate TOML parse (python 3.11+).
    import tomllib  # noqa: PLC0415

    obj = tomllib.loads(_read_text(cfg_path))
    keys = sorted((obj.get("mcp_servers") or {}).keys())
    if server_key not in keys:
        raise RuntimeError(f"expected server key not found after write: {server_key!r} (have: {keys})")
    print(f"OK: wrote {cfg_path}")
    print(f"mcp_servers: {keys}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
