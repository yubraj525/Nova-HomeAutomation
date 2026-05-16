"""
download_tts_model.py - Download sherpa-onnx-ready Piper ne_NP TTS model
=========================================================================
Downloads the pre-packaged tarball from sherpa-onnx GitHub releases into
models/tts/.  These tarballs have the correct ONNX metadata that plain
Piper HuggingFace files lack.

After extraction the layout is:
  models/tts/
    vits-piper-ne_NP-google-medium/
      model.onnx
      tokens.txt
      espeak-ng-data/

Run:
    python scripts/download_tts_model.py
    python scripts/download_tts_model.py --model x_low
    python scripts/download_tts_model.py --model chitwan   # different voice
"""
from __future__ import annotations

import argparse
import sys
import tarfile
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Model catalogue  (all from sherpa-onnx GitHub releases)
# ---------------------------------------------------------------------------
_BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models"

MODELS: dict[str, dict] = {
    "medium": {
        "tarball":    "vits-piper-ne_NP-google-medium.tar.bz2",
        "dir_name":   "vits-piper-ne_NP-google-medium",
        "size_mb":    63,
        "desc":       "Google ne_NP medium (best quality)",
    },
    "medium-int8": {
        "tarball":    "vits-piper-ne_NP-google-medium-int8.tar.bz2",
        "dir_name":   "vits-piper-ne_NP-google-medium-int8",
        "size_mb":    17,
        "desc":       "Google ne_NP medium INT8 quantized (smaller, nearly same quality)",
    },
    "x_low": {
        "tarball":    "vits-piper-ne_NP-google-x_low.tar.bz2",
        "dir_name":   "vits-piper-ne_NP-google-x_low",
        "size_mb":    7,
        "desc":       "Google ne_NP x_low (fastest, smallest, great for Pi)",
    },
    "chitwan": {
        "tarball":    "vits-piper-ne_NP-chitwan-medium.tar.bz2",
        "dir_name":   "vits-piper-ne_NP-chitwan-medium",
        "size_mb":    63,
        "desc":       "Chitwan ne_NP medium (alternative voice)",
    },
}

_ROOT      = Path(__file__).resolve().parent.parent
_MODEL_DIR = _ROOT / "models" / "tts"


# ---------------------------------------------------------------------------

def _progress(count: int, block: int, total: int) -> None:
    done = count * block
    if total > 0:
        pct = min(done * 100 // total, 100)
        bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
        mb  = done / 1_048_576
        print(f"\r  [{bar}] {pct:3d}%  {mb:.1f} MB", end="", flush=True)


def _download_tarball(url: str, dest: Path) -> None:
    print(f"  URL: {url}")
    try:
        urllib.request.urlretrieve(url, dest, _progress)
        print()
    except Exception as exc:
        print(f"\n  ERROR downloading: {exc}")
        if dest.exists():
            dest.unlink()
        sys.exit(1)


def download_model(quality: str = "medium") -> Path:
    if quality not in MODELS:
        print(f"Unknown model '{quality}'. Available: {list(MODELS)}")
        sys.exit(1)

    info     = MODELS[quality]
    tarball  = info["tarball"]
    dir_name = info["dir_name"]

    _MODEL_DIR.mkdir(parents=True, exist_ok=True)

    dest_dir = _MODEL_DIR / dir_name
    tar_path = _MODEL_DIR / tarball

    # Check if already extracted
    if model_file.exists() and model_file.stat().st_size > 100_000:
        print(f"Model already exists: {dest_dir}")
        print("  (delete the folder to re-download)")
        return dest_dir

    # Download
    print(f"\nDownloading {info['desc']}  (~{info['size_mb']} MB):")
    _download_tarball(f"{_BASE}/{tarball}", tar_path)

    # Extract
    print(f"  Extracting {tarball} ...")
    try:
        with tarfile.open(tar_path, "r:bz2") as tf:
            tf.extractall(_MODEL_DIR)
        tar_path.unlink()   # remove tarball to save space
        print(f"  Extracted to: {dest_dir}")
    except Exception as exc:
        print(f"  ERROR extracting: {exc}")
        sys.exit(1)

    # Validate — model file may be named model.onnx or ne_NP-*.onnx
    onnx_files = list(dest_dir.glob("*.onnx"))
    if not onnx_files:
        print(f"ERROR: no .onnx file found inside {dest_dir}")
        sys.exit(1)

    print(f"\nModel ready at: {dest_dir}")
    print(f"  ONNX: {onnx_files[0].name}")
    print("  Test with:  python scripts/test_sherpa_tts.py")
    return dest_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download sherpa-onnx Nepali TTS model")
    parser.add_argument(
        "--model",
        choices=list(MODELS),
        default="medium-int8",
        help=(
            "Model to download (default: medium-int8, ~17 MB). "
            "Options: medium(63MB) medium-int8(17MB) x_low(7MB) chitwan(63MB)"
        ),
    )
    args = parser.parse_args()
    download_model(args.model)
