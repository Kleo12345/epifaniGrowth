"""
Posts a 3-tweet thread to Twitter/X with an image attached to tweet 1.
Uses Tweepy v4 with OAuth 1.0a (Twitter API v2 media upload requires v1.1 media endpoint).
"""
import os
from pathlib import Path

import tweepy
from dotenv import load_dotenv

from core.script_generator import ThreadCopy

load_dotenv()


def is_configured() -> bool:
    return all([
        os.getenv("TWITTER_API_KEY"),
        os.getenv("TWITTER_API_SECRET"),
        os.getenv("TWITTER_ACCESS_TOKEN"),
        os.getenv("TWITTER_ACCESS_SECRET"),
    ])


def _client() -> tuple[tweepy.Client, tweepy.API]:
    """Return (v2 Client for posting, v1.1 API for media upload)."""
    api_key     = os.getenv("TWITTER_API_KEY", "")
    api_secret  = os.getenv("TWITTER_API_SECRET", "")
    access_tok  = os.getenv("TWITTER_ACCESS_TOKEN", "")
    access_sec  = os.getenv("TWITTER_ACCESS_SECRET", "")

    if not all([api_key, api_secret, access_tok, access_sec]):
        raise RuntimeError("Twitter credentials missing — check your .env file.")

    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_tok, access_sec)
    v1_api = tweepy.API(auth)

    v2_client = tweepy.Client(
        consumer_key        = api_key,
        consumer_secret     = api_secret,
        access_token        = access_tok,
        access_token_secret = access_sec,
    )
    return v2_client, v1_api


def post_thread(thread: ThreadCopy, image_path: Path | None = None, dry_run: bool = False) -> list[str]:
    """
    Post a 3-tweet thread.  Image is attached to tweet 1 if provided.

    Returns list of tweet URLs (or dry-run previews).
    """
    tweets = thread.as_list()
    pick   = thread.pick

    if dry_run:
        print(f"\n── DRY RUN: Thread for {pick.match} ──")
        for i, t in enumerate(tweets, 1):
            print(f"  [{i}] {t}")
        if image_path:
            print(f"  [IMG] {image_path}")
        return [f"[dry-run] tweet {i+1}" for i in range(3)]

    client, v1_api = _client()
    posted_ids: list[str] = []

    # Upload image via v1.1 (required for media_id)
    media_id = None
    if image_path and Path(image_path).exists():
        media = v1_api.media_upload(str(image_path))
        media_id = media.media_id_string

    # Tweet 1 — hook + image
    kwargs: dict = {}
    if media_id:
        kwargs["media_ids"] = [media_id]
    resp1 = client.create_tweet(text=tweets[0], **kwargs)
    posted_ids.append(str(resp1.data["id"]))

    # Tweet 2 — reply to tweet 1
    resp2 = client.create_tweet(text=tweets[1], in_reply_to_tweet_id=posted_ids[-1])
    posted_ids.append(str(resp2.data["id"]))

    # Tweet 3 — reply to tweet 2
    resp3 = client.create_tweet(text=tweets[2], in_reply_to_tweet_id=posted_ids[-1])
    posted_ids.append(str(resp3.data["id"]))

    urls = [f"https://twitter.com/i/web/status/{tid}" for tid in posted_ids]
    print(f"  ✓ Thread posted: {urls[0]}")
    return urls


def post_all_threads(pairs: list[dict], dry_run: bool = False) -> list[dict]:
    """
    Post multiple threads. Each item in pairs must have keys: thread, square (image path).
    Returns list of result dicts.
    """
    results = []
    for item in pairs:
        thread     = item["thread"]
        image_path = item.get("square")
        try:
            urls = post_thread(thread, image_path=image_path, dry_run=dry_run)
            results.append({"match": thread.pick.match, "success": True, "urls": urls})
        except Exception as e:
            print(f"  ✗ Post failed for {thread.pick.match}: {e}")
            results.append({"match": thread.pick.match, "success": False, "error": str(e)})
    return results
