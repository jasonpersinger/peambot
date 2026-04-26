#!/usr/bin/env python3
"""Generate TTS positive samples for hey_peambot wake word training."""

import asyncio
import os
import subprocess
import edge_tts

PHRASE = "Hey Peambot"
OUTPUT_DIR = "wake-word-training/positive"
SAMPLES_PER_VOICE = 50

VOICES = [
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-US-EricNeural",
    "en-US-MichelleNeural",
    "en-GB-SoniaNeural",
    "en-GB-RyanNeural",
    "en-AU-NatashaNeural",
    "en-AU-WilliamNeural",
    "en-CA-ClaraNeural",
]

sem = asyncio.Semaphore(10)

async def synthesize(voice: str, idx: int) -> str:
    async with sem:
        out_mp3 = os.path.join(OUTPUT_DIR, f"{voice}_{idx:03d}.mp3")
        out_wav = os.path.join(OUTPUT_DIR, f"{voice}_{idx:03d}.wav")
        if os.path.exists(out_wav):
            return out_wav
        communicate = edge_tts.Communicate(PHRASE, voice)
        await communicate.save(out_mp3)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", out_mp3, "-ar", "16000", "-ac", "1", out_wav],
            check=True
        )
        os.remove(out_mp3)
        return out_wav

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tasks = [
        synthesize(voice, i)
        for voice in VOICES
        for i in range(SAMPLES_PER_VOICE)
    ]
    total = len(tasks)
    done = 0
    for coro in asyncio.as_completed(tasks):
        path = await coro
        done += 1
        if done % 50 == 0 or done == total:
            print(f"  {done}/{total} {path}")
    print(f"Done. {total} samples in {OUTPUT_DIR}/")

if __name__ == "__main__":
    asyncio.run(main())
