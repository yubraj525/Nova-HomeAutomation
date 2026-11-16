"""Turn short speech commands into task create, update, cancel, or status actions."""

from __future__ import annotations

import asyncio
import logging
import re

from app.tasks.manager import TaskManager


_CANCEL_WORDS = re.compile(r"\b(cancel|stop|abort|never mind|nevermind)\b", re.I)
_STATUS_WORDS = re.compile(r"\b(status|what are you doing|list tasks|active tasks)\b", re.I)
_MUSIC_WORDS = re.compile(r"\b(music|song|youtube|play)\b", re.I)
_MAIL_WORDS = re.compile(r"\b(gmail|email|mail)\b", re.I)
_UPDATE_WORDS = re.compile(r"\b(instead|change|actually|replace|rather)\b", re.I)
logger = logging.getLogger(__name__)


class CommandCoordinator:
    """Keep command intake short while task workers run independently."""

    def __init__(self, task_manager: TaskManager, speaker=None):
        self.task_manager = task_manager
        self.speaker = speaker
        self._speech_tasks: set[asyncio.Task] = set()

    async def submit(self, command: str, source_session_id: str | None = None) -> dict:
        text = command.strip()
        if not text:
            return {"action": "ignored", "message": "No command was recognized."}

        kind = self._kind(text)
        if _STATUS_WORDS.search(text):
            active = self.task_manager.active()
            message = self._status_summary(active)
            self._queue_speech(message, task_id=None, priority=10)
            return {"action": "status", "tasks": [t.public_snapshot() for t in active]}

        if _CANCEL_WORDS.search(text):
            task_id_match = re.search(r"\b([0-9a-f]{8,32})\b", text, re.I)
            target = (
                self.task_manager.get_by_prefix(task_id_match.group(1))
                if task_id_match
                else self.task_manager.find_latest_active(kind if kind != "general" else None)
            )
            if target is None or not self.task_manager.can_cancel(target):
                message = "I could not find an active task to cancel."
                self._queue_speech(message, task_id=None, priority=10)
                return {"action": "not_found", "message": message}
            cancelled = await self.task_manager.cancel(target.task_id)
            message = f"Cancelled task {target.task_id[:8]}" if cancelled else "That task already finished."
            self._queue_speech(message, task_id=target.task_id, priority=20)
            return {"action": "cancelled" if cancelled else "not_found", "task_id": target.task_id}

        active = self.task_manager.find_latest_active(kind)
        should_update = active is not None and (
            bool(_UPDATE_WORDS.search(text)) or kind == "music"
        )
        if should_update:
            record = await self.task_manager.update(active.task_id, text)
            self._queue_speech("I updated that task.", task_id=record.task_id, priority=10)
            return {"action": "updated", "task": record.public_snapshot()}

        waiting = self.task_manager.waiting_for_user()
        if waiting is not None and self.task_manager.answer_user(waiting.task_id, text):
            return {"action": "answered", "task_id": waiting.task_id}

        record = await self.task_manager.create(text, source_session_id, kind=kind)
        self._queue_speech("", task_id=record.task_id, priority=10)
        # the mpty strng denmoted a intialize stement for a creting tsak
        return {"action": "created", "task": record.public_snapshot()}

    def _queue_speech(self, text: str, task_id: str | None, priority: int) -> None:
        if self.speaker is None:
            return
        task = asyncio.create_task(
            self.speaker.say(text, task_id=task_id, priority=priority),
            name="nova-coordinator-speech",
        )
        self._speech_tasks.add(task)
        task.add_done_callback(self._speech_finished)

    def _speech_finished(self, task: asyncio.Task) -> None:
        self._speech_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "Coordinator speech request failed",
                exc_info=(type(error), error, error.__traceback__),
            )

    @staticmethod
    def _kind(text: str) -> str:
        if _MAIL_WORDS.search(text):
            return "email"
        if _MUSIC_WORDS.search(text):
            return "music"
        return "general"

    @staticmethod
    def _status_summary(active) -> str:
        if not active:
            return "There are no active tasks."
        summaries = []
        for task in active:
            text = f"{task.kind} task {task.task_id[:8]} is {task.status.value}"
            if task.side_effects:
                text += f" with {', '.join(task.side_effects)} still active"
            summaries.append(text)
        return ". ".join(summaries)
