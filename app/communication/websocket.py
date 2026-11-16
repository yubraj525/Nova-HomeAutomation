import asyncio
import json
import uuid


import websockets

from app.agent.ToolRouter import ToolRouter
from app.agent.pending_manager import PendingRequests
from app.vad.vad_detection import detect_speech
from app.agent.registery import ToolRegistry
from app.agent.remoteToolRegistryRouter import RemoteTool
from app.agent.base import ExecutionType, ToolError
from app.session import SessionManager



CHUNK_SIZE = 512  # Larger chunks are more efficient for Wi-Fi
AUDIO_FILE = "data/output_audio/response.wav"  # For testing streaming to ESP32
ws = None

pc_clients = {}     # { "pc_name": websocket_instance }
esp_clients = set()  # Set of ESP websocket instances
clients = set()


def _complete_remote_response(request_pending, connection_id, client_name, request_id, result, error):
    """Check both registered name and immutable connection ownership atomically."""
    pending_request = request_pending.get(request_id)
    if (
        pending_request is None
        or pending_request["client_name"] != client_name
        or pending_request["connection_id"] != connection_id
    ):
        return False
    return request_pending.complete_owned(
        request_id,
        connection_id,
        result=result,
        error=error,
    )

async def handle_client(
    websocket,
    session_manager: SessionManager,
    tool_registry: ToolRegistry,
    request_pending: PendingRequests,
    router: ToolRouter
):
    session = session_manager.create(websocket)
    connection_id = uuid.uuid4().hex
    clients.add(websocket)

    # Default connection type
    client_type = "esp"
    client_name = None

    # Initially consider every connection as ESP32
    esp_clients.add(websocket)

    print(
        f"[WS] New connection | "
        f"ESP32: {len(esp_clients)} | "
        f"PC: {len(pc_clients)}"
    )

    try:
        async for message in websocket:

            if isinstance(message, str):

                # try:
                data = json.loads(message)
                #     print(f"[WS] Received data: {data}")
                # except json.JSONDecodeError:
                #     data = None

                # =========================
                # JSON MESSAGES
                # =========================
                if isinstance(data, dict):

                    msg_type = data.get("type")

                    # =========================
                    # REGISTER
                    # =========================
                    if msg_type == "register":

                        requested_type = data.get(
                            "client_type",
                            "esp"
                        )

                        requested_name = data.get(
                            "client_name"
                        )

                        # Convert ESP connection to PC
                        if (
                            requested_type == "pc"
                            and requested_name
                        ):
                            existing = pc_clients.get(requested_name)
                            if existing and existing["websocket"] is not websocket:
                                await websocket.send(json.dumps({
                                    "type": "registration_error",
                                    "error": "client_name_already_registered",
                                }))
                                await websocket.close(code=1008, reason="client name already registered")
                                return

                            client_type = "pc"
                            client_name = requested_name

                            await session_manager.close(session)
                            session = None

                            # Remove from ESP clients
                            esp_clients.discard(websocket)

                            # Store as PC client
                            pc_clients[client_name] = {
                                "websocket": websocket,
                                "tools": [],
                                "connection_id": connection_id,
                            }

                            print(
                                f"[WS] Connection registered as PC: "
                                f"{client_name}"
                            )

                            await websocket.send(
                                json.dumps({
                                    "type": "request_tools"
                                })
                            )

                        else:
                            # Remain ESP32
                            client_type = "esp"

                            esp_clients.add(websocket)

                            print(
                                "[WS] Connection registered as ESP32"
                            )

                        continue

                    # =========================
                    # PC TOOL REGISTRATION
                    # =========================
                    if msg_type == "response_tools":

                        if client_type == "pc" and client_name:

                            tools = data.get("tools", [])
                            if not isinstance(tools, list):
                                print(f"[PC] Rejected malformed tool list from {client_name}")
                                continue

                            for tool_data in tools:
                                try:
                                    if not isinstance(tool_data, dict):
                                        raise ValueError("tool entry must be an object")
                                    remote_tool = RemoteTool(
                                        name=tool_data.get("name"),
                                        description=tool_data.get("description", ""),
                                        parameters=tool_data.get("parameters"),
                                        websocket=websocket,
                                        client_name=client_name,
                                        pending_requests=request_pending,
                                        connection_id=connection_id,
                                    )
                                    tool_registry.register(remote_tool, ExecutionType.REMOTE)
                                except (ToolError, TypeError, ValueError) as error:
                                    print(f"[PC] Rejected remote tool from {client_name}: {error}")
                                # this is a testing line to check if the agent can execute a remote tool on the PC client
                            # print(json.dumps(tool_registry.get_tool_schemas(), indent=2));
                        #     agent= Agent(tool_registry,router)
                        #    ## THIS IS A TESTING LINE TO CHECK IF THE AGENT CAN EXECUTE A REMOTE TOOL ON THE PC CLIENT
                        #     response = asyncio.create_task(
                        #          agent.run("play olivia man i need")
                        #                 )
                        #     print(f"Agent response: {response}")
                                # print(tool_registry.get_tool_schemas());
                                
                               


                            print(
                                f"[PC] Tools received from "
                                f"{client_name}: {len(tools)}"
                            )

                        continue

                    # =========================
                    # PC EXECUTION RESPONSE
                    # =========================
                    if msg_type == "response_execute_tool":

                        request_id = data.get("request_id")
                        result = data.get("result")
                        error = data.get("error") or None

                        print(
                            f"[PC] Execution response | "
                            f"request_id={request_id} | "
                            f"result={result} | "
                            f"error={error}"
                        )

                        if request_id:
                            if not _complete_remote_response(
                                request_pending,
                                connection_id,
                                client_name,
                                request_id,
                                result,
                                error,
                            ):
                                print(
                                    f"[PC] Ignored unowned or unknown request response: "
                                    f"{request_id}"
                                )
                                continue

                            if error:
                                print(
                                    f"[PC] Execution error for "
                                    f"request_id={request_id}: {error}"
                                )
                                
                            else:
                                pending = request_pending.list()
                                print(f"[PC] Pending requests after resolution: {pending}")
                                # print(
                                #     f"[PC] Execution result for "
                                #     f"request_id={request_id}: {result}"
                                # )
                        continue

                # =========================
                # ESP32 TEXT MESSAGES
                # =========================
                if client_type == "esp":

                    if message == "play_test":
                        await stream_audio(websocket=websocket)

                    elif message == "Hello from ESP":
                        print("[ESP] Received greeting")

            # =========================
            # ESP32 AUDIO
            # =========================
            elif isinstance(message, bytes):

                if client_type == "esp":
                    await detect_speech(
                        message,
                        session,
                    )

    except websockets.exceptions.ConnectionClosed:
        print(
            f"[WS] Disconnected | "
            f"type={client_type} | "
            f"name={client_name}"
        )

    finally:
        clients.discard(websocket)

        if session is not None:
            await session_manager.close(session)

        if client_type == "pc" and client_name:
            request_pending.reject_connection(
                connection_id,
                f"Remote client {client_name!r} disconnected.",
            )
            removed_tools = tool_registry.unregister_remote_client(
                client_name,
                websocket=websocket,
            )
            current_client = pc_clients.get(client_name)
            if current_client and current_client["websocket"] is websocket:
                pc_clients.pop(client_name, None)

            print(f"[PC] Removed PC client: {client_name}; tools={removed_tools}")

        elif client_type == "esp":
            esp_clients.discard(websocket)

            print("[ESP] Removed ESP32")

        print(
            f"[WS] Active connections | "
            f"Total: {len(clients)} | "
            f"ESP32: {len(esp_clients)} | "
            f"PC: {len(pc_clients)}"
        )

        print(
            f"[WS] Connected PC clients: "
            f"{list(pc_clients.keys())}"
        )
async def send_websocket_message(message):
    ws = get_WSconnection()
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
    if not esp_clients:
        print("[WS] No ESP connection")
        return None

    websocket = next(iter(esp_clients))

    # print(f"[WS] current connection = {websocket}")
    return websocket

async def stream_audio(AUDIO_FILE="data/output_audio/response.wav", websocket=None):
    websocket = websocket or get_WSconnection()
    if websocket is None:
        raise RuntimeError("No active ESP32 WebSocket connection.")
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
   

