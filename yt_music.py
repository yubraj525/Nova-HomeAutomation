import os
import subprocess
import asyncio
from speech import play_audio

COOKIES = r"C:\Users\yubra\OneDrive\Documents\Development\Voice-assitance-py\cookies.txt"
async def download_and_play(query):

    if not query:
        print("No song specified")
        return

    if os.path.exists("song.mp3"):
        os.remove("song.mp3")

    print(f"Searching: {query}")

    search_query = f'ytsearch1:"{query.strip()}"'

    result = subprocess.run([
        "yt-dlp",
        "-f", "bestaudio/best",
        "-x",
        "--audio-format", "mp3",
        "-o", "song.mp3",
        search_query
    ])

    if result.returncode != 0:
        print("Download failed! Trying fallback...")
        # Optional: try fallback with no quotes
        fallback_query = f'ytsearch1:{query.strip()}'
        fallback_result = subprocess.run([
            "yt-dlp",
            "-f", "bestaudio/best",
            "-x",
            "--audio-format", "mp3",
            "-o", "song.mp3",
            fallback_query
        ])
        if fallback_result.returncode != 0:
            print("Fallback failed. Song could not be downloaded.")
            return

    print("Downloaded! Playing...")
    #conversionf mp3 to suppoted wav format for esp32
    from pydub import AudioSegment

# Load your source file
    audio = AudioSegment.from_file("song.mp3")

# 1. Convert to Mono (1 channel)
    audio = audio.set_channels(1)

# 2. Set Sample Rate to 24000Hz
    audio = audio.set_frame_rate(24000)

# 3. Set Sample Width to 2 bytes (16-bit)
    audio = audio.set_sample_width(2) 

# Export as WAV
    audio.export("song.wav", format="wav")

    print("Exported: 24kHz, 16-bit, Mono WAV")
    from websocket import stream_music
    await stream_music("song.wav")

async def main():
    print("🎵 Music test starting...")

    query = "believer imagine dragons"

    await download_and_play(query)

    print("✅ Done playing song")


if __name__ == "__main__":
    asyncio.run(main())