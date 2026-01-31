#!/usr/bin/env python3
"""
Quick proxy check using the same Python stack as the miner.
Uses env vars (no secrets in args/output).
"""
import argparse
import os
import sys

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig


def _build_proxy_config(mode: str, http_url: str | None, https_url: str | None) -> object | None:
    if mode == "webshare":
        user = os.environ.get("WEBSHARE_USERNAME", "").strip()
        pw = os.environ.get("WEBSHARE_PASSWORD", "").strip()
        if not user or not pw:
            raise RuntimeError("Missing WEBSHARE_USERNAME/WEBSHARE_PASSWORD")
        return WebshareProxyConfig(proxy_username=user, proxy_password=pw)
    if mode == "generic":
        if not http_url and not https_url:
            raise RuntimeError("Missing YOUTUBE_PROXY_HTTP_URL/YOUTUBE_PROXY_HTTPS_URL")
        return GenericProxyConfig(http_url=http_url, https_url=https_url)
    if mode == "none":
        return None
    raise RuntimeError(f"Unsupported mode: {mode}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Quick proxy check via youtube_transcript_api")
    parser.add_argument("--video", default="dQw4w9WgXcQ", help="YouTube video ID")
    parser.add_argument(
        "--mode",
        default=os.environ.get("YOUTUBE_PROXY_MODE", "webshare"),
        choices=["webshare", "generic", "none"],
        help="Proxy mode (default: YOUTUBE_PROXY_MODE or webshare)",
    )
    args = parser.parse_args()

    http_url = os.environ.get("YOUTUBE_PROXY_HTTP_URL", "").strip() or None
    https_url = os.environ.get("YOUTUBE_PROXY_HTTPS_URL", "").strip() or None

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
    )

    proxy_cfg = _build_proxy_config(args.mode, http_url, https_url)
    api = YouTubeTranscriptApi(http_client=session, proxy_config=proxy_cfg)

    print(f"Proxy quickcheck: mode={args.mode} video={args.video}")
    try:
        tlist = api.list(args.video)
        transcript = tlist.find_transcript(["en", "de"])
        content = transcript.fetch()
        print(f"OK: fetched {len(content)} snippets")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
