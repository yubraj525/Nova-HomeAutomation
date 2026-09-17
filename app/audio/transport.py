class AudioTransport:

    def __init__(self, websocket):
        self.websocket = websocket

async def start(self):
    print(f"[TRANSPORT] websocket = {self.websocket}")
    print("[TRANSPORT] sending audio_start...")

    await self.websocket.send("audio_start")

    print("[TRANSPORT] audio_start sent")

    async def send(self, chunk):
        await self.websocket.send(chunk.data)

    async def end(self):
        await self.websocket.send("audio_end")