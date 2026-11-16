"""Own task identities, isolated agents, workers, and task lifecycle."""

from __future__ import annotations

import asyncio
import ast
import json
import logging
import uuid
from copy import deepcopy
from typing import Callable

from app.tasks.models import TaskRecord, TaskStatus


logger = logging.getLogger(__name__)
ACTIVE_STATUSES = {
    TaskStatus.ACCEPTED,
    TaskStatus.PLANNING,
    TaskStatus.QUEUED,
    TaskStatus.RUNNING,
    TaskStatus.WAITING_FOR_TOOL,
    TaskStatus.WAITING_FOR_RESOURCE,
    TaskStatus.VERIFYING,
    TaskStatus.WAITING_FOR_USER,
}


def _failure_announcement(error: Exception) -> str:
    """Return user-facing speech, extracting a reply from provider error data."""
    message = str(error)
    # Some OpenAI-compatible providers put a rejected tool-call generation in
    # the error body. It can contain a perfectly usable final response, but it
    # must never be read aloud as the serialized diagnostic payload.
    body_start = message.find("{")
    if body_start >= 0:
        body = message[body_start:]
        try:
            error_data = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            try:
                error_data = ast.literal_eval(body)
            except (SyntaxError, ValueError):
                error_data = None
        if isinstance(error_data, dict):
            detail = error_data.get("error", error_data)
            failed_generation = (
                detail.get("failed_generation")
                if isinstance(detail, dict)
                else None
            )
            if isinstance(failed_generation, str):
                try:
                    generated = json.loads(failed_generation)
                except json.JSONDecodeError:
                    generated = None
                if isinstance(generated, dict):
                    arguments = generated.get("arguments")
                    response = arguments.get("response") if isinstance(arguments, dict) else None
                    if isinstance(response, str) and response.strip():
                        return response.strip()

    return "माफ गर्नुहोस्, यो अनुरोध पूरा गर्न सकिनँ।"


