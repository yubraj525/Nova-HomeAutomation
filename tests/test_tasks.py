import asyncio

from app.audio import speaker_manager as speaker_module
from app.audio.speaker_manager import SpeakerManager
from app.tasks.coordinator import CommandCoordinator
from app.tasks.manager import TaskManager, _failure_announcement
from app.tasks.models import TaskStatus
from app.tasks.resources import ResourceCoordinator
from types import SimpleNamespace
from app.core.runtime import NovaRuntime
from app.agent.registery import ToolRegistry


def test_failure_announcement_extracts_only_embedded_response():
    generated = '{"name": "JSON", "arguments": {"response": "म राम्रो छु, धन्यवाद!"}}'
    provider_body = {
        "error": {
            "message": "Tool call validation failed",
            "failed_generation": generated,
        }
    }
    error = RuntimeError(f"Error code: 400 - {provider_body!r}")

    assert _failure_announcement(error) == "म राम्रो छु, धन्यवाद!"
    assert _failure_announcement(RuntimeError("network unavailable")) == (
        "माफ गर्नुहोस्, यो अनुरोध पूरा गर्न सकिनँ।"
    )


class BlockingAgent:
    def __init__(self, gates, started, slot):
        self.messages = [{"role": "system", "content": "isolated"}]
        self.gates = gates
        self.started = started
        self.calls = 0
        self.slot = slot

    async def run(self, instruction):
        self.calls += 1
        self.messages.append({"role": "user", "content": instruction})
        index = self.slot + self.calls - 1
        self.started[index].set()
        await self.gates[index].wait()
        self.messages.append({"role": "assistant", "content": instruction})
        return instruction


def _task_manager():
    gates = [asyncio.Event() for _ in range(8)]
    started = [asyncio.Event() for _ in range(8)]
    agents = []
    next_slot = 0

    def factory(task_id, session_id, status_callback, observation_callback, register_side_effect, request_user_input):
        nonlocal next_slot
        agent = BlockingAgent(gates, started, next_slot)
        next_slot += 2
        agents.append(agent)
        return agent

    return TaskManager(factory), gates, started, agents


def test_tasks_execute_concurrently_with_isolated_agents_and_cancel_independently():
    async def run():
        manager, gates, started, agents = _task_manager()
        task_a = await manager.create("do music", "session", "music")
        task_b = await manager.create("do email", "session", "email")
        assert task_a.task_id != task_b.task_id
        assert task_a.execution is not task_b.execution

        await asyncio.gather(started[0].wait(), started[2].wait())
        assert task_a.status == task_b.status == TaskStatus.RUNNING
        assert "do music" not in str(task_b.execution.messages)
        assert "do email" not in str(task_a.execution.messages)

        assert await manager.cancel(task_a.task_id)
        assert task_a.status == TaskStatus.CANCELLED
        assert task_b.status == TaskStatus.RUNNING
        gates[2].set()
        await task_b.worker
        assert task_b.status == TaskStatus.COMPLETED
        await manager.shutdown()

    asyncio.run(run())


def test_coordinator_updates_existing_music_task_without_blocking_intake():
    async def run():
        manager, gates, started, agents = _task_manager()
        coordinator = CommandCoordinator(manager)
        first = await coordinator.submit("Play Olivia Rodrigo", "esp-session")
        task_id = first["task"]["task_id"]
        await started[0].wait()

        update = await coordinator.submit("Play Badshah instead", "esp-session")
        assert update["action"] == "updated"
        assert update["task"]["task_id"] == task_id
        await started[2].wait()
        record = manager.get(task_id)
        assert record.instruction == "Play Badshah instead"
        assert record.memory["updates"] == 1

        gates[2].set()
        await record.worker
        assert record.status == TaskStatus.COMPLETED
        await manager.shutdown()

    asyncio.run(run())


def test_coordinator_can_cancel_task_using_spoken_short_id():
    async def run():
        manager, gates, started, agents = _task_manager()
        coordinator = CommandCoordinator(manager)
        result = await coordinator.submit("Play a song")
        record = manager.get(result["task"]["task_id"])
        await started[0].wait()

        cancelled = await coordinator.submit(f"cancel task {record.task_id[:8]}")
        assert cancelled["action"] == "cancelled"
        assert cancelled["task_id"] == record.task_id
        assert record.status == TaskStatus.CANCELLED
        await manager.shutdown()

    asyncio.run(run())


def test_task_can_wait_for_and_receive_user_input():
    async def run():
        class QuestionAgent:
            def __init__(self, request_user_input):
                self.messages = [{"role": "system", "content": "isolated"}]
                self.request_user_input = request_user_input

            async def run(self, instruction):
                answer = await self.request_user_input("Which account should I use?")
                self.messages.append({"role": "tool", "content": answer})
                return answer

        def factory(task_id, session_id, status, observation, register_effect, request_user_input):
            return QuestionAgent(request_user_input)

        manager = TaskManager(factory)
        coordinator = CommandCoordinator(manager)
        created = await coordinator.submit("Send an email", "esp")
        record = manager.get(created["task"]["task_id"])
        for _ in range(100):
            if record.status == TaskStatus.WAITING_FOR_USER:
                break
            await asyncio.sleep(0)
        assert record.status == TaskStatus.WAITING_FOR_USER

        answer = await coordinator.submit("Use my personal Gmail", "esp")
        assert answer == {"action": "answered", "task_id": record.task_id}
        await record.worker
        assert record.status == TaskStatus.COMPLETED
        assert record.result == "Use my personal Gmail"

    asyncio.run(run())


