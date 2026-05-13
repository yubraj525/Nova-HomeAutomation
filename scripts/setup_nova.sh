#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ ! -d venv ]]; then
  echo "[1/5] Creating virtual environment"
  python -m venv venv
fi

if [[ -f venv/Scripts/activate ]]; then
  # Windows venv from Git Bash / MSYS
  # shellcheck disable=SC1091
  source venv/Scripts/activate
elif [[ -f venv/bin/activate ]]; then
  # Unix-style venv
  # shellcheck disable=SC1091
  source venv/bin/activate
else
  echo "Could not find a virtual environment activation script."
  exit 1
fi

echo "[2/5] Upgrading pip tooling"
python -m pip install --upgrade pip setuptools wheel

echo "[3/5] Installing Python requirements"
python -m pip install -r requirements.txt

echo "[4/5] Downloading sherpa STT model"
python scripts/download_stt_model.py

echo "[5/5] Preparing Kokoro assets"
mkdir -p models

if [[ -s models/kokoro-v1.0.int8.onnx ]]; then
  echo "  ok  models/kokoro-v1.0.int8.onnx already present"
else
  if [[ -s kokoro-v1.0.fp16-gpu.onnx ]]; then
    cp kokoro-v1.0.fp16-gpu.onnx models/kokoro-v1.0.int8.onnx
    echo "  copied  kokoro-v1.0.fp16-gpu.onnx -> models/kokoro-v1.0.int8.onnx"
  else
    echo "  missing  Kokoro model file"
    echo "  expected: models/kokoro-v1.0.int8.onnx"
  fi
fi

if [[ -s models/voices-v1.0.bin ]]; then
  echo "  ok  models/voices-v1.0.bin already present"
else
  if [[ -s voices-v1.0.bin ]]; then
    cp voices-v1.0.bin models/voices-v1.0.bin
    echo "  copied  voices-v1.0.bin -> models/voices-v1.0.bin"
  else
    echo "  missing  Kokoro voices file"
    echo "  expected: models/voices-v1.0.bin"
  fi
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "  warning: ffmpeg is not installed or not on PATH"
  if command -v winget >/dev/null 2>&1; then
    echo "  trying: winget install --id Gyan.FFmpeg -e"
    winget install --id Gyan.FFmpeg -e --source winget || true
  fi
else
  echo "  ok  ffmpeg found"
fi

if command -v yt-dlp >/dev/null 2>&1; then
  echo "  ok  yt-dlp found"
else
  echo "  warning: yt-dlp command not found even after pip install"
fi

echo
if [[ -z "${GROQ:-}" && -z "${GROQ_API_KEY:-}" ]]; then
  echo "GROQ is not set yet. Add it to .env before running the assistant."
fi

echo "Setup complete."
