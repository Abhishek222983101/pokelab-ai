import os

import pytest

from pokelab_brain.voice import transcribe


def _load_env_key(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1]
    return None


GROQ_KEY = _load_env_key("GROQ_API_KEY_1")


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
def test_real_whisper_transcription_call_succeeds(tmp_path):
    import math
    import struct
    import wave

    wav_path = tmp_path / "tone.wav"
    with wave.open(str(wav_path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        frames = b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / 16000))) for i in range(16000 * 2))
        w.writeframes(frames)

    # a pure tone isn't speech, so an empty/garbage transcript is a VALID
    # result here — the point is the real HTTP round trip (auth,
    # multipart upload, JSON response) doesn't error
    text = transcribe(GROQ_KEY, str(wav_path))
    assert isinstance(text, str)
