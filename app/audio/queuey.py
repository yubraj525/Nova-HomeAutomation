import asyncio

from app.audio.chunk import AudioChunk

class AudioQueue:

    def __init__(self, max_size: int = 50):
        self._queue = asyncio.Queue(maxsize=max_size)

    async def put(self, chunk: AudioChunk) -> None:
        await self._queue.put(chunk)

    async def get(self) -> AudioChunk:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    async def join(self) -> None:
        print("[QUEUE] waiting for all tasks to be done...")
        await self._queue.join()

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()

    def clear(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break