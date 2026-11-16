"""Task identity, lifecycle, and task-local execution memory."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable


class TaskStatus(str, Enum):
    ACCEPTED = "accepted"
    PLANNING = "planning"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_TOOL = "waiting_for_tool"
    WAITING_FOR_RESOURCE = "waiting_for_resource"
    VERIFYING = "verifying"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


VALID_TRANSITIONS = {
    TaskStatus.ACCEPTED: {TaskStatus.PLANNING, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.PLANNING: {TaskStatus.QUEUED, TaskStatus.WAITING_FOR_USER, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.RUNNING: {
        TaskStatus.WAITING_FOR_TOOL, TaskStatus.WAITING_FOR_RESOURCE,
        TaskStatus.VERIFYING, TaskStatus.WAITING_FOR_USER,
        TaskStatus.PLANNING, TaskStatus.CANCELLED, TaskStatus.FAILED,
    },
    TaskStatus.WAITING_FOR_TOOL: {TaskStatus.RUNNING, TaskStatus.PLANNING, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.WAITING_FOR_RESOURCE: {TaskStatus.RUNNING, TaskStatus.PLANNING, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.VERIFYING: {
        TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.WAITING_FOR_USER,
        TaskStatus.PLANNING, TaskStatus.CANCELLED, TaskStatus.FAILED,
    },
    TaskStatus.WAITING_FOR_USER: {
        TaskStatus.RUNNING, TaskStatus.PLANNING, TaskStatus.QUEUED,
        TaskStatus.CANCELLED, TaskStatus.FAILED,
    },
    TaskStatus.COMPLETED: {TaskStatus.PLANNING},
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TaskRecord:
    task_id: str
    instruction: str
    kind: str
    source_session_id: str | None
    status: TaskStatus = TaskStatus.ACCEPTED
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    result: str | None = None
    error: str | None = None
    memory: dict[str, Any] = field(default_factory=dict)
    observations: list[Any] = field(default_factory=list)
    side_effects: dict[str, Callable[[], Awaitable[None]]] = field(default_factory=dict, repr=False)
    history: list[dict[str, Any]] = field(default_factory=list)
    announced: bool = False
    generation: int = 0
    user_reply: asyncio.Future | None = field(default=None, repr=False, compare=False)
    operation_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)
    execution: Any = field(default=None, repr=False, compare=False)
    worker: Any = field(default=None, repr=False, compare=False)

    def transition(self, status: TaskStatus) -> None:
        if status == self.status:
            return
        if status not in VALID_TRANSITIONS[self.status]:
            raise ValueError(f"Invalid task transition: {self.status} -> {status}")
        self.status = status
        self.updated_at = utc_now()

    def public_snapshot(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "instruction": self.instruction,
            "kind": self.kind,
            "source_session_id": self.source_session_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "result": self.result,
            "error": self.error,
            "memory": dict(self.memory),
            "observations": list(self.observations),
            "active_side_effects": list(self.side_effects),
        }
