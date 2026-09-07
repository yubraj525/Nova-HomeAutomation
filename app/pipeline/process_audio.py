# import asyncio
# import os
# from app.audio.queuey import AudioQueue
# from app.llm.ollama import generate_local_async
# from app.pipeline.process_transcript import handle_command
# # from app.tts.tts_engine import pause_music, play_audio, resume_music, stop_music, text_to_speech
# from app.llm.groq import groq_llm_json
# from app.audio.player import download_and_play
# from app.tts.tts_engine import synthesize_to_queue
# from app.tts.tts_kokoro_english import stream_tts


# def _transcribe(audio_path: str = "data/output_audio/speech.wav") -> str:
#     """
#     Try the offline sherpa-onnx Whisper model first (no internet, Nepali-aware).
#     Falls back to Groq cloud Whisper if the local model isn't downloaded yet.
#     """
#     try:
#         from app.stt.whisper import transcribe_audio as transcribe_offline
#         return transcribe_offline(audio_path)
#     except FileNotFoundError:
#         print(
#             "[pipeline] Offline model not found — falling back to Groq cloud.\n"
#             "           Run once: python scripts/download_stt_model.py"
#         )
#         from app.stt.whisper import transcribe_audio as transcribe_cloud
#         return transcribe_cloud(audio_path)


# async def process_audio():
#     text = _transcribe()
#     print(f"Transcribed text: {text}")
#     if not text or len(text.strip()) < 2:
#         print("Empty or invalid transcription — skipping!")
#         return
    
#     response = await groq_llm_json(text)
#     print(f"Parsed response: {response}")
           
#     # 1. Speak the response if present
#     reply = response.get('response', '')
#     if reply.strip():

#         print(f"Nova says: {reply}")
#         file = await synthesize_to_queue(reply, AudioQueue())
#         # await play_audio(file)
#         # stream_tts(reply)
#         from app.communication.websocket import stream_audio
#         await stream_audio()
    
#     # 2. Handle commands (Music, Lights, etc.)
#     # if response.get('type') == 'command':
#     #     target = response.get('target')
#     #     action = response.get('action')

#     #     if target == 'music':
#     #         if action == 'play':
#     #             song = response.get('song', text)
#     #             print(f"Playing music: {song}")
#     #             asyncio.create_task(download_and_play(song)) # Run in background so pipeline can finish
#     #         elif action == 'pause':
#     #             pause_music()
#     #         elif action == 'resume':
#     #             resume_music()
#     #         elif action == 'stop':
#     #             stop_music()
#     #     else:
#     #         # Device commands (lights, etc.)
#     #         result = handle_command(response)
#     #         try:
#     #             from app.communication.websocket import broadcast
#     #             await broadcast({"type": "command", "payload": result})
#     #         except Exception as e:
#     #             print(f"Error broadcasting command: {e}")

#     # # 3. Speak the follow-up/convo if present
#     # convo_reply = response.get('convo', '')
#     # if convo_reply.strip():
#     #     print(f"Nova asks: {convo_reply}")
#     #     file = await text_to_speech(convo_reply)
#     #     await play_audio(file)

#     print("Pipeline finished, triggering next steps...")
#     try:
#         from app.communication.websocket import send_websocket_message
#         await send_websocket_message("start_stream")
#     except Exception as e:
#         print(f"Error sending start_stream: {e}")




# //synchronize the queue join method with the AudioQueue class in queuey.py to ensure proper task completion handling.
import asyncio

from app.audio.queuey import AudioQueue
from app.audio.consumer import consume_audio
from app.audio.transport import AudioTransport

from app.llm.groq import groq_llm_json
from app.tts.tts_engine import synthesize_to_queue

from app.pipeline.process_transcript import handle_command
from app.audio.player import download_and_play


