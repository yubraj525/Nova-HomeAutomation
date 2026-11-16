from __future__ import annotations

import asyncio
import json
from typing import Any

from app.agent.base import (
    RemoteClientDisconnectedError,
    RemoteToolTimeoutError,
    ToolExecutionContext,
    ToolExecutionError,
)
from app.agent.pending_manager import PendingRequests
from .base import Tool


class RemoteTool(Tool):
    """Remote implementation using the same validated Tool contract as local tools."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        websocket,
        client_name: str,
        pending_requests: PendingRequests,
        timeout: float = 5.0,
        connection_id: str | None = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.websocket = websocket
        self.client_name = client_name
        self.connection_id = connection_id
        self.pending_requests = pending_requests
        self.timeout = timeout

    async def execute(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext | None = None,
    ) -> Any:
        context = context or ToolExecutionContext()
        request_id, future = self.pending_requests.create(
            tool_name=self.name,
            tool_call_id=context.tool_call_id,
            arguments=arguments,
            source="remote",
            client_name=self.client_name,
            session_id=context.session_id,
            connection_id=self.connection_id,
            task_id=context.task_id,
        )
        payload = {
            "type": "execute_tool",
            "request_id": request_id,
            "tool_name": self.name,
            "arguments": arguments,
        }

        async def send_and_wait():
            await self.websocket.send(json.dumps(payload))
            return await future

        try:
            return await asyncio.wait_for(send_and_wait(), timeout=self.timeout)
        except asyncio.TimeoutError as exc:
            self.pending_requests.discard(request_id)
            raise RemoteToolTimeoutError(
                f"Remote tool {self.name!r} on client {self.client_name!r} timed out."
            ) from exc
        except asyncio.CancelledError:
            self.pending_requests.discard(request_id)
            raise
        except (ConnectionError, OSError) as exc:
            self.pending_requests.discard(request_id)
            raise RemoteClientDisconnectedError(
                f"Remote client {self.client_name!r} disconnected during {self.name!r}."
            ) from exc
        except RuntimeError as exc:
            self.pending_requests.discard(request_id)
            message = str(exc).lower()
            if "disconnect" in message or "closed" in message:
                raise RemoteClientDisconnectedError(
                    f"Remote client {self.client_name!r} disconnected during {self.name!r}."
                ) from exc
            raise ToolExecutionError(f"Remote tool {self.name!r} failed: {exc}") from exc
        except Exception as exc:
            self.pending_requests.discard(request_id)
            # websockets raises its own ConnectionClosed exception; avoid binding this
            # tool contract to a specific websocket implementation by inspecting it.
            if "connectionclosed" in type(exc).__name__.lower():
                raise RemoteClientDisconnectedError(
                    f"Remote client {self.client_name!r} disconnected during {self.name!r}."
                ) from exc
            raise ToolExecutionError(f"Remote tool {self.name!r} failed: {exc}") from exc
