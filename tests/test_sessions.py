import asyncio
import json
import time
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import BaseModel

from app.agent.Agent import Agent
from app.agent.ToolRouter import ToolRouter
from app.agent.base import ExecutionType, Tool, ToolExecutionContext
from app.agent.pending_manager import PendingRequests
from app.agent.registery import ToolRegistry
from app.agent.remoteToolRegistryRouter import RemoteTool
from app.communication.websocket import _complete_remote_response
from app.audio.local_transport import LocalAudioTransport
from app.pipeline import process_audio as process_audio_module
from app.pipeline.process_audio import ProcessAudio
from app.session import SessionManager
from app.vad.vad_detection import detect_speech


def _message(content="reply", tool_calls=None):
    return SimpleNamespace(content=content, reasoning=None, tool_calls=tool_calls)


class FakeCompletions:
    def __init__(self, responses=None, delay=0):
        self.responses = list(responses or [_message()])
        self.calls = []
        self.delay = delay

    def create(self, **kwargs):
        if self.delay:
            time.sleep(self.delay)
        self.calls.append([dict(item) for item in kwargs["messages"]])
        return SimpleNamespace(choices=[SimpleNamespace(message=self.responses.pop(0))])


class FakeClient:
    def __init__(self, responses=None, delay=0):
        self.completions = FakeCompletions(responses, delay)
        self.chat = SimpleNamespace(completions=self.completions)


def _agent(client, session_id, history_limit=20):
    registry = ToolRegistry()
    return Agent(
        registry,
        ToolRouter(registry, PendingRequests()),
        client=client,
        session_id=session_id,
        history_limit=history_limit,
    )


def test_agents_keep_independent_histories_and_do_not_expose_other_session():
    async def run():
        client = FakeClient([_message("a1"), _message("b1"), _message("a2")])
        agent_a = _agent(client, "server-session-a")
        agent_b = _agent(client, "server-session-b")

        await agent_a.run("private alpha")
        await agent_b.run("private beta")
        await agent_a.run("alpha follow-up")

        calls = client.completions.calls
        assert "private alpha" in [m["content"] for m in calls[0] if m["role"] == "user"]
        assert "private beta" not in str(calls[0])
        assert "private beta" in [m["content"] for m in calls[1] if m["role"] == "user"]
        assert "private alpha" not in str(calls[1])
        assert "private alpha" in str(calls[2])
        assert "private beta" not in str(calls[2])

    asyncio.run(run())


def test_simultaneous_runs_in_different_sessions_keep_histories_separate():
    async def run():
        client_a = FakeClient([_message("reply a")], delay=0.02)
        client_b = FakeClient([_message("reply b")], delay=0.02)
        agent_a = _agent(client_a, "session-a")
        agent_b = _agent(client_b, "session-b")
        assert await asyncio.gather(agent_a.run("private a"), agent_b.run("private b")) == ["reply a", "reply b"]
        assert "private a" in str(client_a.completions.calls[0])
        assert "private b" not in str(client_a.completions.calls[0])
        assert "private b" in str(client_b.completions.calls[0])
        assert "private a" not in str(client_b.completions.calls[0])

    asyncio.run(run())


def test_agent_serializes_same_session_and_enforces_turn_history_limit():
    async def run():
        client = FakeClient([_message("one"), _message("two"), _message("three")], delay=0.01)
        agent = _agent(client, "session-a", history_limit=2)
        await asyncio.gather(agent.run("first"), agent.run("second"))
        await agent.run("third")

        assert len(client.completions.calls) == 3
        assert len([m for m in agent.messages if m["role"] == "user"]) == 2
        assert "first" not in str(client.completions.calls[-1])
        assert "second" in str(client.completions.calls[-1])
        assert "third" in str(client.completions.calls[-1])

    asyncio.run(run())


def _tool_call(call_id, name):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments="{}"),
    )


def _assert_tool_history_is_complete(messages):
    for message in messages:
        if message["role"] != "assistant" or "tool_calls" not in message:
            continue
        expected = {call["id"] for call in message["tool_calls"]}
        actual = {
            item.get("tool_call_id")
            for item in messages
            if item["role"] == "tool" and item.get("tool_call_id") in expected
        }
        assert actual == expected


