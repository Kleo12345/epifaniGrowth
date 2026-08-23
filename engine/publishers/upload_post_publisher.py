"""
Direct publishers for TikTok and Instagram Reels using their official free Developer APIs.
Replaces the paid Upload-Post service integration.
"""
import os
import time
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

# We keep these for backwards compatibility with the scheduler/dashboard,
# but we map them to the official APIs.
PLATFORMS = ["tiktok", "instagram"]


def is_configured() -> bool:
    """Check if either Instagram or TikTok credentials are configured."""
    has_instagram = bool(os.getenv("INSTAGRAM_ACCESS_TOKEN"))
    has_tiktok = bool(os.getenv("TIKTOK_ACCESS_TOKEN"))
    return has_instagram or has_tiktok


def _upload_to_temp_host(video_path: Path) -> str:
    """
    Uploads the video temporarily to a free file sharing service
    so Meta's API can fetch it. Once published, the file is no longer needed.
    """
    # Attempt 1: Catbox.moe (Free, fast, no limits)
    try:
        url = "https://catbox.moe/user/api.php"
        with open(video_path, "rb") as f:
            files = {"fileToUpload": f}
            data = {"reqtype": "fileupload"}
            resp = requests.post(url, files=files, data=data, timeout=90)
            if resp.status_code == 200 and resp.text.startswith("http"):
                return resp.text.strip()
    except Exception as e:
        print(f"  ⚠  Catbox upload failed: {e}. Trying fallback...")

    # Attempt 2: File.io (Free, expires in 1 day, automatically deleted after 1 download)
    try:
        url = "https://file.io"
        with open(video_path, "rb") as f:
            files = {"file": f}
            resp = requests.post(url, files=files, timeout=90)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("success") and result.get("link"):
                    return result.get("link")
    except Exception as e:
        print(f"  ⚠  File.io upload failed: {e}")

    raise RuntimeError("Failed to host video on temporary storage for Meta to fetch.")


def _post_instagram(video_path: Path, caption: str) -> str:
    """Publish video to Instagram Reels via new Instagram Business API."""
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")

    if not access_token:
        raise ValueError("Instagram credentials missing. Need INSTAGRAM_ACCESS_TOKEN in .env")

    print("  Uploading video to temporary hosting for Instagram...")
    public_url = _upload_to_temp_host(video_path)
    print(f"  Hosted at: {public_url}")

    headers = {"Authorization": f"Bearer {access_token}"}

    # Step 1: Create the media container
    payload = {
        "media_type": "REELS",
        "video_url": public_url,
        "caption": caption,
        "share_to_feed": "true",
    }
    resp = requests.post(
        "https://graph.instagram.com/v21.0/me/media",
        headers=headers, data=payload, timeout=30
    )
    resp.raise_for_status()
    container_id = resp.json().get("id")
    if not container_id:
        raise RuntimeError(f"Failed to get container ID: {resp.text}")

    print(f"  Created IG container: {container_id}. Waiting for Instagram to process video...")

    # Step 2: Poll for processing completion (max 5 minutes)
    for _ in range(30):
        time.sleep(10)
        status_resp = requests.get(
            f"https://graph.instagram.com/v21.0/{container_id}",
            headers=headers,
            params={"fields": "status_code"},
            timeout=20
        )
        status_resp.raise_for_status()
        status_code = status_resp.json().get("status_code")
        if status_code == "FINISHED":
            print("  Video processing finished on Instagram servers.")
            break
        elif status_code == "ERROR":
            raise RuntimeError("Instagram failed to process the video.")
        print(f"  Status: {status_code}... waiting")
    else:
        raise TimeoutError("Instagram video processing timed-out.")

    # Step 3: Publish the Reel
    publish_resp = requests.post(
        "https://graph.instagram.com/v21.0/me/media_publish",
        headers=headers,
        data={"creation_id": container_id},
        timeout=30
    )
    publish_resp.raise_for_status()
    post_id = publish_resp.json().get("id")
    print(f"  ✓ Instagram Reel published successfully: {post_id}")
    return post_id


