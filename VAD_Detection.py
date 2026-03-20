
from save_audio import save_audio
import numpy as np
import websockets
import webrtcvad 
from collections import deque
from Process_audio import process_audio


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

async def detect_speech(audio_data):
            global speech_active
            global silence_frames
            global speech_frames
            global audio_buffer

      
            frame = audio_data

            audio = np.frombuffer(frame, dtype=np.int16)

            volume = np.sqrt(np.mean(audio.astype(np.float32)**2))

            vad_result = vad.is_speech(frame, RATE)

            is_speech = vad_result and volume > VOLUME_THRESHOLD

            pre_buffer.append(frame)

            if is_speech:

                speech_frames += 1

                if speech_frames >= SPEECH_CONFIRM_FRAMES and not speech_active:

                    print("Speech started")

                    speech_active = True
                    audio_buffer.extend(pre_buffer)

                if speech_active:

                    audio_buffer.append(frame)

                silence_frames = 0

            else:

                speech_frames = 0

                if speech_active:

                    silence_frames += 1
                    audio_buffer.append(frame)

                    if silence_frames > SILENCE_LIMIT:

                        print("Speech ended")

                        audio = b''.join(audio_buffer)
                        save_audio(audio)
                        from websocket import get_WSconnection
                        websocket = get_WSconnection()
                        await websocket.send("stop_stream")
                       
                        await process_audio()  # ← process after each speech segment!

                        speech_active = False
                        silence_frames = 0
                        audio_buffer = []
                        