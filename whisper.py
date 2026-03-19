from faster_whisper import WhisperModel

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


# def transcribe_audio():
#     print("Transcribing")
#     whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
#     segments, _ = whisper_model.transcribe("speech.wav", language="en")
#     text = " ".join([seg.text for seg in segments])
#     return text


client = Groq(api_key=os.getenv("GROQ"))


def transcribe_audio(filepath="speech.wav"):
    print("Transcribing...")
    with open(filepath, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3",  # or "whisper-large-v3-turbo" (faster)
            file=audio_file,
            # language="ne",
        )
    text = transcription.text
    print(f"Transcribed: {text}")
    return text

