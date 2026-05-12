import asyncio
import os
from app.llm.ollama import generate_local_async
from app.pipeline.process_transcript import handle_command
from app.tts.tts_engine import pause_music,play_audio, resume_music, stop_music, text_to_speech
from app.llm.groq import groq_llm_json
from app.stt.whisper import transcribe_audio
from app.audio.player import download_and_play

async def process_audio():
    text = transcribe_audio()
    print(f"Transcribed text: {text}")
    if not text or len(text.strip()) < 2:
        print("Empty or invalid transcription — skipping!")
        return
    
    response = await groq_llm_json(text)
    print(f"Parsed response: {response}")
           
    # 1. Speak the response if present
    reply = response.get('response', '')
    if reply.strip():
        print(f"Nova says: {reply}")
        file = await text_to_speech(reply)
        await play_audio(file)
    
    # 2. Handle commands (Music, Lights, etc.)
    if response.get('type') == 'command':
        target = response.get('target')
        action = response.get('action')

        if target == 'music':
            if action == 'play':
                song = response.get('song', text)
                print(f"Playing music: {song}")
                asyncio.create_task(download_and_play(song)) # Run in background so pipeline can finish
            elif action == 'pause':
                pause_music()
            elif action == 'resume':
                resume_music()
            elif action == 'stop':
                stop_music()
        else:
            # Device commands (lights, etc.)
            result = handle_command(response)
            try:
                from app.communication.websocket import broadcast
                await broadcast({"type": "command", "payload": result})
            except Exception as e:
                print(f"Error broadcasting command: {e}")

    # 3. Speak the follow-up/convo if present
    # convo_reply = response.get('convo', '')
    # if convo_reply.strip():
    #     print(f"Nova asks: {convo_reply}")
    #     file = await text_to_speech(convo_reply)
    #     await play_audio(file)

    print("Pipeline finished, triggering next steps...")
    try:
        from app.communication.websocket import send_websocket_message
        await send_websocket_message("start_stream")
    except Exception as e:
        print(f"Error sending start_stream: {e}")
