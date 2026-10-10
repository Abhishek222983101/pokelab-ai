"""Voice redirect (§10.5): the phone's push-to-talk sends audio, Groq's
Whisper transcribes it, and the text is handed to the same
LlmRouter/agent path a typed command would take — voice is just another
way to produce a string, not a separate pipeline.
"""
from __future__ import annotations

import httpx


def transcribe(api_key: str, audio_path: str, model: str = "whisper-large-v3") -> str:
    """A real call to Groq's audio transcription endpoint. Returns the
    transcribed text (possibly empty for silence/noise — that's a valid
    outcome, not an error)."""
    with open(audio_path, "rb") as f:
        files = {"file": (audio_path, f, "audio/wav")}
        data = {"model": model}
        headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "PokeLab/1.0 (+hackathon demo)"}
        resp = httpx.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers=headers, data=data, files=files, timeout=30,
        )
    resp.raise_for_status()
    return resp.json().get("text", "").strip()
