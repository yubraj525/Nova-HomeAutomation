import asyncio
import asyncio
import sounddevice as sd


class LocalAudioTransport:

    async def start(self):
        print("[LOCAL] audio playback started")

    async def send(self, chunk):
        print(
            f"[LOCAL] playing "
            f"seq={chunk.sequence} | "
            f"duration={chunk.duration:.3f}s"
        )

        # AudioChunk contains raw PCM bytes
        audio = chunk.data

        # Convert bytes to int16 PCM
        import numpy as np

        samples = np.frombuffer(audio, dtype=np.int16)

        # Play through computer speaker
        sd.play(
            samples,
            samplerate=chunk.sample_rate,
        )

        # Wait until this chunk finishes
        await asyncio.to_thread(sd.wait)

    async def end(self):
        print("[LOCAL] audio playback finished")