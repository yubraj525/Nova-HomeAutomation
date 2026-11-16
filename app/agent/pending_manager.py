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
