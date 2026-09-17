# app/communication/websocket_transport.py

import asyncio


class WebSocketAudioTransport:

    MAX_CHUNK_SIZE = 4096

    def __init__(self, get_websocket):
        self.get_websocket = get_websocket

    def _get_ws(self):
        websocket = self.get_websocket()

        if websocket is None:
            raise RuntimeError("[WS] No active WebSocket connection")

        return websocket

    async def start(self):
        websocket = self._get_ws()
        print(f"[WS] Starting audio playback on {websocket}")

        print("[WS] audio playback started")

        await websocket.send("audio_start")

    async def send(self, chunk):
        websocket = self._get_ws()

        data = chunk.data

        print(
            f"[WS] sending seq={chunk.sequence} | "
            f"duration={chunk.duration:.3f}s | "
            f"data={len(data)} bytes"
        )

        for i in range(0, len(data), self.MAX_CHUNK_SIZE):

            piece = data[i:i + self.MAX_CHUNK_SIZE]

            await websocket.send(piece)

            # Small pacing delay
            await asyncio.sleep(0.003)

        print(
            f"[WS] sent seq={chunk.sequence} "
            f"as {((len(data) - 1) // self.MAX_CHUNK_SIZE) + 1} packets"
        )

    async def end(self):
        websocket = self._get_ws()
        print(f"[WS] Starting audio playback on {websocket}")
        await asyncio.sleep(1)

        print("[WS] audio playback finished")
        print(f"[WS] Stopping audio stream on {websocket}")

        await websocket.send("audio_end")
        await websocket.send("stop_stream")