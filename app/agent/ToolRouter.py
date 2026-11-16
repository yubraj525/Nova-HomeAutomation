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


class ToolRouter:
    """Resolve, validate, and execute all tools through one boundary."""

    def __init__(self, registry: ToolRegistry, pending_requests: PendingRequests):
        self.registry = registry
        self.pending_requests = pending_requests

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_call_id: str | None = None,
    ) -> Any:
        validate_tool_name(tool_name)
        tool = self.registry.get(tool_name)
        validated_arguments = tool.validate_arguments(arguments)
        context = ToolExecutionContext(tool_call_id=tool_call_id)

        try:
            return await tool.execute(validated_arguments, context)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"Tool {tool_name!r} failed: {exc}") from exc
