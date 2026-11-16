import asyncio

import numpy as np

from app.audio.speaker_manager import SpeakerManager
from app.tts.tts_router import TTSLanguage, TTSRouter, route_language
from app.tts.tts_kokoro_english import KokoroEnglishTTS, MAX_CHUNK_CHARS, chunk_text


def test_script_routing_cases():
    assert route_language("नमस्ते") is TTSLanguage.NEPALI
    assert route_language("Hello there") is TTSLanguage.ENGLISH
    assert route_language("There are 42 items.") is TTSLanguage.ENGLISH
    assert route_language("नमस्ते?!") is TTSLanguage.NEPALI
    assert route_language("Hello नमस्ते") is TTSLanguage.NEPALI
    assert route_language("") is TTSLanguage.ENGLISH
    assert route_language(None) is TTSLanguage.ENGLISH
    assert route_language("🙂 café १२") is TTSLanguage.NEPALI
    assert route_language("café Ελληνικά") is TTSLanguage.ENGLISH
    assert route_language("ॐ") is TTSLanguage.NEPALI


class _Synth:
    sample_rate = 22050

    def __init__(self, marker):
        self.marker = marker
        self.received = []

    def synthesize_stream(self, text):
        self.received.append(text)
        yield np.array([0.0, 0.1], dtype=np.float32)


def test_router_passes_original_text_to_selected_synthesizer():
    nepali = _Synth("ne")
    english = _Synth("en")
    router = TTSRouter(nepali, english)
    original = "Hello, नमस्ते!"

    list(router.synthesize_stream(original))

    assert nepali.received == [original]
    assert english.received == []


def test_kokoro_uses_existing_voice_settings_and_streams_text_chunks():
    class Kokoro:
        def __init__(self):
            self.calls = []

        def create(self, text, **settings):
            self.calls.append((text, settings))
            return np.array([0.1], dtype=np.float32), 24000

    model = Kokoro()
    synthesizer = KokoroEnglishTTS(model)
    generated = synthesizer.synthesize_stream("First. Second!")

    next(generated)
    assert [call[0] for call in model.calls] == ["First."]
    next(generated)
    assert [call[0] for call in model.calls] == ["First.", "Second!"]
    assert all(call[1] == {"voice": "af_sky", "speed": 1.1, "lang": "en-us"} for call in model.calls)
    assert synthesizer.sample_rate == 24000


def test_english_chunking_splits_sentences_and_caps_long_sentences():
    text = "A short sentence. " + ("long words " * 30)
    chunks = chunk_text(text)

    assert chunks[0] == "A short sentence."
    assert len(chunks) > 2
    assert all(len(chunk) <= MAX_CHUNK_CHARS for chunk in chunks)
    assert " ".join(chunks) == text.strip()


class _Transport:
    def __init__(self):
        self.chunks = []

    async def start(self):
        pass

    async def send(self, chunk):
        self.chunks.append(chunk)


def test_shared_speaker_serializes_requests_and_survives_failure():
    async def run():
        transport = _Transport()

        class Synth:
            sample_rate = 22050

            def synthesize_stream(self, text):
                if text == "fail":
                    raise RuntimeError("synthesis failed")
                # The marker lets the test verify playback ordering.
                yield np.array([ord(text[0]) / 256], dtype=np.float32)
                yield np.array([0.0], dtype=np.float32)

        speaker = SpeakerManager(transport, Synth())
        first = asyncio.create_task(speaker.say("A", task_id="task-a"))
        second = asyncio.create_task(speaker.say("B", task_id="task-b"))
        await asyncio.gather(first, second)
        assert len(transport.chunks) == 4
        assert transport.chunks[0].data != transport.chunks[2].data

        try:
            await speaker.say("fail", task_id="task-fail")
        except RuntimeError as error:
            assert str(error) == "synthesis failed"
        else:
            raise AssertionError("synthesis error was not returned to caller")

        await speaker.say("C", task_id="task-c")
        await speaker.close()

    asyncio.run(run())


def test_cancelling_active_task_speech_keeps_shared_speaker_alive():
    async def run():
        started = asyncio.Event()

        class BlockingTransport(_Transport):
            async def send(self, chunk):
                self.chunks.append(chunk)
                if not started.is_set():
                    started.set()
                    await asyncio.Future()

        class Synth:
            sample_rate = 22050

            def synthesize_stream(self, text):
                yield np.array([0.1], dtype=np.float32)

        transport = BlockingTransport()
        speaker = SpeakerManager(transport, Synth())
        cancelled = asyncio.create_task(speaker.say("A", task_id="cancel-me"))
        await started.wait()
        await speaker.cancel_task("cancel-me")
        try:
            await cancelled
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancelled speech did not cancel its caller")

        await speaker.say("B", task_id="keep-going")
        assert len(transport.chunks) == 2
        await speaker.close()

    asyncio.run(run())
