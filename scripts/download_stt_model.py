"""
Download the sherpa-onnx Whisper tiny-multilingual ONNX model for offline Nepali STT.

Model: sherpa-onnx-whisper-tiny (multilingual)
Size: ~140 MB total (encoder ~40 MB + decoder ~100 MB)
Supports: 99 languages including Nepali (ne)
Source: https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models

Run from project root:
    python scripts/download_stt_model.py

Files are saved to: models/sherpa/whisper-tiny/
"""

import os
import sys
import tarfile
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODEL_NAME = "sherpa-onnx-whisper-tiny"
RELEASE_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    f"{MODEL_NAME}.tar.bz2"
)
DEST_DIR = Path(__file__).resolve().parent.parent / "models" / "sherpa"
ARCHIVE_PATH = DEST_DIR / f"{MODEL_NAME}.tar.bz2"
MODEL_DIR = DEST_DIR / MODEL_NAME

EXPECTED_FILES = [
    "tiny-encoder.int8.onnx",
    "tiny-decoder.int8.onnx",
    "tiny-tokens.txt",
]


def download_with_progress(url: str, dest: Path) -> None:
    """Download with a simple ASCII progress bar."""
    # Force UTF-8 on stdout so Windows CP doesn't choke on special chars
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print(f"Downloading: {url}")
    print(f"         to: {dest}")
    sys.stdout.flush()

    def _reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(downloaded / total_size * 100, 100)
            bar_len = 40
            filled = int(bar_len * pct / 100)
            bar = "#" * filled + "." * (bar_len - filled)
            mb_dl = downloaded / 1_048_576
            mb_tot = total_size / 1_048_576
            sys.stdout.write(f"\r  [{bar}] {pct:5.1f}%  {mb_dl:.1f}/{mb_tot:.1f} MB")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, dest, reporthook=_reporthook)
    sys.stdout.write("\n")
    sys.stdout.flush()


def extract_archive(archive: Path, dest: Path) -> None:
    print(f"Extracting {archive.name} …")
    with tarfile.open(archive, "r:bz2") as tf:
        tf.extractall(dest)
    print(f"Extracted to {dest}")


def verify_model(model_dir: Path) -> bool:
    """Check all expected files exist and are non-empty."""
    ok = True
    for fname in EXPECTED_FILES:
        fpath = model_dir / fname
        if not fpath.exists():
            print(f"  ✗ Missing: {fpath}")
            ok = False
        elif fpath.stat().st_size < 1000:
            print(f"  ✗ Looks empty: {fpath} ({fpath.stat().st_size} bytes)")
            ok = False
        else:
            size_mb = fpath.stat().st_size / 1_048_576
            print(f"  ✓ {fname}  ({size_mb:.1f} MB)")
    return ok


def main():
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Already downloaded?
    # ------------------------------------------------------------------
    if MODEL_DIR.exists() and any(MODEL_DIR.iterdir()):
        print(f"\n✅ Model already present at: {MODEL_DIR}")
        print("   Verifying files …")
        if verify_model(MODEL_DIR):
            print("\nAll good — skipping download.")
            return
        else:
            print("\nModel directory incomplete, re-downloading …")

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------
    if not ARCHIVE_PATH.exists():
        try:
            download_with_progress(RELEASE_URL, ARCHIVE_PATH)
        except Exception as exc:
            print(f"\n❌ Download failed: {exc}", file=sys.stderr)
            print(
                "   Check your internet connection or manually download from:\n"
                f"   {RELEASE_URL}",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        print(f"Archive already downloaded: {ARCHIVE_PATH}")

    # ------------------------------------------------------------------
    # Extract
    # ------------------------------------------------------------------
    try:
        extract_archive(ARCHIVE_PATH, DEST_DIR)
    except Exception as exc:
        print(f"\n❌ Extraction failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------
    print("\nVerifying extracted files …")
    if verify_model(MODEL_DIR):
        print(f"\n✅ Model ready at: {MODEL_DIR}")
        # Clean up the tarball to save space
        ARCHIVE_PATH.unlink(missing_ok=True)
        print("   (archive deleted to save disk space)")
    else:
        print("\n❌ Verification failed — check the files above.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