class TaskManager:
    """Schedule one isolated Agent per task over shared runtime services."""

    def __init__(self, agent_factory: Callable, speaker=None):
        self._agent_factory = agent_factory
        self._speaker = speaker
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = asyncio.Lock()
        self._retired_workers: set[asyncio.Task] = set()

    async def create(self, instruction: str, source_session_id: str | None, kind: str = "general") -> TaskRecord:
        async with self._lock:
            record = TaskRecord(
                task_id=uuid.uuid4().hex,
                instruction=instruction,
                kind=kind,
                source_session_id=source_session_id,
            )
            self._tasks[record.task_id] = record
            record.transition(TaskStatus.PLANNING)
            record.generation = 1
            record.execution = self._new_execution(record, record.generation)
            record.history = deepcopy(record.execution.messages)
            record.transition(TaskStatus.QUEUED)
            record.worker = asyncio.create_task(
                self._execute(record, record.generation, record.execution, record.instruction),
                name=f"nova-task-{record.task_id}",
            )
            return record

    async def update(self, task_id: str, instruction: str) -> TaskRecord:
        record = self._tasks.get(task_id)
        if record is None or not self._can_update(record):
            raise ValueError(f"No active task with id {task_id!r}.")
        async with record.operation_lock:
            if not self._can_update(record):
                raise ValueError(f"No active task with id {task_id!r}.")
            worker = record.worker
            if record.status in ACTIVE_STATUSES and worker is not None and not worker.done():
                self._retire(worker)
            record.generation += 1
            self._cancel_user_reply(record)
            if self._speaker is not None:
                await self._speaker.cancel_task(task_id)
            await self._stop_effects(record)
            record.instruction = instruction
            record.memory["updates"] = int(record.memory.get("updates", 0)) + 1
            record.memory["last_update"] = instruction
            record.result = None
            record.error = None
            record.announced = False
            record.execution = self._new_execution(record, record.generation)
            record.execution.messages = deepcopy(record.history)
            record.transition(TaskStatus.PLANNING)
            record.transition(TaskStatus.QUEUED)
            record.worker = asyncio.create_task(
                self._execute(record, record.generation, record.execution, instruction),
                name=f"nova-task-{record.task_id}",
            )
            return record

    async def cancel(self, task_id: str) -> bool:
        record = self._tasks.get(task_id)
        if record is None or not self.can_cancel(record):
            return False
        async with record.operation_lock:
            if not self.can_cancel(record):
                return False
            worker = record.worker
            was_active = record.status in ACTIVE_STATUSES
            if was_active and worker is not None and not worker.done():
                self._retire(worker)
            if was_active:
                record.generation += 1
                self._cancel_user_reply(record)
            if self._speaker is not None:
                await self._speaker.cancel_task(task_id)
            await self._stop_effects(record)
            if was_active:
                record.transition(TaskStatus.CANCELLED)
            return True

    def _new_execution(self, record: TaskRecord, generation: int):
        return self._agent_factory(
            record.task_id,
            record.source_session_id,
            lambda status: self._set_status(record, generation, status),
            lambda tool_name, result: self._observe(record, generation, tool_name, result),
            lambda effect_id, callback: self._register_effect(
                record, generation, effect_id, callback
            ),
            lambda prompt: self._request_user_input(record, generation, prompt),
        )

    async def _request_user_input(self, record, generation: int, prompt: str) -> str:
        if generation != record.generation:
            raise asyncio.CancelledError
        if record.status != TaskStatus.WAITING_FOR_USER:
            record.transition(TaskStatus.WAITING_FOR_USER)
        record.memory["waiting_for_user"] = prompt
        reply = asyncio.get_running_loop().create_future()
        record.user_reply = reply
        try:
            if self._speaker is not None:
                await self._speaker.say(prompt, task_id=record.task_id, priority=15)
            answer = await reply
            if generation != record.generation:
                raise asyncio.CancelledError
            record.memory.pop("waiting_for_user", None)
            record.transition(TaskStatus.RUNNING)
            return answer
        finally:
            if record.user_reply is reply:
                record.user_reply = None
            if not reply.done():
                reply.cancel()

    @staticmethod
    def _cancel_user_reply(record) -> None:
        if record.user_reply is not None and not record.user_reply.done():
            record.user_reply.cancel()

    def waiting_for_user(self) -> TaskRecord | None:
        for record in reversed(list(self._tasks.values())):
            if record.status == TaskStatus.WAITING_FOR_USER:
                return record
        return None

    def answer_user(self, task_id: str, answer: str) -> bool:
        record = self._tasks.get(task_id)
        if (
            record is None
            or record.status != TaskStatus.WAITING_FOR_USER
            or record.user_reply is None
            or record.user_reply.done()
        ):
            return False
        record.user_reply.set_result(answer)
        return True

    @staticmethod
    def _observe(record: TaskRecord, generation: int, tool_name: str, result) -> None:
        if record.generation == generation:
            record.observations.append({"tool": tool_name, "result": result})

    @staticmethod
    def _register_effect(record, generation, effect_id, cancel_callback) -> None:
        if generation == record.generation and record.status in ACTIVE_STATUSES:
            record.side_effects[effect_id] = cancel_callback

    async def _stop_effects(self, record: TaskRecord) -> None:
        for effect_id, cancel_callback in list(record.side_effects.items()):
            await cancel_callback()
            record.side_effects.pop(effect_id, None)

    async def _execute(self, record: TaskRecord, generation: int, execution, instruction: str) -> None:
        try:
            if record.generation != generation:
                return
            record.transition(TaskStatus.RUNNING)
            result = await execution.run(instruction)
            if record.generation != generation:
                return
            record.transition(TaskStatus.VERIFYING)
            record.result = str(result)
            record.history = deepcopy(execution.messages)
            if self._speaker is not None and not record.announced and record.result.strip():
                try:
                    await self._speaker.say(
                        record.result,
                        task_id=record.task_id,
                        priority=0,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Task %s completion announcement failed", record.task_id)
                else:
                    record.announced = True
            if record.generation != generation:
                return
            record.transition(TaskStatus.COMPLETED)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if record.generation != generation:
                return
            record.error = str(error)
            try:
                await self._stop_effects(record)
            except Exception:
                logger.exception("Task %s side-effect cleanup failed", record.task_id)
            if record.status in ACTIVE_STATUSES:
                record.transition(TaskStatus.FAILED)
            logger.exception("Task %s failed", record.task_id)
            if self._speaker is not None and not record.announced:
                record.announced = True
                try:
                    await self._speaker.say(
                        _failure_announcement(error), task_id=record.task_id, priority=5
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Task %s failure announcement failed", record.task_id)

    async def _set_status(self, record: TaskRecord, generation: int, status: str) -> None:
        if record.generation != generation:
            return
        next_status = TaskStatus(status)
        if record.status == next_status:
            return
        # The tool router reports execution sub-states; ignore callbacks arriving
        # after cancellation or terminal completion.
        if record.status not in ACTIVE_STATUSES:
            return
        record.transition(next_status)

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def get_by_prefix(self, task_id_prefix: str) -> TaskRecord | None:
        matches = [
            record for task_id, record in self._tasks.items()
            if task_id.startswith(task_id_prefix)
        ]
        return matches[0] if len(matches) == 1 else None

    def list_tasks(self) -> list[TaskRecord]:
        return list(self._tasks.values())

    def find_latest_active(self, kind: str | None = None) -> TaskRecord | None:
        for record in reversed(list(self._tasks.values())):
            if self.can_cancel(record) and (kind is None or record.kind == kind):
                return record
        return None

    def active(self) -> list[TaskRecord]:
        return [record for record in self._tasks.values() if self.can_cancel(record)]

    @staticmethod
    def has_active_effects(record: TaskRecord) -> bool:
        return bool(record.side_effects)

    @classmethod
    def can_cancel(cls, record: TaskRecord) -> bool:
        return record.status in ACTIVE_STATUSES or cls.has_active_effects(record)

    @classmethod
    def _can_update(cls, record: TaskRecord) -> bool:
        return record.status in ACTIVE_STATUSES or (
            record.status == TaskStatus.COMPLETED and cls.has_active_effects(record)
        )

    async def shutdown(self) -> None:
        workers = []
        for record in self._tasks.values():
            if record.status in ACTIVE_STATUSES:
                record.generation += 1
            if record.worker is not None and not record.worker.done():
                if record.status in ACTIVE_STATUSES:
                    self._retire(record.worker)
                workers.append(record.worker)
            if record.status in ACTIVE_STATUSES:
                record.transition(TaskStatus.CANCELLED)
            try:
                await self._stop_effects(record)
            except Exception:
                logger.exception("Task %s side-effect shutdown failed", record.task_id)
        workers.extend(worker for worker in self._retired_workers if not worker.done())
        if workers:
            await asyncio.gather(*set(workers), return_exceptions=True)

    def _retire(self, worker: asyncio.Task) -> None:
        self._retired_workers.add(worker)
        worker.add_done_callback(self._retired_workers.discard)
        worker.cancel()