def _post_tiktok(video_path: Path, caption: str) -> str:
    """Upload video to TikTok via official Content Posting API or note that it is saved locally for manual upload."""
    access_token = os.getenv("TIKTOK_ACCESS_TOKEN")

    if not access_token:
        raise ValueError("TikTok credentials missing. Need TIKTOK_ACCESS_TOKEN in .env")

    if access_token.lower() in ("manual", "local", "telegram"):
        print(f"\n📢  [MANUAL TIKTOK POST] Video saved locally:")
        print(f"  File path: {video_path}")
        print(f"  Caption:\n{caption}\n")
        return "saved_locally"

    video_size = os.path.getsize(video_path)

    # Step 1: Initialize Upload
    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8"
    }
    payload = {
        "post_info": {
            "title": caption[:150],  # TikTok title limit is 150 characters
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_stitch": False,
            "disable_comment": False
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": video_size,
            "total_chunk_count": 1
        }
    }
    resp = requests.post(init_url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    res_data = resp.json()

    if res_data.get("error", {}).get("code") != "ok":
        raise RuntimeError(f"TikTok Init failed: {res_data.get('error', {}).get('message')}")

    upload_url = res_data["data"]["upload_url"]
    publish_id = res_data["data"]["publish_id"]
    print(f"  Initialized TikTok upload (publish_id: {publish_id}). Uploading video...")

    # Step 2: Upload Video File
    with open(video_path, "rb") as f:
        put_headers = {
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
            "Content-Length": str(video_size),
            "Content-Type": "video/mp4"
        }
        upload_resp = requests.put(upload_url, data=f, headers=put_headers, timeout=300)
        upload_resp.raise_for_status()

    print(f"  ✓ TikTok video uploaded successfully (publish_id: {publish_id})")
    return publish_id


def post_video(
    video_path: Path,
    caption: str,
    platforms: list[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    Upload a video to TikTok and/or Instagram Reels.
    """
    platforms = platforms or PLATFORMS
    
    # Filter to only the platforms that have environment variables configured
    configured_platforms = []
    if "instagram" in platforms and os.getenv("INSTAGRAM_ACCESS_TOKEN"):
        configured_platforms.append("instagram")
    if "tiktok" in platforms and os.getenv("TIKTOK_ACCESS_TOKEN"):
        configured_platforms.append("tiktok")

    if not configured_platforms:
        print("  ⚠  No direct video publishers configured in .env (need INSTAGRAM_ACCESS_TOKEN or TIKTOK_ACCESS_TOKEN)")
        return {"success": False, "error": "No direct video publishers configured"}

    if dry_run:
        print(f"\n── DRY RUN: Direct Video Publishing ──")
        print(f"  File:      {video_path}")
        print(f"  Caption:   {caption[:80]}...")
        print(f"  Platforms: {', '.join(configured_platforms)}")
        return {"success": True, "dry_run": True, "request_id": "dry_run_id"}

    if not Path(video_path).exists():
        return {"success": False, "error": f"Video file not found: {video_path}"}

    successes = []
    errors = []
    request_id = f"direct_{int(time.time())}"

    # Instagram
    if "instagram" in configured_platforms:
        try:
            print("🎥 Publishing Reel to Instagram...")
            _post_instagram(video_path, caption)
            successes.append("instagram")
        except Exception as e:
            print(f"  ✗ Instagram publishing failed: {e}")
            errors.append(f"Instagram: {str(e)}")

    # TikTok
    if "tiktok" in configured_platforms:
        try:
            print("🎥 Publishing Video to TikTok...")
            _post_tiktok(video_path, caption)
            successes.append("tiktok")
        except Exception as e:
            print(f"  ✗ TikTok publishing failed: {e}")
            errors.append(f"TikTok: {str(e)}")

    if successes:
        print(f"  ✓ Successfully posted to: {', '.join(successes)}")
        return {"success": True, "request_id": request_id, "platforms": successes}
    else:
        return {"success": False, "error": "; ".join(errors)}


def post_all_videos(items: list[dict], dry_run: bool = False) -> list[dict]:
    """
    Post multiple videos. Each item must have: video_path, caption.
    """
    results = []
    for item in items:
        result = post_video(
            video_path=item["video_path"],
            caption=item["caption"],
            dry_run=dry_run,
        )
        results.append({"match": item.get("match", ""), **result})
    return results
