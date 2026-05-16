"""
fillers.py — Pre-rendered Nepali "thinking sounds"
====================================================
Use play_filler() to instantly play a short hesitation sound while a
slower operation (LLM call, etc.) runs in the background.

render_fillers() generates the WAV files once using the TTS engine.
Call it once after install.

Available defaults: ah, oh, eh, la
Custom fillers can be passed as a dict to render_fillers().
"""
from __future__ import annotations

import logging
import os
import struct
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_ROOT       = Path(__file__).resolve().parent.parent.parent
_FILLER_DIR = _ROOT / "assets" / "sounds" / "fillers"

# Default filler texts  (Nepali "thinking" sounds)
DEFAULT_FILLERS: dict[str, str] = {
    "ah":  "अहँ...",
    "oh":  "ओहो...",
    "eh":  "एह...",
    "la":  "ल त...",
    "hmm": "हम्म...",
}


def _filler_path(name: str) -> Path:
    return _FILLER_DIR / f"{name}.wav"


def render_fillers(
    fillers: Optional[dict[str, str]] = None,
    force: bool = False,
) -> None:
    """
    Pre-render filler WAVs using NepanglishTTS.
    Skips files that already exist unless *force=True*.

    Args:
        fillers: dict of {name: nepali_text}.  Defaults to DEFAULT_FILLERS.
        force:   re-render even if the WAV already exists.
    """
    from app.tts.nepanglish_tts import get_synthesizer  # local import to avoid circularity

    _FILLER_DIR.mkdir(parents=True, exist_ok=True)
    synth   = get_synthesizer()
    fillers = fillers or DEFAULT_FILLERS

    for name, text in fillers.items():
        path = _filler_path(name)
        if path.exists() and not force:
            logger.debug("Filler '%s' already rendered — skipping", name)
            continue

        logger.info("Rendering filler '%s' …", name)
        samples = synth.synthesize(text)
        pcm     = (np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes()

        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(synth.sample_rate)
            wf.writeframes(pcm)

        logger.info("  → saved %s", path)

    print(f"Fillers rendered to {_FILLER_DIR}")


def play_filler(name: str = "ah") -> None:
    """
    Play a pre-rendered filler WAV synchronously.
    Falls back to rendering on-the-fly if the WAV doesn't exist yet.
    """
    path = _filler_path(name)

    if not path.exists():
        logger.warning("Filler '%s' not found — rendering now (add render_fillers() to setup)", name)
        text = DEFAULT_FILLERS.get(name, "अहँ...")
        render_fillers({name: text})

    try:
        import sounddevice as sd  # type: ignore
        import soundfile as sf    # type: ignore
        data, sr = sf.read(str(path), dtype="float32")
        sd.play(data, samplerate=sr, blocking=True)
    except Exception:
        try:
            import pygame  # type: ignore
            pygame.mixer.init()
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.02)
            pygame.mixer.music.unload()
        except Exception as exc:
            logger.error("play_filler failed: %s", exc)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    render_fillers(force=True)
    for name in DEFAULT_FILLERS:
        print(f"Playing: {name}")
        play_filler(name)
        time.sleep(0.3)
