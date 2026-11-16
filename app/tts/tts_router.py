"""Script based selection between NOVA's independent TTS engines."""

from __future__ import annotations

from enum import Enum
import threading


class TTSLanguage(str, Enum):
    NEPALI = "nepali"
    ENGLISH = "english"


def route_language(text: str | None) -> TTSLanguage:
    """Route any text containing a Devanagari block code point to Nepali."""
    devanagari_ranges = (
        (0x0900, 0x097F),  # Devanagari
        (0x1CD0, 0x1CFF),  # Vedic Extensions
        (0xA8E0, 0xA8FF),  # Devanagari Extended
        (0x11B00, 0x11B5F),  # Devanagari Extended-A
    )
    if text and any(
        start <= ord(character) <= end
        for character in text
        for start, end in devanagari_ranges
    ):
        return TTSLanguage.NEPALI
    return TTSLanguage.ENGLISH


class TTSRouter:
    """Select and stream from one engine without changing the input text."""

    def __init__(self, nepali_synthesizer, english_synthesizer):
        self.nepali_synthesizer = nepali_synthesizer
        self.english_synthesizer = english_synthesizer
        self._nepali_lock = threading.Lock()
        self._english_lock = threading.Lock()

    def synthesize_stream(self, text: str):
        is_nepali = route_language(text) is TTSLanguage.NEPALI
        engine = self.nepali_synthesizer if is_nepali else self.english_synthesizer
        lock = self._nepali_lock if is_nepali else self._english_lock
        # The Nepali ONNX wrapper exposes mutable speed/model state, and its
        # thread-safety is unspecified. Keep a cancelled producer from
        # overlapping a later call on that shared instance.
        with lock:
            yield from engine.synthesize_stream(text)

    def sample_rate_for(self, text: str) -> int:
        engine = (
            self.nepali_synthesizer
            if route_language(text) is TTSLanguage.NEPALI
            else self.english_synthesizer
        )
        return engine.sample_rate
