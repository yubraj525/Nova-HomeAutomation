import os
from groq import Groq
from dotenv import load_dotenv

# -----------------------------
# INIT
# -----------------------------
load_dotenv()
client = Groq(api_key=os.getenv("GROQ"))
async def generate_speech(text):
    print(f"Generating speech for: {text}")
    speech_file_path = "response.wav" 
    model = "canopylabs/orpheus-v1-english"
    voice = "hannah"
    
    response_format = "wav"

    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=text,
        response_format=response_format
    )
    response.write_to_file(speech_file_path)
    print("reponse saved")
    from websocket import stream_audio
    await stream_audio()
    
# if __name__ == "__main__":
#     import asyncio
#     test_text = "Hello, this is a test of the speech generation system!"
#     asyncio.run(generate_speech(test_text))