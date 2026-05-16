"""
test_sherpa_tts.py  -  Standalone sherpa-onnx 1.13 TTS smoke test
===================================================================
Tests the Piper Nepali ONNX model directly via the sherpa-onnx API.
No dependency on nepanglish_tts.py.

Usage (from project root):
    python scripts/test_sherpa_tts.py
    python scripts/test_sherpa_tts.py --model x_low
    python scripts/test_sherpa_tts.py --no-play       # synthesise only
    python scripts/test_sherpa_tts.py --stream        # streaming callback demo

Download the model first:
    python scripts/download_tts_model.py              # medium-int8 by default
    python scripts/download_tts_model.py --model medium   # full quality
"""
from __future__ import annotations

import argparse
import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODEL_DIR = ROOT / "models" / "tts"
OUT_DIR   = ROOT / "data" / "output_audio"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Model layout  (mirrors download_tts_model.py)
# ---------------------------------------------------------------------------
MODEL_DIRS: dict[str, str] = {
    "medium":     "vits-piper-ne_NP-google-medium",
    "medium-int8":"vits-piper-ne_NP-google-medium-int8",
    "x_low":      "vits-piper-ne_NP-google-x_low",
    "chitwan":    "vits-piper-ne_NP-chitwan-medium",
}

TEST_SENTENCES = [
    ("nepali_greeting",
     "namaste, mero naam nova ho."),           # phonetic Devanagari
    ("nepali_full",
     "namasthe. kasto chha tapai? Ma nova hun."),
    ("mixed_script",
     "yo robot ko speed badhaau. AC on gara ra light off gara."),
    ("numbers",
     "aaja dui hajar chaubis sal ho. masanga pandhra say rupaiyan chha."),
    ("long_sentence",
     "nepali ra angrezi shabdaharu misaera boliene bhasalai prayah neplish bhaninchhha."),
]

# ---------------------------------------------------------------------------

def find_model_dir(quality: str) -> Path:
    dir_name = MODEL_DIRS.get(quality)
    if not dir_name:
        print(f"Unknown model '{quality}'. Choose: {list(MODEL_DIRS)}")
        sys.exit(1)
    return MODEL_DIR / dir_name


def build_tts(model_dir: Path, num_threads: int = 2):
    """Build sherpa_onnx.OfflineTts for the extracted Piper model directory."""
    import sherpa_onnx   # type: ignore

    onnx_files  = list(model_dir.glob("*.onnx"))
    tokens_path = model_dir / "tokens.txt"
    data_dir    = model_dir / "espeak-ng-data"

    if not onnx_files:
        print(f"ERROR: No .onnx file found in {model_dir}")
        print("\nRun:  python scripts/download_tts_model.py")
        sys.exit(1)

    onnx_path = onnx_files[0]   # take the first (only) ONNX in the dir

    print(f"[sherpa-onnx v{sherpa_onnx.__version__}]")
    print(f"  model   : {onnx_path.name}")
    print(f"  tokens  : {tokens_path.name}")
    print(f"  data_dir: {data_dir}")

    vits_cfg = sherpa_onnx.OfflineTtsVitsModelConfig(
        model    = str(onnx_path),
        lexicon  = "",
        tokens   = str(tokens_path),
        data_dir = str(data_dir),
    )

    model_cfg = sherpa_onnx.OfflineTtsModelConfig(
        vits        = vits_cfg,
        provider    = "cpu",
        debug       = False,
        num_threads = num_threads,
    )

    tts_cfg = sherpa_onnx.OfflineTtsConfig(
        model               = model_cfg,
        rule_fsts           = "",
        max_num_sentences   = 1,
    )

    tts = sherpa_onnx.OfflineTts(tts_cfg)
    print(f"  sample_rate : {tts.sample_rate} Hz")
    print(f"  num_speakers: {tts.num_speakers}")
    print()
    return tts


# ---------------------------------------------------------------------------

def synthesize_and_save(tts, label: str, text: str) -> Path:
    out_path = OUT_DIR / f"tts_{label}.wav"

    print(f"  [{label}]")
    print(f"    text: {text}")

    t0    = time.perf_counter()
    audio = tts.generate(text, sid=0, speed=1.0)
    elapsed = time.perf_counter() - t0

    samples = np.array(audio.samples, dtype=np.float32)
    sr      = audio.sample_rate
    pcm     = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm)

    duration = len(samples) / sr
    rtf      = elapsed / duration if duration > 0 else 0.0
    print(f"    -> {out_path.name}  |  {duration:.2f}s audio  |  {elapsed:.2f}s synth  |  RTF={rtf:.3f}")
    return out_path


def play_wav(path: Path) -> None:
    try:
        import sounddevice as sd   # type: ignore
        import soundfile  as sf    # type: ignore
        data, sr = sf.read(str(path), dtype="float32")
        sd.play(data, samplerate=sr, blocking=True)
        return
    except Exception:
        pass
    try:
        import pygame   # type: ignore
        pygame.mixer.init()
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
        pygame.mixer.music.unload()
        pygame.mixer.quit()
    except Exception as exc:
        print(f"    [playback unavailable: {exc}]")


def streaming_demo(tts) -> None:
    """
    Demonstrates the real-time streaming callback (sherpa-onnx 1.10+).
    The callback fires per audio chunk as the model generates, so you can
    pipe chunks to a speaker or WebSocket before synthesis finishes.
    """
    print("\n--- Streaming callback demo ---")
    text   = "namaste. kasto chha? Ma nova hun."
    chunks: list[np.ndarray] = []

    def _on_chunk(samples: np.ndarray, progress: float) -> int:
        chunks.append(np.array(samples, dtype=np.float32))
        print(f"  chunk: {len(samples):6d} samples  progress={progress:.0%}")
        return 0   # returning non-zero cancels generation

    tts.generate(text, sid=0, speed=1.0, callback=_on_chunk)
    total_s = sum(len(c) for c in chunks) / tts.sample_rate
    print(f"  Total: {total_s:.2f}s audio in {len(chunks)} chunks\n")


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="sherpa-onnx 1.13 TTS smoke test")
    ap.add_argument(
        "--model", choices=list(MODEL_DIRS), default="medium-int8",
        help="Model quality (default: medium-int8). Download with download_tts_model.py",
    )
    ap.add_argument("--threads", type=int, default=2,
                    help="CPU inference threads (default 2)")
    ap.add_argument("--no-play",  action="store_true",
                    help="Skip audio playback")
    ap.add_argument("--stream",   action="store_true",
                    help="Run streaming callback demo")
    ap.add_argument("--text",     type=str, default=None,
                    help="Synthesise a single custom text and exit")
    args = ap.parse_args()

    model_dir = find_model_dir(args.model)
    tts       = build_tts(model_dir, num_threads=args.threads)

    # Single custom text mode
    if args.text:
        path = synthesize_and_save(tts, "custom", args.text)
        if not args.no_play:
            play_wav(path)
        return

    # Streaming demo
    if args.stream:
        streaming_demo(tts)

    # Full sentence suite
    print("=" * 60)
    print("Synthesis tests")
    print("=" * 60)

    saved: list[Path] = []
    for label, text in TEST_SENTENCES:
        path = synthesize_and_save(tts, label, text)
        saved.append(path)
        print()

    if not args.no_play:
        print("=" * 60)
        print("Playback")
        print("=" * 60)
        for path in saved:
            print(f"  Playing: {path.name}")
            play_wav(path)
            time.sleep(0.3)

    print(f"\nAll done. WAVs saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
