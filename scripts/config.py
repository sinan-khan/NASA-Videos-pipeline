"""Central configuration for the auto-video pipeline.

Every setting is read from the environment so the exact same code runs
locally (`.env` file) and in GitHub Actions (repository Secrets). Defaults
are chosen so the pipeline is usable with zero configuration beyond the
credentials.

Secret names are prefixed with USER_/YT_/GROQ_/NASA_ to keep them clearly
namespaced to this project -- they are populated by the user, never derived
from the agent environment.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Load a local `.env` if present (ignored in CI where secrets are injected).
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _path(*parts: str) -> str:
    return os.path.join(REPO_ROOT, *parts)


def _get(name: str, default: str = "") -> str:
    val = os.getenv(name, default).strip()
    return val


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name, "").strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    if val in {"0", "false", "no", "off"}:
        return False
    return default


class Settings:
    def __init__(self) -> None:
        # --- LLM (script writing) ----------------------------------------
        self.groq_api_key = _get("GROQ_API_KEY")
        self.groq_model = _get("GROQ_MODEL", "llama-3.3-70b-versatile")

        # --- Imagery ------------------------------------------------------
        self.nasa_api_key = _get("NASA_API_KEY", "DEMO_KEY")
        self.image_count_fallback = _get_int("IMAGE_COUNT_FALLBACK", 5)

        # --- YouTube -------------------------------------------------------
        self.yt_client_id = _get("YT_CLIENT_ID")
        self.yt_client_secret = _get("YT_CLIENT_SECRET")
        self.yt_refresh_token = _get("YT_REFRESH_TOKEN")
        self.yt_privacy = _get("YT_PRIVACY_STATUS", "private")
        self.yt_language = _get("YT_LANGUAGE", "en")
        self.yt_category_id = _get("YT_CATEGORY_ID", "28")  # Science & Technology
        self.yt_channel_id = _get("YT_CHANNEL_ID")  # optional, only used for verification
        self.yt_max_title_len = _get_int("YT_MAX_TITLE_LEN", 95)
        self.yt_max_desc_len = _get_int("YT_MAX_DESC_LEN", 4800)

        # --- Video ---------------------------------------------------------
        self.target_seconds = _get_int("TARGET_SECONDS", 65)
        self.video_voice = _get("VIDEO_VOICE")  # optional override, otherwise rotates
        self.video_font = _get("VIDEO_FONT")  # optional .ttf/.otf path
        self.music_url = _get("MUSIC_URL")  # optional royalty-free background music
        self.music_volume = _get("MUSIC_VOLUME", "0.08")
        self.segment_padding = _get_float("SEGMENT_PADDING", 0.45)  # seconds between segments

        # --- Behaviour -----------------------------------------------------
        self.dry_run = _get_bool("DRY_RUN", False)  # skip upload, keep video locally
        self.upload_only = _get_bool("UPLOAD_ONLY", False)  # skip regeneration, upload existing
        self.max_topic_retries = _get_int("MAX_TOPIC_RETRIES", 3)
        self.keep_artifacts = _get_bool("KEEP_ARTIFACTS", False)  # keep intermediate files
        self.verbosity = _get("LOG_LEVEL", "INFO").upper()

        # --- Paths ----------------------------------------------------------
        self.output_dir = _path("output")
        self.state_file = _path("used-topics.json")
        self.topic_file = _path("output", "topic.json")
        self.script_file = _path("output", "script.json")
        self.images_dir = _path("output", "images")
        self.audio_dir = _path("output", "audio")
        self.video_file = _path("output", "final.mp4")
        self.result_file = _path("output", "result.json")

    def validate(self, *, for_upload: bool = True) -> list[str]:
        """Return a list of missing mandatory settings (empty == all good)."""
        missing: list[str] = []
        if not self.groq_api_key:
            missing.append("GROQ_API_KEY")
        if for_upload:
            if not self.yt_client_id:
                missing.append("YT_CLIENT_ID")
            if not self.yt_client_secret:
                missing.append("YT_CLIENT_SECRET")
            if not self.yt_refresh_token:
                missing.append("YT_REFRESH_TOKEN")
        return missing


settings = Settings()
