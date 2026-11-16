"""One application-owned speech queue over NOVA's existing TTS pipeline."""

from __future__ import annotations

import asyncio
import itertools
import logging
from dataclasses import dataclass

from app.tts.speak import speak


logger = logging.getLogger(__name__)


@dataclass
class _SpeechRequest:
    task_id: str | None
    text: str
    priority: int
    sequence: int
    completed: asyncio.Future
    playback: asyncio.Task | None = None
    cancelled: bool = False


class SpeakerManager:
    """Serialize all task and coordinator speech through one persistent worker."""

    def __init__(self, transport, synthesizer):
        self.transport = transport
        self.synthesizer = synthesizer
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._sequence = itertools.count()
        self._by_id: dict[int, _SpeechRequest] = {}
        self._active_by_task: dict[str, set[int]] = {}
        self._worker: asyncio.Task | None = None
        self._closed = False

    def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run(), name="nova-speaker-manager")

    async def say(self, text: str, task_id: str | None = None, priority: int = 0) -> None:
        if self._closed:
            raise RuntimeError("SpeakerManager is closed.")
        self.start()
        sequence = next(self._sequence)
        future = asyncio.get_running_loop().create_future()
        request = _SpeechRequest(task_id, text, priority, sequence, future)
        self._by_id[sequence] = request
        if task_id is not None:
            self._active_by_task.setdefault(task_id, set()).add(sequence)
        await self._queue.put((-priority, sequence, request))
        try:
            await future
        except asyncio.CancelledError:
            self._cancel_request(request)
            raise

    async def cancel_task(self, task_id: str) -> None:
        for sequence in list(self._active_by_task.get(task_id, ())):
            request = self._by_id.get(sequence)
            if request is not None:
                self._cancel_request(request)

    def _cancel_request(self, request: _SpeechRequest) -> None:
        request.cancelled = True
        if not request.completed.done():
            request.completed.cancel()
        if request.playback is not None and not request.playback.done():
            request.playback.cancel()
        self._forget(request)

    def _forget(self, request: _SpeechRequest) -> None:
        self._by_id.pop(request.sequence, None)
        if request.task_id is not None:
            active = self._active_by_task.get(request.task_id)
            if active is not None:
                active.discard(request.sequence)
                if not active:
                    self._active_by_task.pop(request.task_id, None)

    async def _run(self) -> None:
        while True:
            _, _, request = await self._queue.get()
            try:
                if request.cancelled or request.completed.cancelled():
                    continue
                playback = asyncio.create_task(
                    speak(request.text, self.transport, self.synthesizer),
                    name=f"nova-speech-{request.sequence}",
                )
                request.playback = playback
                try:
                    await playback
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling():
                        raise
                    if not request.completed.cancelled():
                        request.completed.cancel()
                except Exception as error:
                    if not request.completed.done():
                        request.completed.set_exception(error)
                    logger.exception("Speech request %s failed", request.sequence)
                else:
                    if not request.completed.done():
                        request.completed.set_result(None)
            finally:
                self._forget(request)
                self._queue.task_done()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for request in list(self._by_id.values()):
            self._cancel_request(request)
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None
