class WebSocketAudioTransport:

    def __init__(self, websocket):
        self.websocket = websocket

    async def start(self):
        await self.websocket.send("audio_start")

    async def send(self, chunk):
        await self.websocket.send(chunk.data)

    async def end(self):
        await self.websocket.send("audio_end")