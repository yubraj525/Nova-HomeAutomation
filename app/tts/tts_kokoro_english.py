import time
import queue
import threading
import sounddevice as sd
from kokoro_onnx import Kokoro

# =========================================================
# MODEL INIT (ONCE ONLY)
# =========================================================

kokoro = Kokoro(
    "C:/Users/yubra/OneDrive/Documents/Development/Voice-assitance-py/models/kokoro-v1.0.int8.onnx",
    "C:/Users/yubra/OneDrive/Documents/Development/Voice-assitance-py/models/voices-v1.0.bin"
)

# =========================================================
# CONFIG
# =========================================================

VOICE = "af_sky"
SPEED = 1.1
LANG = "en-us"

audio_queue = queue.Queue()

# =========================================================
# CHUNK TEXT
# =========================================================

def chunk_text(text):
    separators = [".", "?", "!", ","]

    chunks = []
    current = ""

    for c in text:
        current += c
        if c in separators:
            if current.strip():
                chunks.append(current.strip())
            current = ""

    if current.strip():
        chunks.append(current.strip())

    return chunks

# =========================================================
# AUDIO PLAYER THREAD (NON-BLOCKING)
# =========================================================

def audio_player():
    while True:
        item = audio_queue.get()
        if item is None:
            break

        samples, sr = item
        sd.play(samples, sr)
        sd.wait()

threading.Thread(target=audio_player, daemon=True).start()

# =========================================================
# STREAMING TTS ENGINE
# =========================================================

def stream_tts(text):
    chunks = chunk_text(text)

    print("Chunks:", chunks)

    start_total = time.time()

    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}: {chunk}")

        start = time.time()

        samples, sr = kokoro.create(
            chunk,              # ✅ FIXED (use chunk not full text)
            voice=VOICE,
            speed=SPEED,
            lang=LANG
        )

        print("Generated in:", round(time.time() - start, 3), "s")

        audio_queue.put((samples, sr))

    print("\nTOTAL TIME:", round(time.time() - start_total, 2), "s")
