"""Uploads the finished video to YouTube via the Data API v3.

Uses the refresh token obtained by the one-time local auth (oauth_local.py).
The upload is resumable and retried with exponential backoff, so a flaky
network or a rate-limit blip does not kill the run. Privacy is configurable
(default "private" so nothing goes live before you're ready).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from scripts.config import settings

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
APPLICATION_NAME = "Auto Space Videos"


def build_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=None,
        refresh_token=settings.yt_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.yt_client_id,
        client_secret=settings.yt_client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def _build_body(script: dict[str, Any]) -> dict[str, Any]:
    title = script.get("title", "").strip() or "Daily Space Fact"
    if len(title) > settings.yt_max_title_len:
        title = title[: settings.yt_max_title_len - 1].rstrip() + "…"

    tags = script.get("tags") or []
    tags = [t for t in tags if t][:15]
    description = (script.get("description") or "").strip()
    description += "\n\n#SpaceDaily #SpaceFacts #Astronomy #NASA #Universe #Science"
    description = description[: settings.yt_max_desc_len]

    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": settings.yt_category_id,
            "defaultLanguage": settings.yt_language,
        },
        "status": {
            "privacyStatus": settings.yt_privacy,
            "selfDeclaredMadeForKids": False,
        },
    }


def _media_body(path: str, chunk: int = 8 << 20):
    from googleapiclient.http import MediaFileUpload

    return MediaFileUpload(path, mimetype="video/mp4", chunksize=chunk, resumable=True)


def _upload(youtube: Any, video_path: str, body: dict[str, Any]) -> dict[str, Any]:
    media = _media_body(video_path)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response: dict[str, Any] | None = None
    backoff = 4
    max_retries = 5
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"Upload progress: {pct}%")
        if response is None:
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
    return response


def upload_video(script: dict[str, Any], video_path: str) -> dict[str, Any]:
    from googleapiclient.discovery import build

    creds = build_credentials()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = _build_body(script)

    if settings.dry_run:
        result = {"dry_run": True, "title": body["snippet"]["title"], "privacy": settings.yt_privacy}
        print(json.dumps(result, indent=2))
        return result

    response = _upload(youtube, video_path, body)
    video_id = response.get("id")
    result = {
        "dry_run": False,
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "title": body["snippet"]["title"],
        "privacy": settings.yt_privacy,
        "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return result


def save_result(result: dict[str, Any]) -> None:
    os.makedirs(settings.output_dir, exist_ok=True)
    with open(settings.result_file, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, settings.output_dir)
    script_path = sys.argv[1] if len(sys.argv) > 1 else settings.script_file
    with open(script_path, "r", encoding="utf-8") as fh:
        script_data = json.load(fh)
    result = upload_video(script_data, settings.video_file)
    save_result(result)
    print(json.dumps(result, indent=2))
