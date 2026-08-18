"""Narration audio generation.

Primary: edge-tts -- Microsoft's free neural voices, no API key needed.
Fallback: gTTS -- Google Translate TTS, also free and keyless.
Voice rotates per video for variety; one voice is used for the whole video
so it sounds consistent. Each segment is rendered to its own audio file and
its exact duration is measured for the video assembler.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import subprocess
from typing import Any

from scripts.config import settings

VOICES = [
    "en-US-ChristopherNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-US-AriaNeural",
    "en-US-EricNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
    "en-AU-NatashaNeural",
    "en-AU-WilliamNeural",
]

# Fallback voices if the preferred set is unavailable (edge-tts uses an alias list).
FALLBACK_VOICES = [
    "en-US-ChristopherNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-US-AriaNeural",
]

# Slight per-video pitch/rate jitter keeps consecutive uploads feeling fresh.
RATES = ["-4%", "-2%", "+0%", "+2%"]
PITCHES = ["-8Hz", "-4Hz", "+0Hz", "+4Hz"]


def pick_voice() -> str:
    if settings.video_voice:
        return settings.video_voice
    return random.choice(VOICES)


def _ffprobe_duration(path: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return float(out.stdout.strip().splitlines()[0])
    except (subprocess.SubprocessError, ValueError, IndexError):
        return 5.0


async def _edge_tts(text: str, voice: str, rate: str, pitch: str, dest: str) -> bool:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(dest)
    return os.path.exists(dest) and os.path.getsize(dest) > 0


def _gtts(text: str, dest: str) -> bool:
    try:
        from gtts import gTTS
    except ImportError:
        return False
    try:
        tts = gTTS(text=text, lang="en", tld="com")
        tts.save(dest)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    except Exception:
        return False


def _clip_text(text: str, limit: int = 1900) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


def generate_audio(script: dict[str, Any]) -> list[dict[str, Any]]:
    os.makedirs(settings.audio_dir, exist_ok=True)
    voice = pick_voice()
    rate = random.choice(RATES)
    pitch = random.choice(PITCHES)
    segments = script["segments"]
    audio_segments: list[dict[str, Any]] = []
    engine = "edge-tts"

    for i, seg in enumerate(segments):
        dest = os.path.join(settings.audio_dir, f"seg_{i:02d}.mp3")
        text = _clip_text(seg["text"])
        ok = False
        try:
            ok = asyncio.run(_edge_tts(text, voice, rate, pitch, dest))
        except Exception:
            ok = False
        if not ok:
            engine = "gtts"
            ok = _gtts(text, dest)
        if not ok:
            raise RuntimeError(f"All TTS engines failed for segment {i}")
        audio_segments.append(
            {
                "path": os.path.relpath(dest, settings.output_dir),
                "duration": round(_ffprobe_duration(dest), 3),
            }
        )

    with open(os.path.join(settings.output_dir, "audio.json"), "w", encoding="utf-8") as fh:
        json.dump({"engine": engine, "voice": voice, "rate": rate, "pitch": pitch, "segments": audio_segments}, fh, indent=2)
    return audio_segments
