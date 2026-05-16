
from collections import deque

import numpy as np
import webrtcvad

from app.pipeline.process_audio import process_audio
from app.audio.utils import save_audio

# speech_active = False
# silence_frames = 0
# speech_frames = 0
# audio_buffer = []

# pre_buffer = deque(maxlen=25)
# RATE = 16000
# FRAME_MS = 20
# FRAME_SIZE = int(RATE * FRAME_MS / 1000)

# vad = webrtcvad.Vad(3)

# VOLUME_THRESHOLD = 600
# SPEECH_CONFIRM_FRAMES = 5
# SILENCE_LIMIT = int(2000 / FRAME_MS)

# async def detect_speech(audio_data):
#             global speech_active
#             global silence_frames
#             global speech_frames
#             global audio_buffer

      
#             frame = audio_data

#             audio = np.frombuffer(frame, dtype=np.int16)

#             volume = np.sqrt(np.mean(audio.astype(np.float32)**2))

#             vad_result = vad.is_speech(frame, RATE)

#             is_speech = vad_result and volume > VOLUME_THRESHOLD

#             pre_buffer.append(frame)

#             if is_speech:

#                 speech_frames += 1

#                 if speech_frames >= SPEECH_CONFIRM_FRAMES and not speech_active:

#                     print("Speech started")

#                     speech_active = True
#                     audio_buffer.extend(pre_buffer)

#                 if speech_active:

#                     audio_buffer.append(frame)

#                 silence_frames = 0

#             else:

#                 speech_frames = 0

#                 if speech_active:

#                     silence_frames += 1
#                     audio_buffer.append(frame)

#                     if silence_frames > SILENCE_LIMIT:

#                         print("Speech ended")

#                         audio = b''.join(audio_buffer)
#                         save_audio(audio)
#                         from app.communication.websocket import get_WSconnection
#                         websocket = get_WSconnection()
#                         await websocket.send("stop_stream")
                       
#                         await process_audio()  # ← process after each speech segment!

#                         speech_active = False
#                         silence_frames = 0
#                         audio_buffer = []
                        






speech_active = False
silence_frames = 0
speech_frames = 0
audio_buffer = []

pre_buffer = deque(maxlen=25)
RATE = 16000
FRAME_MS = 20
FRAME_SIZE = int(RATE * FRAME_MS / 1000)

vad = webrtcvad.Vad(3)

VOLUME_THRESHOLD = 600
SPEECH_CONFIRM_FRAMES = 5
SILENCE_LIMIT = int(2000 / FRAME_MS)

no_speech_frames = 0  # NEW
NO_SPEECH_LIMIT = int(6000 / FRAME_MS)  # 4 sec

async def detect_speech(audio_data):
    global speech_active
    global silence_frames
    global speech_frames
    global audio_buffer
    global no_speech_frames   # NEW

    frame = audio_data
    audio = np.frombuffer(frame, dtype=np.int16)

    volume = np.sqrt(np.mean(audio.astype(np.float32)**2))
    vad_result = vad.is_speech(frame, RATE)

    is_speech = vad_result and volume > VOLUME_THRESHOLD

    pre_buffer.append(frame)

    # -------------------------
    # CASE 1: SPEECH DETECTED
    # -------------------------
    if is_speech:

        no_speech_frames = 0  # RESET idle timer

        speech_frames += 1

        if speech_frames >= SPEECH_CONFIRM_FRAMES and not speech_active:
            print("Speech started")
            speech_active = True
            audio_buffer.extend(pre_buffer)

        if speech_active:
            audio_buffer.append(frame)

        silence_frames = 0

    # -------------------------
    # CASE 2: NO SPEECH
    # -------------------------
    else:
        speech_frames = 0

        # 🔴 NEW: Handle "no speech at all"
        if not speech_active:
            no_speech_frames += 1

            if no_speech_frames > NO_SPEECH_LIMIT:
                print("No speech detected for 4 seconds → stopping stream")

                from app.communication.websocket import send_websocket_message
                await send_websocket_message("stop_stream")
              

                no_speech_frames = 0
                return

        # -------------------------
        # EXISTING: speech ended
        # -------------------------
        if speech_active:
            silence_frames += 1
            audio_buffer.append(frame)

            if silence_frames > SILENCE_LIMIT:
                print("Speech ended")

                audio = b''.join(audio_buffer)
                save_audio(audio)

                from app.communication.websocket import send_websocket_message
                await send_websocket_message("stop_stream")

                await process_audio()

                speech_active = False
                silence_frames = 0
                audio_buffer = []