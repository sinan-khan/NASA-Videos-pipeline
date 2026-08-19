"""Generate simple, high-CTR NASA thumbnails with a short curiosity hook.

The thumbnail is derived from the actual story title/script and the first visual,
so every upload gets a relevant image instead of a generic template.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from scripts.config import settings

STOP = {"the", "a", "an", "of", "to", "in", "on", "and", "for", "how", "why", "what", "is", "are", "was", "were", "this", "that", "from"}
HOOKS = [
    (r"black hole|black holes", "WHAT'S INSIDE?"),
    (r"voyager", "IT LEFT FOREVER"),
    (r"mars.*water|water.*mars", "MARS HAD WATER"),
    (r"james webb|jwst", "THE FIRST GALAXIES"),
    (r"solar flare|solar storm|sun", "THE SUN IS ANGRY"),
    (r"asteroid|impact", "THIS COULD HIT EARTH"),
    (r"moon", "THE MOON IS CHANGING"),
    (r"alien|life beyond|life on", "ARE WE ALONE?"),
    (r"dark matter", "WE CAN'T SEE IT"),
    (r"supernova", "A STAR JUST DIED"),
]


def make_hook(title: str, text: str = "") -> str:
    source = f"{title} {text}".lower()
    for pattern, hook in HOOKS:
        if re.search(pattern, source):
            return hook
    words = [w.strip(".,:;!?()[]{}\"'") for w in title.split()]
    words = [w for w in words if w.lower() not in STOP and len(w) > 2]
    if len(words) >= 3:
        return " ".join(words[:4]).upper()
    return title[:28].upper().strip()


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"Thumbnail generation failed: {p.stderr[-1000:]}")


def generate_thumbnail(image_path: str, title: str, script_text: str = "", output: str | None = None) -> str:
    """Create a 1280x720 JPEG with one short, phone-readable hook."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(image_path)
    output = output or os.path.join(settings.output_dir, "thumbnail.jpg")
    hook = make_hook(title, script_text).replace(":", "\\:")
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if settings.video_font and os.path.exists(settings.video_font):
        font = settings.video_font
    # Keep the NASA visual dominant. Add a subtle dark gradient at the bottom,
    # then a large 2-5 word hook with a black outline for mobile readability.
    vf = (
        "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
        "format=yuv420p,"
        "drawbox=x=0:y=520:w=1280:h=200:color=black@0.48:t=fill,"
        f"drawtext=fontfile='{font}':text='{hook}':fontcolor=white:fontsize=76:"
        "borderw=5:bordercolor=black:x=60:y=555:"
        "enable='between(t,0,1)'"
    )
    _run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", image_path, "-vf", vf, "-frames:v", "1", "-q:v", "2", output])
    return output