def test_complete_multi_tool_turn_and_history_trimming_keep_complete_exchanges():
    async def run():
        calls = [_tool_call("call-1", "one"), _tool_call("call-2", "two")]
        client = FakeClient([
            _message(None, calls), _message("first done"),
            _message(None, calls), _message("second done"),
        ])
        agent = _agent(client, "session-a", history_limit=1)
        await agent.run("older tool turn")
        assert len([m for m in agent.messages if m["role"] == "tool"]) == 2
        _assert_tool_history_is_complete(agent.messages)

        await agent.run("newer tool turn")
        assert "older tool turn" not in str(agent.messages)
        assert "newer tool turn" in str(agent.messages)
        _assert_tool_history_is_complete(agent.messages)

    asyncio.run(run())


@pytest.mark.parametrize("cancel_point", ["during_completion", "before_tools", "after_one_tool"])
def test_cancelled_agent_turn_restores_valid_history_and_next_turn_works(cancel_point):
    async def run():
        client = FakeClient([_message(None, [_tool_call("one", "one"), _tool_call("two", "two")]), _message("next turn")], delay=0.03)
        agent = _agent(client, "session-a")
        original = [dict(item) for item in agent.messages]
        started = asyncio.Event()
        release = asyncio.Event()

        if cancel_point == "before_tools":
            async def blocked_tools(tool_calls):
                started.set()
                await release.wait()
            agent._execute_tool_calls = blocked_tools
        elif cancel_point == "after_one_tool":
            async def one_then_block(tool_calls):
                agent.messages.append({"role": "tool", "tool_call_id": tool_calls[0].id, "content": "done"})
                started.set()
                await release.wait()
            agent._execute_tool_calls = one_then_block

        task = asyncio.create_task(agent.run("interrupted"))
        if cancel_point == "during_completion":
            await asyncio.sleep(0)
        else:
            await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert agent.messages == original
        _assert_tool_history_is_complete(agent.messages)

        agent._execute_tool_calls = Agent._execute_tool_calls.__get__(agent, Agent)
        assert await agent.run("follow up") == "next turn"
        _assert_tool_history_is_complete(agent.messages)

    asyncio.run(run())


