"""Production NASA pipeline: daily Short + 48-hour long-form documentary."""
from __future__ import annotations
import json, logging, os, sys, traceback
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts import assemble_video, fetch_images, longform, state, topics, tts, upload, write_script
from scripts.config import settings
logging.basicConfig(level=getattr(logging, settings.verbosity, logging.INFO), format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log=logging.getLogger("autospace")
LONG_FORM_INTERVAL_HOURS=48

def _load_state()->dict:
    try:return json.loads(Path(settings.state_file).read_text(encoding="utf-8"))
    except (FileNotFoundError,json.JSONDecodeError):return {}

def _long_form_due(data:dict)->bool:
    stamp=data.get("last_longform_publish")
    if not stamp:return True
    try:last=datetime.fromisoformat(stamp.replace("Z","+00:00"))
    except ValueError:return True
    return (datetime.now(timezone.utc)-last).total_seconds()>=LONG_FORM_INTERVAL_HOURS*3600

def run()->int:
    if settings.upload_only:
        script=json.loads(Path(settings.script_file).read_text(encoding="utf-8")); video=settings.video_file
        if not os.path.exists(video):raise RuntimeError(f"UPLOAD_ONLY but missing {video}")
        upload.save_result(upload.upload_video(script,video));return 0
    missing=settings.validate(for_upload=not settings.dry_run)
    if missing:raise RuntimeError("Missing required settings: "+", ".join(missing))
    previous=_load_state()
    with __import__('tempfile').TemporaryDirectory(prefix="nasa-videos-") as tmp:
        root=Path(tmp)
        short_topic=topics.pick_topic(settings.state_file)
        if not short_topic:raise RuntimeError("No NASA Short topic available")
        log.info("Building daily NASA Short: %s",short_topic["title"])
        short_script=write_script.write_script(short_topic);write_script.save_script(short_script)
        images=fetch_images.absolute_image_paths(fetch_images.fetch_images(short_script))
        audio=tts.generate_audio(short_script)
        short_path=assemble_video.build_video(short_script,audio,images)
        if settings.dry_run:
            log.info("DRY_RUN=1; no uploads or state changes");return 0
        short_result=upload.upload_video(short_script,short_path);upload.save_result(short_result)
        state.mark_used(settings.state_file,short_topic["id"],short_result.get("title") or short_script["title"])
        log.info("Short uploaded: %s",short_result.get("url"))
        if _long_form_due(previous):
            long_topic=topics.pick_topic(settings.state_file)
            if not long_topic:raise RuntimeError("No NASA topic available for documentary")
            log.info("Building 25-35 minute NASA documentary: %s",long_topic["title"])
            long_path,long_script=longform.build(long_topic,root/"long")
            long_result=upload.upload_video(long_script,str(long_path));upload.save_result(long_result)
            state.mark_used(settings.state_file,long_topic["id"],long_result.get("title") or long_script["title"])
            data=_load_state();data["last_longform_publish"]=datetime.now(timezone.utc).isoformat();state.save_state(settings.state_file,data)
            log.info("Long-form uploaded: %s; next documentary due in 48 hours",long_result.get("url"))
    return 0

def main()->int:
    try:return run()
    except Exception as exc:log.error("Pipeline failed: %s",exc);log.debug(traceback.format_exc());return 2

if __name__=="__main__":raise SystemExit(main())
