import asyncio
import json

import webrtcvad
import websockets

from VAD_Detection import detect_speech

CHUNK_SIZE = 1024 # Larger chunks are more efficient for Wi-Fi
  # For testing streaming to ESP32
ws = None
clients = set()
RATE = 24000
FRAME_MS = 20
FRAME_SIZE = int(RATE * FRAME_MS / 1000)

vad = webrtcvad.Vad(3)

VOLUME_THRESHOLD = 600
SPEECH_CONFIRM_FRAMES = 5
SILENCE_LIMIT = int(2000 / FRAME_MS)

async def handle_client(websocket):
    global ws
    ws = websocket
    clients.add(websocket)

    print("ESP32 connected!")
    print(f"Total clients: {len(clients)}")

    try:
     
        async for message in websocket:
            if(message == "play_test"):
                  await stream_audio()
            if(message == "Hello from ESP"):
                    print("Received greeting from ESP!")
            # process incoming audio frames
            
            if isinstance(message, bytes):
                 await detect_speech(message)

    except websockets.exceptions.ConnectionClosed:
        print("ESP disconnected")

    finally:
        clients.discard(websocket)


async def send_websocket_message(websocket, message):
    try:
        await websocket.send(json.dumps(message))
        print(f"Sent: {message}")
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected while sending!")


async def broadcast(data):
    for client in clients:
        try:
            print(f"Broadcasting to {client.remote_address}: {data}")
            await client.send(json.dumps(data))
        except websockets.exceptions.ConnectionClosed:
            clients.discard(client)  
            print("Removed disconnected client!")


# def save_wav(audio_bytes, filename="received_audio.wav"):
#     with wave.open(filename, "wb") as wf:
#         wf.setnchannels(CHANNELS)
#         wf.setsampwidth(SAMPLE_WIDTH)
#         wf.setframerate(SAMPLE_RATE)
#         wf.writeframes(audio_bytes)
#     print(f"Audio saved → {filename}")

def get_WSconnection():
    return ws


async def stream_audio(AUDIO_FILE="response.wav"):
    websocket = get_WSconnection()
    print("▶ Streaming audio...")

    # Tell ESP to start playback
    await websocket.send("audio_start")

    with open(AUDIO_FILE, "rb") as f:
        # 🔥 Skip WAV header (44 bytes)
        f.seek(44)

        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            
            if len(chunk) % 2 != 0:
               chunk += b'\x00'

            await websocket.send(chunk)
            await asyncio.sleep(0.01)  # correct pacing

    # Tell ESP playback finished
    await asyncio.sleep(2)  # correct pacing
    await websocket.send("audio_end")
    print("✅ Audio finished")
    await websocket.send("start_stream")  # trigger test playback on ESP


async def stream_music(AUDIO_FILE="song.wav"):
    websocket = get_WSconnection()
    print("▶ Streaming audio...")

    # Tell ESP to start playback
    await websocket.send("audio_start")

    with open(AUDIO_FILE, "rb") as f:
        # 🔥 Skip WAV header (44 bytes)
        f.seek(44)

        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            
            if len(chunk) % 2 != 0:
               chunk += b'\x00'

            await websocket.send(chunk)
            await asyncio.sleep(0.01)  # correct pacing

    # Tell ESP playback finished
    await asyncio.sleep(2)  # correct pacing
    await websocket.send("audio_end")
    print("song finished")
   

