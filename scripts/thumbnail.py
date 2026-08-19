"""Generate cinematic, high-quality NASA thumbnails with a short hook.

Quality rules:
- Prefer the best available NASA source frame/asset, never a tiny thumbnail.
- Render at 1280x720 (YouTube HD thumbnail) with Lanczos scaling.
- Preserve the subject's composition instead of blindly stretching it.
- Apply subtle cinematic contrast/sharpening and a readable dark text zone.
- Use a 2-5 word curiosity hook derived from the actual story.
"""
from __future__ import annotations

import os
import re
import subprocess
from urllib.parse import urlparse

import requests

from scripts.config import settings

NASA_MEDIA_API = "https://images-api.nasa.gov/search"
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
    return (" ".join(words[:4]) if len(words) >= 3 else title[:28]).upper().strip()


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"Thumbnail generation failed: {p.stderr[-1200:]}")


def _best_nasa_image(query: str, dest: str) -> str | None:
    """Fetch a large NASA image when the pipeline doesn't already have one.

    Prefer original/high-resolution assets; reject tiny API thumbnails.
    """
    try:
        data = requests.get(
            NASA_MEDIA_API,
            params={"q": query, "media_type": "image", "page_size": 12},
            timeout=30,
        ).json()
        candidates = []
        for item in data.get("collection", {}).get("items", []):
            meta = (item.get("data") or [{}])[0]
            href = item.get("href", "")
            if not href or not (urlparse(href).hostname or "").endswith("nasa.gov"):
                continue
            try:
                assets = requests.get(href, timeout=20).json()
            except Exception:
                continue
            for url in assets:
                if isinstance(url, str) and url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    score = ("orig" in url.lower()) * 4 + ("large" in url.lower()) * 3 + ("full" in url.lower()) * 2
                    candidates.append((score, url, meta.get("title", "")))
        candidates.sort(reverse=True)
        for _, url, _ in candidates:
            r = requests.get(url, timeout=60)
            if r.ok and len(r.content) > 300_000:
                with open(dest, "wb") as fh:
                    fh.write(r.content)
                return dest
    except Exception:
        return None
    return None


def generate_thumbnail(image_path: str | None, title: str, script_text: str = "", output: str | None = None) -> str:
    """Create a polished 1280x720 JPEG from a high-resolution NASA visual."""
    output = output or os.path.join(settings.output_dir, "thumbnail.jpg")
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    source = image_path if image_path and os.path.exists(image_path) else None
    if not source:
        source = _best_nasa_image(title, os.path.join(settings.output_dir, "thumbnail_source.jpg"))
    if not source:
        raise RuntimeError("No high-quality NASA thumbnail source image is available")

    hook = make_hook(title, script_text)
    # Escape FFmpeg drawtext-sensitive characters.
    hook = hook.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if settings.video_font and os.path.exists(settings.video_font):
        font = settings.video_font

    # High-quality pipeline: scale/crop with Lanczos, gentle contrast and
    # sharpening, then a soft dark lower gradient so the NASA subject remains
    # the hero while the 2-5 word hook stays readable on mobile.
    vf = (
        "scale=1280:720:force_original_aspect_ratio=increase:flags=lanczos,"
        "crop=1280:720,"
        "eq=contrast=1.06:saturation=1.04:brightness=0.01,"
        "unsharp=5:5:0.45:5:5:0,"
        "drawbox=x=0:y=500:w=1280:h=220:color=black@0.42:t=fill,"
        f"drawtext=fontfile='{font}':text='{hook}':fontcolor=white:fontsize=76:"
        "fontcolor_expr=white:borderw=5:bordercolor=black@0.9:"
        "x=60:y=545:shadowx=2:shadowy=2:shadowcolor=black@0.85"
    )
    _run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", source,
        "-vf", vf,
        "-frames:v", "1", "-q:v", "1", "-pix_fmt", "yuvj420p", output,
    ])
    if not os.path.exists(output) or os.path.getsize(output) < 100_000:
        raise RuntimeError("Thumbnail output is unexpectedly small")
    return output
