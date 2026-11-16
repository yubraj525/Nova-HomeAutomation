"""Connection-scoped state for speech, conversation, recordings, and work."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Callable

from app.audio.utils import save_audio
from app.vad.vad_detection import VADSessionState


logger = logging.getLogger(__name__)


class ClientSession:
    def __init__(
        self,
        session_id: str,
        websocket,
        process_audio,
        pending_requests,
        recording_dir: str | Path,
    ):
        self.session_id = session_id
        self.websocket = websocket
        self.process_audio = process_audio
        self.agent = process_audio.agent
        self.pending_requests = pending_requests
        self.recording_dir = Path(recording_dir)
        self.vad_state = VADSessionState()
        self.recording_paths: set[Path] = set()
        self.processing_tasks: set[asyncio.Task] = set()
        self.closed = False
        self._close_lock = asyncio.Lock()

    def new_recording_path(self) -> Path:
        return self.recording_dir / f"nova-{self.session_id}-{uuid.uuid4().hex}.wav"

    async def send_control(self, message: str) -> None:
        if self.closed:
            return
        await self.websocket.send(message)

    async def submit_recording(self, audio: bytes) -> None:
        if self.closed:
            raise RuntimeError(f"Session {self.session_id} is closed.")

        path = self.new_recording_path()
        self.recording_paths.add(path)
        try:
            await asyncio.to_thread(save_audio, audio, path)
        except Exception:
            self.recording_paths.discard(path)
            path.unlink(missing_ok=True)
            raise

        if self.closed:
            self._remove_recording(path)
            return

        task = asyncio.create_task(
            self._process_recording(path),
            name=f"nova-audio-{self.session_id}",
        )
        self.processing_tasks.add(task)
        task.add_done_callback(self._processing_finished)

    async def _process_recording(self, path: Path) -> None:
        try:
            if not self.closed:
                await self.process_audio.process_audio(str(path))
        finally:
            self._remove_recording(path)

    def _processing_finished(self, task: asyncio.Task) -> None:
        self.processing_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "Session %s audio processing failed",
                self.session_id,
                exc_info=(type(error), error, error.__traceback__),
            )

    def _remove_recording(self, path: Path) -> None:
        self.recording_paths.discard(path)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not remove session recording %s", path)

    async def close(self) -> None:
        """Idempotently reject calls, cancel session work, and remove recordings."""
        async with self._close_lock:
            if self.closed:
                return
            self.closed = True
            self.vad_state.reset()
            tasks = list(self.processing_tasks)
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            self.pending_requests.cancel_session(self.session_id)

            for path in list(self.recording_paths):
                self._remove_recording(path)


class SessionManager:
    """Create server-identified sessions around shared application resources."""

    def __init__(
        self,
        process_audio_factory: Callable[[str, object], object],
        pending_requests,
        recording_dir: str | Path | None = None,
    ):
        self._process_audio_factory = process_audio_factory
        self._pending_requests = pending_requests
        self._recording_dir = (
            Path(recording_dir)
            if recording_dir is not None
            else Path(__file__).resolve().parent.parent / "data" / "temp"
        )
        self._sessions: dict[str, ClientSession] = {}

    def create(self, websocket) -> ClientSession:
        session_id = uuid.uuid4().hex
        process_audio = self._process_audio_factory(session_id, websocket)
        session = ClientSession(
            session_id,
            websocket,
            process_audio,
            self._pending_requests,
            self._recording_dir,
        )
        self._sessions[session_id] = session
        return session

    async def close(self, session: ClientSession) -> None:
        await session.close()
        self._sessions.pop(session.session_id, None)

    def get(self, session_id: str) -> ClientSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[ClientSession]:
        return list(self._sessions.values())
