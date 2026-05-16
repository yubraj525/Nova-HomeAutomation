"""
tts_engine.py — Nova TTS wrapper
=================================
Public API (unchanged):
    await text_to_speech(text, emotion="sad")  → audio path str
    await play_audio(path)
    pause_music() / resume_music() / stop_music()

Now routes ALL synthesis (Nepali, English, mixed Nepanglish) through the
offline NepanglishTTS engine (Piper ONNX via sherpa-onnx).
No cloud calls, no GPU needed — runs on Raspberry Pi.

The filler/streaming helpers are also re-exported so other modules can do:
    from app.tts.tts_engine import speak, play_filler, render_fillers
"""
from __future__ import annotations

import asyncio
import logging
import os
import struct
import tempfile
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
_ROOT      = Path(__file__).resolve().parent.parent.parent
_AUDIO_DIR = _ROOT / "data" / "output_audio"
_FINAL_WAV = str(_AUDIO_DIR / "response.wav")
_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Keep AUDIO_PATH import-compatible with config (if it exists)
try:
    from config.config import AUDIO_PATH  # type: ignore
except ImportError:
    AUDIO_PATH = _FINAL_WAV

# ── Thread pool ────────────────────────────────────────────────────────────
_executor = ThreadPoolExecutor(max_workers=1)

# ── Pygame state ───────────────────────────────────────────────────────────
_music_paused  = False
_music_playing = False


# ── Lazy imports (avoid loading heavy model at import time) ────────────────
def _get_synth():
    from app.tts.nepanglish_tts import get_synthesizer
    return get_synthesizer()


# ---------------------------------------------------------------------------
# Core synthesis  (blocking, runs in executor)
# ---------------------------------------------------------------------------

def _synthesize_to_wav(text: str) -> str:
    """
    Synthesise *text* (any mix of Nepali/English) to _FINAL_WAV.
    Returns the path to the written WAV file.
    """
    synth   = _get_synth()
    chunks  = list(synth.synthesize_stream(text))

    if not chunks:
        logger.warning("TTS produced no audio for: %r", text)
        return _FINAL_WAV

    samples = np.concatenate(chunks).astype(np.float32)
    pcm     = (np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes()

    # Release pygame's hold on the file before overwriting
    try:
        import pygame  # type: ignore
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            pygame.mixer.quit()
    except Exception:
        pass

    with wave.open(_FINAL_WAV, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(synth.sample_rate)
        wf.writeframes(pcm)

    logger.debug("WAV written → %s  (%d samples)", _FINAL_WAV, len(samples))
    return _FINAL_WAV


# ---------------------------------------------------------------------------
# Public async API  (keeps exact same signature as old tts_engine)
# ---------------------------------------------------------------------------

async def text_to_speech(text: str, emotion: str = "sad") -> str:
    """
    Synthesise *text* offline.  *emotion* is accepted for API compatibility
    but is not used (the Nepali Piper voice has a single speaker style).

    Returns the path to the output WAV file.
    """
    logger.info("TTS (%s chars) …", len(text))
    loop = asyncio.get_event_loop()
    path = await loop.run_in_executor(_executor, _synthesize_to_wav, text)
    return path


# ---------------------------------------------------------------------------
# Playback helpers
# ---------------------------------------------------------------------------

def _play_blocking(path: str):
    import pygame  # type: ignore
    pygame.mixer.init()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.05)
    pygame.mixer.music.unload()
    logger.debug("Done playing: %s", path)


async def play_audio(path: str = AUDIO_PATH):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, _play_blocking, path)


# ---------------------------------------------------------------------------
# Music controls  (unchanged from original)
# ---------------------------------------------------------------------------

def pause_music():
    global _music_paused
    try:
        import pygame  # type: ignore
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            _music_paused = True
            print("Music paused!")
        else:
            print("Nothing playing to pause!")
    except Exception as exc:
        logger.error("pause_music: %s", exc)


def resume_music():
    global _music_paused
    try:
        import pygame  # type: ignore
        if pygame.mixer.get_init() and _music_paused:
            pygame.mixer.music.unpause()
            _music_paused = False
            print("Music resumed!")
        else:
            print(f"Cannot resume! paused={_music_paused}")
    except Exception as exc:
        logger.error("resume_music: %s", exc)


def stop_music():
    global _music_paused, _music_playing
    try:
        import pygame  # type: ignore
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            pygame.mixer.quit()
            _music_paused  = False
            _music_playing = False
            print("Music stopped!")
        else:
            print("Nothing to stop!")
    except Exception as exc:
        logger.error("stop_music: %s", exc)


# ---------------------------------------------------------------------------
# Convenience re-exports  (so callers can do: from app.tts.tts_engine import speak)
# ---------------------------------------------------------------------------

def speak(text: str, filler: str | None = None, speed: float = 1.0):
    """Synchronous speak — wraps nepanglish_tts.speak()."""
    from app.tts.nepanglish_tts import speak as _speak
    _speak(text, filler=filler, speed=speed)


def play_filler(name: str = "ah"):
    from app.tts.fillers import play_filler as _pf
    _pf(name)


def render_fillers(fillers=None, force: bool = False):
    from app.tts.fillers import render_fillers as _rf
    _rf(fillers=fillers, force=force)
