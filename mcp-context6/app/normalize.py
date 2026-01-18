from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup
from markdownify import markdownify as md


@dataclass(frozen=True)
class NormalizedDoc:
    title: str | None
    markdown: str
    raw_format: str
    norm_format: str


_re_ws = re.compile(r"[ \t]+\n")


def normalize_html(html: str) -> NormalizedDoc:
    soup = BeautifulSoup(html, "html.parser")
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # Remove scripts/styles/nav/footer boilerplate (best-effort)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text_html = str(soup)
    markdown = md(text_html, heading_style="ATX")
    markdown = _re_ws.sub("\n", markdown).strip() + "\n"

    return NormalizedDoc(title=title, markdown=markdown, raw_format="html", norm_format="markdown")


def normalize_markdown(markdown: str) -> NormalizedDoc:
    m = markdown.strip() + "\n"
    return NormalizedDoc(title=None, markdown=m, raw_format="markdown", norm_format="markdown")

