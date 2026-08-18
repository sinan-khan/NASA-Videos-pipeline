"""One-time local authorization: turns your Google login into a refresh token.

Run this ONCE on your own machine (it opens a browser and you click
"Allow" -- this is the only manual step in the entire pipeline, Google
does not allow it to be scripted away):

    pip install -r requirements.txt
    YT_CLIENT_ID=... YT_CLIENT_SECRET=... python scripts/oauth_local.py

It prints a refresh token. Add it to your GitHub repository Secrets as
YT_REFRESH_TOKEN and the workflow will be able to upload forever, silently.
"""

from __future__ import annotations

import os

from scripts.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def main() -> None:
    client_id = settings.yt_client_id or input("OAuth Client ID: ").strip()
    client_secret = settings.yt_client_secret or input("OAuth Client Secret: ").strip()
    if not client_id or not client_secret:
        raise SystemExit("Missing OAuth Client ID/Secret. Create them at Google Cloud console → Credentials → OAuth client ID → Desktop app.")

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config(
        {"installed": {"client_id": client_id, "client_secret": client_secret, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": ["http://localhost"]}},
        scopes=SCOPES,
    )
    creds = flow.run_local_server(port=0, prompt="consent", authorization_prompt_message="", success_message="Done! You can close this tab and return to the terminal.")

    print("\n" + "=" * 60)
    print("Refresh token (keep it secret):")
    print(creds.refresh_token)
    print("=" * 60)
    print("\nAdd this as the YT_REFRESH_TOKEN secret in your GitHub repo.")


if __name__ == "__main__":
    main()
