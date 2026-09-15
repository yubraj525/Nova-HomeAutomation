import asyncio
import json

import webrtcvad
import websockets

from app.agent.base import ExecutionType
from app.agent.pending_manager import PendingRequests
from app.vad.vad_detection import detect_speech
from app.agent.registery import ToolRegistry
from app.agent.remoteToolRegistryRouter import RemoteTool
from app.agent.registery import ToolRegistry



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

async def handle_client(websocket, process_audio, tool_registry: ToolRegistry,request_pending:PendingRequests):
    clients.add(websocket)

    client_type = "esp"
    client_name = None

    try:
        async for message in websocket:

            if isinstance(message, str):

                try:
                    data = json.loads(message)
                    # print(f"[WS] Received JSON: {data}")
                except json.JSONDecodeError:
                    data = None

                if isinstance(data, dict):
                  

                    msg_type = data.get("type")

                    # =========================
                    # REGISTER
                    # =========================
                    if msg_type == "register":

                        client_type = data.get(
                            "client_type",
                            "esp"
                        )

                        client_name = data.get(
                            "client_name"
                        )

                        if client_type == "pc" and client_name:

                            pc_clients[client_name] = {
                                "websocket": websocket,
                                "tools": []
                            }

                            print(
                                f"[PC] Connected: {client_name}"
                            )

                            await websocket.send(
                                json.dumps({
                                    "type": "request_tools"
                                })
                            )

                            print(
                                f"[PC] Total connected: "
                                f"{len(pc_clients)}"
                            )

                        continue

                    # =========================
                    # RESPONSE TO request_tools
                    # =========================
                    if msg_type == "response_tools":
                     if client_type == "pc" and client_name:
                         tools = data.get("tools", [])

                       

                         for tool_data in tools:
                             remote_tool = RemoteTool(
                                 name=tool_data["name"],
                                 description=tool_data.get("description", ""),
                                 parameters=tool_data.get("parameters", {}),
                                 websocket=websocket,
                                 client_name=client_name,
                                 pending_requests=request_pending
                             )
                             tool_registry.register(remote_tool, ExecutionType.REMOTE)

                         print(f"[PC] Tools received from {client_name}: {len(tools)}")

                        
                         from app.agent.ToolRouter import ToolRouter
                         print("execution test...")
                         tool_router = ToolRouter(tool_registry,request_pending)
                         asyncio.create_task(tool_router.execute(
                                 tool_name="browser_open_tab",
                                 arguments={"url": "https://www.youtube.com","tool_call_id":"call_abc123"}
                                 
                                 
                             ) ) 

                         # Get LLM-ready JSON schemas for model requests
                        #  tools_schema = tool_registry.get_tool_schemas()
                        #  print(f"[PC] Clean LLM Tools Schema: {json.dumps(tools_schema, indent=2)}")

                         continue
                    if msg_type == "response_execute_tool":
                        request_id = data.get("request_id")
                        result = data.get("result")
                        error = data.get("error")
                        print(
                            f"[PC] Received execution response for request_id={request_id}: "
                            f"result={result}, error={error}"
                        )
                        requestes=request_pending.list()
                        for req in requestes:
                            print(f"Pending request: {req}/\n")

                        if request_id:
                            if error:
                                request_pending.reject(
                                    request_id,
                                    error
                                )
                            else:
                                request_pending.resolve(
                                    request_id,
                                    result
                                )
                        continue
                    
                # =========================
                # ESP32 TEXT MESSAGES
                # =========================
                if client_type == "esp":

                    if websocket not in esp_clients:
                        esp_clients.add(websocket)

                        print(
                            f"[ESP] Connected "
                            f"(Total ESP32: "
                            f"{len(esp_clients)})"
                        )

                    if message == "play_test":
                        await stream_audio()

                    elif message == "Hello from ESP":
                        print("[ESP] Received greeting")

            # =========================
            # ESP32 AUDIO
            # =========================
            elif isinstance(message, bytes):

                if client_type == "esp":
                    await detect_speech(
                        message,
                        process_audio
                    )

    except websockets.exceptions.ConnectionClosed:

        print(
            f"[WS] Disconnected: "
            f"type={client_type}, "
            f"name={client_name}"
        )

    finally:

        clients.discard(websocket)

        if client_type == "pc" and client_name:

            pc_clients.pop(
                client_name,
                None
            )

            print(
                f"[PC] Removed: {client_name}"
            )

        elif client_type == "esp":

            esp_clients.discard(websocket)

            print("[ESP] Removed")

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
   

