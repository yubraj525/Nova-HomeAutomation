# Nova

Nova is a multi-language, voice-enabled AI assistant for home automation, media control, and natural conversation. It supports English and Nepali, integrates with ESP32-based IoT hardware, and can stream music from YouTube with yt-dlp.

## Features

- Voice interaction in English and Nepali
- AI-powered conversational responses through Groq
- Emotion-aware text-to-speech with Kokoro for English and Edge TTS for Nepali
- ESP32 / IoT device control over WebSocket
- YouTube music playback through yt-dlp
- Media controls for play, pause, resume, and stop
- Offline Nepali / Nepanglish speech recognition with sherpa-onnx Whisper-tiny

## Architecture

```text
User (Voice or Text)
        |
        v
   AI Engine (LLM)
        |
        v
 JSON Response Parser
        |
        +---------------------+----------------------+----------------------+
        |                     |                      |
        v                     v                      v
   TTS Engine           Command Handler          Music System
        |                     |                      |
        v                     v                      v
   Audio Output          ESP32 / IoT            yt-dlp / local audio
```

Music flow:

```text
User request -> intent extraction -> yt-dlp search -> audio download / conversion -> playback
```

## Tech Stack

### Python / Software

- Python 3.9+
- FastAPI and Uvicorn for the API server
- WebSockets for live audio and device communication
- Groq SDK for conversational responses
- Kokoro ONNX for English TTS
- Edge TTS for Nepali TTS
- yt-dlp for music search and streaming support
- sherpa-onnx for offline speech recognition
- pygame, sounddevice, soundfile, pydub, and scipy for audio handling

### Hardware

- ESP32 or ESP32-CAM
- I2S microphone and speaker path
- DAC / I2S audio module such as MAX98357A
- External amplifier such as TDA7297 or TDA2030 for larger speakers
- Speaker system and optional sensors / actuators

See [Hardware/MCU.txt](Hardware/MCU.txt) for the current ESP32 wiring and streaming notes.

## Python Requirements

Install the project dependencies with:

```bash
pip install -r requirements.txt
```

Runtime and helper packages used by the project:

- edge-tts
- fastapi
- groq
- kokoro-onnx
- numpy
- ollama
- openwakeword
- pyaudio
- pydub
- pygame
- python-dotenv
- scipy
- sherpa-onnx
- sounddevice
- soundfile
- uvicorn
- webrtcvad-wheels
- websockets
- yt-dlp

Optional packages used by local tests and experiments:

- google-genai
- pytest

System-level tools that should also be installed:

- ffmpeg for audio conversion and playback workflows
- a working microphone and speaker output device

## Model Requirements

### Groq API

Create a `.env` file in the project root and set:

```env
GROQ=your_groq_api_key_here
```

Some legacy test scripts also look for `GROQ_API_KEY`, so you can set both if you want compatibility with older helpers.

### Kokoro English TTS

The app expects these files under `models/`:

```text
models/kokoro-v1.0.int8.onnx
models/voices-v1.0.bin
```

If you only have the Kokoro files at the repository root, the installer script will copy them into `models/`.

### Offline Sherpa STT

Download the whisper-tiny model with:

```bash
python scripts/download_stt_model.py
```

That script places the required files under:

```text
models/sherpa/sherpa-onnx-whisper-tiny/
```

Required files:

- tiny-encoder.int8.onnx
- tiny-decoder.int8.onnx
- tiny-tokens.txt

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/nova-home-automation.git
cd nova-home-automation
```

### 2. Run the one-shot installer

The recommended setup path is:

```bash
bash scripts/setup_nova.sh
```

That script will:

- create or reuse a virtual environment
- install all Python requirements
- download the offline sherpa model
- copy the available Kokoro model files into `models/`
- verify `ffmpeg` and `yt-dlp`

### 3. Configure environment variables

Create a `.env` file in the project root with your Groq key:

```env
GROQ=your_groq_api_key_here
```

## Run Nova

From the project root:

```bash
python app/main.py
```

Example interaction:

```text
User: Turn on the lights
Nova: Lights have been turned on.

