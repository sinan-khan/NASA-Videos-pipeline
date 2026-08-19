"""Build a 25-35 minute NASA documentary from one or more NASA video sources.

The core rule is beat synchronization: every narration beat gets its own TTS
file, exact measured duration, and a corresponding section of source footage.
Captions use the same timestamps, so story, voice, visuals, and text cannot drift.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from scripts import fetch_video, tts
from scripts.config import settings

MIN_SECONDS = 25 * 60
MAX_SECONDS = 35 * 60
TARGET_SECONDS = 30 * 60


def _probe(path: Path) -> float:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(p.stdout.strip())


def _write_documentary_script(topic: dict[str, Any]) -> dict[str, Any]:
    """Ask the LLM for a chaptered documentary whose beats can be narrated individually."""
    from groq import Groq
    client = Groq(api_key=settings.groq_api_key)
    prompt = f"""Create a deeply researched ORIGINAL 25-35 minute NASA documentary about {topic['title']}.
Target 30 minutes / about 4,200-4,800 spoken words. Structure it as 8-12 chapters with 6-12 beats per chapter.
Every beat must be independently narratable and visually matchable. Return ONLY JSON:
{{"title":string,"description":string,"tags":[string],"thumbnail_text":string,"chapters":[{{"title":string,"beats":[{{"text":string,"visual_query":string}}]}}]}}
Rules: factual, chronological where appropriate, no invented facts, no filler, explain causes and evidence, distinguish confirmed facts from hypotheses, and build a coherent story with callbacks. Each beat should be 35-85 spoken words. visual_query must describe the exact NASA footage/scene that should appear while that beat is spoken. The documentary should end naturally, not with repeated social-media CTAs."""
    response = client.chat.completions.create(model=settings.groq_model, messages=[{"role":"user", "content": prompt}], temperature=0.45, max_tokens=12000)
    raw = response.choices[0].message.content or ""
    start, end = raw.find("{"), raw.rfind("}")
    data = json.loads(raw[start:end + 1])
    beats = [b for c in data.get("chapters", []) for b in c.get("beats", []) if b.get("text")]
    if not 25 * 60 <= len(" ".join(b["text"] for b in beats).split()) / 150 * 60 <= 35 * 60:
        raise ValueError("Documentary script is outside the 25-35 minute target")
    data["beats"] = beats
    return data


def _source_segments(source: Path, beats: list[dict], work: Path) -> list[Path]:
    """Slice the downloaded NASA master into one visual segment per beat."""
    total = _probe(source)
    out: list[Path] = []
    cursor = 0.0
    for i, beat in enumerate(beats):
        # Cycle through the source, but never use less than a beat's duration.
        duration = max(2.0, beat["duration"])
        if cursor + duration > total:
            cursor = 0.0
        dest = work / f"source_{i:03d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{cursor:.3f}", "-i", str(source), "-t", f"{duration:.3f}", "-an", "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(dest)], check=True)
        out.append(dest)
        cursor += duration
    return out


def build(topic: dict[str, Any], work: Path) -> tuple[Path, dict[str, Any]]:
    work.mkdir(parents=True, exist_ok=True)
    script = _write_documentary_script(topic)
    audio_dir = work / "audio"
    audio_dir.mkdir()
    audio = tts.generate_audio({"segments": [{"text": b["text"]} for b in script["beats"]]})
    for beat, a in zip(script["beats"], audio):
        beat["audio_path"] = str(settings.output_dir / a["path"])
        beat["duration"] = a["duration"]
    total = sum(b["duration"] for b in script["beats"])
    if not MIN_SECONDS <= total <= MAX_SECONDS:
        raise RuntimeError(f"Narrated documentary is {total/60:.1f} minutes; target is 25-35 minutes")
    query = " ".join([topic.get("keywords", ""), topic.get("title", "")]).strip()
    manifest = fetch_video.download_long_video(query, work / "nasa_source")
    source = Path(manifest["asset"])
    visuals = _source_segments(source, script["beats"], work / "visuals")
    final = work / "final_long.mp4"
    _assemble( script, visuals, final, work )
    script["source_manifest"] = manifest
    script["duration_seconds"] = total
    return final, script


def _assemble(script: dict[str, Any], visuals: list[Path], out: Path, work: Path) -> None:
    clips = []
    timeline = []
    t = 0.0
    for i, (beat, visual) in enumerate(zip(script["beats"], visuals)):
        clip = work / f"beat_{i:03d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(visual), "-i", beat["audio_path"], "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(clip)], check=True)
        clips.append(clip)
        timeline.append({"start": t, "end": t + beat["duration"], "text": beat["text"], "chapter": beat.get("chapter", "")})
        t += beat["duration"]
    listing = work / "concat.txt"
    listing.write_text("\n".join(f"file '{p.resolve()}'" for p in clips), encoding="utf-8")
    joined = work / "joined.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)], check=True)
    srt = work / "captions.srt"
    lines=[]
    def ts(x):
        ms=int((x-int(x))*1000); total=int(x); return f"{total//3600:02d}:{(total%3600)//60:02d}:{total%60:02d},{ms:03d}"
    for i,b in enumerate(timeline,1): lines += [str(i), f"{ts(b['start'])} --> {ts(b['end'])}", b["text"], ""]
    srt.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-vf", f"subtitles={srt}:force_style='FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00101010,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=55'", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    (work / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