def test_remote_tool_call_retains_originating_session_id():
    async def run():
        pending = PendingRequests()
        session_id = "server-generated-session"
        task_id = "task-context-123"
        observations = []

        class ReplyingWebSocket:
            async def send(self, raw_message):
                message = json.loads(raw_message)
                request = pending.get(message["request_id"])
                observations.append((request["session_id"], request["task_id"], set(message)))
                pending.resolve(message["request_id"], {"ok": True})

        call = SimpleNamespace(
            id="tool-call-1",
            function=SimpleNamespace(name="remote_echo", arguments='{"value":"x"}'),
        )
        client = FakeClient([_message(None, [call]), _message("done")])
        registry = ToolRegistry()
        registry.register(
            RemoteTool(
                "remote_echo",
                "Echo remotely.",
                {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
                ReplyingWebSocket(),
                "pc-1",
                pending,
                connection_id="remote-connection-1",
            ),
            ExecutionType.REMOTE,
        )
        router = ToolRouter(registry, pending)
        agent = Agent(registry, router, client=client, session_id=session_id, task_id=task_id)

        assert await agent.run("use my session tool") == "done"
        assert observations == [(session_id, task_id, {"type", "request_id", "tool_name", "arguments"})]
        assert pending.list() == []

    asyncio.run(run())


def test_remote_response_requires_originating_websocket_and_survives_wrong_owner():
    async def run():
        pending = PendingRequests()
        websocket_a, websocket_b = FakeWebSocket(), FakeWebSocket()
        connection_id_by_socket = {
            websocket_a: "connection-a",
            websocket_b: "connection-b",
        }
        assert websocket_a is not websocket_b
        request_id, future = pending.create(
            "remote_echo", "call", {}, source="remote", client_name="same-name",
            session_id="session-a", connection_id=connection_id_by_socket[websocket_a],
        )

        # A distinct live socket using the same name cannot consume the request.
        assert not _complete_remote_response(
            pending, connection_id_by_socket[websocket_b], "same-name", request_id, "spoofed", None
        )
        assert pending.get(request_id)["connection_id"] == "connection-a"
        assert not future.done()

        # Reconnecting with the same client name gets a different server identity.
        assert not _complete_remote_response(
            pending, "reconnected-a", "same-name", request_id, "stale", None
        )
        assert _complete_remote_response(
            pending, connection_id_by_socket[websocket_a], "same-name", request_id, "valid", None
        )
        assert await future == "valid"
        assert pending.get(request_id) is None

    asyncio.run(run())


def test_remote_response_and_disconnect_cleanup_complete_request_once():
    # PendingRequests is event-loop owned; exercise both possible atomic orderings.
    async def deterministic():
        for response_first in (True, False):
            pending = PendingRequests()
            request_id, future = pending.create(
                "remote_echo", "call", {}, source="remote", client_name="pc",
                session_id="session-a", connection_id="connection-a",
            )
            if response_first:
                assert _complete_remote_response(
                    pending, "connection-a", "pc", request_id, "ok", None
                )
                assert pending.reject_connection("connection-a", "disconnected") == []
            else:
                assert pending.reject_connection("connection-a", "disconnected") == [request_id]
                assert not _complete_remote_response(
                    pending, "connection-a", "pc", request_id, "late", None
                )
            assert future.done()
            assert pending.get(request_id) is None
            if response_first:
                assert await future == "ok"
            else:
                with pytest.raises(RuntimeError, match="disconnected"):
                    await future

    asyncio.run(deterministic())


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


class FakeProcessAudio:
    def __init__(self, agent=None, started=None, completed=None):
        self.agent = agent or SimpleNamespace()
        self.started = started
        self.completed = completed
        self.recordings = []

    async def process_audio(self, path):
        path = Path(path)
        with wave.open(str(path), "rb") as audio_file:
            content = audio_file.readframes(audio_file.getnframes())
        self.recordings.append((path, content))
        if self.started:
            self.started.set()
        if self.completed:
            await self.completed.wait()


def test_two_sessions_process_recordings_independently_and_use_unique_paths(tmp_path):
    async def run():
        pending = PendingRequests()
        processors = {}

        def factory(session_id, websocket):
            processor = FakeProcessAudio()
            processors[session_id] = processor
            return processor

        manager = SessionManager(factory, pending, recording_dir=tmp_path)
        session_a = manager.create(FakeWebSocket())
        session_b = manager.create(FakeWebSocket())
        assert session_a.session_id != session_b.session_id

        await asyncio.gather(
            session_a.submit_recording(b"\x01\x00" * 20),
            session_b.submit_recording(b"\x02\x00" * 20),
        )
        tasks = list(session_a.processing_tasks | session_b.processing_tasks)
        await asyncio.gather(*tasks)

        record_a = processors[session_a.session_id].recordings[0]
        record_b = processors[session_b.session_id].recordings[0]
        assert record_a[0] != record_b[0]
        assert record_a[1] == b"\x01\x00" * 20
        assert record_b[1] == b"\x02\x00" * 20
        assert not record_a[0].exists()
        assert not record_b[0].exists()
        await manager.close(session_a)
        await manager.close(session_b)

    asyncio.run(run())


def test_vad_buffers_are_per_session():
    class AlwaysSpeech:
        def is_speech(self, frame, rate):
            return True

    async def run():
        manager = SessionManager(lambda sid, ws: FakeProcessAudio(), PendingRequests())
        session_a = manager.create(FakeWebSocket())
        session_b = manager.create(FakeWebSocket())
        session_a.vad_state.vad = AlwaysSpeech()
        session_b.vad_state.vad = AlwaysSpeech()
        frame = np.full(320, 2000, dtype=np.int16).tobytes()

        for _ in range(5):
            await detect_speech(frame, session_a)
        await detect_speech(frame, session_b)

        assert session_a.vad_state.speech_active
        assert len(session_a.vad_state.audio_buffer) > len(session_b.vad_state.audio_buffer)
        assert session_b.vad_state.speech_frames == 1
        assert session_a.vad_state.audio_buffer is not session_b.vad_state.audio_buffer
        await manager.close(session_a)
        await manager.close(session_b)

    asyncio.run(run())


def test_vad_speech_endpoint_records_and_dispatches_through_own_session(tmp_path):
    class SpeechThenSilence:
        def __init__(self):
            self.calls = 0

        def is_speech(self, frame, rate):
            self.calls += 1
            return self.calls <= 5

    async def run():
        processor = FakeProcessAudio()
        websocket = FakeWebSocket()
        manager = SessionManager(lambda sid, ws: processor, PendingRequests(), tmp_path)
        session = manager.create(websocket)
        session.vad_state.vad = SpeechThenSilence()
        speech_frame = np.full(320, 2000, dtype=np.int16).tobytes()
        silence_frame = np.zeros(320, dtype=np.int16).tobytes()

        for _ in range(5):
            await detect_speech(speech_frame, session)
        for _ in range(101):
            await detect_speech(silence_frame, session)

        tasks = list(session.processing_tasks)
        assert len(tasks) == 1
        await asyncio.gather(*tasks)
        assert websocket.sent == ["stop_stream"]
        assert len(processor.recordings) == 1
        assert processor.recordings[0][1].startswith(speech_frame)
        assert not processor.recordings[0][0].exists()
        await manager.close(session)

    asyncio.run(run())


def test_session_disconnect_cancels_only_its_tasks_and_pending_requests(tmp_path):
    async def run():
        pending = PendingRequests()
        started_a, started_b = asyncio.Event(), asyncio.Event()
        completed = asyncio.Event()
        processors = {}

        def factory(session_id, websocket):
            processor = FakeProcessAudio(started=started_a if not processors else started_b, completed=completed)
            processors[session_id] = processor
            return processor

        manager = SessionManager(factory, pending, tmp_path)
        session_a = manager.create(FakeWebSocket())
        session_b = manager.create(FakeWebSocket())
        await asyncio.gather(session_a.submit_recording(b"\x01\x00"), session_b.submit_recording(b"\x02\x00"))
        await asyncio.gather(started_a.wait(), started_b.wait())
        request_a, future_a = pending.create("remote", "a", {}, source="remote", client_name="pc", session_id=session_a.session_id)
        request_b, future_b = pending.create("remote", "b", {}, source="remote", client_name="pc", session_id=session_b.session_id)

        await manager.close(session_a)
        assert session_a.closed
        assert not session_b.closed
        assert pending.get(request_a) is None
        assert pending.get(request_b) is not None
        with pytest.raises(asyncio.CancelledError):
            await future_a
        assert not future_b.done()
        assert session_b.processing_tasks

        completed.set()
        await asyncio.gather(*list(session_b.processing_tasks))
        pending.discard(request_b)
        await manager.close(session_b)

    asyncio.run(run())


def test_late_remote_response_cannot_resolve_disconnected_session_request():
    async def run():
        pending = PendingRequests()
        manager = SessionManager(lambda sid, ws: FakeProcessAudio(), pending)
        session = manager.create(FakeWebSocket())
        request_id, future = pending.create(
            "remote_tool", "call-id", {}, source="remote", client_name="pc", session_id=session.session_id
        )

        await manager.close(session)
        assert pending.resolve(request_id, "late result") is False
        assert pending.get(request_id) is None
        with pytest.raises(asyncio.CancelledError):
            await future

    asyncio.run(run())


def test_session_cleanup_is_idempotent_and_removes_recordings(tmp_path):
    async def run():
        manager = SessionManager(lambda sid, ws: FakeProcessAudio(), PendingRequests(), tmp_path)
        session = manager.create(FakeWebSocket())
        await session.submit_recording(b"\x00\x00" * 16)
        path = next(iter(session.recording_paths))
        assert path.exists()

        await manager.close(session)
        await manager.close(session)
        assert session.closed
        assert not path.exists()
        assert manager.get(session.session_id) is None
        assert session.processing_tasks == set()

    asyncio.run(run())


class EchoArgs(BaseModel):
    value: str


class EchoLocalTool(Tool):
    name = "echo"
    description = "Echo the supplied value."
    arguments_model = EchoArgs

    async def execute(self, arguments, context: ToolExecutionContext | None = None):
        return arguments["value"]


def test_single_session_audio_path_and_local_tool_workflow(monkeypatch, tmp_path):
    async def run():
        pending = PendingRequests()
        registry = ToolRegistry()
        registry.register(EchoLocalTool())
        router = ToolRouter(registry, pending)
        session_ws = FakeWebSocket()
        client = FakeClient([_message("voice reply")])
        agents = {}
        spoken = []

        async def fake_speak(text, transport, synthesizer):
            spoken.append(text)

        monkeypatch.setattr(process_audio_module, "speak", fake_speak)
        monkeypatch.setattr(process_audio_module, "_transcribe", lambda path: "recognized words")
        def factory(session_id, websocket):
            agent = Agent(registry, router, client=client, session_id=session_id)
            agents[session_id] = agent
            return ProcessAudio(
                object(), LocalAudioTransport(), agent,
                session_id=session_id, websocket=websocket,
            )

        manager = SessionManager(factory, pending, tmp_path)
        session = manager.create(session_ws)
        recording = tmp_path / "input.wav"
        from app.audio.utils import save_audio
        save_audio(b"\x00\x00" * 32, recording)

        response = await router.execute("echo", {"value": "tool result"}, session_id=session.session_id)
        await session.process_audio.process_audio(str(recording))

        assert response == "tool result"
        assert spoken == ["voice reply"]
        assert session_ws.sent == ["start_stream"]
        assert agents[session.session_id].session_id == session.session_id
        await manager.close(session)

    asyncio.run(run())