User: Play Nepali song
Nova: Playing a Nepali song from YouTube.
```

## Hardware Setup

Suggested signal flow:

```text
ESP32 microphone input -> WebSocket server -> STT / LLM / TTS -> ESP32 speaker output
```

The current hardware notes in [Hardware/MCU.txt](Hardware/MCU.txt) use:

- I2S microphone on the ESP32
- I2S speaker output on the ESP32
- Wi-Fi WebSocket communication with the Python server
- Audio playback at 24 kHz mono for the speaker path

If you are wiring an external audio chain, the usual layout is:

```text
ESP32 -> I2S / DAC -> Amplifier -> Speaker
```

## Verification

Run the check script to validate the local environment and API access:

```bash
bash scripts/test_nova_setup.sh
```

The script checks:

- Required model files on disk
- Python imports used by the project
- Kokoro model loading and sample generation
- sherpa-onnx model loading and a local transcription pass
- Groq API authentication and a minimal chat request
- `ffmpeg` and `yt-dlp` availability

## Common Issues

- Music does not play: verify internet access, `yt-dlp`, and `ffmpeg`
- Nepali TTS fails: verify the `edge-tts` install and Unicode input
- English TTS fails: verify the Kokoro model files in `models/`
- Offline STT fails: verify the sherpa-onnx model download completed successfully
- Groq errors: verify the `GROQ` environment variable is set correctly

## Future Improvements

- Better offline speech recognition coverage
- Mobile app or dashboard UI
- Custom wake-word detection
- Context-aware music commands
- Spotify / local library integration



## Author

Yubraj, AI and embedded systems enthusiast

## version 2 introduction a streaming audio and agentic development 
this udate or documen tfoxuese on how nova form stt all chunk and play at once after saving in a wav to real time streaming is dveloped and lowed

For now, we are focusing on everything after the response text reaches TTS.

2. Current Audio Flow

The current architecture is:

                    NOVA AUDIO OUTPUT

                 Response Text
                      │
                      ▼
              ┌─────────────────┐
              │       TTS       │
              │  Text → Audio   │
              └────────┬────────┘
                       │
                       │ AudioChunk
                       ▼
              ┌─────────────────┐
              │   AudioQueue    │
              │                 │
              │ Producer →      │
              │ Consumer        │
              └────────┬────────┘
                       │
                       │ AudioChunk
                       ▼
              ┌─────────────────┐
              │     Consumer    │
              │                 │
              │ Queue →         │
              │ Transport       │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │    Transport    │
              └────────┬────────┘
                       │
                 Current testing
                       │
                       ▼
              ┌─────────────────┐
              │ Local Transport │
              │                 │
              │ Computer 🔊     │
              └─────────────────┘

Later, the transport can become a WebSocket transport:

TTS
 ↓
AudioQueue
 ↓
Consumer
 ↓
WebSocket Transport
 ↓
WebSocket
 ↓
ESP32
 ↓
Speaker 🔊

The important idea is:

TTS does not know how audio is played.

The queue does not know about WebSockets.

The consumer does not know how TTS generates audio.

Each component has one responsibility.

3. Why Did We Build This Architecture?

A simple implementation could do everything in one function:

Generate TTS
    ↓
Send WebSocket
    ↓
Play audio

But that creates tightly coupled code.

Instead, NOVA separates the responsibilities:

TTS
 ↓
AudioChunk
 ↓
Queue
 ↓
Consumer
 ↓
Transport

This allows us to change the destination without changing TTS.

For example:

                    ┌── Local Speaker
                    │
TTS → Queue → Consumer ── WebSocket → ESP32
                    │
                    └── Other Transport

The TTS system can remain the same.

4. AudioChunk

File:

app/audio/chunk.py

The AudioChunk is the basic unit of audio that moves through the system.

Conceptually:

AudioChunk
│
├── data
├── sequence
├── sample_rate
├── channels
├── sample_width
└── duration

Example:

AudioChunk(
    data=b"...",
    sequence=0,
    sample_rate=24000,
    channels=1,
    sample_width=2,
    duration=2.519
)
What each field means
data

The actual raw audio bytes.

data → 🔊 audio
sequence

The order of the chunk.

0
1
2
3
4
...

This is important because audio must be played in the correct order.

sample_rate

How many audio samples are produced per second.

Example:

24000 Hz

means 24,000 samples per second.

channels

Number of audio channels.

1 → mono
2 → stereo
sample_width

Number of bytes used for each sample.

For example:

2 bytes → 16-bit audio
duration

How long this particular chunk represents.

Example:

chunk 0 → 2.519 seconds
chunk 1 → 4.156 seconds
5. TTS — Text to Speech

File:

app/tts/tts_engine.py

TTS converts:

Text
 ↓
Audio

Example:

"नमस्ते, आज मौसम राम्रो छ।"

becomes audio.

The current TTS layer exposes:

synthesize_to_queue(text, queue)

Conceptually:

                 TTS Producer

Response Text
     │
     ▼
TTS Engine
     │
     ├── AudioChunk 0 ──→ Queue
     ├── AudioChunk 1 ──→ Queue
     ├── AudioChunk 2 ──→ Queue
     ├── AudioChunk 3 ──→ Queue
     └── ...

The TTS producer's job is:

Generate audio chunks and put them into the queue.

It should not:

❌ manage WebSocket
❌ play audio
❌ know about ESP32
❌ control the consumer
6. AudioQueue

File:

app/audio/queuey.py

The queue is the meeting point between the producer and consumer.

             Producer
                │
                ▼
        ┌───────────────┐
        │  AudioQueue   │
        └───────┬───────┘
                │
                ▼
             Consumer

The TTS producer puts chunks into it:

await queue.put(chunk)

The consumer takes chunks out:

chunk = await queue.get()

After processing:

queue.task_done()
7. Why an Async Queue?

Imagine TTS creates audio faster than the speaker can consume it.

The queue temporarily stores the chunks:

TTS
 ↓
chunk 0
chunk 1
chunk 2
chunk 3
 ↓
┌─────────────────────┐
│ Queue               │
│                     │
│ [1][2][3]           │
└──────────┬──────────┘
           │
           ▼
        Consumer

The producer and consumer don't need to run at exactly the same speed.

This is called a:

Producer–Consumer architecture

8. Consumer

File:

app/audio/consumer.py

The consumer is responsible for taking audio from the queue and giving it to the transport.

Conceptually:

while True:

    chunk = await queue.get()

    try:
        await transport.send(chunk)

    finally:
        queue.task_done()

The consumer does NOT generate audio.

Its job is:

Queue
  ↓
Get AudioChunk
  ↓
Transport
9. Transport

Current file:

app/audio/transport.py

The transport is responsible for deciding:

How does this AudioChunk reach the playback device?

The interface is conceptually:

start()
send(chunk)
end()

So:

Consumer
   │
   ▼
Transport

The consumer does not care whether the transport uses:

Computer speaker
WebSocket
Bluetooth
Network
ESP32

That is the transport's responsibility.

10. LocalAudioTransport

File:

app/audio/local_transport.py

We introduced this specifically to test the architecture without depending on the ESP32 or WebSocket.

Current test flow:

TTS
 ↓
AudioQueue
 ↓
Consumer
 ↓
LocalAudioTransport
 ↓
Computer Speaker

The local transport is currently being used to play the generated PCM audio on the computer.

This lets us verify the audio architecture independently from the network.

11. WebSocket Transport

The eventual transport will be:

AudioChunk
    ↓
Consumer
    ↓
AudioTransport
    ↓
WebSocket
    ↓
ESP32
    ↓
Speaker

The ESP32 should receive the audio data and play it.

The important architectural point is:

TTS does NOT directly call websocket.send()

Instead:

TTS
 ↓
Queue
 ↓
Consumer
 ↓
Transport
 ↓
WebSocket

This keeps the system modular.

12. Audio Lifecycle

The transport has three conceptual stages:

START
  ↓
AUDIO CHUNKS
  ↓
END

For WebSocket communication this can eventually look like:

audio_start
     ↓
chunk 0
     ↓
chunk 1
     ↓
chunk 2
     ↓
...
     ↓
chunk N
     ↓
audio_end

The ESP32 can use these messages to understand the playback lifecycle.

13. Current Test

Our current test does:

producer = asyncio.create_task(
    synthesize_to_queue(text, queue)
)

consumer = asyncio.create_task(
    consume_audio(queue, transport)
)

Then:

Producer starts
Consumer starts
       │
       ├───────────────┐
       │               │
       ▼               ▼
     TTS             Consumer
       │               │
       ▼               ▼
     Queue ─────────→ Speaker

After the producer finishes:

await producer

we wait for every queued chunk to be processed:

await queue.join()

Only after every chunk has called:

queue.task_done()

does queue.join() return.

14. What queue.join() Means

Suppose:

Queue:
[chunk 0]
[chunk 1]
[chunk 2]

There are 3 unfinished tasks.

Consumer processes chunk 0:

task_done()

Remaining:

2

Then chunk 1:

task_done()

Remaining:

1

Then chunk 2:

task_done()

Remaining:

0

Now:

await queue.join()

can continue.

So:

queue.join() means "wait until everything that was put into this queue has been processed."

15. Current Performance Result

Our longer test produced:

7 audio chunks

with durations approximately:

chunk 0 → 2.519 s
chunk 1 → 4.156 s
chunk 2 → 5.399 s
chunk 3 → 4.818 s
chunk 4 → 1.358 s
chunk 5 → 2.554 s
chunk 6 → 6.374 s

We measured:

Time to First Audio (TTFA)
≈ 7.96 seconds

Total pipeline
≈ 35.83 seconds
16. Important Discovery: We Are Not Truly Streaming Yet

This is the most important current architectural observation.

Although we have:

TTS → Queue → Consumer

the current TTS implementation still effectively does:

Generate chunk 0
Generate chunk 1
Generate chunk 2
Generate chunk 3
...
Generate chunk 6
        ↓
Producer finishes
        ↓
Playback

Therefore, the architecture is chunked, but TTS generation is not yet truly streaming.

The desired architecture is:

Generate chunk 0
      ↓
Queue
      ↓
PLAY chunk 0
      ↓
while chunk 0 plays
      ↓
Generate chunk 1
      ↓
Queue
      ↓
PLAY chunk 1

This should reduce Time to First Audio.

17. Current Goal

Our immediate goal is NOT to optimize everything.

We first want this:

Response Text
     ↓
TTS
     ↓
AudioChunk
     ↓
AudioQueue
     ↓
Consumer
     ↓
LocalAudioTransport
     ↓
Computer Speaker 🔊

Once this is reliable:

        LocalAudioTransport
               │
               │ replace
               ▼
         WebSocketTransport
               │
               ▼
             ESP32

Then we optimize TTS for true streaming.

18. Future NOVA Voice Architecture

Eventually the complete system should look approximately like:

                     NOVA AI

User
 │
 │ speaks
 ▼
Microphone / ESP32
 │
 ▼
STT
 │
 │ text
 ▼
Agent / LLM
 │
 │ response text
 ▼
TTS
 │
 │ AudioChunk
 ▼
AudioQueue
 │
 ▼
AudioConsumer
 │
 ▼
AudioTransport
 │
 ├──────────────► Local Speaker
 │
 └──────────────► WebSocket
                         │
                         ▼
                        ESP32
                         │
                         ▼
                       Speaker

The STT side will be documented separately.

19. Project File Responsibilities

Current relevant files:

app/
│
├── audio/
│   ├── chunk.py
│   │     └── Defines AudioChunk
│   │
│   ├── queuey.py
│   │     └── Producer/Consumer queue
│   │
│   ├── consumer.py
│   │     └── Takes chunks from queue
│   │
│   ├── transport.py
│   │     └── WebSocket transport abstraction
│   │
│   └── local_transport.py
│         └── Computer speaker testing
│
├── tts/
│   └── tts_engine.py
│         └── Generates audio chunks
│
└── communication/
    └── websocket.py
          └── Current WebSocket connection handling
20. The Golden Rule of This Architecture

Each layer should answer only one question.

TTS

How do I convert text into audio?

AudioChunk

What is one piece of audio?

Queue

Where do generated audio chunks wait?

Consumer

How do I move chunks from the queue to playback?

Transport

How do I deliver a chunk to the playback device?

LocalAudioTransport

How do I play a chunk on this computer?

WebSocket Transport

How do I send a chunk to the ESP32?

This separation is what makes the NOVA audio system easier to extend and debug.

21. Current Status
[✓] AudioChunk
[✓] AudioQueue
[✓] Producer
[✓] Consumer
[✓] Local transport
[✓] Multiple audio chunks
[✓] Queue completion with join()
[✓] Local playback pipeline

[ ] True streaming TTS
[ ] First-chunk latency optimization
[ ] Final WebSocket transport integration
[ ] ESP32 streaming playback integration
[ ] Full STT → Agent → TTS documentation
22. Next Step

The next technical step is:

CURRENT:

TTS
 │
 ├── generate ALL chunks
 │
 ▼
Queue
 │
 ▼
Consumer
 │
 ▼
Speaker


TARGET:

TTS
 │
 ├── generate chunk 0 ──→ Queue ──→ Speaker
 │
 ├── generate chunk 1 ──→ Queue ──→ Speaker
 │
 ├── generate chunk 2 ──→ Queue ──→ Speaker
 │
 └── ...

That is where we will work next: making the TTS producer genuinely stream chunks instead of blocking until all chunks have been generated.