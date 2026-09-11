import asyncio
import json

import webrtcvad
import websockets

from app.vad.vad_detection import detect_speech

CHUNK_SIZE = 512  # Larger chunks are more efficient for Wi-Fi
AUDIO_FILE = "data/output_audio/response.wav"  # For testing streaming to ESP32
ws = None
RATE = 24000
FRAME_MS = 20
FRAME_SIZE = int(RATE * FRAME_MS / 1000)

vad = webrtcvad.Vad(3)

VOLUME_THRESHOLD = 600
SPEECH_CONFIRM_FRAMES = 5
SILENCE_LIMIT = int(2000 / FRAME_MS)

pc_clients = {}     # { "pc_name": websocket_instance }
esp_clients = set()  # Set of ESP websocket instances
clients = set()

async def handle_client(websocket, process_audio):
    clients.add(websocket)
    
    # Assume connection is ESP32 by default
    client_type = "esp"  
    client_name = None

    # Store ESP instance immediately on connection
    esp_clients.add(websocket)
    print(f"[ESP] Connected & Stored Instance (Total ESPs: {len(esp_clients)})")

    try:
        async for message in websocket:

            # -----------------------------------------------------------
            # 1. HANDLE TEXT / JSON MESSAGES
            # -----------------------------------------------------------
            if isinstance(message, str):
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    data = None

                if data and isinstance(data, dict):
                    msg_type = data.get("type")

                    # PC Registration (Explicit type check prevents infinite registration loops)
                    if msg_type == "register" and client_type != "pc":
                        client_type = "pc"
                        client_name = data.get("client_name") or data.get("client_id") or "unknown_pc"

                        # Remove from ESP storage since it's a PC
                        esp_clients.discard(websocket)

                        # Store PC instance
                        pc_clients[client_name] = websocket
                        print(f"[PC] Connected & Registered: {client_name}")

                        # Request tools from PC ONCE upon registration
                        await websocket.send(json.dumps({"type": "request_tools"}))
                        print(f"[PC] Sent 'request_tools' to {client_name}")
                        continue

                    # PC Tools List Response
                    if msg_type == "response_tools":
                        tools = data.get("tools")
                        print(f"\n==================== [PC: {client_name} Tools Registered] ====================")

                        for tool in tools:
                             name = tool.get("name", "Unknown")
                             description = tool.get("description", "No description provided.")
                             params = tool.get("parameters", {}).get("properties", {})
                             required = tool.get("parameters", {}).get("required", [])

                             print(f"\n🛠️  {name}")
                             print(f"   Description: {description}")

                             if params:
                                 param_list = []
                                 for param_name, param_info in params.items():
                                     is_req = "*" if param_name in required else ""
                                     param_type = param_info.get("type", "any")
                                     param_list.append(f"{param_name}{is_req} ({param_type})")

                                 print(f"   Parameters:  {', '.join(param_list)}  [*=required]")

                        print("\n===============================================================================\n")
                        continue
                        

                # Handle simple raw text signals (ESP32)
                if message == "play_test":
                    await stream_audio()
                elif message == "Hello from ESP":
                    print("[ESP] Received greeting from ESP!")

            # -----------------------------------------------------------
            # 2. HANDLE BINARY MESSAGES (Audio Stream from ESP32)
            # -----------------------------------------------------------
            elif isinstance(message, bytes):
                if client_type == "pc":
                    print(f"[PC {client_name}] Unexpected binary data ignored.")
                    continue

                await detect_speech(message, process_audio)

    except websockets.exceptions.ConnectionClosed:
        print(f"[WS] Disconnected: type={client_type}, name={client_name}")

    finally:
        # CLEANUP: Remove instances from storage on disconnect
        clients.discard(websocket)
        
        if client_type == "esp":
            esp_clients.discard(websocket)
            print("[ESP] Disconnected & Removed Instance")
        elif client_type == "pc" and client_name:
            pc_clients.pop(client_name, None)
            print(f"[PC] Removed Instance: {client_name}")
async def send_websocket_message(message):
    global ws
    if ws is None:
        print("No active websocket connection to send message!")
        return
    try:
        await ws.send(message)
        print(f"Sent: {message}")
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected while sending!")
        ws = None


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
    print(f"[WS] current connection = {ws}")
    return ws

async def stream_audio(AUDIO_FILE="data/output_audio/response.wav"):
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


async def stream_music(AUDIO_FILE="assets/music/song.wav"):
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
   

