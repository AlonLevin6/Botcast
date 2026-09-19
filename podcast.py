"""
Minimal CLI proof-of-concept for the Daily Commute Podcast Bot.

Flow: topic (CLI arg) -> Gemini writes a ~15-minute spoken script
      -> edge-tts renders it to an MP3 -> saved locally.

Usage:
    python podcast.py "the history of espresso"

Requires GEMINI_API_KEY to be set as an environment variable
(get one for free at https://aistudio.google.com/apikey).
"""

import argparse
import asyncio
import os
import re
import sqlite3
import sys
import time
from datetime import datetime

import edge_tts
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

VOICE = "en-US-AndrewNeural"  # natural-sounding English voice, free via edge-tts
MODEL = "gemini-3.6-flash"
TARGET_WORD_COUNT = 600  # shortened while we work out TTS turnaround time; target is 2000+
MAX_RETRIES = 3  # Gemini's free tier returns transient 503s ("high demand") fairly often

PODCASTS_DIR = "podcasts"
DB_PATH = os.path.join(PODCASTS_DIR, "index.db")

SYSTEM_PROMPT = f"""You are a professional podcast scriptwriter. Write an engaging,
well-structured spoken-word script on the topic the user gives you.

Rules:
- Length: approximately {TARGET_WORD_COUNT} words.
- Write in plain, natural spoken English - no markdown, no headers, no bullet points,
  no stage directions, nothing but the words to be read aloud.
- Open with a short hook, cover the topic with a clear narrative arc, and close with
  a brief, satisfying wrap-up.
- Assume a single narrator voice and an audience listening while commuting."""


def generate_script(topic: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("Missing GEMINI_API_KEY environment variable.")

    client = genai.Client(api_key=api_key)

    print("Writing script...")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=f"Topic: {topic}",
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
            return response.text.strip()
        except errors.ServerError:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(2 * attempt)


async def synthesize_audio(script: str, output_path: str) -> None:
    print("Recording audio...")
    communicate = edge_tts.Communicate(script, VOICE)
    await communicate.save(output_path)


def _slugify(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug[:50] or "topic"


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            topic TEXT NOT NULL,
            script_path TEXT NOT NULL,
            audio_path TEXT NOT NULL,
            rating TEXT
        )
        """
    )


def create_episode(topic: str, script: str) -> tuple[int, str, str]:
    """Reserve on-disk paths for a new episode and record it in the index.
    Returns (episode_id, script_path, audio_path); the caller still has to
    actually synthesize the audio to audio_path."""
    os.makedirs(PODCASTS_DIR, exist_ok=True)
    base = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{_slugify(topic)}"
    script_path = os.path.join(PODCASTS_DIR, f"{base}.txt")
    audio_path = os.path.join(PODCASTS_DIR, f"{base}.mp3")

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    conn = sqlite3.connect(DB_PATH)
    try:
        _init_db(conn)
        cursor = conn.execute(
            "INSERT INTO episodes (created_at, topic, script_path, audio_path) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), topic, script_path, audio_path),
        )
        conn.commit()
        return cursor.lastrowid, script_path, audio_path
    finally:
        conn.close()


def set_rating(episode_id: int, rating: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("UPDATE episodes SET rating = ? WHERE id = ?", (rating, episode_id))
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a daily commute podcast.")
    parser.add_argument("topic", help="The topic to generate a podcast about.")
    args = parser.parse_args()

    script = generate_script(args.topic)
    episode_id, script_path, audio_path = create_episode(args.topic, script)
    print(f"Script saved: {script_path} ({len(script.split())} words)")

    asyncio.run(synthesize_audio(script, audio_path))
    print(f"Podcast ready: {audio_path} (episode #{episode_id})")


if __name__ == "__main__":
    main()
