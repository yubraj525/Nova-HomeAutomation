"""
speak_test.py — Quick REPL for testing Nepanglish TTS
=======================================================
Run from project root:
    python scripts/speak_test.py

Make sure you've downloaded the model first:
    python scripts/download_tts_model.py
"""
import sys
import logging
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

from app.tts.nepanglish_tts import speak, transliterate_mixed, get_synthesizer

DEMO_SENTENCES = [
    "नमस्ते, मेरो नाम नोवा हो।",
    "यो robot को speed बढाउ।",
    "AC अन गर र light off गर।",
    "Hello, how are you doing today?",
    "आज २०२४ साल हो। मसँग 1500 रुपैयाँ छ।",
]

def run_demo():
    print("\n━━━━━━  Nepanglish TTS Demo  ━━━━━━")
    synth = get_synthesizer()  # pre-load model once
    for sent in DEMO_SENTENCES:
        print(f"\n▶  {sent}")
        speak(sent)
        print("   done.")

def run_repl():
    print("\n━━━━━━  Nepanglish TTS REPL  ━━━━━━")
    print("Type a sentence → hear it.  'demo' → run samples.  'quit' → exit.\n")
    print("Slash commands:  /tr <text>  (show transliteration only)\n")

    synth = get_synthesizer()  # pre-load model once

    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not line:
            continue
        if line in ("quit", "q", "exit"):
            break
        if line == "demo":
            run_demo()
            continue
        if line.startswith("/tr "):
            print(" →", transliterate_mixed(line[4:]))
            continue

        speak(line)

if __name__ == "__main__":
    if "--demo" in sys.argv:
        run_demo()
    else:
        run_repl()
