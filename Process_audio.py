

from local_ollama import generate_local_async
from process_transcipt import handle_command
from speech import pause_music, resume_music, stop_music, text_to_speech
from groqLLm import groq_llm_json
# from test.ws_stream_audio import stream_audio
from whisper import transcribe_audio
from yt_music import download_and_play


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
    await text_to_speech(reply)


    # if response['type'] == 'command':
    #     target = response.get('target')
    #     action = response.get('action')

    #     if target == 'music':
    #         if action == 'play':
    #             song = response.get('song', text)
    #             # speak first, then play music!
    #             if reply:
    #                 await text_to_speech(reply)
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
    #         from websocket import broadcast
    #         await broadcast({"type": "command", "payload": result})
    #         # speak confirmation!
    #         if reply:
    #             await text_to_speech(reply)

    # elif response['type'] == 'query':
    #     print(f"Nova says: {reply}")
    #     await text_to_speech(reply)


    from websocket import stream_audio
    await stream_audio()
