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
