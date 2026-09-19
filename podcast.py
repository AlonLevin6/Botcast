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
import sys
from datetime import datetime

import edge_tts
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

VOICE = "en-US-AndrewNeural"  # natural-sounding English voice, free via edge-tts
TARGET_WORD_COUNT = 2000  # roughly 15 minutes of spoken audio

SYSTEM_PROMPT = f"""You are a professional podcast scriptwriter. Write an engaging,
well-structured spoken-word script on the topic the user gives you.

Rules:
- Length: approximately {TARGET_WORD_COUNT} words (about 15 minutes spoken aloud).
- Write in plain, natural spoken English - no markdown, no headers, no bullet points,
  no stage directions, nothing but the words to be read aloud.
- Open with a short hook, cover the topic with a clear narrative arc, and close with
  a brief, satisfying wrap-up.
- Assume a single narrator voice and an audience listening while commuting."""


def generate_script(topic: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("Missing GEMINI_API_KEY environment variable.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT,
    )

    print("Writing script...")
    response = model.generate_content(f"Topic: {topic}")
    return response.text.strip()


async def synthesize_audio(script: str, output_path: str) -> None:
    print("Recording audio...")
    communicate = edge_tts.Communicate(script, VOICE)
    await communicate.save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a daily commute podcast.")
    parser.add_argument("topic", help="The topic to generate a podcast about.")
    args = parser.parse_args()

    script = generate_script(args.topic)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = f"script_{timestamp}.txt"
    audio_path = f"podcast_{timestamp}.mp3"

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"Script saved: {script_path} ({len(script.split())} words)")

    asyncio.run(synthesize_audio(script, audio_path))
    print(f"Podcast ready: {audio_path}")


if __name__ == "__main__":
    main()
