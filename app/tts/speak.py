import asyncio

from app.audio.queuey import AudioQueue
from app.audio.consumer import consume_audio
from app.tts.tts_engine import synthesize_to_queue


async def speak(
    text: str,
    transport,
    synthesizer,
):
    queue = AudioQueue()

    await transport.start()

    producer = asyncio.create_task(
        synthesize_to_queue(
            text,
            queue,
            synthesizer,
        )
    )

    consumer = asyncio.create_task(
        consume_audio(
            queue,
            transport,
        )
    )

    try:
        await producer
        print("[TTS] producer finished")

        await queue.join()
        print("[QUEUE] all chunks consumed")

    finally:
        await transport.end()

        consumer.cancel()

        try:
            await consumer
        except asyncio.CancelledError:
            pass

        print("[AUDIO] playback finished")