"""Per-key async resource leases shared by task tool calls."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager


class ResourceCoordinator:
    """Serialize operations that declare the same browser or input resource."""

    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = {}

    def keys_for(self, tool, arguments: dict) -> tuple[str, ...]:
        declared = getattr(tool, "resource_keys", None)
        if callable(declared):
            return tuple(sorted(set(declared(arguments))))
        if declared:
            return tuple(sorted(set(declared)))

        # Remote schemas and wire messages stay unchanged. Infer common resource
        # scopes from the existing remote tool name/arguments when supplied.
        name = getattr(tool, "name", "").lower()
        if "browser" in name:
            tab_id = arguments.get("tab_id") or arguments.get("tabId")
            return (f"browser-tab:{tab_id}",) if tab_id is not None else ("browser",)
        if any(token in name for token in ("mouse", "keyboard", "computer_input")):
            return ("physical-input",)
        return ()

    @asynccontextmanager
    async def lease(self, keys):
        ordered = tuple(sorted(set(keys)))
        locks = [self._locks.setdefault(key, asyncio.Lock()) for key in ordered]
        acquired = []
        try:
            for lock in locks:
                await lock.acquire()
                acquired.append(lock)
            yield
        finally:
            for lock in reversed(acquired):
                lock.release()
