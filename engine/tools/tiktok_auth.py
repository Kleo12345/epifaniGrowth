#!/usr/bin/env python3
"""
One-time TikTok login → saves TIKTOK_REFRESH_TOKEN (valid ~1 year) to engine/.env.
After this the engine mints its own 24h access tokens (publishers/upload_post_publisher.py).

Prereqs (developers.tiktok.com → your app):
  - Products: Login Kit + Content Posting API
  - Scopes: user.info.basic, user.info.stats, video.upload, video.list
  - Redirect URI registered exactly as TIKTOK_REDIRECT_URI (default https://www.epifanii.com/)
  - TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET in engine/.env

Run:
  python tools/tiktok_auth.py
Open the printed link, approve, and paste back the full URL you get redirected to
(the page itself doesn't matter — only the ?code=... in its address).
"""
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

ENG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENG))
load_dotenv(ENG / ".env")

from publishers.upload_post_publisher import save_env_value

SCOPES = "user.info.basic,user.info.stats,video.upload,video.list"


def main() -> None:
    key = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
    secret = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
    redirect = os.getenv("TIKTOK_REDIRECT_URI", "https://www.epifanii.com/").strip()
    if not (key and secret):
        sys.exit("Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in engine/.env first.")

    state = secrets.token_urlsafe(16)
    url = "https://www.tiktok.com/v2/auth/authorize/?" + urlencode({
        "client_key": key, "scope": SCOPES, "response_type": "code",
        "redirect_uri": redirect, "state": state,
    })
    print(f"\n1. Open this link and approve:\n\n{url}\n")
    pasted = input("2. Paste the full URL you were redirected to:\n> ").strip()
    query = parse_qs(urlparse(pasted).query)
    if query.get("state", [""])[0] != state:
        sys.exit("✗ State mismatch — paste the URL from THIS login attempt.")
    if "code" not in query:
        sys.exit(f"✗ No code in that URL: {query.get('error_description') or query}")

    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        data={"client_key": key, "client_secret": secret, "code": query["code"][0],
              "grant_type": "authorization_code", "redirect_uri": redirect},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    data = resp.json()
    if "refresh_token" not in data:
        sys.exit(f"✗ Token exchange failed: {data}")
    save_env_value("TIKTOK_REFRESH_TOKEN", data["refresh_token"])
    print(f"✓ Saved TIKTOK_REFRESH_TOKEN to {ENG / '.env'} (scopes: {data.get('scope')})")


if __name__ == "__main__":
    main()
