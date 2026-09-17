# import asyncio

# from app.audio.consumer import consume_audio
# from app.audio.queuey import AudioQueue
# from app.audio.transport import AudioTransport
# from app.tts.tts_engine import synthesize_to_queue
# from app.communication.websocket import get_WSconnection
# from app.audio.transport import AudioTransport
# from app.communication.websocket import get_WSconnection
# from app.audio.local_transport import LocalAudioTransport

# # async def main():

# #     queue = AudioQueue()

# #     websocket = get_WSconnection()
# #     transport = AudioTransport(websocket)

# #     producer = asyncio.create_task(
# #         synthesize_to_queue(
# #             "नमस्ते, आज मौसम राम्रो छ। How are you today?",
# #             queue,
# #         )
# #     )

# #     consumer = asyncio.create_task(
# #         consume_audio(
# #             queue,
# #             transport,
# #         )
# #     )

# #     await producer

# #     print("[TTS] producer finished")

# #     await queue.join()

# #     print("[QUEUE] all chunks consumed")

# #     consumer.cancel()

# #     try:
# #         await consumer
# #     except asyncio.CancelledError:
# #         pass

# #     print("[TEST] finished")

# # async def main():
# #     queue = AudioQueue()

# #     transport = LocalAudioTransport()
# #     text = """
# # नमस्ते, आज मौसम निकै राम्रो छ। म तिमीलाई आजको दिनको बारेमा केही कुरा बताउन चाहन्छु।
# # बिहानको मौसम शान्त थियो र अहिले पनि बाहिरको वातावरण निकै रमाइलो देखिन्छ।
# # यदि तिमीलाई कुनै काम गर्न मन छ भने म त्यसमा पनि सहयोग गर्न सक्छु।
# # How are you today? I hope you are having a great day.
# # We can continue talking about anything you want, and I will try my best to help you.
# # """

# #     producer = asyncio.create_task(
# #         synthesize_to_queue(
# #             text,
# #             queue
# #         )
# #     )

# #     consumer = asyncio.create_task(
# #         consume_audio(
# #             queue,
# #             transport
# #         )
# #     )

# #     await producer
# #     print("[TTS] producer finished")

# #     await queue.join()
# #     print("[QUEUE] all chunks consumed")

# #     await transport.end()

# #     consumer.cancel()

# #     try:
# #         await consumer
# #     except asyncio.CancelledError:
# #         pass

# #     print("[TEST] finished")
# import time
# async def main():
#     start_time = time.perf_counter()

#     queue = AudioQueue()
#     transport = LocalAudioTransport()

#     text = """
#     नमस्ते, आज मौसम निकै राम्रो छ। म तिमीलाई आजको दिनको बारेमा केही कुरा बताउन चाहन्छु।
#     बिहानको मौसम शान्त थियो र अहिले पनि बाहिरको वातावरण निकै रमाइलो देखिन्छ।
#     यदि तिमीलाई कुनै काम गर्न मन छ भने म त्यसमा पनि सहयोग गर्न सक्छु।
#     How are you today? I hope you are having a great day.
#     We can continue talking about anything you want, and I will try my best to help you.
#     """

#     producer = asyncio.create_task(
#         synthesize_to_queue(text, queue)
#     )

#     consumer = asyncio.create_task(
#         consume_audio(queue, transport)
#     )

#     await producer
#     print("[TTS] producer finished")

#     await queue.join()
#     print("[QUEUE] all chunks consumed")

#     await transport.end()

#     consumer.cancel()

#     try:
#         await consumer
#     except asyncio.CancelledError:
#         pass

#     end_time = time.perf_counter()

#     print(f"[TEST] finished")
#     print(f"[TIME] total: {end_time - start_time:.3f} seconds")


# if __name__ == "__main__":
#     asyncio.run(main())
# if __name__ == "__main__":
#     asyncio.run(main())














import asyncio
import time

from app.audio.consumer import consume_audio
from app.audio.local_transport import LocalAudioTransport
from app.audio.queuey import AudioQueue
from app.tts.tts_engine import synthesize_to_queue

# Create an event signal to capture the exact time the first frame arrives
first_chunk_event = asyncio.Event()
ttfa_time = None


class TimingAudioQueue(AudioQueue):
    """Subclass or wrapper to detect when the first chunk enters or exits the queue."""

    async def get(self):
        global ttfa_time
        chunk = await super().get()
        if not first_chunk_event.is_set() and chunk is not None:
            ttfa_time = time.perf_counter()
            first_chunk_event.set()
        return chunk


async def main():
    from app.tts.nepanglish_tts import get_synthesizer

    # Load synthesizer once
    synthesizer = get_synthesizer()

    while True:
        text = await asyncio.to_thread(input, "\nYou: ")

        if text.strip().lower() == "exit":
            break

        if not text.strip():
            continue

        start_time = time.perf_counter()

        queue = TimingAudioQueue()
        transport = LocalAudioTransport()

        producer = asyncio.create_task(
            synthesize_to_queue(
                text,
                queue,
                synthesizer
            )
        )

        consumer = asyncio.create_task(
            consume_audio(queue, transport)
        )

        # Wait for first chunk
        await first_chunk_event.wait()

        latency_ms = (ttfa_time - start_time) * 1000

        print(
            f"\n[LATENCY] Time to First Audio (TTFA): "
            f"{latency_ms:.2f} ms\n"
        )

        await producer
        print("[TTS] producer finished")

        await queue.join()
        print("[QUEUE] all chunks consumed")

        await transport.end()

        consumer.cancel()

        try:
            await consumer
        except asyncio.CancelledError:
            pass

        end_time = time.perf_counter()

        print("[TEST] finished")
        print(
            f"[TIME] total duration: "
            f"{end_time - start_time:.3f} seconds"
        )


if __name__ == "__main__":
    asyncio.run(main())
if __name__ == "__main__":
    asyncio.run(main())