def _transcribe(audio_path: str = "data/output_audio/speech.wav") -> str:
    """
    Try offline Sherpa-ONNX Whisper first.
    Fall back to Groq cloud Whisper if the local model is unavailable.
    """

    try:
        from app.stt.whisper import transcribe_audio as transcribe_offline

        return transcribe_offline(audio_path)

    except FileNotFoundError:
        print(
            "[pipeline] Offline model not found — "
            "falling back to Groq cloud.\n"
            "           Run once: python scripts/download_stt_model.py"
        )

        from app.stt.whisper import transcribe_audio as transcribe_cloud

        return transcribe_cloud(audio_path)


async def process_audio():
    # =========================================================
    # 1. STT
    # =========================================================

    text = _transcribe()

    print(f"Transcribed text: {text}")

    if not text or len(text.strip()) < 2:
        print("Empty or invalid transcription — skipping!")
        return

    # =========================================================
    # 2. LLM
    # =========================================================

    response = await groq_llm_json(text)

    print(f"Parsed response: {response}")

    # =========================================================
    # 3. SPEAK LLM RESPONSE
    # =========================================================

    reply = response.get("response", "")

    if reply.strip():

        print(f"Nova says: {reply}")

        # -----------------------------------------------------
        # Create audio queue
        # -----------------------------------------------------

        queue = AudioQueue()

        # -----------------------------------------------------
        # Create WebSocket transport
        # -----------------------------------------------------

        from app.communication.websocket import get_WSconnection

        websocket = get_WSconnection()

        transport = AudioTransport(websocket)

        # -----------------------------------------------------
        # Start TTS producer
        # -----------------------------------------------------

        producer = asyncio.create_task(
            synthesize_to_queue(
                reply,
                queue,
            )
        )

        # -----------------------------------------------------
        # Start audio consumer
        # -----------------------------------------------------

        consumer = asyncio.create_task(
            consume_audio(
                queue,
                transport,
            )
        )

        # -----------------------------------------------------
        # Wait until TTS has generated everything
        # -----------------------------------------------------

        await producer

        print("[TTS] producer finished")

        # -----------------------------------------------------
        # Wait until every generated chunk has been consumed
        # -----------------------------------------------------

        await queue.join()

        print("[QUEUE] all chunks consumed")

        # -----------------------------------------------------
        # Tell ESP32 playback is finished
        # -----------------------------------------------------

        await transport.end()

        # -----------------------------------------------------
        # Consumer is no longer needed
        # -----------------------------------------------------

        consumer.cancel()

        try:
            await consumer

        except asyncio.CancelledError:
            pass

        print("[AUDIO] playback finished")

    # =========================================================
    # 4. HANDLE COMMANDS
    # =========================================================

    if response.get("type") == "command":

        target = response.get("target")
        action = response.get("action")

        if target == "music":

            if action == "play":

                song = response.get("song", text)

                print(f"Playing music: {song}")

                asyncio.create_task(
                    download_and_play(song)
                )

            elif action == "pause":

                # pause_music()

                pass

            elif action == "resume":

                # resume_music()

                pass

            elif action == "stop":

                # stop_music()

                pass

        else:

            result = handle_command(response)

            try:

                from app.communication.websocket import broadcast

                await broadcast(
                    {
                        "type": "command",
                        "payload": result,
                    }
                )

            except Exception as e:

                print(
                    f"Error broadcasting command: {e}"
                )

    # =========================================================
    # 5. CONVERSATION FOLLOW-UP
    # =========================================================

    convo_reply = response.get("convo", "")

    if convo_reply.strip():

        print(f"Nova asks: {convo_reply}")

        # Later we can send convo_reply through
        # the exact same speak() pipeline.

    # =========================================================
    # 6. TRIGGER ESP32 LISTENING AGAIN
    # =========================================================

    print(
        "Pipeline finished, triggering next steps..."
    )

    try:

        from app.communication.websocket import (
            send_websocket_message
        )

        await send_websocket_message(
            "start_stream"
        )

    except Exception as e:

        print(
            f"Error sending start_stream: {e}"
        )