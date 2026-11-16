from collections import deque
from dataclasses import dataclass, field

import numpy as np
import webrtcvad


RATE = 16000
FRAME_MS = 20
FRAME_SIZE = int(RATE * FRAME_MS / 1000)
VOLUME_THRESHOLD = 800
SPEECH_CONFIRM_FRAMES = 5
SILENCE_LIMIT = int(2000 / FRAME_MS)
NO_SPEECH_LIMIT = int(6000 / FRAME_MS)


@dataclass
class VADSessionState:
    """Mutable speech detection state owned by one connected client."""

    vad: object = field(default_factory=lambda: webrtcvad.Vad(3))
    speech_active: bool = False
    silence_frames: int = 0
    speech_frames: int = 0
    no_speech_frames: int = 0
    audio_buffer: list[bytes] = field(default_factory=list)
    pre_buffer: deque = field(default_factory=lambda: deque(maxlen=25))

    def reset(self) -> None:
        self.speech_active = False
        self.silence_frames = 0
        self.speech_frames = 0
        self.no_speech_frames = 0
        self.audio_buffer.clear()
        self.pre_buffer.clear()


async def detect_speech(audio_data: bytes, session) -> None:
    """Update only the supplied session's VAD state and route its audio onward."""
    if session.closed:
        return

    state = session.vad_state
    samples = np.frombuffer(audio_data, dtype=np.int16)
    volume = np.sqrt(np.mean(samples.astype(np.float32) ** 2)) if samples.size else 0
    speech_detected = state.vad.is_speech(audio_data, RATE) and volume > VOLUME_THRESHOLD
    state.pre_buffer.append(audio_data)

    if speech_detected:
        state.no_speech_frames = 0
        state.speech_frames += 1
        if state.speech_frames >= SPEECH_CONFIRM_FRAMES and not state.speech_active:
            print(f"[VAD {session.session_id}] Speech started")
            state.speech_active = True
            state.audio_buffer.extend(state.pre_buffer)
        if state.speech_active:
            state.audio_buffer.append(audio_data)
        state.silence_frames = 0
        return

    state.speech_frames = 0
    if not state.speech_active:
        state.no_speech_frames += 1
        if state.no_speech_frames > NO_SPEECH_LIMIT:
            await session.send_control("stop_stream")
            state.no_speech_frames = 0
        return

    state.silence_frames += 1
    state.audio_buffer.append(audio_data)
    if state.silence_frames > SILENCE_LIMIT:
        print(f"[VAD {session.session_id}] Speech ended")
        audio = b"".join(state.audio_buffer)
        state.reset()
        await session.send_control("stop_stream")
        await session.submit_recording(audio)
