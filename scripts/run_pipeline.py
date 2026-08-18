"""End-to-end pipeline: topic → script → images → narration → video → upload.

Runs identically in GitHub Actions and locally:

    python scripts/run_pipeline.py

Set DRY_RUN=1 to build the video without uploading it to YouTube.
Set UPLOAD_ONLY=1 to re-upload an already-built video (after a YT hiccup).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import assemble_video, fetch_images, state, topics, tts, upload, write_script  # noqa: E402
from scripts.config import settings  # noqa: E402

logging.basicConfig(
    level=getattr(logging, settings.verbosity, logging.INFO),
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("autospace")


def _save_topic(topic: dict) -> None:
    os.makedirs(settings.output_dir, exist_ok=True)
    with open(settings.topic_file, "w", encoding="utf-8") as fh:
        json.dump(topic, fh, ensure_ascii=False, indent=2)


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def run() -> int:
    if settings.upload_only:
        script = _load(settings.script_file)
        if not os.path.exists(settings.video_file):
            log.error("UPLOAD_ONLY set but no video found at %s", settings.video_file)
            return 1
        result = upload.upload_video(script, settings.video_file)
        upload.save_result(result)
        log.info("Re-upload done: %s", result.get("url") or result)
        return 0

    missing = settings.validate(for_upload=not settings.dry_run)
    if missing and not settings.dry_run:
        log.error("Missing required settings: %s", ", ".join(missing))
        return 1

    # 1. Topic
    topic = None
    for attempt in range(settings.max_topic_retries):
        topic = topics.pick_topic(settings.state_file)
        if topic:
            break
        log.warning("Topic selection returned nothing (attempt %s)", attempt + 1)
    if not topic:
        log.error("No topic could be selected")
        return 1
    _save_topic(topic)
    log.info("Topic: %s [%s]", topic["title"], topic["category"])

    # 2. Script
    log.info("Writing narration script...")
    script = write_script.write_script(topic)
    write_script.save_script(script)
    log.info("Script done (%s segments, source=%s)", len(script["segments"]), script.get("source"))

    # 3. Images
    log.info("Fetching images...")
    manifest = fetch_images.fetch_images(script)
    image_paths = fetch_images.absolute_image_paths(manifest)
    missing_imgs = sum(1 for p in image_paths if not p)
    log.info("Images fetched: %s/%s (fallbacks: %s)", len(image_paths) - missing_imgs, len(image_paths), missing_imgs)

    # 4. Narration
    log.info("Generating narration audio...")
    audio_segments = tts.generate_audio(script)
    total_audio = round(sum(a["duration"] for a in audio_segments), 1)
    log.info("Narration done: %s segments, ~%ss total", len(audio_segments), total_audio)

    # 5. Video
    log.info("Assembling video (this can take a few minutes)...")
    video_path = assemble_video.build_video(script, audio_segments, image_paths)
    log.info("Video ready: %s", video_path)

    # 6. Upload
    if settings.dry_run:
        log.info("DRY_RUN=1, skipping upload")
        upload.save_result({"dry_run": True, "title": script["title"], "video": video_path})
        state.mark_used(settings.state_file, topic["id"], script["title"])
        log.info("State updated (dry run still marks the topic as used)")
        return 0

    log.info("Uploading to YouTube...")
    result = upload.upload_video(script, video_path)
    upload.save_result(result)
    log.info("Uploaded: %s", result.get("url", "?"))
    state.mark_used(settings.state_file, topic["id"], result.get("title") or script["title"])
    log.info("State updated. Done.")

    print("\n=== SUMMARY ===")
    print(f"Title : {script['title']}")
    print(f"URL   : {result.get('url', '(dry run)')}")
    print(f"Segs  : {len(script['segments'])}  Audio: {total_audio}s")
    print(f"State : {settings.state_file}")
    return 0


def main() -> int:
    try:
        return run()
    except Exception as exc:  # noqa: BLE001
        log.error("Pipeline failed: %s", exc)
        log.debug(traceback.format_exc())
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
