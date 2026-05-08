import asyncio
import time

import cv2
import numpy as np

from app.face.face_tools import FrameBuffer, get_bridge
from app.face.person_memory import get_memory
from app.orchestration.cooldown import CooldownManager
from app.orchestration.event_bus import EventBus
from app.orchestration.state import ConversationState, ConversationStateMachine

POLL_INTERVAL = 1.0


class FaceMonitor:
    def __init__(
        self,
        event_bus: EventBus,
        state_machine: ConversationStateMachine,
        cooldown: CooldownManager,
        preview=None,
    ):
        self.event_bus = event_bus
        self.state = state_machine
        self.cooldown = cooldown
        self.preview = preview
        self._bridge = get_bridge()
        self._memory = get_memory()
        self._prev_face_id = None
        self._unknown_streak = 0
        self._face_present = False
        self._poll_count = 0

    async def run(self):
        fb = FrameBuffer()
        print("[FACE] FaceMonitor started (poll every {}s)".format(POLL_INTERVAL))
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            self._poll_count += 1
            try:
                frame, ts = fb.get()
                if frame is None:
                    continue

                h, w = frame.shape[:2]
                has_face, result = await self._process_frame(frame)
                await self._handle_result(has_face, result, w, h)
                if self.preview is not None:
                    self.preview.update_face(result if has_face else None)
            except Exception as e:
                print(f"[FACE] Error in poll cycle: {e}")

    async def _process_frame(self, frame: np.ndarray) -> tuple[bool, dict | None]:
        small = cv2.resize(frame, None, fx=0.5, fy=0.5)
        t0 = time.time()
        result = self._bridge.recognize(small)
        elapsed = time.time() - t0
        if result is None:
            return False, None
        print(f"[FACE] Recognize result: name={result.get('name')} "
              f"conf={result.get('confidence')} id={result.get('id')} "
              f"unknown={result.get('unknown')} (took {elapsed:.3f}s)")
        return True, result

    async def _handle_result(self, has_face: bool, result: dict | None, frame_w=0, frame_h=0):
        if not has_face:
            if self._face_present:
                print(f"[FACE] Face LOST (was: id={self._prev_face_id})")
                self._face_present = False
                self._unknown_streak = 0
                await self.event_bus.publish("face_lost", {"id": self._prev_face_id})
                self._prev_face_id = None
            return

        self._face_present = True
        self.cooldown.touch_face()

        if result and not result.get("unknown", True):
            face_id = result["id"]
            name = result.get("name", "unknown")
            conf = result.get("confidence", 0)
            self._unknown_streak = 0

            if face_id != self._prev_face_id:
                print(f"[FACE] ✓ RECOGNIZED: {name} (conf={conf}, id={face_id})")
                self._prev_face_id = face_id
                mem = self._memory.get(face_id, name)
                print(f"[FACE] Memory for {name}: {mem}")
                await self.event_bus.publish("face_recognized", {
                    "id": face_id,
                    "name": name,
                    "confidence": conf,
                    "memory": mem,
                })
        else:
            self._unknown_streak += 1
            if self._prev_face_id is not None:
                print(f"[FACE] Face changed → UNKNOWN (was id={self._prev_face_id})")
                self._prev_face_id = None
                self.cooldown.reset_session()
            if self._unknown_streak == 1 or self._unknown_streak % 5 == 0:
                print(f"[FACE] UNKNOWN streak={self._unknown_streak}")
            await self.event_bus.publish("face_unknown", {
                "streak": self._unknown_streak,
            })
