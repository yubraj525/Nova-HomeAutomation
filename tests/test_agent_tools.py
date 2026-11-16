import asyncio
import json
from datetime import datetime

import pytest
from pydantic import BaseModel

from app.agent.ToolRouter import ToolRouter
from app.agent.base import (
    ExecutionType,
    RemoteClientDisconnectedError,
    RemoteToolTimeoutError,
    Tool,
    ToolArgumentError,
    ToolExecutionContext,
    ToolExecutionError,
    ToolRegistrationError,
    UnknownToolError,
)
from app.agent.pending_manager import PendingRequests
from app.agent.registery import ToolRegistry
from app.agent.remoteToolRegistryRouter import RemoteTool
from app.agent.tools.calculator import CalculatorTool
from app.agent.tools.currenTime import GetTimeTool


class FailingArgs(BaseModel):
    value: int


class FailingTool(Tool):
    name = "failing_tool"
    description = "Raises an error for dispatch regression coverage."
    arguments_model = FailingArgs

    async def execute(self, arguments, context: ToolExecutionContext | None = None):
        raise RuntimeError("expected failure")


class FakeWebSocket:
    def __init__(self, on_send=None, send_error=None):
        self.on_send = on_send
        self.send_error = send_error
        self.sent = []

    async def send(self, message):
        if self.send_error:
            raise self.send_error
        self.sent.append(message)
        if self.on_send:
            await self.on_send(message)


def _router(*tools):
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    pending = PendingRequests()
    return ToolRouter(registry, pending), registry, pending


def test_local_tool_registration_and_schema():
    _, registry, _ = _router(CalculatorTool(), GetTimeTool())
    schemas = registry.get_tool_schemas()
    assert [schema["function"]["name"] for schema in schemas] == ["calculator", "get_time"]
    assert all(schema["function"]["parameters"]["type"] == "object" for schema in schemas)


def test_registration_rejects_duplicate_name_and_invalid_remote_schema():
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    with pytest.raises(ToolRegistrationError, match="already registered"):
        registry.register(CalculatorTool())

    remote = RemoteTool(
        name="remote_invalid",
        description="Invalid schema",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "not-a-json-schema-type"}},
        },
        websocket=FakeWebSocket(),
        client_name="pc-a",
        pending_requests=PendingRequests(),
    )
    with pytest.raises(ToolRegistrationError, match="Invalid tool parameters schema"):
        registry.register(remote, ExecutionType.REMOTE)

    unsupported = RemoteTool(
        name="remote_unsupported",
        description="External schema reference",
        parameters={
            "type": "object",
            "properties": {"value": {"$ref": "https://example.invalid/schema.json"}},
        },
        websocket=FakeWebSocket(),
        client_name="pc-a",
        pending_requests=PendingRequests(),
    )
    with pytest.raises(ToolRegistrationError, match="External schema reference"):
        registry.register(unsupported, ExecutionType.REMOTE)

    invalid_name = RemoteTool(
        name="bad.name",
        description="Invalid name",
        parameters={"type": "object", "properties": {}},
        websocket=FakeWebSocket(),
        client_name="pc-a",
        pending_requests=PendingRequests(),
    )
    with pytest.raises(ToolRegistrationError, match="Tool names"):
        registry.register(invalid_name, ExecutionType.REMOTE)


def test_local_calculator_dispatch():
    async def run():
        router, _, _ = _router(CalculatorTool())
        assert await router.execute("calculator", {"a": 4, "b": 3, "operation": "multiply"}) == 12
        assert await router.execute("calculator", {"a": 7, "b": 2, "operation": "divide"}) == 3.5

    asyncio.run(run())


def test_local_time_tool_dispatch():
    async def run():
        router, _, _ = _router(GetTimeTool())
        value = await router.execute("get_time", {})
        assert datetime.fromisoformat(value)

    asyncio.run(run())


