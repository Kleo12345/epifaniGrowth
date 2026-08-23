"""
Direct publisher for YouTube Shorts using YouTube Data API v3 via official Google OAuth 2.0 flow.
Does not require heavy Google libraries.
"""
import os
import time
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()


def is_configured() -> bool:
    """Check if YouTube credentials are configured in .env."""
    return bool(
        os.getenv("YOUTUBE_CLIENT_ID")
        and os.getenv("YOUTUBE_CLIENT_SECRET")
        and os.getenv("YOUTUBE_REFRESH_TOKEN")
    )


def _get_access_token() -> str:
    """Refresh the OAuth 2.0 access token using the refresh token."""
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        raise ValueError(
            "YouTube credentials missing. Need YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN in .env"
        )

    url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    
    resp = requests.post(url, data=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def post_short(video_path: Path, title: str, description: str = "") -> str:
    """
    Uploads a vertical video to YouTube as a Short using resumable upload.
    Returns the YouTube Video ID on success.
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    access_token = _get_access_token()
    video_size = os.path.getsize(video_path)

    # 1. Initialize Resumable Upload Session
    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": str(video_size),
        "X-Upload-Content-Type": "video/mp4",
    }

    # YouTube Shorts titles should be within 100 characters.
    # We append #Shorts to the description/title to help YouTube classify it.
    title_clean = title[:90]
    if "#Shorts" not in title_clean and len(title_clean) <= 90:
        title_clean += " #Shorts"

    desc_clean = description
    if "#Shorts" not in desc_clean:
        desc_clean = f"{desc_clean}\n\n#Shorts".strip()

    metadata = {
        "snippet": {
            "title": title_clean,
            "description": desc_clean,
            "categoryId": "17",  # Sports category
        },
        "status": {
            "privacyStatus": "public",  # Can be "public", "unlisted", "private"
            "selfDeclaredMadeForKids": False,
        },
    }

    print(f"  Initializing YouTube upload for: {title_clean}")
    resp = requests.post(init_url, json=metadata, headers=headers, timeout=30)
    resp.raise_for_status()

    upload_url = resp.headers.get("Location")
    if not upload_url:
        raise RuntimeError("Failed to retrieve upload session location from YouTube API.")

    # 2. Upload the raw video file
    print("  Uploading video file to YouTube...")
    put_headers = {
        "Content-Length": str(video_size),
        "Content-Type": "video/mp4",
    }
    with open(video_path, "rb") as f:
        upload_resp = requests.put(upload_url, data=f, headers=put_headers, timeout=300)
        upload_resp.raise_for_status()

    res_data = upload_resp.json()
    video_id = res_data.get("id")
    if not video_id:
        raise RuntimeError(f"Failed to get video ID: {upload_resp.text}")

    print(f"  ✓ YouTube Short published successfully! Video ID: {video_id}")
    return video_id


def post_all_shorts(items: list[dict], dry_run: bool = False) -> list[dict]:
    """
    Upload multiple vertical videos as YouTube Shorts.
    Each item must have: video_path, caption, match.
    """
    results = []
    if not is_configured() and not dry_run:
        print("  ⚠  YouTube API not configured (need YOUTUBE_REFRESH_TOKEN in .env)")
        return []

    for item in items:
        match_name = item.get("match", "Unknown Match")
        if dry_run:
            print(f"\n── DRY RUN: YouTube Shorts Publishing ──")
            print(f"  File:      {item['video_path']}")
            print(f"  Title:     {match_name} Pick #Shorts")
            print(f"  Caption:   {item['caption']}")
            results.append({"match": match_name, "success": True, "dry_run": True, "video_id": "dry_run_yt_id"})
            continue

        try:
            print(f"🎥 Publishing YouTube Short for {match_name}...")
            video_id = post_short(
                video_path=item["video_path"],
                title=f"{match_name} AI Prediction",
                description=item["caption"],
            )
            results.append({"match": match_name, "success": True, "video_id": video_id})
        except Exception as e:
            print(f"  ✗ YouTube Short publishing failed for {match_name}: {e}")
            results.append({"match": match_name, "success": False, "error": str(e)})

    return results
