# Botcast

Daily commute podcast bot — send a topic, get back an MP3.

Current stage: minimal CLI proof of concept (topic → Gemini script → edge-tts audio).
See [Project Plan.md](Project%20Plan.md) for the full motivation and roadmap.

## Setup

```bash
python -m venv venv
./venv/Scripts/pip install -r requirements.txt
```

Create a `.env` file (see `.env.example`) with your [Gemini API key](https://aistudio.google.com/apikey):

```
GEMINI_API_KEY=your-key-here
```

## Usage

```bash
./venv/Scripts/python.exe podcast.py "the history of espresso"
```

Produces `script_<timestamp>.txt` and `podcast_<timestamp>.mp3` in the project folder.
