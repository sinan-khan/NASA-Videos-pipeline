"""Generates an Advanced SubStation Alpha (.ass) subtitle file.

The file is burned into the video by FFmpeg so captions always show up
on every platform (no external .srt needed). Text is split into a few
lines with automatic smart wrapping for a clean look on 1080x1920.
"""

from __future__ import annotations

import os
from typing import Any

from scripts.config import settings

PLAYRES_X = 1080
PLAYRES_Y = 1920

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {playres_x}
PlayResY: {playres_y}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},56,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,3,1,0,2,40,40,340,1
Style: Title,{font},92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,1,0,0,0,100,100,0,0,3,2,0,8,40,40,170,1
Style: CTA,{font},80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,3,1,0,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _esc(text: str) -> str:
    return text.replace("{", "\\{").replace("}", "\\}").replace("\n", " ")


def _ts(seconds: float) -> str:
    """ASS timestamp: H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs == 100:
        s += 1
        cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _wrap(text: str, max_chars: int = 26) -> str:
    """Insert \\N line breaks for better on-screen layout."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\\N".join(lines)


def build_ass(script: dict[str, Any], timings: list[dict[str, float]], font: str) -> str:
    """timings: list of {start, end, speak_end} per segment."""
    out = [HEADER.format(playres_x=PLAYRES_X, playres_y=PLAYRES_Y, font=font)]
    segments = script["segments"]
    for i, (seg, t) in enumerate(zip(segments, timings)):
        text = _esc(_wrap(seg["text"]))
        if i == 0 and t.get("is_title", False):
            style = "Title"
            label = _esc(script.get("title", ""))[:80]
            out.append(f"Dialogue: 0,{_ts(t['start'])},{_ts(t['speak_end'])},Title,,0,0,0,,{label}")
            out.append(f"Dialogue: 0,{_ts(t['start'])},{_ts(t['speak_end'])},Caption,,0,0,0,,{text}")
        elif i == len(segments) - 1:
            style = "CTA"
            out.append(f"Dialogue: 0,{_ts(t['start'])},{_ts(t['end'])},{style},,0,0,0,,{text}")
        else:
            style = "Caption"
            out.append(f"Dialogue: 0,{_ts(t['start'])},{_ts(t['end'])},{style},,0,0,0,,{text}")
    return "\n".join(out) + "\n"


def save_ass(script: dict[str, Any], timings: list[dict[str, float]], font: str) -> str:
    path = os.path.join(settings.output_dir, "captions.ass")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_ass(script, timings, font))
    return path
