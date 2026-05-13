"""
speak_test.py — pass any Nepali / English / Nepanglish text and hear it.

Usage:
    venv\Scripts\python.exe scripts\speak_test.py

Or import the function anywhere:
    from scripts.speak_test import speak
    speak("का छ खबर हजुर को?")
"""

import sys, os, io, asyncio

# Windows UTF-8 fix
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add project root so imports work
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from app.tts.tts_engine import text_to_speech, play_audio


# ─────────────────────────────────────────────
# THE FUNCTION YOU ASKED FOR
# ─────────────────────────────────────────────
async def speak_async(text: str, emotion: str = "assistant"):
    """Generate TTS for *text* and play it immediately."""
    print(f"\n[Nova speaks] {text}")
    audio_file = await text_to_speech(text, emotion)
    await play_audio(audio_file)


def speak(text: str, emotion: str = "assistant"):
    """
    Synchronous wrapper — call this from anywhere, no async needed.

    speak("का छ खबर हजुर को? खाना खानु भो?")
    speak("Hello, I am Nova.")
    speak("यो robot को speed बढाउ।")
    """
    asyncio.run(speak_async(text, emotion))


# ─────────────────────────────────────────────
# DEMO — runs when you execute this file
# ─────────────────────────────────────────────
if __name__ == "__main__":
    demos = [
        # Natural conversational Nepali
        ("का छ खबर हजुर को?",                              "assistant"),
        ("खाना खानु भो? राम्रोसँग खानुस् है।",              "friendly"),
        ("आज मौसम एकदमै राम्रो छ, हैन र?",               "cheerful"),
        ("म नोवा हुँ, तपाईंको सहायक।",                    "assistant"),
        # Nepanglish
        ("तपाईंको room को light off गर्दिन् है?",          "assistant"),
        ("Robot को speed थोडा बढाउनु पर्ला।",              "serious"),
        # Pure English
        ("Good morning! How can I help you today?",        "friendly"),
    ]

    for text, emotion in demos:
        speak(text, emotion)

