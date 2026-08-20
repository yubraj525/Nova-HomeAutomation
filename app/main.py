import asyncio

import uvicorn
import websockets
from fastapi import FastAPI
from app.audio.player import download_and_play
from config.config import PORT_API, PORT_WS
from app.communication.websocket import handle_client

# Load model once at startup


app = FastAPI()


@app.get("/api/check")
async def check():
    return {"message": "Nova is alive!"}


@app.get("/api/test")
async def test():
    return {"message": "Nova is alive!"}

#  this is a  oldfer verison of nova in http now moved in ws
# @app.post("/api/audio")
# async def receive_audio(request: Request):
#     # Read raw binary audio from ESP32
#     audio_bytes = await request.body()

#     print(f"Received audio: {len(audio_bytes)} bytes")

#     # Save as WAV file
#     with wave.open("received_audio.wav", "wb") as wf:
#         wf.setnchannels(1)  # mono
#         wf.setsampwidth(2)  # 16-bit = 2 bytes
#         wf.setframerate(16000)  # 16kHz
#         wf.writeframes(audio_bytes)

#     print("Audio saved as received_audio.wav ✅")
#     asyncio.create_task(process_audio())    
#     return JSONResponse(
#         status_code=200, content={"message": "audio received!" }
#     )

# // older version of process_audio, now moved to nova.py for better control flow and access to websocket broadcasting
# async def process_audio():
#         print("Transcribing...")

#         text = transcribe_audio()
#         print(f"Transcribed text: {text}")

#         command_data = match_command(text)
#         print(f"Command data: {command_data}")

#         if command_data['type'] == 'command':
#             target = command_data.get('target')
#             action = command_data.get('action')

#         if target == 'music':
#             if action == 'play':
#                 song = command_data.get('song', '')
#                 print(f"Playing: {song}")
#                 await download_and_play(song)
    
#             elif action == 'pause':
#                 print("Pausing music...")
#                 pause_music()

#             elif action == 'resume':
#                 print("Resuming music...")
#                 resume_music()

#             elif action == 'stop':
#                 print("Stopping music...")
#                 stop_music()

#         else:
#             # light, fan etc
#             print("Executing command...")
#             result = handle_command(command_data)
#             print(f"Command result: {result}")
#             await broadcast({"type": "command", "payload": result})
#         if(command_data['type'] == 'query'):
#          print("Generating response...")
#         # response=await generate_response()
#         # print("Nova says: " +  response)
#         # asyncio.create_task(text_to_speech(response['response']))

# local ai reponse 


async def main():
    # Start WebSocket server
    print("Nova server starting...")
    ws_server = websockets.serve(handle_client, "0.0.0.0", PORT_WS)

    # Start FastAPI server
    api_server = uvicorn.Server(uvicorn.Config(app, host="192.168.1.71", port=PORT_API))


    print(f"WebSocket running on port {PORT_WS}")
    print(f"API running on port {PORT_API}")
    # await download_and_play("never gonna give you up")


    async with ws_server:
        await api_server.serve()



# asyncio.run(play_audio())

asyncio.run(main())


#  ollama run phi4-mini:latest  "do you know about nepal"
