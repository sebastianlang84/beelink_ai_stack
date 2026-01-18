"""Markdown link audit (md -> md) for repository hygiene.

This script exists to prevent "doc drift" where tracked documentation links to
files that only exist locally/untracked (or are missing).

Behavior:
- Scans only tracked Markdown files (via `git ls-files '*.md'`).
- Extracts Markdown links `[text](target)`.
- Considers only targets that look like local `.md` paths (ignores URLs/anchors).
- Reports two classes:
  1) MISSING: target file does not exist on disk.
  2) UNTRACKED: target exists on disk but is not tracked by git.

Exit codes:
- 0 if no MISSING targets found.
- 1 if any MISSING targets found.

UNTRACKED targets are reported as warnings (to keep the script safe to run on
worktrees with local, uncommitted docs).
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _sh(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=ROOT, text=True)


def _git_ls_files(pattern: str) -> set[str]:
    out = _sh(["git", "ls-files", pattern])
    return {line.strip() for line in out.splitlines() if line.strip()}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _strip_anchor_and_line(target: str) -> str:
    t = target.strip().strip("<>").strip()
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        t = t[1:-1]
    # ignore URLs (http:, https:, mailto:, etc.)
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", t):
        return ""
    if t.startswith("#"):
        return ""
    # drop anchor
    t = t.split("#", 1)[0]
    # drop VSCode-style :<line>
    t = re.sub(r":\d+$", "", t)
    return t.strip()


def _resolve_rel(src_md: Path, target: str) -> Path | None:
    if not target:
        return None
    try:
        abs_path = (src_md.parent / target).resolve()
    except Exception:
        return None
    try:
        rel = abs_path.relative_to(ROOT)
    except Exception:
        return None
    return rel


@dataclass(frozen=True)
class Finding:
    src: str
    tgt: str
    kind: str  # MISSING | UNTRACKED


def main() -> int:
    tracked_md = _git_ls_files("*.md")
    tracked_paths = {str((ROOT / p).resolve()): p for p in tracked_md}
    tracked_md_abs = set(tracked_paths.keys())

    findings: list[Finding] = []

    for rel_src in sorted(tracked_md):
        src_path = (ROOT / rel_src).resolve()
        if not src_path.exists():
            continue
        text = _read_text(src_path)
        for raw in MD_LINK_RE.findall(text):
            t = _strip_anchor_and_line(raw)
            if not t.lower().endswith(".md"):
                continue
            rel_tgt = _resolve_rel(src_path, t)
            if rel_tgt is None:
                continue
            tgt_abs = str((ROOT / rel_tgt).resolve())
            tgt_rel = str(rel_tgt)
            if not (ROOT / rel_tgt).exists():
                findings.append(Finding(rel_src, tgt_rel, "MISSING"))
            elif tgt_abs not in tracked_md_abs:
                findings.append(Finding(rel_src, tgt_rel, "UNTRACKED"))

    missing = [f for f in findings if f.kind == "MISSING"]
    untracked = [f for f in findings if f.kind == "UNTRACKED"]

    if missing:
        print("MISSING md-link targets (tracked docs -> missing file):")
        for f in missing:
            print(f"- {f.src} -> {f.tgt}")
        print()

    if untracked:
        print("UNTRACKED md-link targets (tracked docs -> file exists but not in git):")
        for f in untracked:
            print(f"- {f.src} -> {f.tgt}")
        print()
        print("Note: UNTRACKED is a warning. Either `git add` the target or update the link.")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

