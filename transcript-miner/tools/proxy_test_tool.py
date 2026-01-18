import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig, GenericProxyConfig
import logging

logging.basicConfig(level=logging.DEBUG)


def test_proxy(mode, username, password, video_id="dQw4w9WgXcQ"):
    print(f"\n--- Testing Mode: {mode} ---")
    session = requests.Session()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    session.headers.update({"User-Agent": ua})

    proxy_config = None
    if mode == "webshare-rotate":
        proxy_config = WebshareProxyConfig(
            proxy_username=username, proxy_password=password
        )
    elif mode == "webshare-sticky":
        proxy_config = WebshareProxyConfig(
            proxy_username=f"{username.replace('-rotate', '')}-session-test",
            proxy_password=password,
        )
    elif mode == "static":
        # Einer der US Proxies aus der Liste
        proxy_config = GenericProxyConfig(
            http_url=f"http://{username.replace('-rotate', '')}:{password}@216.10.27.159:6837"
        )

    try:
        api = YouTubeTranscriptApi(http_client=session, proxy_config=proxy_config)
        print("Fetching transcript list...")
        transcript_list = api.list(video_id)
        print("Success! Found transcripts.")
        transcript = transcript_list.find_transcript(["en"])
        print("Fetching actual text...")
        content = transcript.fetch()
        print(f"SUCCESS! Fetched {len(content)} snippets.")
        return True
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    user = "hgnktkba"
    pw = "pt4z82ch2oj8"
    video = "42RfznSu91o"  # Das Video das wir minen wollen

    # Test 1: Webshare Rotate (Standard)
    test_proxy("webshare-rotate", f"{user}-rotate", pw, video)

    # Test 2: Webshare Sticky
    test_proxy("webshare-sticky", user, pw, video)

    # Test 3: Static Proxy
    test_proxy("static", user, pw, video)
