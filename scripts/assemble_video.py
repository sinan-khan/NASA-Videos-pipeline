"""Assembles the final vertical video with FFmpeg.

Per segment:
  * Ken Burns (slow zoom in/out) on the segment image
  * clip duration sized to the measured narration audio + padding

Then clips are concatenated, captions + watermark are burned in, the full
narration track (segment audio interleaved with silence) is built, optional
royalty-free music is mixed underneath, and everything is rendered to a
1080x1920 H.264 + AAC MP4 with faststart for instant YouTube processing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

from scripts import captions
from scripts.config import settings

W, H = 1080, 1920
FPS = 30

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
]


def find_font() -> str:
    if settings.video_font and os.path.exists(settings.video_font):
        return settings.video_font
    for cand in FONT_CANDIDATES:
        if os.path.exists(cand):
            return cand
    return FONT_CANDIDATES[0]


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd[:6])}...\n{proc.stderr[-1200:]}")


def _audio_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True,
        text=True,
    )
    try:
        return float(out.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return 0.0


def _build_clip(image_path: str, duration: float, index: int, dest: str) -> None:
    frames = max(int(round(duration * FPS)), 2)
    zoom_in = index % 2 == 0
    zoom = (
        f"min(1.0+0.0008*on,1.15)"
        if zoom_in
        else f"max(1.15-0.0008*on,1.0)"
    )
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", image_path,
        "-vf",
        ",".join(
            [
                f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase",
                f"crop={W * 2}:{H * 2}",
                "setsar=1",
                f"zoompan=z='{zoom}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}",
                "format=yuv420p",
            ]
        ),
        "-r", str(FPS),
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-an",
        dest,
    ]
    _run(cmd)


def _silence(duration: float, dest: str) -> None:
    _run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{duration:.3f}",
            "-c:a", "pcm_s16le",
            dest,
        ]
    )


def _concat_demuxer(file_list: list[str], list_path: str, output: str, audio: bool) -> None:
    if audio:
        _join_audio(file_list, output)
        return
    with open(list_path, "w", encoding="utf-8") as fh:
        for f in file_list:
            fh.write(f"file '{os.path.abspath(f)}'\n")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output])


def _join_audio(inputs: list[str], output: str) -> None:
    """Concatenate mixed-codec audio (mp3 + wav) into one AAC track.

    Uses the concat *filter* (not the demuxer) so every input is resampled
    to a common format automatically -- segments and silence pad correctly.
    """
    n = len(inputs)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for f in inputs:
        cmd += ["-i", f]
    chain = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    cmd += ["-filter_complex", chain, "-map", "[a]", "-c:a", "aac", "-b:a", "192k", output]
    _run(cmd)


def _download_music() -> str | None:
    if not settings.music_url:
        return None
    import requests

    dest = os.path.join(settings.output_dir, "music.mp3")
    try:
        resp = requests.get(settings.music_url, timeout=60)
        if resp.status_code == 200:
            with open(dest, "wb") as fh:
                fh.write(resp.content)
            return dest
    except Exception:
        pass
    return None


def build_video(script: dict[str, Any], audio_segments: list[dict[str, Any]], image_paths: list[str]) -> str:
    os.makedirs(os.path.join(settings.output_dir, "clips"), exist_ok=True)
    os.makedirs(settings.audio_dir, exist_ok=True)

    font = find_font()
    n = len(audio_segments)
    timings: list[dict[str, float]] = []
    clips: list[str] = []
    audio_parts: list[str] = []

    start = 0.0
    for i, ad in enumerate(audio_segments):
        audio_dur = ad["duration"]
        padding = 0.8 if i == n - 1 else settings.segment_padding
        clip_dur = round(audio_dur + padding, 3)
        timings.append(
            {
                "start": round(start, 3),
                "end": round(start + clip_dur, 3),
                "speak_end": round(start + audio_dur + 0.15, 3),
                "is_title": i == 0,
            }
        )
        start += clip_dur

    total = round(start, 3)

    # 1) Per-segment video clips (Ken Burns).
    for i in range(n):
        clip = os.path.join(settings.output_dir, "clips", f"clip_{i:02d}.mp4")
        img = image_paths[i] if i < len(image_paths) and image_paths[i] else ""
        if not img or not os.path.exists(img):
            raise RuntimeError(f"Missing image for segment {i}")
        _build_clip(img, timings[i]["end"] - timings[i]["start"], i, clip)
        clips.append(clip)

    joined_video = os.path.join(settings.output_dir, "joined_video.mp4")
    _concat_demuxer(clips, os.path.join(settings.output_dir, "clips.txt"), joined_video, audio=False)

    # 2) Full narration track (segment audio + silence padding).
    for i, ad in enumerate(audio_segments):
        seg_audio = os.path.join(settings.audio_dir, os.path.basename(ad["path"]))
        audio_parts.append(seg_audio)
        silence_path = os.path.join(settings.audio_dir, f"silence_{i:02d}.wav")
        pad = round(timings[i]["end"] - timings[i]["start"] - ad["duration"], 3)
        if pad > 0.01:
            _silence(pad, silence_path)
            audio_parts.append(silence_path)
    joined_audio = os.path.join(settings.output_dir, "joined_audio.m4a")
    _concat_demuxer(audio_parts, os.path.join(settings.output_dir, "audio_list.txt"), joined_audio, audio=True)

    # 3) Subtitles + fades + optional music.
    ass_path = captions.save_ass(script, timings, font)
    ass_filter = f"ass='{ass_path}'"

    music = _download_music()
    handle = os.getenv("CHANNEL_HANDLE", "").strip()

    if music:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", joined_video, "-i", joined_audio, "-i", music,
            "-filter_complex",
            ";".join(
                [
                    f"[0:v]{ass_filter},fade=t=in:st=0:d=0.4,fade=t=out:st={max(total - 0.5, 0):.3f}:d=0.5[v]",
                    f"[1:a]afade=t=in:st=0:d=0.2,afade=t=out:st={max(total - 0.4, 0):.3f}:d=0.4[nar]",
                    f"[2:a]volume={settings.music_volume},aloop=loop=-1:size=2e9,atrim=duration={total},afade=t=out:st={max(total - 0.4, 0):.3f}:d=0.4[mus]",
                    "[nar][mus]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
                ]
            ),
            "-map", "[v]", "-map", "[a]",
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", joined_video, "-i", joined_audio,
            "-filter_complex",
            ";".join(
                [
                    f"[0:v]{ass_filter},fade=t=in:st=0:d=0.4,fade=t=out:st={max(total - 0.5, 0):.3f}:d=0.5[v]",
                    f"[1:a]afade=t=in:st=0:d=0.2,afade=t=out:st={max(total - 0.4, 0):.3f}:d=0.4[a]",
                ]
            ),
            "-map", "[v]", "-map", "[a]",
        ]

    if handle:
        wm = f"drawtext=text='@{handle}':fontfile={font}:fontcolor=white:fontsize=30:x=(w-text_w)/2:y=h-100:box=1:boxcolor=black@0.5:boxborderw=8"
        cmd[cmd.index("-filter_complex") + 1] += f";[v]{wm}[v]"

    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        settings.video_file,
    ]
    _run(cmd)

    with open(os.path.join(settings.output_dir, "timings.json"), "w", encoding="utf-8") as fh:
        json.dump(timings, fh, indent=2)

    if not settings.keep_artifacts:
        shutil.rmtree(os.path.join(settings.output_dir, "clips"), ignore_errors=True)
        for f in os.listdir(settings.audio_dir):
            if f.startswith("silence_"):
                os.remove(os.path.join(settings.audio_dir, f))
        for f in ("joined_video.mp4", "joined_audio.m4a", "clips.txt", "audio_list.txt", "music.mp3"):
            p = os.path.join(settings.output_dir, f)
            if os.path.exists(p):
                os.remove(p)

    return settings.video_file
