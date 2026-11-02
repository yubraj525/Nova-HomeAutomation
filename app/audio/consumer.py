from app.audio.queuey import AudioQueue
from app.audio.transport import AudioTransport


async def consume_audio(
    queue: AudioQueue,
    transport: AudioTransport,
):
    print("[CONSUMER] started")

    print("[CONSUMER] starting transport...")
    await transport.start()
    print("[CONSUMER] transport started")

    while True:
        print("[CONSUMER] waiting for chunk...")

        chunk = await queue.get()

        try:
            print(
                f"[CONSUMER] sending "
                f"seq={chunk.sequence} | "
                f"duration={chunk.duration:.3f}s | "
                f"queue={queue.qsize()}"
            )

            await transport.send(chunk)

        finally:
            queue.task_done()
            print(f"[CONSUMER] task done seq={chunk.sequence}")