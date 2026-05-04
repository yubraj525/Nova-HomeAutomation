

from email.mime import text

from app.llm.ollama import generate_local_async
from app.pipeline.process_transcript import handle_command
from app.tts.tts_engine import pause_music, play_audio, resume_music, stop_music, text_to_speech
from app.llm.groq import groq_llm_json
# from test.ws_stream_audio import stream_audio
from app.stt.whisper import transcribe_audio
from app.audio.player import download_and_play
# import winsound
import asyncio
import os

async def process_audio():
    text = transcribe_audio()
    print(f"Transcribed text: {text}")
    if not text or len(text.strip()) < 2:
        print("Empty or invalid transcription — skipping!")
        return
    
    response = await groq_llm_json(text)
    print(f"Parsed response: {response}")
           

    reply = response.get('response', '')  # get reply for all cases!
    print(f"Nova says: {reply}")
    file = await text_to_speech(reply)
    # await wait_until_stable(file)
    await play_audio(file)
    print("Audio playback finished, processing command...")
    from app.communication.websocket import get_WSconnection
    ws = get_WSconnection()
    ws.send("start_stream")  # trigger next steps on ESP after audio done

    # if response['type'] == 'command':
    #     target = response.get('target')
    #     action = response.get('action')

    #     if target == 'music':
    #         if action == 'play':
    #             song = response.get('song', text)
    #             # speak first, then play music!
                
    #             print(f"Playing: {song}")
    #             await download_and_play(song)

    #         elif action == 'pause':
    #             pause_music()
    #             if reply:
    #                 await text_to_speech(reply)

    #         elif action == 'resume':
    #             resume_music()
    #             if reply:
    #                 await text_to_speech(reply)

    #         elif action == 'stop':
    #             stop_music()
    #             if reply:
    #                 await text_to_speech(reply)

    #     else:
    #         # light, fan etc
    #         result = handle_command(response)
    #         from app.communication.websocket import broadcast
    #         await broadcast({"type": "command", "payload": result})
    #         # speak confirmation!
    #         if reply:
    #             await text_to_speech(reply)

    # elif response['type'] == 'query':
    #     print(f"Nova says: {reply}")
    #     await text_to_speech(reply)


    
