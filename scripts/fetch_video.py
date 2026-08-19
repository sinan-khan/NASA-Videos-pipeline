"""Download NASA video footage for long-form documentaries.

Uses NASA's public media search API and only accepts video assets whose metadata
identifies nasa.gov/nasa.gov hosts. The downloader prefers long, high-resolution
assets and keeps a manifest for attribution/auditability.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

NASA_SEARCH = "https://images-api.nasa.gov/search"
ALLOWED_HOSTS = {"images-assets.nasa.gov", "svs.gsfc.nasa.gov", "assets.science.nasa.gov", "www.nasa.gov", "nasa.gov"}


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_")[:100] or "nasa_video"


def _allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in ALLOWED_HOSTS or host.endswith(".nasa.gov")


def _search(query: str, limit: int = 25) -> list[dict]:
    r = requests.get(NASA_SEARCH, params={"q": query, "media_type": "video", "page_size": limit}, timeout=30)
    r.raise_for_status()
    return r.json().get("collection", {}).get("items", [])


def _assets(item: dict) -> list[str]:
    href = item.get("href")
    if not href:
        return []
    r = requests.get(href, timeout=30)
    r.raise_for_status()
    return [u for u in r.json() if isinstance(u, str) and u.lower().endswith((".mp4", ".mov", ".m4v")) and _allowed(u)]


def download_long_video(query: str, dest_dir: Path, *, min_seconds: int = 180) -> dict:
    """Download the best NASA source video available for *query*.

    The NASA API does not guarantee duration in search results, so selection
    uses metadata first and ffprobe later. The returned manifest is deliberately
    retained so the final documentary can cite the exact NASA source.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    items = _search(query)
    candidates: list[tuple[dict, str]] = []
    for item in items:
        data = (item.get("data") or [{}])[0]
        try:
            urls = _assets(item)
        except requests.RequestException:
            continue
        for url in urls:
            candidates.append((data, url))
    if not candidates:
        raise RuntimeError(f"No downloadable NASA video found for query: {query}")

    candidates.sort(key=lambda pair: ("4k" in pair[1].lower(), "1080" in pair[1].lower(), len(pair[1])), reverse=True)
    last_error = None
    for data, url in candidates[:12]:
        try:
            title = data.get("title") or data.get("nasa_id") or "NASA video"
            out = dest_dir / f"{_safe_name(data.get('nasa_id') or title)}.mp4"
            with requests.get(url, stream=True, timeout=(20, 180)) as r:
                r.raise_for_status()
                with open(out, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            fh.write(chunk)
            if out.stat().st_size < 100_000:
                out.unlink(missing_ok=True)
                continue
            manifest = {
                "query": query,
                "title": title,
                "nasa_id": data.get("nasa_id"),
                "description": data.get("description", ""),
                "date_created": data.get("date_created"),
                "source_url": url,
                "asset": str(out),
                "min_seconds": min_seconds,
            }
            (dest_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            return manifest
        except requests.RequestException as exc:
            last_error = exc
            continue
    raise RuntimeError(f"NASA video downloads failed for query '{query}': {last_error}")
