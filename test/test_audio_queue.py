import asyncio

from app.audio.chunk import AudioChunk
from app.audio.queuey import AudioQueue

async def main():
    queue = AudioQueue()

    chunk = AudioChunk(
        data=b"\x00\x00" * 2205,
        sample_rate=22050,
        channels=1,
        sample_width=2,
        sequence=0,
    )

    print("Chunk duration:", chunk.duration)
    print("Queue empty:", queue.empty())

    await queue.put(chunk)

    print("Queue size:", queue.qsize())

    received = await queue.get()

    print("Received sequence:", received.sequence)
    print("Received duration:", received.duration)

    queue.task_done()

    print("Queue empty:", queue.empty())


if __name__ == "__main__":
    asyncio.run(main())