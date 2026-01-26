#!/usr/bin/env python3
import argparse
import logging
import os
import sys
from http.cookiejar import MozillaCookieJar
from pathlib import Path
import requests

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from common.config import load_config  # noqa: E402


def _resolve_cookie_file(config_path: str | None, cookies_file: str | None) -> str | None:
    if cookies_file:
        return cookies_file

    if config_path:
        config = load_config(config_path)
        if config.api.youtube_cookies:
            return str(config.api.youtube_cookies)

    return os.environ.get("YOUTUBE_COOKIES_FILE")


def _check_cookie_file(cookie_file: str) -> None:
    path = Path(cookie_file).expanduser()
    print(f"Cookie file: {path}")
    print(f"Exists: {path.exists()}")
    if path.exists():
        print(f"Size bytes: {path.stat().st_size}")
        print(f"Readable: {os.access(path, os.R_OK)}")

    jar = MozillaCookieJar()
    jar.load(str(path), ignore_discard=True, ignore_expires=True)
    print(f"Cookie load ok. Entries: {len(jar)}")


def _test_transcript_request(video_id: str, cookie_file: str) -> None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception as exc:
        print(f"Failed to import youtube-transcript-api: {exc}")
        sys.exit(2)

    print(f"Calling YouTubeTranscriptApi().list({video_id})...")
    session = requests.Session()
    jar = MozillaCookieJar()
    jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
    session.cookies.update(jar)
    api = YouTubeTranscriptApi(http_client=session)
    transcript_list = api.list(video_id)
    langs = [f"{t.language} ({t.language_code}) [generated={t.is_generated}]" for t in transcript_list]
    print(f"Success. Transcripts: {', '.join(langs) if langs else 'none'}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repro cookie-load and YouTube transcript request errors."
    )
    parser.add_argument("--config", help="Path to config YAML (optional).")
    parser.add_argument(
        "--cookies-file",
        help="Cookie file path (overrides config/api.youtube_cookies).",
    )
    parser.add_argument(
        "--video-id",
        default="dQw4w9WgXcQ",
        help="YouTube video ID to test (default: dQw4w9WgXcQ).",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Only validate cookie file load; skip YouTube request.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    cookie_file = _resolve_cookie_file(args.config, args.cookies_file)
    if not cookie_file:
        print("No cookie file provided. Use --cookies-file or --config.")
        return 2

    try:
        _check_cookie_file(cookie_file)
    except Exception as exc:
        print(f"Cookie file load failed: {type(exc).__name__}: {exc}")
        return 1

    if args.no_network:
        return 0

    try:
        _test_transcript_request(args.video_id, cookie_file)
    except Exception as exc:
        print(f"YouTube request failed: {type(exc).__name__}: {exc}")
        if "cookie" in str(exc).lower():
            print("Note: error mentions cookies; verify the file format and permissions.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
