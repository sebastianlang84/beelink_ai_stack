import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from youtube_transcript_api import YouTubeTranscriptApi
import logging

logging.basicConfig(level=logging.INFO)


def test_transcript(video_id):
    print(f"--- Testing video_id: {video_id} ---")
    try:
        # Wir nutzen die Logik aus transcript_downloader.py
        # YouTubeTranscriptApi().list(video_id)
        print("Calling YouTubeTranscriptApi().list(video_id)...")
        transcript_list = YouTubeTranscriptApi().list(video_id)
        print("Success! Transcripts found.")
        for t in transcript_list:
            print(f"  - {t.language} ({t.language_code}) [generated={t.is_generated}]")
    except Exception as e:
        print(f"Caught exception: {type(e).__name__}")
        print(f"Message: {str(e)}")

        # Check if it's a known block exception
        if "Too Many Requests" in str(e) or "429" in str(e):
            print("Confirmed: Rate limited (429).")
        elif "blocked" in str(e).lower():
            print("Confirmed: IP seems blocked.")


if __name__ == "__main__":
    # Rick Astley - Never Gonna Give You Up (sehr populär, sollte Transkripte haben)
    video_id = "dQw4w9WgXcQ"
    if len(sys.argv) > 1:
        video_id = sys.argv[1]

    test_transcript(video_id)
