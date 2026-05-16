import os
import time
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


async def _tts_async(text, emotion="sad"):
    temp_file = "data/output_audio/temp_response.mp3"
    final_file = "data/output_audio/response.wav"

    if is_nepali(text):
        # keep your existing EdgeTTS pipeline unchanged
        tts = edge_tts.Communicate(
            text,
            voice="ne-NP-HemkalaNeural",
            rate="+10%",
            pitch="+5Hz",
            volume="+20%"
        )

        await tts.save(temp_file)

        audio = AudioSegment.from_file(temp_file)
        audio = audio.set_frame_rate(24000).set_sample_width(2).set_channels(1)
        audio.export(final_file, format="wav", codec="pcm_s16le")

    else:
        # ─── GROQ TTS REPLACEMENT ─────────────────────────────
        voice_map = {
            "friendly": "alloy",
            "excited": "verse",
            "calm": "alloy",
            "sad": "verse",
            "cheerful": "verse",
            "serious": "alloy",
            "assistant": "alloy",
        }

        voice = voice_map.get(emotion, "alloy")

        response = client.audio.speech.create(
            model="canopylabs/orpheus-v1-english",
            voice=voice,
            input=text,
            response_format="wav"
        )

        # IMPORTANT: keep SAME output name
        response.write_to_file(final_file)