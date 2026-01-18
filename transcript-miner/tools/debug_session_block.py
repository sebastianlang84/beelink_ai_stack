import requests
from youtube_transcript_api import YouTubeTranscriptApi
import logging

logging.basicConfig(level=logging.INFO)


def test_with_session(video_id):
    session = requests.Session()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    session.headers.update(
        {
            "User-Agent": ua,
            "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
        }
    )

    print(f"Testing with Session and User-Agent: {ua}")
    try:
        api = YouTubeTranscriptApi(http_client=session)
        transcript_list = api.list(video_id)
        print("Success with list()!")
        transcript = transcript_list.find_generated_transcript(["en"])
        print(f"Found transcript: {transcript.language}. Fetching content...")
        content = transcript.fetch()
        print(f"Success with fetch()! Length: {len(content)}")
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {e}")


def test_with_minimal_session(video_id):
    session = requests.Session()
    # Kein User-Agent setzen, requests nutzt Standard
    print("Testing with Minimal Session (Default Requests UA)")
    try:
        api = YouTubeTranscriptApi(http_client=session)
        transcript_list = api.list(video_id)
        transcript = transcript_list.find_generated_transcript(["en"])
        content = transcript.fetch()
        print(f"Success with minimal session! Length: {len(content)}")
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    video_id = "42RfznSu91o"
    test_with_minimal_session(video_id)
    print("-" * 20)
    test_with_session(video_id)
