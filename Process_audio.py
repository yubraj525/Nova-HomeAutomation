
from process_transcipt import handle_command
from whisper import transcribe_audio
from speech import text_to_speech,pause_music,resume_music,stop_music
from local_ollama import generate_local_async
from groqLLm import groqLLM
from yt_music import download_and_play
from response import generate_response_from_text

import wave

async def process_audio():
    text = transcribe_audio()
    print(f"Transcribed text: {text}")
    if not text or len(text.strip()) < 2:
        print("Empty or invalid transcription — skipping!")
        return
    
    response = await groqLLM(text)
    print(f"Parsed response: {response}")

    reply = response.get('response', '')  # get reply for all cases!
    print(f"Nova says: {reply}")

    if response['type'] == 'command':
        target = response.get('target')
        action = response.get('action')

        if target == 'music':
            if action == 'play':
                song = response.get('song', text)
                # speak first, then play music!
                if reply:
                    await text_to_speech(reply)
                print(f"Playing: {song}")
                await download_and_play(song)

            elif action == 'pause':
                pause_music()
                if reply:
                    await text_to_speech(reply)

            elif action == 'resume':
                resume_music()
                if reply:
                    await text_to_speech(reply)

            elif action == 'stop':
                stop_music()
                if reply:
                    await text_to_speech(reply)

        else:
            # light, fan etc
            result = handle_command(response)
            from websocket import broadcast
            await broadcast({"type": "command", "payload": result})
            # speak confirmation!
            if reply:
                await text_to_speech(reply)

    elif response['type'] == 'query':
        print(f"Nova says: {reply}")
        await text_to_speech(reply)
