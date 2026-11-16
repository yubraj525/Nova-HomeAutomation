"""Application composition root for shared NOVA runtime services."""

from __future__ import annotations

import asyncio

from app.agent.Agent import Agent
from app.agent.ToolRouter import ToolRouter
from app.agent.pending_manager import PendingRequests
from app.agent.registery import ToolRegistry
from app.audio.local_transport import LocalAudioTransport
from app.audio.speaker_manager import SpeakerManager
from app.communication.websocket_transport import WebSocketAudioTransport
from app.pipeline.process_audio import ProcessAudio
from app.session import SessionManager
from app.tasks.coordinator import CommandCoordinator
from app.tasks.manager import TaskManager
from app.tasks.resources import ResourceCoordinator
from config.config import AUDIO_TRANSPORT



class NovaRuntime:
    """Own shared services and construct session/task-specific execution state."""

    def __init__(self):
        self.registry: ToolRegistry | None = None
        self.pending_requests: PendingRequests | None = None
        self.resources: ResourceCoordinator | None = None
        self.router: ToolRouter | None = None
        self.speaker: SpeakerManager | None = None
        self.task_manager: TaskManager | None = None
        self.coordinator: CommandCoordinator | None = None
        self.session_manager: SessionManager | None = None
        self.synthesizer = None
        self.transport = None
        self._stt_lock: asyncio.Lock | None = None

    async def initialize(self, registry: ToolRegistry | None = None) -> None:
        if self.session_manager is not None:
            return
        from app.tts.nepanglish_tts import get_synthesizer
        from app.tts.tts_kokoro_english import get_synthesizer as get_english_synthesizer
        from app.tts.tts_router import TTSRouter

        self.registry = registry or ToolRegistry()
        self.pending_requests = PendingRequests()
        self.resources = ResourceCoordinator()
        self.router = ToolRouter(self.registry, self.pending_requests, self.resources)
        nepali_synthesizer = get_synthesizer()
        english_synthesizer = get_english_synthesizer()
        self.synthesizer = TTSRouter(nepali_synthesizer, english_synthesizer)
        if AUDIO_TRANSPORT == "websocket":
            from app.communication.websocket import get_WSconnection

            self.transport = WebSocketAudioTransport(get_WSconnection)
        elif AUDIO_TRANSPORT == "local":
            self.transport = LocalAudioTransport()
        else:
            raise ValueError(
                "NOVA_AUDIO_TRANSPORT must be 'websocket' or 'local', "
                f"got {AUDIO_TRANSPORT!r}"
            )
        self.speaker = SpeakerManager(self.transport, self.synthesizer)
        self.speaker.start()
        self._stt_lock = asyncio.Lock()

        def agent_factory(
            task_id, source_session_id, status_callback,
            observation_callback, register_side_effect, request_user_input,
        ):
            # Task work is app-owned. The source session is metadata, not the
            # lifetime owner of a task or its remote pending requests.
            return Agent(
                self.registry,
                self.router,
                task_id=task_id,
                status_callback=status_callback,
                observation_callback=observation_callback,
                register_side_effect=register_side_effect,
                request_user_input=request_user_input,
            )

        self.task_manager = TaskManager(agent_factory, self.speaker)
        self.coordinator = CommandCoordinator(self.task_manager, self.speaker)

        def process_audio_factory(session_id, websocket):
            return ProcessAudio(
                self.synthesizer,
                self.transport,
                agent=None,
                session_id=session_id,
                websocket=websocket,
                stt_lock=self._stt_lock,
                coordinator=self.coordinator,
                speaker=self.speaker,
            )

        self.session_manager = SessionManager(process_audio_factory, self.pending_requests)

    async def shutdown(self) -> None:
        if self.task_manager is not None:
            await self.task_manager.shutdown()
        if self.session_manager is not None:
            sessions = self.session_manager.list_sessions()
            if sessions:
                await asyncio.gather(
                    *(self.session_manager.close(session) for session in sessions),
                    return_exceptions=True,
                )
        if self.speaker is not None:
            await self.speaker.close()
