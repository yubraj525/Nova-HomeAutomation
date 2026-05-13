"""
Offline Nepali / Nepanglish Speech-to-Text
==========================================
Uses sherpa-onnx's Whisper tiny (multilingual) model — runs entirely on CPU,
no internet required after the one-time model download.

Language auto-detection is ON by default.  Forcing language="ne" makes it
faster and more accurate for pure Nepali; "en" for pure English. Leave it as
"auto" (None) for Nepanglish code-switching.

Quick test:
    python -m app.stt.sherpa_stt          # transcribes data/output_audio/speech.wav
    python -m app.stt.sherpa_stt path/to/audio.wav
"""

from __future__ import annotations

import os
import sys
import wave
import struct
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model paths (relative to project root)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_MODEL_DIR = _PROJECT_ROOT / "models" / "sherpa" / "sherpa-onnx-whisper-tiny"

ENCODER_PATH = _MODEL_DIR / "tiny-encoder.int8.onnx"
DECODER_PATH = _MODEL_DIR / "tiny-decoder.int8.onnx"
TOKENS_PATH  = _MODEL_DIR / "tiny-tokens.txt"

# Default audio path matches the rest of the pipeline
DEFAULT_AUDIO = str(_PROJECT_ROOT / "data" / "output_audio" / "speech.wav")

# Language hint:  "ne" = Nepali,  "en" = English,  "" = auto-detect
# Auto-detect is slightly slower but handles Nepanglish best.
LANGUAGE: str = ""   # empty string → auto-detect inside sherpa-onnx

# ---------------------------------------------------------------------------
# Lazy model singleton — loaded once, re-used across calls
# ---------------------------------------------------------------------------
_recognizer = None


def _check_model() -> bool:
    """Return True if all model files exist and are non-trivially sized."""
    for p in (ENCODER_PATH, DECODER_PATH, TOKENS_PATH):
        if not p.exists() or p.stat().st_size < 1000:
            return False
    return True


def _load_recognizer():
    """Load the sherpa-onnx OfflineRecognizer once and cache it."""
    global _recognizer
    if _recognizer is not None:
        return _recognizer

    if not _check_model():
        raise FileNotFoundError(
            f"Sherpa-ONNX Whisper model not found at:\n  {_MODEL_DIR}\n\n"
            "Run this once to download it:\n"
            "  python scripts/download_stt_model.py"
        )

    try:
        import sherpa_onnx
    except ImportError as exc:
        raise ImportError(
            "sherpa-onnx is not installed.\n"
            "  pip install sherpa-onnx"
        ) from exc

    logger.info("Loading Whisper-tiny model from %s …", _MODEL_DIR)

    _recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=str(ENCODER_PATH),
        decoder=str(DECODER_PATH),
        tokens=str(TOKENS_PATH),
        language=LANGUAGE,          # "" = auto-detect
        task="transcribe",
        num_threads=min(4, os.cpu_count() or 2),
        decoding_method="greedy_search",
    )
    logger.info("Model loaded ✓")
    return _recognizer


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _read_wave_mono16k(path: str) -> tuple[list[float], int]:
    """
    Read a WAV file and return (samples_as_floats, sample_rate).
    sherpa-onnx expects float32 PCM in [-1, 1].  We accept any standard
    WAV and resample to 16 kHz mono if needed (via a simple decimation —
    good enough for speech; use soxr for production quality if desired).
    """
    with wave.open(path, "rb") as wf:
        n_channels = wf.getnchannels()
        samp_width = wf.getsampwidth()
        frame_rate = wf.getframerate()
        n_frames   = wf.getnframes()
        raw        = wf.readframes(n_frames)

    # Decode PCM bytes → int16 list
    if samp_width == 2:
        fmt = f"<{n_frames * n_channels}h"
        samples = list(struct.unpack(fmt, raw))
    elif samp_width == 1:
        # 8-bit unsigned → signed
        samples = [b - 128 for b in raw]
        samples = [s * 256 for s in samples]
        n_frames = len(samples) // n_channels
    else:
        raise ValueError(f"Unsupported sample width: {samp_width}")

    # Mix down to mono
    if n_channels > 1:
        mono = [
            sum(samples[i * n_channels: (i + 1) * n_channels]) // n_channels
            for i in range(n_frames)
        ]
    else:
        mono = samples

    # Normalise to [-1, 1]
    floats = [s / 32768.0 for s in mono]

    # Resample to 16 kHz via simple decimation (fine for STT)
    if frame_rate != 16000:
        ratio = frame_rate / 16000
        floats = [floats[int(i * ratio)] for i in range(int(len(floats) / ratio))]
        frame_rate = 16000

    return floats, frame_rate


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe_audio_offline(filepath: str = DEFAULT_AUDIO) -> str:
    """
    Transcribe *filepath* fully offline using sherpa-onnx Whisper-tiny.

    Returns the transcribed text string (may contain Devanagari, Latin, or
    both — Whisper handles Nepanglish code-switching naturally).

    Raises FileNotFoundError if the model hasn't been downloaded yet.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Audio file not found: {filepath}")

    recognizer = _load_recognizer()

    logger.info("Transcribing (offline): %s", filepath)

    samples, sample_rate = _read_wave_mono16k(filepath)

    stream = recognizer.create_stream()
    stream.accept_waveform(sample_rate, samples)
    recognizer.decode_stream(stream)

    text = stream.result.text.strip()
    logger.info("Transcribed: %s", text)
    return text


# ---------------------------------------------------------------------------
# Backwards-compatible wrapper — drop-in for app.stt.whisper.transcribe_audio
# ---------------------------------------------------------------------------

def transcribe_audio(filepath: str = DEFAULT_AUDIO) -> str:
    """
    Drop-in replacement for the cloud Whisper transcribe_audio().
    Uses the offline sherpa-onnx model — no internet required.
    """
    print("Transcribing (offline sherpa-onnx) …")
    try:
        text = transcribe_audio_offline(filepath)
        print(f"Transcribed: {text}")
        return text
    except FileNotFoundError as exc:
        print(f"[sherpa_stt] ERROR: {exc}")
        raise


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    audio_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AUDIO
    result = transcribe_audio(audio_file)
    print(f"\n📝 Result: {result}")
