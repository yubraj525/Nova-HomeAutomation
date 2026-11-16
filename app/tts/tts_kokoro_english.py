"""Kokoro English synthesis, exposed as chunks for NOVA's shared playback."""

from __future__ import annotations

import threading
from pathlib import Path
import re


VOICE = "af_sky"
SPEED = 1.1
LANG = "en-us"
MAX_CHUNK_CHARS = 160


def chunk_text(text: str) -> list[str]:
    """Split at sentence boundaries, then cap long pieces for quicker audio."""
    chunks: list[str] = []
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for sentence in sentences:
        remaining = sentence.strip()
        while len(remaining) > MAX_CHUNK_CHARS:
            # Prefer a word boundary. If a single token is unusually long,
            # cut at the limit so one token cannot hold up the entire reply.
            boundary = remaining.rfind(" ", 0, MAX_CHUNK_CHARS + 1)
            if boundary <= 0:
                boundary = MAX_CHUNK_CHARS
            piece = remaining[:boundary].strip()
            if piece:
                chunks.append(piece)
            remaining = remaining[boundary:].strip()
        if remaining:
            chunks.append(remaining)
    return chunks


class KokoroEnglishTTS:
    """Kokoro wrapper preserving the project's existing voice configuration."""

    def __init__(self, kokoro=None):
        if kokoro is None:
            from kokoro_onnx import Kokoro

            root = Path(__file__).resolve().parents[2]
            kokoro = Kokoro(
                str(root / "models" / "kokoro-v1.0.int8.onnx"),
                str(root / "models" / "voices-v1.0.bin"),
            )
        self.kokoro = kokoro
        self.sample_rate = 24000
        self._lock = threading.Lock()

    def synthesize_stream(self, text: str):
        # Kokoro's create() returns a complete waveform for each input chunk.
        # Yield each punctuation chunk immediately to NOVA's shared playback.
        for part in chunk_text(text):
            with self._lock:
                samples, sample_rate = self.kokoro.create(
                    part, voice=VOICE, speed=SPEED, lang=LANG
                )
            self.sample_rate = sample_rate
            yield samples


_synthesizer: KokoroEnglishTTS | None = None
_synthesizer_lock = threading.Lock()


def get_synthesizer() -> KokoroEnglishTTS:
    global _synthesizer
    with _synthesizer_lock:
        if _synthesizer is None:
            _synthesizer = KokoroEnglishTTS()
        return _synthesizer


# Retain the original script-facing entry point, without creating a second
# audio queue or player thread. App playback is owned by SpeakerManager.
def stream_tts(text: str) -> None:
    synthesizer = get_synthesizer()
    for samples in synthesizer.synthesize_stream(text):
        import sounddevice as sd

        sd.play(samples, synthesizer.sample_rate)
        sd.wait()
