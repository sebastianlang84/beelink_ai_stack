from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    heading_path: str
    text: str
    char_len: int


_re_heading = re.compile(r"^(#{1,6})\s+(.*)$")


def _approx_tokens(text: str) -> int:
    # crude heuristic: ~4 chars per token
    return max(1, len(text) // 4)


def chunk_markdown(
    *,
    markdown: str,
    target_chunk_tokens: int = 400,
    max_chunk_tokens: int = 800,
    overlap_tokens: int = 60,
) -> list[Chunk]:
    lines = markdown.splitlines()
    heading_stack: list[tuple[int, str]] = []

    def current_heading_path() -> str:
        if not heading_stack:
            return ""
        return " > ".join(h for _, h in heading_stack)

    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_tokens = 0
    last_overlap: list[str] = []
    last_overlap_tokens = 0

    def flush() -> None:
        nonlocal buf, buf_tokens, last_overlap, last_overlap_tokens
        text = "\n".join(buf).strip()
        if not text:
            buf = []
            buf_tokens = 0
            return
        chunks.append(Chunk(heading_path=current_heading_path(), text=text + "\n", char_len=len(text)))

        # Build overlap from end of buf
        if overlap_tokens > 0:
            overlap: list[str] = []
            tok = 0
            for line in reversed(buf):
                tok += _approx_tokens(line + "\n")
                overlap.append(line)
                if tok >= overlap_tokens:
                    break
            overlap.reverse()
            last_overlap = overlap
            last_overlap_tokens = tok
        else:
            last_overlap = []
            last_overlap_tokens = 0

        buf = []
        buf_tokens = 0

    for raw in lines:
        line = raw.rstrip()
        m = _re_heading.match(line)
        if m:
            # new section => flush current chunk
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            continue

        # preserve empty lines as paragraph boundaries
        tok = _approx_tokens(line + "\n")
        if buf_tokens + tok > max_chunk_tokens and buf:
            flush()
            # carry overlap into next buffer
            if last_overlap:
                buf.extend(last_overlap)
                buf_tokens = last_overlap_tokens

        buf.append(line)
        buf_tokens += tok

        if buf_tokens >= target_chunk_tokens:
            flush()
            if last_overlap:
                buf.extend(last_overlap)
                buf_tokens = last_overlap_tokens

    flush()
    return [c for c in chunks if c.text.strip()]

