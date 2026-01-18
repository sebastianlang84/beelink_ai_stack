from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx


_skip_prefixes = ("/assets/", "/static/", "/img/", "/css/", "/js/")
_drop_query_keys_prefix = ("utm_",)
_drop_query_keys_exact = {"gclid", "fbclid", "ref", "source"}


def canonicalize_url(url: str) -> str:
    p = urlparse(url)
    scheme = p.scheme or "https"
    netloc = p.netloc
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    q = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        kl = k.lower()
        if any(kl.startswith(prefix) for prefix in _drop_query_keys_prefix):
            continue
        if kl in _drop_query_keys_exact:
            continue
        q.append((k, v))
    query = urlencode(q, doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))


def is_allowed_url(*, url: str, allow_domains: list[str], allow_path_prefixes: list[str]) -> bool:
    p = urlparse(url)
    if p.netloc not in allow_domains:
        return False
    path = p.path or "/"
    if any(path.startswith(prefix) for prefix in _skip_prefixes):
        return False
    return any(path.startswith(prefix) for prefix in allow_path_prefixes)


def match_globs(path: str, *, include: list[str], exclude: list[str]) -> bool:
    if exclude and any(fnmatch.fnmatch(path, pat) for pat in exclude):
        return False
    if include:
        return any(fnmatch.fnmatch(path, pat) for pat in include)
    return True


@dataclass(frozen=True)
class FetchedDoc:
    canonical_path: str
    url_or_path: str
    raw_bytes: bytes
    content_type: str


class LocalFetcher:
    def __init__(self, *, root: str, include: list[str], exclude: list[str], max_doc_size_bytes: int) -> None:
        self._root = Path(root)
        self._include = include
        self._exclude = exclude
        self._max = max_doc_size_bytes

    def fetch(self) -> Iterable[FetchedDoc]:
        for path in self._root.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(self._root))
            if not match_globs(rel, include=self._include, exclude=self._exclude):
                continue
            data = path.read_bytes()
            if len(data) > self._max:
                continue
            yield FetchedDoc(canonical_path=rel, url_or_path=str(path), raw_bytes=data, content_type="text/markdown")


class GithubFetcher:
    def __init__(self, *, repo: str, ref: str, include: list[str], exclude: list[str], max_doc_size_bytes: int) -> None:
        self._repo = repo
        self._ref = ref
        self._include = include
        self._exclude = exclude
        self._max = max_doc_size_bytes

    def fetch(self) -> tuple[str, list[FetchedDoc]]:
        tmp = Path(tempfile.mkdtemp(prefix="context6_git_"))
        try:
            url = f"https://github.com/{self._repo}.git"
            subprocess.check_call(["git", "clone", "--depth", "1", "--branch", self._ref, url, str(tmp)])
            resolved = subprocess.check_output(["git", "-C", str(tmp), "rev-parse", "HEAD"], text=True).strip()
            docs: list[FetchedDoc] = []
            for path in tmp.rglob("*"):
                if not path.is_file():
                    continue
                rel = str(path.relative_to(tmp))
                if not match_globs(rel, include=self._include, exclude=self._exclude):
                    continue
                data = path.read_bytes()
                if len(data) > self._max:
                    continue
                docs.append(FetchedDoc(canonical_path=rel, url_or_path=f"github:{self._repo}@{resolved}:{rel}", raw_bytes=data, content_type="text/markdown"))
            return resolved, docs
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class CrawlFetcher:
    def __init__(
        self,
        *,
        start_urls: list[str],
        allow_domains: list[str],
        allow_path_prefixes: list[str],
        max_pages: int,
        max_depth: int,
        delay_s: float,
        max_doc_size_bytes: int,
        user_agent: str = "context6-poC/0.1",
    ) -> None:
        self._start_urls = [canonicalize_url(u) for u in start_urls]
        self._allow_domains = allow_domains
        self._allow_prefixes = allow_path_prefixes
        self._max_pages = int(max_pages)
        self._max_depth = int(max_depth)
        self._delay_s = float(delay_s)
        self._max = max_doc_size_bytes
        self._ua = user_agent

    def fetch(self) -> list[FetchedDoc]:
        out: list[FetchedDoc] = []
        visited: set[str] = set()
        queue: list[tuple[str, int]] = []
        for u in self._start_urls:
            queue.append((u, 0))

        robots_cache: dict[str, RobotFileParser] = {}

        def can_fetch(url: str) -> bool:
            p = urlparse(url)
            base = f"{p.scheme}://{p.netloc}"
            if base not in robots_cache:
                rp = RobotFileParser()
                rp.set_url(urljoin(base, "/robots.txt"))
                try:
                    rp.read()
                except Exception:
                    # strict: if robots can't be fetched, treat as disallow
                    return False
                robots_cache[base] = rp
            rp = robots_cache[base]
            return bool(rp.can_fetch(self._ua, url))

        with httpx.Client(headers={"User-Agent": self._ua}, timeout=20.0, follow_redirects=True) as client:
            while queue and len(out) < self._max_pages:
                url, depth = queue.pop(0)
                url = canonicalize_url(url)
                if url in visited:
                    continue
                visited.add(url)

                if depth < 0:
                    continue
                if not is_allowed_url(url=url, allow_domains=self._allow_domains, allow_path_prefixes=self._allow_prefixes):
                    continue
                if not can_fetch(url):
                    continue

                resp = client.get(url)
                ct = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if resp.status_code != 200:
                    continue

                if ct and not (ct.startswith("text/") or ct in ("application/xhtml+xml",)):
                    continue

                data = resp.content
                if len(data) > self._max:
                    continue

                out.append(
                    FetchedDoc(
                        canonical_path=urlparse(url).path or "/",
                        url_or_path=url,
                        raw_bytes=data,
                        content_type=ct or "text/html",
                    )
                )

                # Extract more links (HTML only)
                if depth < self._max_depth and ("html" in (ct or "") or ct in ("application/xhtml+xml",)):
                    text = resp.text
                    for m in re.finditer(r'href=["\\\']([^"\\\']+)["\\\']', text, flags=re.IGNORECASE):
                        href = m.group(1)
                        if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                            continue
                        nxt = canonicalize_url(urljoin(url, href))
                        if nxt in visited:
                            continue
                        if not is_allowed_url(url=nxt, allow_domains=self._allow_domains, allow_path_prefixes=self._allow_prefixes):
                            continue
                        queue.append((nxt, depth + 1))

                if self._delay_s > 0:
                    import time

                    time.sleep(self._delay_s)

        return out
