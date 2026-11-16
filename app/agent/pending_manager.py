from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any


class PendingRequests:
    """Correlate remote tool calls with their replies and clean up failures."""

    def __init__(self):
        self._requests: dict[str, dict[str, Any]] = {}

    def create(
        self,
        tool_name: str,
        tool_call_id: str | None,
        arguments: dict,
        source: str = "local",
        client_name: str | None = None,
        session_id: str | None = None,
        connection_id: str | None = None,
        task_id: str | None = None,
    ):
        request_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self._requests[request_id] = {
            "request_id": request_id,
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "source": source,
            "client_name": client_name,
            "session_id": session_id,
            "connection_id": connection_id,
            "task_id": task_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "future": future,
        }
        return request_id, future

    def resolve(self, request_id: str, result: Any) -> bool:
        request = self._requests.pop(request_id, None)
        if request is None:
            return False
        future = request["future"]
        if not future.done():
            future.set_result(result)
        return True

    def reject(self, request_id: str, error: str | Exception) -> bool:
        request = self._requests.pop(request_id, None)
        if request is None:
            return False
        future = request["future"]
        if not future.done():
            future.set_exception(error if isinstance(error, Exception) else RuntimeError(error))
        return True

    def reject_client(self, client_name: str, error: str) -> list[str]:
        """Fail all outstanding calls owned by a disconnected remote client."""
        request_ids = [
            request_id
            for request_id, request in self._requests.items()
            if request["client_name"] == client_name and request["source"] == "remote"
        ]
        for request_id in request_ids:
            self.reject(request_id, error)
        return request_ids

    def reject_session(self, session_id: str, error: str) -> list[str]:
        """Reject and remove outstanding requests owned by one session."""
        request_ids = [
            request_id
            for request_id, request in self._requests.items()
            if request["session_id"] == session_id
        ]
        for request_id in request_ids:
            self.reject(request_id, error)
        return request_ids

    def complete_owned(
        self,
        request_id: str,
        connection_id: str,
        *,
        result: Any = None,
        error: str | Exception | None = None,
    ) -> bool:
        """Atomically complete a remote request only for its originating connection."""
        request = self._requests.get(request_id)
        if (
            request is None
            or request["source"] != "remote"
            or request["connection_id"] != connection_id
        ):
            return False
        # Pop and complete synchronously, so another response or disconnect cannot
        # also consume this request on the event loop.
        self._requests.pop(request_id)
        future = request["future"]
        if not future.done():
            if error is not None:
                future.set_exception(error if isinstance(error, Exception) else RuntimeError(error))
            else:
                future.set_result(result)
        return True

    def reject_connection(self, connection_id: str, error: str) -> list[str]:
        """Reject outstanding calls from exactly one remote WebSocket connection."""
        request_ids = [
            request_id
            for request_id, request in self._requests.items()
            if request["source"] == "remote" and request["connection_id"] == connection_id
        ]
        for request_id in request_ids:
            self.reject(request_id, error)
        return request_ids

    def cancel_session(self, session_id: str) -> list[str]:
        """Cancel and remove any remaining work after session tasks are stopped."""
        request_ids = [
            request_id
            for request_id, request in self._requests.items()
            if request["session_id"] == session_id
        ]
        for request_id in request_ids:
            self.discard(request_id)
        return request_ids

    def discard(self, request_id: str) -> bool:
        """Remove a timed-out/cancelled call without leaving a pending future."""
        request = self._requests.pop(request_id, None)
        if request is None:
            return False
        future = request["future"]
        if not future.done():
            future.cancel()
        return True

    def list(self):
        return [
            {key: value for key, value in request.items() if key != "future"}
            for request in self._requests.values()
        ]

    def get(self, request_id: str):
        request = self._requests.get(request_id)
        if request is None:
            return None
        return {key: value for key, value in request.items() if key != "future"}
