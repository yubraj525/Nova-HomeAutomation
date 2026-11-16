# app/core/runtime.py

class NovaRuntime:

    def __init__(self):
        self.speaker = None
        self.agent = None
        self.router = None
        self.registry = None
        self.pending_requests = None
        self.process_audio = None
        self.task_manager = None

    async def initialize(self):

        # TTS
        from app.tts.nepanglish_tts import get_synthesizer
        from app.audio.local_transport import LocalAudioTransport
        from app.audio.audio_speaker import AudioSpeaker

        synthesizer = get_synthesizer()
        transport = LocalAudioTransport()

        self.speaker = AudioSpeaker(
            transport,
            synthesizer
        )

        await self.speaker.initialize()

        # Agent infrastructure
        self.registry = create_tool_registry()

        self.pending_requests = PendingRequests()

        self.router = ToolRouter(
            self.registry,
            self.pending_requests
        )

        self.agent = Agent(
            self.registry,
            self.router
        )

        # Audio pipeline
        self.process_audio = ProcessAudio(
            self.speaker,
            self.agent
        )

    async def shutdown(self):

        if self.speaker:
            await self.speaker.close()