"""Reliable NASA image acquisition with validation and graceful fallbacks."""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import time
from datetime import datetime, timedelta
from typing import Any

import requests

from scripts.config import settings

IMAGE_RE = re.compile(r"\.(?:jpg|jpeg|png|webp)(?:\?|$)", re.I)
MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"RIFF")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "NASA-Videos-pipeline/2.0"})


def _request(url: str, *, timeout: int = 20, **kwargs: Any) -> requests.Response:
    last: Exception | None = None
    for attempt in range(3):
        try:
            response = SESSION.get(url, timeout=timeout, **kwargs)
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise requests.RequestException(str(last or "request failed"))


def is_valid_image(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            head = fh.read(12)
        return any(head.startswith(magic) for magic in MAGIC) and os.path.getsize(path) > 512
    except OSError:
        return False


def _download(url: str, dest: str) -> str | None:
    tmp = dest + ".part"
    try:
        response = _request(url, timeout=40, stream=True)
        with open(tmp, "wb") as fh:
            for chunk in response.iter_content(65536):
                if chunk:
                    fh.write(chunk)
        if is_valid_image(tmp):
            os.replace(tmp, dest)
            return dest
    except (requests.RequestException, OSError):
        pass
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return None


def _search_nasa(query: str, limit: int = 10) -> list[str]:
    try:
        data = _request(
            "https://images-api.nasa.gov/search",
            params={"q": query, "media_type": "image", "page_size": limit},
        ).json()
    except (requests.RequestException, ValueError):
        return []
    urls: list[str] = []
    for item in data.get("collection", {}).get("items", []):
        for link in item.get("links", []):
            href = link.get("href", "")
            if IMAGE_RE.search(href):
                urls.append(href)
    return urls


def _apod_fallback(limit: int = 8) -> list[str]:
    urls: list[str] = []
    now = datetime.utcnow()
    for _ in range(limit):
        date = (now - timedelta(days=random.randint(3, 1460))).strftime("%Y-%m-%d")
        try:
            data = _request(
                "https://api.nasa.gov/planetary/apod",
                params={"api_key": settings.nasa_api_key, "date": date},
            ).json()
            href = data.get("hdurl") or data.get("url", "")
            if data.get("media_type") == "image" and IMAGE_RE.search(href):
                urls.append(href)
        except (requests.RequestException, ValueError):
            continue
    return urls


def _placeholder(dest: str, seed: str) -> str:
    rng = random.Random(seed)
    c0, c1 = rng.choice([("#050514", "#101a3b"), ("#080812", "#25205a"), ("#02030c", "#111827")])
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
             f"gradients=s=1280x720:c0={c0}:c1={c1}:d=1", "-frames:v", "1", dest],
            check=True, timeout=30, capture_output=True,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return dest if is_valid_image(dest) else ""


def fetch_one(query: str, used_urls: set[str], index: int) -> dict[str, Any]:
    os.makedirs(settings.images_dir, exist_ok=True)
    dest = os.path.join(settings.images_dir, f"img_{index:02d}.jpg")
    queries = [query.strip(), " ".join(query.split()[:3]).strip(), "space" ]
    for q in dict.fromkeys(x for x in queries if x):
        for url in _search_nasa(q):
            if url in used_urls:
                continue
            if _download(url, dest):
                return {"path": os.path.relpath(dest, settings.output_dir), "source": "nasa_library", "url": url}
    for url in _apod_fallback():
        if url not in used_urls and _download(url, dest):
            return {"path": os.path.relpath(dest, settings.output_dir), "source": "apod", "url": url}
    saved = _placeholder(dest, f"{query}-{index}")
    return {"path": os.path.relpath(saved, settings.output_dir) if saved else "", "source": "placeholder" if saved else "missing", "url": ""}


def fetch_images(script: dict[str, Any]) -> dict[str, Any]:
    os.makedirs(settings.output_dir, exist_ok=True)
    used: set[str] = set()
    manifest = {"images": []}
    for index, segment in enumerate(script.get("segments", [])):
        result = fetch_one(segment.get("visual_hint", "space"), used, index)
        manifest["images"].append(result)
        if result.get("url"):
            used.add(result["url"])
    with open(os.path.join(settings.output_dir, "images.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return manifest


def absolute_image_paths(manifest: dict[str, Any]) -> list[str]:
    return [os.path.join(settings.output_dir, item["path"]) if item.get("path") else "" for item in manifest.get("images", [])]
