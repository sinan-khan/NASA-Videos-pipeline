# SETUP.md — go from zero to autopilot

Walk through these once. Steps 2–8 are one-time manual tasks; the only moment
that requires a human to *click a button* is step 6 (Google does not allow that
to be scripted away). Everything after step 12 runs itself.

---

## 1. Create your YouTube channel

- Sign in to YouTube with the Google account that should own the channel.
- Go to your channel page and create a channel (or use your existing one).
- Optional: upload a profile picture + banner so the channel looks alive.

## 2. Create the Google Cloud project

1. Go to https://console.cloud.google.com and create a project (e.g. `auto-space-video`).
2. Enable billing only if Google asks — **the YouTube Data API is free**, no card is required for this.

## 3. Enable the YouTube Data API v3

1. In the project, go to **APIs & Services → Library**.
2. Search for **YouTube Data API v3** and click **Enable**.

## 4. Set up the OAuth consent screen

1. **APIs & Services → OAuth consent screen**.
2. User type: **External** (yes, even for your own channel).
3. Fill app name (e.g. `Auto Space Video`) and your email.
4. On **Audience**, add your own Google account as a **Test user**.
5. No scopes need to be added manually here — the local auth script requests
   the upload scope, and the consent screen will ask you to approve it.
   (Optional: press "Add or remove scopes" and add
   `https://www.googleapis.com/auth/youtube.upload` to avoid the unverified-app warning.)

## 5. Create OAuth client credentials

1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. Application type: **Desktop app**. (Simplest for the one-time auth.)
3. Copy the **Client ID** and **Client Secret** — you'll need them next.

## 6. One-time authorization (the only manual click)

On your own computer:

```bash
git clone <your-repo-url> && cd <repo>
pip install -r requirements.txt

YT_CLIENT_ID=xxxx YT_CLIENT_SECRET=xxxx python scripts/oauth_local.py
```

- A browser opens → pick your Google account → click **Allow**.
- The script prints a **refresh token**. Treat it like a password.

## 7. Get a free NASA API key

- Sign up at https://api.nasa.gov → instant key by email.
- (The pipeline also works without a key using `DEMO_KEY`, but the real key
  gives a higher rate limit.)

## 8. Get a free Groq API key

- Sign up at https://console.groq.com → **API Keys** → create one.
- (Model default `llama-3.3-70b-versatile`, free tier. Change with `GROQ_MODEL`.)

## 9. Create the GitHub repo

- Create a new repo on GitHub (public = unlimited Actions minutes; private =
  2,000 min/month — plenty for ~60 runs/month).
- Push this project:

```bash
git add .
git commit -m "feat: automated space video pipeline"
git branch -M main
git remote add origin git@github.com:YOU/REPO.git
git push -u origin main
```

## 10. Add all secrets

```bash
# login once
gh auth login

# interactive: fills every secret and asks for the optional ones
bash scripts/setup_secrets.sh YOU/REPO
```

Required secrets: `GROQ_API_KEY`, `NASA_API_KEY`, `YT_CLIENT_ID`,
`YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
Optional: `YT_PRIVACY_STATUS`, `YT_LANGUAGE`, `CHANNEL_HANDLE`,
`NOTIFY_WEBHOOK`, `MUSIC_URL`, `VIDEO_VOICE`, `GROQ_MODEL`.

Verify with `gh secret list --repo YOU/REPO`.

## 11. (Done) The code is already scaffolded

`scripts/` + `.github/workflows/daily-video.yml` are ready as-is.

## 12. Manual test run

1. GitHub → **Actions** → **Auto Space Video** → **Run workflow**.
2. Watch the job: topic → script → images → narration → video → upload.
3. If the upload succeeded, check YouTube Studio → **Content** (privacy is
   `private` by default). Download the `video-output` artifact to inspect the
   MP4 quality.

> Trouble? Re-run with the artifact: the workflow uploads `output/final.mp4`
> even when the YouTube upload fails, so you always keep the produced video.

## 13. Turn on the schedule

The workflow already runs at **12:00 and 18:00 UTC** daily (UTC, not local
time). To change it, edit the `cron` line in
`.github/workflows/daily-video.yml`:

```yaml
- cron: '0 12,18 * * *'   # hour minute UTC: 0 12 = 12:00 UTC
```

Push the change. From here it runs forever — no more human involvement.

## 14. Let it run

- Each run commits `used-topics.json` so topics never repeat.
- A failed run notifies your `NOTIFY_WEBHOOK` (if set) and keeps the video
  artifact.
- Review uploaded videos occasionally under YouTube Studio while private, then
  flip `YT_PRIVACY_STATUS` to `unlisted` or `public` when you're confident.

---

## Re-uploading a video after a failed YouTube upload

If a run produced the video but the YouTube upload failed:

1. Download the `video-output` artifact from the failed run.
2. Place `final.mp4` (and `script.json`) into `output/`.
3. Trigger a run with the `UPLOAD_ONLY` secret set to `1` — it skips
   regeneration and uploads the existing video.
   (Or locally: `UPLOAD_ONLY=1 python scripts/run_pipeline.py`.)
