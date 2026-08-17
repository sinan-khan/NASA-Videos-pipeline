# Auto Space Video

A fully-automated YouTube channel pipeline. Twice a day, a scheduled GitHub
Actions job picks a fresh space topic, writes an **original** narration script,
finds NASA imagery, generates voiceover, assembles a vertical video, uploads it
to YouTube, and records the topic so it never repeats — with **zero manual
work** once it's live.

Everything runs on free tiers:

| Piece | Cost |
|---|---|
| GitHub Actions (cron + build) | Free (public repos unlimited; private 2,000 min/mo) |
| YouTube Data API v3 | Free |
| NASA API key | Free |
| Groq API | Free tier |
| edge-tts / gTTS (voiceover) | Free, no key |
| FFmpeg | Free / open source |

## How it works

```
cron (2x/day)
   └─ pick topic (never repeats, state in used-topics.json)
        └─ write original script (Groq)  ── fallback: local template narration
             └─ fetch images (NASA Image Library) ── fallback: APOD ── fallback: gradient
                  └─ voiceover (edge-tts) ── fallback: gTTS
                       └─ assemble 1080x1920 video (FFmpeg: Ken Burns + captions + optional music)
                            └─ upload to YouTube (resumable, retries)
                                 └─ commit state, upload artifacts, done
```

Every stage degrades gracefully: if Groq is down, narration still gets written;
if NASA is unreachable, images still get found; if the upload hiccups, the video
is kept as a CI artifact and can be re-uploaded with `UPLOAD_ONLY=1`.

## Repository layout

```
.github/workflows/daily-video.yml  # the scheduled job + manual trigger
scripts/
  run_pipeline.py        # orchestrator (topic → upload)
  topics.py              # curated topic pool + selection logic
  write_script.py        # LLM script writer + offline fallback
  fetch_images.py        # NASA image search + fallbacks
  tts.py                 # edge-tts narration (+ gTTS fallback)
  captions.py            # .ass subtitle generation
  assemble_video.py      # FFmpeg: Ken Burns, captions, music, render
  upload.py              # YouTube Data API v3 uploader
  oauth_local.py         # ONE-TIME local auth → refresh token
  setup_secrets.sh       # pushes all secrets to GitHub
requirements.txt
.env.example             # template for local runs
used-topics.json         # state file (committed after every run)
```

## Get it live

Full step-by-step guide: [SETUP.md](SETUP.md)

Quick version:

1. Create your YouTube channel.
2. Create a Google Cloud project, enable **YouTube Data API v3**, configure the
   OAuth consent screen (add yourself as a test user), and create a **Desktop
   app** OAuth client.
3. Run `python scripts/oauth_local.py` locally and click Allow once — it prints
   the refresh token that lets the workflow upload forever.
4. Grab a free [NASA API key](https://api.nasa.gov) and a free
   [Groq API key](https://console.groq.com).
5. Push this repo to GitHub, then run
   `bash scripts/setup_secrets.sh owner/repo` to add every secret.
6. Trigger the workflow manually once to confirm a real video uploads.
7. Edit the cron in `.github/workflows/daily-video.yml` if you want different
   times, push, and it runs forever.

## Configuration

All settings live in GitHub Secrets (or `.env` locally). See `.env.example`.

| Secret | Purpose |
|---|---|
| `GROQ_API_KEY` | Script writing (free) |
| `NASA_API_KEY` | Imagery (free, optional — `DEMO_KEY` works) |
| `YT_CLIENT_ID` / `YT_CLIENT_SECRET` | OAuth client from Google Cloud |
| `YT_REFRESH_TOKEN` | From the one-time `oauth_local.py` run |
| `YT_PRIVACY_STATUS` | `private` (default) → `unlisted` → `public` |
| `CHANNEL_HANDLE` | Optional `@handle` watermark burned into videos |
| `NOTIFY_WEBHOOK` | Optional Discord/Slack URL for failure alerts |
| `MUSIC_URL` | Optional royalty-free background music link |
| `VIDEO_VOICE` | Optional TTS voice override |

## Local testing

```bash
pip install -r requirements.txt
# apt-get install ffmpeg   (macOS: brew install ffmpeg)
cp .env.example .env       # fill in your keys

# Build a video WITHOUT uploading (good first check):
DRY_RUN=1 python scripts/run_pipeline.py

# Build + upload for real:
python scripts/run_pipeline.py
```

## Notes on running a healthy channel

- **Original scripts matter.** Groq writes fresh narration every run; the
  offline fallback also rephrases seed facts. Nothing reuses NASA's text
  verbatim, which keeps content varied.
- Start with `YT_PRIVACY_STATUS=private`, review a couple of videos, then flip
  it to `public`.
- Check the Actions tab after the first scheduled run; artifacts contain the
  finished MP4 so you can inspect quality before anything goes public.
- Voice, narration style, hooks and image sources rotate automatically to keep
  consecutive uploads feeling fresh.
