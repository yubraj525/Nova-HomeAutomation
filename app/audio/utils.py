
import wave
from pathlib import Path


def save_audio(audio, filename="data/output_audio/speech.wav"):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(audio)
    print(f"Saved {path}")
    return path
