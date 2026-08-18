"""State management so topics never repeat.

Persisted in `used-topics.json` at the repo root and committed back to git
after every run. Keeps:
  * used_topic_ids  -- ids already made into videos
  * recent_ids      -- ids used in the last N videos (avoid near repeats)
  * history         -- every video title produced (nice for review)
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

DEFAULT_RECENT = 12


def load_state(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {"used_topic_ids": [], "recent_ids": [], "history": []}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {"used_topic_ids": [], "recent_ids": [], "history": []}
    data.setdefault("used_topic_ids", [])
    data.setdefault("recent_ids", [])
    data.setdefault("history", [])
    return data


def save_state(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def mark_used(path: str, topic_id: str, video_title: str, recent: int = DEFAULT_RECENT) -> None:
    data = load_state(path)
    if topic_id not in data["used_topic_ids"]:
        data["used_topic_ids"].append(topic_id)
    data["recent_ids"] = ([topic_id] + [i for i in data["recent_ids"] if i != topic_id])[:recent]
    data["history"].append(
        {
            "topic_id": topic_id,
            "title": video_title,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    save_state(path, data)


def is_used(path: str, topic_id: str) -> bool:
    return topic_id in load_state(path)["used_topic_ids"]


def recent_ids(path: str) -> list[str]:
    return list(load_state(path)["recent_ids"])
