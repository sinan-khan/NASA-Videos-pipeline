"""Fetches one image per script segment for the video.

Strategy (each layer degrades gracefully so a video is always produced):
  1. NASA Image Library search -- free, no key needed, matches visual hints.
  2. NASA APOD (Astronomy Picture of the Day) -- random past images.
  3. Locally generated space gradient -- guaranteed last resort.

All images are downloaded to output/images/ and verified as real pictures.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Any

import requests

from scripts.config import settings

IMG_MAGIC = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"RIFF": ".webp",
}


def is_valid_image(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            head = fh.read(12)
        return any(head.startswith(m) for m in IMG_MAGIC)
    except OSError:
        return False


def _get(url: str, timeout: int = 20, **kwargs: Any) -> requests.Response:
    return requests.get(url, timeout=timeout, headers={"User-Agent": "autospace/1.0"}, **kwargs)


def _download(url: str, dest: str, timeout: int = 30) -> str | None:
    try:
        resp = _get(url, timeout=timeout, stream=True)
        if resp.status_code != 200:
            return None
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
        if is_valid_image(dest):
            return dest
    except (requests.RequestException, OSError):
        pass
    return None


def _search_nasa_library(query: str, limit: int = 8) -> list[str]:
    """Search the NASA Image Library; returns a list of direct image URLs."""
    url = "https://images-api.nasa.gov/search"
    params = {"q": query, "media_type": "image", "page_size": limit}
    try:
        resp = _get(url, params=params)
        resp.raise_for_status()
        items = resp.json().get("collection", {}).get("items", [])
    except (requests.RequestException, ValueError):
        return []
    urls: list[str] = []
    for item in items:
        links = item.get("links") or []
        for link in links:
            href = link.get("href") or ""
            if re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", href, re.I):
                urls.append(href)
    return urls


def _random_apod_images(count: int = 10) -> list[str]:
    """Random APOD images within roughly the last 4 years."""
    urls: list[str] = []
    now = datetime.utcnow()
    dates = [
        (now - timedelta(days=random.randint(5, 1460))).strftime("%Y-%m-%d") for _ in range(count)
    ]
    for d in dates:
        url = "https://api.nasa.gov/planetary/apod"
        try:
            resp = _get(url, params={"api_key": settings.nasa_api_key, "date": d, "hd": False})
            if resp.status_code != 200:
                continue
            data = resp.json()
            href = data.get("hdurl") or data.get("url")
            if href and re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", href, re.I):
                urls.append(href)
        except (requests.RequestException, ValueError):
            continue
    return urls


def _placeholder(dest: str, seed: str) -> str:
    """Generate a deep-space gradient image with ffmpeg as the final fallback."""
    import subprocess

    hues = ["#050514", "#0a1035", "#151b54", "#02030c"]
    cols = random.Random(seed).choice(
        [
            (hues[0], hues[1]),
            (hues[2], hues[0]),
            (hues[0], hues[3]),
        ]
    )
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i",
        f"gradients=s=1280x720:c0={cols[0]}:c1={cols[1]}:d=1",
        "-frames:v", "1", dest,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        return dest if is_valid_image(dest) else ""
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def _pick_from(urls: list[str], used: set[str]) -> str | None:
    for u in urls:
        if u in used:
            continue
        return u
    return None


def fetch_one(query: str, used_urls: set[str], index: int) -> dict[str, Any]:
    """Fetch one image for a query; returns {path, source, url} or {path:""}."""
    os.makedirs(settings.images_dir, exist_ok=True)
    dest = os.path.join(settings.images_dir, f"img_{index:02d}.jpg")

    # Layer 1: NASA Image Library search
    for q in (query, query.split()[0] if query.split() else query):
        for url in _search_nasa_library(q, limit=8):
            if url in used_urls:
                continue
            saved = _download(url, dest)
            if saved:
                return {"path": os.path.relpath(saved, settings.output_dir), "source": "nasa_library", "url": url}
            time.sleep(0.2)

    # Layer 2: random APOD
    for url in _random_apod_images(12):
        if url in used_urls:
            continue
        saved = _download(url, dest)
        if saved:
            return {"path": os.path.relpath(saved, settings.output_dir), "source": "apod", "url": url}
        time.sleep(0.2)

    # Layer 3: generated placeholder
    saved = _placeholder(dest, f"{query}-{index}")
    if saved:
        return {"path": os.path.relpath(saved, settings.output_dir), "source": "placeholder", "url": ""}
    return {"path": "", "source": "missing", "url": ""}


def fetch_images(script: dict[str, Any]) -> dict[str, Any]:
    used: set[str] = set()
    manifest = {"images": []}
    for i, seg in enumerate(script["segments"]):
        result = fetch_one(seg.get("visual_hint", "space"), used, i)
        manifest["images"].append(result)
        if result["url"]:
            used.add(result["url"])
        time.sleep(0.3)
    with open(os.path.join(settings.output_dir, "images.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return manifest


def absolute_image_paths(manifest: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for item in manifest.get("images", []):
        rel = item.get("path", "")
        paths.append(os.path.join(settings.output_dir, rel) if rel else "")
    return paths
