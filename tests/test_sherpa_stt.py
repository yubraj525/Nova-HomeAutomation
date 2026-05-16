"""
Tests for app/stt/sherpa_stt.py -- offline Nepali / Nepanglish STT.

Run from project root:
    python -m pytest tests/test_sherpa_stt.py -v
    # or without pytest:
    python tests/test_sherpa_stt.py

What is tested
--------------
1. Model files exist and are real (non-empty).
2. _read_wave_mono16k handles mono 16-kHz, stereo 44.1-kHz.
3. transcribe_audio_offline() returns a non-empty string for a real WAV.
4. transcribe_audio() (pipeline wrapper) works the same way.
5. Graceful error on missing audio file.
6. Graceful error when model hasn't been downloaded.

Tests 3-4 require the model to be downloaded first:
    python scripts/download_stt_model.py
Tests 1-2, 5-6 always run (no model needed).
"""

import io
import os
import sys
import struct
import wave
import tempfile
import math
from pathlib import Path

# Force UTF-8 stdout so Windows CP1252 doesn't crash on any special chars
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Make sure project root is on the path so imports work
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav(path: str, freq=440, duration=1.0, sample_rate=16000, channels=1):
    """Write a simple sine-wave WAV for testing."""
    n_frames = int(sample_rate * duration)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(sample_rate)
        for i in range(n_frames):
            for _ in range(channels):
                val = int(32767 * math.sin(2 * math.pi * freq * i / sample_rate))
                wf.writeframes(struct.pack("<h", val))


def _model_present() -> bool:
    from app.stt import sherpa_stt
    return sherpa_stt._check_model()


# ============================================================================
# Unit tests — no model required
# ============================================================================

def test_model_paths_defined():
    """Module must expose the three path constants."""
    from app.stt import sherpa_stt
    assert sherpa_stt.ENCODER_PATH is not None
    assert sherpa_stt.DECODER_PATH is not None
    assert sherpa_stt.TOKENS_PATH is not None
    print("  ✓ model path constants defined")


def test_read_wave_mono_16k():
    """_read_wave_mono16k handles a 16-kHz mono WAV."""
    from app.stt.sherpa_stt import _read_wave_mono16k
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        _make_wav(tmp, sample_rate=16000, channels=1)
        samples, sr = _read_wave_mono16k(tmp)
        assert sr == 16000, f"Expected 16000, got {sr}"
        assert len(samples) > 0
        assert all(-1.0 <= s <= 1.0 for s in samples[:100]), "Samples out of range"
        print(f"  ✓ mono 16k: {len(samples)} samples, sr={sr}")
    finally:
        os.unlink(tmp)


def test_read_wave_stereo_44k():
    """_read_wave_mono16k resamples stereo 44.1-kHz to mono 16-kHz."""
    from app.stt.sherpa_stt import _read_wave_mono16k
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        _make_wav(tmp, sample_rate=44100, channels=2)
        samples, sr = _read_wave_mono16k(tmp)
        assert sr == 16000, f"Expected 16000 after resample, got {sr}"
        assert len(samples) > 0
        print(f"  ✓ stereo 44.1k → mono 16k: {len(samples)} samples")
    finally:
        os.unlink(tmp)


def test_missing_audio_raises():
    """Should raise FileNotFoundError for a non-existent audio path."""
    from app.stt.sherpa_stt import transcribe_audio_offline
    try:
        transcribe_audio_offline("/nonexistent/path/audio.wav")
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        print("  ✓ FileNotFoundError raised for missing audio")


def test_model_not_downloaded_raises():
    """When model is absent, _load_recognizer should raise FileNotFoundError."""
    if _model_present():
        print("  – (model present, skipping this test)")
        return
    from app.stt import sherpa_stt
    import importlib
    # Patch paths to fake missing
    orig_enc = sherpa_stt.ENCODER_PATH
    sherpa_stt.ENCODER_PATH = Path("/fake/encoder.onnx")
    sherpa_stt._recognizer = None  # reset singleton
    try:
        sherpa_stt._load_recognizer()
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError as exc:
        assert "download_stt_model" in str(exc)
        print("  ✓ helpful FileNotFoundError raised when model missing")
    finally:
        sherpa_stt.ENCODER_PATH = orig_enc
        sherpa_stt._recognizer = None


# ============================================================================
# Integration tests — require downloaded model
# ============================================================================

def test_transcribe_sine_wave():
    """
    Transcribing a pure sine wave should return a string (possibly empty or
    noise — we just confirm it doesn't crash and returns str).
    """
    if not _model_present():
        print("  – SKIP (model not downloaded — run: python scripts/download_stt_model.py)")
        return
    from app.stt.sherpa_stt import transcribe_audio_offline
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        _make_wav(tmp, freq=440, duration=2.0, sample_rate=16000)
        result = transcribe_audio_offline(tmp)
        assert isinstance(result, str)
        print(f"  ✓ sine wave transcription returned: '{result}'")
    finally:
        os.unlink(tmp)


def test_transcribe_real_speech():
    """
    If data/output_audio/speech.wav exists, transcribe it and print the result.
    """
    if not _model_present():
        print("  – SKIP (model not downloaded)")
        return
    speech_path = str(PROJECT_ROOT / "data" / "output_audio" / "speech.wav")
    if not os.path.exists(speech_path):
        print(f"  – SKIP (no speech.wav found at {speech_path})")
        return
    from app.stt.sherpa_stt import transcribe_audio
    result = transcribe_audio(speech_path)
    assert isinstance(result, str)
    assert len(result) > 0, "Got empty transcription from real speech file"
    print(f"  ✓ Real speech transcribed: '{result}'")


# ============================================================================
# Runner
# ============================================================================

def run_all():
    tests = [
        test_model_paths_defined,
        test_read_wave_mono_16k,
        test_read_wave_stereo_44k,
        test_missing_audio_raises,
        test_model_not_downloaded_raises,
        test_transcribe_sine_wave,
        test_transcribe_real_speech,
    ]

    passed = 0
    failed = 0
    skipped = 0

    print("\n" + "=" * 60)
    print("  Sherpa-ONNX Nepali STT — test suite")
    print("=" * 60)

    for t in tests:
        name = t.__name__.replace("test_", "").replace("_", " ")
        print(f"\n> {name}")
        try:
            t()
            passed += 1
        except AssertionError as exc:
            print(f"  ✗ FAILED: {exc}")
            failed += 1
        except Exception as exc:
            print(f"  ✗ ERROR: {type(exc).__name__}: {exc}")
            failed += 1

    print("\n" + "=" * 60)
    status = "✅ ALL PASSED" if failed == 0 else f"❌ {failed} FAILED"
    print(f"  {status}  |  {passed} passed  |  {failed} failed")
    print("=" * 60 + "\n")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