def test_task_state_transitions_reject_invalid_changes():
    async def run():
        manager, gates, started, agents = _task_manager()
        record = await manager.create("work", None)
        try:
            record.transition(TaskStatus.ACCEPTED)
        except ValueError:
            pass
        else:
            raise AssertionError("terminal transition validation was not applied")
        await manager.cancel(record.task_id)

    asyncio.run(run())


def test_slow_task_cancellation_does_not_block_new_command_acceptance():
    async def run():
        started = asyncio.Event()
        cancelling = asyncio.Event()
        cleanup = asyncio.Event()

        class SlowCleanupAgent:
            messages = [{"role": "system", "content": "isolated"}]

            async def run(self, instruction):
                started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelling.set()
                    await cleanup.wait()
                    raise

        manager = TaskManager(lambda *args: SlowCleanupAgent())
        slow = await manager.create("slow", None)
        await started.wait()
        cancel_task = asyncio.create_task(manager.cancel(slow.task_id))
        await cancelling.wait()

        # This create would stall if cancel held the global task registry lock
        # while waiting for the old worker to clean up.
        next_task = await asyncio.wait_for(manager.create("new command", None), timeout=0.2)
        assert next_task.status in (TaskStatus.QUEUED, TaskStatus.RUNNING)
        cleanup.set()
        assert await cancel_task
        await manager.cancel(next_task.task_id)

    asyncio.run(run())


def test_speaker_manager_serializes_requests(monkeypatch):
    async def run():
        active = 0
        maximum_active = 0

        async def fake_speak(text, transport, synthesizer):
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            await asyncio.sleep(0.01)
            active -= 1

        monkeypatch.setattr(speaker_module, "speak", fake_speak)
        speaker = SpeakerManager(object(), object())
        await asyncio.gather(
            speaker.say("first", task_id="task-a"),
            speaker.say("second", task_id="task-b"),
        )
        assert maximum_active == 1
        await speaker.close()

    asyncio.run(run())


def test_resource_coordinator_serializes_same_tab_and_allows_independent_tabs():
    async def run():
        resources = ResourceCoordinator()
        active = 0
        maximum_active = 0

        async def use_tab(tab_id):
            nonlocal active, maximum_active
            keys = resources.keys_for(
                SimpleNamespace(name="browser_click"), {"tab_id": tab_id}
            )
            async with resources.lease(keys):
                active += 1
                maximum_active = max(maximum_active, active)
                await asyncio.sleep(0.01)
                active -= 1

        await asyncio.gather(use_tab("tab-a"), use_tab("tab-a"))
        assert maximum_active == 1
        maximum_active = 0
        await asyncio.gather(use_tab("tab-a"), use_tab("tab-b"))
        assert maximum_active == 2
        assert resources.keys_for(
            SimpleNamespace(name="computer_mouse_click"), {}
        ) == ("physical-input",)

    asyncio.run(run())


def test_completed_task_can_own_and_cancel_a_persistent_side_effect():
    async def run():
        stopped = []

        class MusicAgent:
            messages = [{"role": "system", "content": "music"}]

            async def run(self, instruction):
                async def stop_playback():
                    stopped.append(instruction)

                register("music-playback", stop_playback)
                self.messages.append({"role": "user", "content": instruction})
                return "Playback started"

        def factory(task_id, session_id, status, observation, register_effect, request_user_input):
            nonlocal register
            register = register_effect
            return MusicAgent()

        register = None
        manager = TaskManager(factory)
        task = await manager.create("Play Olivia Rodrigo", None, "music")
        await task.worker
        assert task.status == TaskStatus.COMPLETED
        assert manager.find_latest_active("music") is task
        assert task.public_snapshot()["active_side_effects"] == ["music-playback"]

        updated = await manager.update(task.task_id, "Play Badshah instead")
        await updated.worker
        assert updated.task_id == task.task_id
        assert updated.status == TaskStatus.COMPLETED
        assert updated.instruction == "Play Badshah instead"
        assert stopped == ["Play Olivia Rodrigo"]

        assert await manager.cancel(task.task_id)
        assert updated.status == TaskStatus.COMPLETED
        assert stopped == ["Play Olivia Rodrigo", "Play Badshah instead"]
        assert not updated.side_effects

    asyncio.run(run())


def test_runtime_shares_services_but_constructs_independent_audio_sessions(monkeypatch):
    async def run():
        monkeypatch.setattr("app.tts.nepanglish_tts.get_synthesizer", lambda: object())
        runtime = NovaRuntime()
        await runtime.initialize(ToolRegistry())
        session_a = runtime.session_manager.create(object())
        session_b = runtime.session_manager.create(object())
        assert session_a.session_id != session_b.session_id
        assert session_a.process_audio is not session_b.process_audio
        assert session_a.process_audio.coordinator is runtime.coordinator
        assert session_b.process_audio.coordinator is runtime.coordinator
        assert runtime.coordinator.task_manager is runtime.task_manager
        assert runtime.router.resources is runtime.resources
        await runtime.shutdown()

    asyncio.run(run())