def test_invalid_arguments_rejected_before_execution():
    async def run():
        router, _, _ = _router(CalculatorTool())
        with pytest.raises(ToolArgumentError, match="Unexpected argument"):
            await router.execute("calculator", {"a": 1, "b": 2, "operation": "add", "extra": 3})
        with pytest.raises(ToolArgumentError):
            await router.execute("calculator", {"a": "not-a-number", "b": 2, "operation": "add"})
        with pytest.raises(ToolArgumentError):
            await router.execute("calculator", {"a": 1, "b": 2, "operation": "power"})

    asyncio.run(run())


def test_unknown_tool_and_tool_execution_failure_are_explicit():
    async def run():
        router, _, _ = _router(FailingTool())
        with pytest.raises(UnknownToolError, match="not registered"):
            await router.execute("not_registered", {})
        with pytest.raises(ToolExecutionError, match="expected failure"):
            await router.execute("failing_tool", {"value": 1})

    asyncio.run(run())


def test_remote_tool_dispatch_uses_validated_contract_and_correlates_response():
    async def run():
        pending = PendingRequests()

        async def respond(message):
            payload = json.loads(message)
            assert payload["tool_name"] == "search_notes"
            assert payload["arguments"] == {"query": "NOVA"}
            request = pending.get(payload["request_id"])
            assert request["tool_call_id"] == "call-123"
            pending.resolve(payload["request_id"], {"matches": 2})

        websocket = FakeWebSocket(on_send=respond)
        remote = RemoteTool(
            name="search_notes",
            description="Search notes.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string", "minLength": 1}},
                "required": ["query"],
                "additionalProperties": False,
            },
            websocket=websocket,
            client_name="pc-a",
            pending_requests=pending,
        )
        registry = ToolRegistry()
        registry.register(remote, ExecutionType.REMOTE)
        router = ToolRouter(registry, pending)
        result = await router.execute("search_notes", {"query": "NOVA"}, tool_call_id="call-123")
        assert result == {"matches": 2}
        assert pending.list() == []
        with pytest.raises(ToolArgumentError):
            await router.execute("search_notes", {"query": "", "extra": True})

    asyncio.run(run())


def test_remote_timeout_cleans_pending_request():
    async def run():
        pending = PendingRequests()
        remote = RemoteTool(
            name="slow_tool",
            description="Never replies.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            websocket=FakeWebSocket(),
            client_name="pc-a",
            pending_requests=pending,
            timeout=0.01,
        )
        registry = ToolRegistry()
        registry.register(remote, ExecutionType.REMOTE)
        with pytest.raises(RemoteToolTimeoutError, match="timed out"):
            await ToolRouter(registry, pending).execute("slow_tool", {})
        assert pending.list() == []

    asyncio.run(run())


def test_remote_disconnected_during_send_is_explicit_and_cleaned():
    async def run():
        pending = PendingRequests()
        remote = RemoteTool(
            name="offline_tool",
            description="Client is offline.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            websocket=FakeWebSocket(send_error=ConnectionError("socket closed")),
            client_name="pc-a",
            pending_requests=pending,
        )
        registry = ToolRegistry()
        registry.register(remote, ExecutionType.REMOTE)
        with pytest.raises(RemoteClientDisconnectedError, match="disconnected"):
            await ToolRouter(registry, pending).execute("offline_tool", {})
        assert pending.list() == []

    asyncio.run(run())


def test_disconnected_remote_client_rejects_waiters_and_unregisters_its_tools():
    async def run():
        pending = PendingRequests()
        websocket = FakeWebSocket()
        remote = RemoteTool(
            name="waiting_tool",
            description="Waits for a reply.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            websocket=websocket,
            client_name="pc-a",
            pending_requests=pending,
        )
        registry = ToolRegistry()
        registry.register(remote, ExecutionType.REMOTE)
        task = asyncio.create_task(ToolRouter(registry, pending).execute("waiting_tool", {}))
        await asyncio.sleep(0)
        assert len(pending.list()) == 1
        pending.reject_client("pc-a", "Remote client disconnected.")
        with pytest.raises(RemoteClientDisconnectedError):
            await task
        assert registry.unregister_remote_client("pc-a", websocket) == ["waiting_tool"]
        with pytest.raises(UnknownToolError):
            registry.get("waiting_tool")

    asyncio.run(run())
