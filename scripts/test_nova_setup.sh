#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT_DIR
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

missing=0

echo "[1/5] Checking required model files"
required_files=(
  "models/kokoro-v1.0.int8.onnx"
  "models/voices-v1.0.bin"
  "models/sherpa/sherpa-onnx-whisper-tiny/tiny-encoder.int8.onnx"
  "models/sherpa/sherpa-onnx-whisper-tiny/tiny-decoder.int8.onnx"
  "models/sherpa/sherpa-onnx-whisper-tiny/tiny-tokens.txt"
)

for file in "${required_files[@]}"; do
  if [[ -s "$file" ]]; then
    echo "  ok  $file"
  else
    echo "  missing  $file"
    missing=1
  fi
done

echo
echo "[2/5] Checking local Python imports"
if ! python - <<'PY'
import importlib
import sys

modules = [
    "edge_tts",
    "fastapi",
    "groq",
    "kokoro_onnx",
    "numpy",
    "ollama",
    "openwakeword",
    "pyaudio",
    "pydub",
    "pygame",
    "scipy",
    "sherpa_onnx",
    "sounddevice",
    "soundfile",
    "uvicorn",
    "webrtcvad",
    "websockets",
    "yt_dlp",
]

failed = []
for module in modules:
    try:
        importlib.import_module(module)
        print(f"  ok  {module}")
    except Exception as exc:
        failed.append((module, exc))
        print(f"  missing  {module}: {exc}")

if failed:
    sys.exit(1)
PY
then
  missing=1
fi

echo
echo "[3/5] Testing Kokoro TTS model load"
if ! python - <<'PY'
import os
from pathlib import Path

from kokoro_onnx import Kokoro

root = Path(os.environ["ROOT_DIR"])
model = root / "models" / "kokoro-v1.0.int8.onnx"
voices = root / "models" / "voices-v1.0.bin"

kokoro = Kokoro(str(model), str(voices))
samples, sample_rate = kokoro.create("Nova setup test", voice="af_heart", speed=1.0, lang="en-us")
print(f"  ok  Kokoro loaded: {len(samples)} samples @ {sample_rate} Hz")
PY
then
  missing=1
fi

echo
echo "[4/5] Testing offline Sherpa STT model"
if ! python - <<'PY'
import math
import os
import struct
import tempfile
import wave
from pathlib import Path

from app.stt.sherpa_stt import _check_model, transcribe_audio_offline

root = Path(os.environ["ROOT_DIR"])
model_dir = root / "models" / "sherpa" / "sherpa-onnx-whisper-tiny"

if not _check_model():
    raise SystemExit(f"Sherpa model missing or incomplete at: {model_dir}")

with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
    tmp_path = Path(tmp.name)

try:
    with wave.open(str(tmp_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        for i in range(16000):
            value = int(8000 * math.sin(2 * math.pi * 220 * i / 16000))
            wf.writeframesraw(struct.pack("<h", value))

    text = transcribe_audio_offline(str(tmp_path))
    print(f"  ok  Sherpa transcription returned: {text!r}")
finally:
    tmp_path.unlink(missing_ok=True)
PY
then
  missing=1
fi

echo
echo "[5/5] Testing Groq API and command-line tools"
if ! python - <<'PY'
import os

from groq import Groq

api_key = os.getenv("GROQ") or os.getenv("GROQ_API_KEY")
if not api_key:
    raise SystemExit("Set GROQ in your environment or .env file before running this script.")

client = Groq(api_key=api_key)
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": "Reply with OK only."}],
    temperature=0,
    max_completion_tokens=8,
)

message = response.choices[0].message.content.strip()
print(f"  ok  Groq responded with: {message!r}")
PY
then
  missing=1
fi

if command -v ffmpeg >/dev/null 2>&1; then
  echo "  ok  ffmpeg found"
else
  echo "  missing  ffmpeg"
  missing=1
fi

if command -v yt-dlp >/dev/null 2>&1; then
  echo "  ok  yt-dlp found"
else
  echo "  missing  yt-dlp"
  missing=1
fi

echo
if [[ "$missing" -ne 0 ]]; then
  echo "Setup check failed. Fix the missing files or tools above and run again."
  exit 1
fi

echo "Setup check passed."