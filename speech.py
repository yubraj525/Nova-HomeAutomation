# speech.py — replace text_to_speech with Kokoro!

import os
import time
import pygame
import edge_tts
import asyncio
from concurrent.futures import ThreadPoolExecutor
from kokoro_onnx import Kokoro
import soundfile as sf

executor = ThreadPoolExecutor()
music_paused = False
music_playing = False

# load Kokoro once!
kokoro = Kokoro("kokoro-v1.0.fp16-gpu.onnx", "voices-v1.0.bin")

EMOTIONS = {
    "friendly":  {"voice": "af_heart", "speed": 1.1},
    "excited":   {"voice": "af_sky",   "speed": 1.3},
    "calm":      {"voice": "af_heart", "speed": 0.85},
    "sad":       {"voice": "af_heart", "speed": 0.75},
    "cheerful":  {"voice": "af_sky",   "speed": 1.2},
    "serious":   {"voice": "am_adam",  "speed": 0.9},
    "assistant": {"voice": "af_heart", "speed": 1.0},
}

def is_nepali(text):
    return any('\u0900' <= c <= '\u097F' for c in text)


# ─── PLAYBACK ───────────────────────────────────────────────

def _play_blocking(path):
    global music_playing
    pygame.mixer.init()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    music_playing = True

    while pygame.mixer.music.get_busy():
        time.sleep(0.1)

    pygame.mixer.music.unload()
    pygame.mixer.quit()
    music_playing = False
    print("Done playing!")

async def play_audio(path):
    print("Playing audio...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, _play_blocking, path)


# ─── TTS ────────────────────────────────────────────────────

def _tts_blocking(text, emotion="sad"):
    asyncio.run(_tts_async(text, emotion))

async def _tts_async(text, emotion="sad"):
    if is_nepali(text):
        # edge-tts for Nepali
        tts = edge_tts.Communicate(
            text,
            voice="ne-NP-HemkalaNeural",
            rate="+10%",
            pitch="+5Hz",
            volume="+20%"
        )
        await tts.save("response.wav")
        # //this is to play in server side, not on client!
        # _play_blocking("response.wav")
        # time.sleep(0.2)
        # if os.path.exists("response.wav"):
        #     os.remove("response.wav")
    else:
        # Kokoro for English — natural!
        style = EMOTIONS.get(emotion, EMOTIONS["sad"])
        samples, sr = kokoro.create(
            text,
            voice=style["voice"],
            speed=style["speed"],
            lang="en-us"
        )
        sf.write("response.wav", samples, sr)
        # _play_blocking("response.wav")
        # time.sleep(0.2)
        # if os.path.exists("response.wav"):
        #     os.remove("response.wav")

async def text_to_speech(text, emotion="sad"):
    print("Generating speech...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, _tts_blocking, text, emotion)


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
        pygame.mixer.quit()
        music_paused = False
        music_playing = False
        print("Music stopped!")
    else:
        print("Nothing to stop!")

# async def test_tts():
#      await text_to_speech("Hello! I am Nova, your personal assistant. How can I help you today?")

# if __name__ == "__main__":
#     asyncio.run(test_tts())    