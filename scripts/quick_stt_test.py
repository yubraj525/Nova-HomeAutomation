"""
Quick STT voice test — speak into mic, transcribe offline, hear it back.

Run with the VENV Python (NOT system Python):
    venv\\Scripts\\python.exe scripts\\quick_stt_test.py

What it does:
  1. Records N seconds from your mic  -> data/output_audio/speech.wav
  2. Transcribes it offline with sherpa-onnx Whisper-tiny
  3. Prints the Nepali/English/Nepanglish result
  4. (optional) speaks it back with Kokoro TTS

Requirements: run `python scripts/download_stt_model.py` once first.
"""

import sys
import os
import io
import wave
import asyncio

# Force UTF-8 so Windows CP1252 doesn't crash
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add project root to path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

SPEECH_WAV = os.path.join(ROOT, "data", "output_audio", "speech.wav")
RECORD_SECONDS = 5         # seconds to record from mic
SAMPLE_RATE    = 16000     # Hz — Whisper expects 16 kHz
SPEAK_BACK     = True      # set False to skip TTS playback


# ---------------------------------------------------------------------------
# Step 1: record from mic
# ---------------------------------------------------------------------------
def record_mic(output_path: str, seconds: int = RECORD_SECONDS):
    try:
        import pyaudio
    except ImportError:
        print("[ERROR] pyaudio not found in venv. Install it:")
        print("        venv\\Scripts\\pip install pyaudio")
        sys.exit(1)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    CHUNK  = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1

    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    print(f"\n[MIC] Recording for {seconds} seconds... speak now!")
    frames = []
    for _ in range(int(SAMPLE_RATE / CHUNK * seconds)):
        frames.append(stream.read(CHUNK, exception_on_overflow=False))

    stream.stop_stream()
    stream.close()
    p.terminate()
    print("[MIC] Done recording.")

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(frames))

    print(f"[MIC] Saved to: {output_path}")


# ---------------------------------------------------------------------------
# Step 2: transcribe offline
# ---------------------------------------------------------------------------
def transcribe(audio_path: str) -> str:
    from app.stt.sherpa_stt import transcribe_audio
    return transcribe_audio(audio_path)


# ---------------------------------------------------------------------------
# Step 3: speak back (optional)
# ---------------------------------------------------------------------------
async def speak(text: str):
    from app.tts.tts_engine import text_to_speech, play_audio
    print(f"\n[TTS] Speaking: {text}")
    audio_file = await text_to_speech(text)
    await play_audio(audio_file)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 55)
    print("  Nova STT Quick Test  (Ctrl+C to quit)")
    print("=" * 55)

    while True:
        try:
            input("\nPress ENTER to record, Ctrl+C to quit...")
        except KeyboardInterrupt:
            print("\nBye!")
            break

        # 1. Record
        try:
            record_mic(SPEECH_WAV, RECORD_SECONDS)
        except Exception as exc:
            print(f"[ERROR] Recording failed: {exc}")
            continue

        # 2. Transcribe
        try:
            text = transcribe(SPEECH_WAV)
        except FileNotFoundError as exc:
            print(f"\n[ERROR] {exc}")
            break
        except Exception as exc:
            print(f"[ERROR] Transcription failed: {exc}")
            continue

        print(f"\n  Heard: {text}")

        if not text.strip():
            print("  (empty — nothing detected)")
            continue

        # 3. Speak back
        if SPEAK_BACK:
            try:
                asyncio.run(speak(text))
            except Exception as exc:
                print(f"[TTS] Skipped (error: {exc})")


if __name__ == "__main__":
    main()
