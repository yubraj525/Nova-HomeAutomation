import subprocess
import pygame
import asyncio
import os
from speech  import play_audio

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
    await play_audio("song.mp3")