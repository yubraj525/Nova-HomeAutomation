from __future__ import annotations

from typing import Any

from app.agent.base import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolError,
    validate_tool_name,
)
from app.agent.pending_manager import PendingRequests
from app.agent.registery import ToolRegistry
from app.tasks.resources import ResourceCoordinator


class ToolRouter:
    """Resolve, validate, and execute all tools through one boundary."""

    def __init__(
        self,
        registry: ToolRegistry,
        pending_requests: PendingRequests,
        resources: ResourceCoordinator | None = None,
    ):
        self.registry = registry
        self.pending_requests = pending_requests
        self.resources = resources or ResourceCoordinator()

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_call_id: str | None = None,
        session_id: str | None = None,
        task_id: str | None = None,
        status_callback=None,
        register_side_effect=None,
        request_user_input=None,
    ) -> Any:
        validate_tool_name(tool_name)
        tool = self.registry.get(tool_name)
        validated_arguments = tool.validate_arguments(arguments)
        context = ToolExecutionContext(
            tool_call_id=tool_call_id,
            session_id=session_id,
            task_id=task_id,
            status_callback=status_callback,
            register_side_effect=register_side_effect,
            request_user_input=request_user_input,
        )

        try:
            keys = self.resources.keys_for(tool, validated_arguments)
            if keys and status_callback:
                await status_callback("waiting_for_resource")
            async with self.resources.lease(keys):
                if keys and status_callback:
                    await status_callback("running")
                if getattr(tool, "executor", None) == "remote" and status_callback:
                    await status_callback("waiting_for_tool")
                try:
                    return await tool.execute(validated_arguments, context)
                finally:
                    if status_callback:
                        await status_callback("running")
        except ToolError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"Tool {tool_name!r} failed: {exc}") from exc
