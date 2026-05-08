import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor

import edge_tts
import pygame
import soundfile as sf
from kokoro_onnx import Kokoro
from pydub import AudioSegment

from config.config import AUDIO_PATH

executor = ThreadPoolExecutor()
music_paused = False
music_playing = False

# Load Kokoro once at module import.
kokoro = Kokoro("models/tts/kokoro-v1.0.fp16-gpu.onnx", "models/tts/voices-v1.0.bin")

# Init the SDL mixer ONCE — re-initializing on every play wastes ~50ms per turn.
pygame.mixer.init()

EMOTIONS = {
    "friendly": {"voice": "af_heart", "speed": 1.1},
    "excited": {"voice": "af_sky", "speed": 1.3},
    "calm": {"voice": "af_heart", "speed": 0.85},
    "sad": {"voice": "af_heart", "speed": 0.75},
    "cheerful": {"voice": "af_sky", "speed": 1.2},
    "serious": {"voice": "am_adam", "speed": 0.9},
    "assistant": {"voice": "af_heart", "speed": 1.0},
}


def is_nepali(text):
    return any("ऀ" <= c <= "ॿ" for c in text)


# ─── PLAYBACK ───────────────────────────────────────────────


def _play_blocking(path):
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.05)
    pygame.mixer.music.unload()
    print("Done playing!")


def wait_for_file(path):
    print("Waiting for file...")
    while not os.path.exists(path) or os.path.getsize(path) < 1000:
        time.sleep(0.1)
    print("File ready!")


async def play_audio(path=AUDIO_PATH):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(executor, _play_blocking, path)


def _tts_blocking(text, emotion, out_path):
    return asyncio.run(_tts_async(text, emotion, out_path))


async def _tts_async(text, emotion, out_path):
    temp_file = os.path.splitext(out_path)[0] + "_temp.mp3"
    if is_nepali(text):
        tts = edge_tts.Communicate(
            text, voice="ne-NP-HemkalaNeural", rate="+10%", pitch="+5Hz", volume="+20%"
        )
        await tts.save(temp_file)
        audio = AudioSegment.from_file(temp_file)
        audio = audio.set_frame_rate(24000).set_sample_width(2).set_channels(1)
        audio.export(out_path, format="wav", codec="pcm_s16le")
    else:
        style = EMOTIONS.get(emotion, EMOTIONS["sad"])
        samples, sr = kokoro.create(
            text, voice=style["voice"], speed=style["speed"], lang="en-us"
        )
        sf.write(out_path, samples, sr)


async def text_to_speech(text, emotion="sad", out_path=None):
    out_path = out_path or AUDIO_PATH
    print(f"Generating speech → {out_path}")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, _tts_blocking, text, emotion, out_path)
    return out_path


# ─── MUSIC CONTROLS ─────────────────────────────────────────


def pause_music():
    global music_paused
    if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
        pygame.mixer.music.pause()
        music_paused = True
        print("Music paused!")
    else:
        print("Nothing playing to pause!")


def resume_music():
    global music_paused
    if pygame.mixer.get_init() and music_paused:
        pygame.mixer.music.unpause()
        music_paused = False
        print("Music resumed!")
    else:
        print(f"Cannot resume! init={pygame.mixer.get_init()}, paused={music_paused}")


def stop_music():
    global music_paused, music_playing
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        music_paused = False
        music_playing = False
        print("Music stopped!")
    else:
        print("Nothing to stop!")
