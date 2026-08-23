"""
Builds branded short-form videos for each pick.

Pipeline:
  1. Generate script via Gemini (30-45s voiceover script)
  2. Start MoneyPrinterTurbo as a local API (localhost:8080)
  3. POST the script → MPT assembles stock footage + Edge-TTS + subtitles
  4. Poll until complete, download the .mp4
  5. ffmpeg post-process: add intro card, Epifani watermark, outro card
"""
import os
import subprocess
import sys
import time
import json
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

from core.prediction_fetcher import Pick

load_dotenv()

BASE_DIR   = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "assets" / "output" / "videos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MPT_DIR  = BASE_DIR.parent / "MoneyPrinterTurbo"
MPT_URL  = os.getenv("MPT_URL", "http://localhost:8080")
MPT_PORT = 8080

# Branding overlay settings
WATERMARK_TEXT = "EPIFANI AI"
FONT_COLOR     = "0x00f2ff"   # cyan
INTRO_DURATION = 3            # seconds
OUTRO_DURATION = 5            # seconds


# ── MPT process management ────────────────────────────────────────

_mpt_process = None

def start_mpt() -> bool:
    """Start MoneyPrinterTurbo API as a background subprocess if not already running."""
    global _mpt_process

    # Check if already up
    try:
        r = requests.get(f"{MPT_URL}/docs", timeout=3)
        if r.status_code == 200:
            return True
    except requests.RequestException:
        pass

    main_py = MPT_DIR / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(
            f"MoneyPrinterTurbo not found at {MPT_DIR}. "
            "Ensure it is cloned inside the epifaniGrowthPlan directory."
        )

    # Reuse the interpreter running this process — correct on Linux/macOS/Windows
    # and for both conda and venv, unlike reconstructing a conda bin/ path (which
    # doesn't exist on Windows, where python.exe sits at the env root).
    python_bin = sys.executable

    _mpt_process = subprocess.Popen(
        [python_bin, str(main_py)],
        cwd=str(MPT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait up to 30s for it to become ready
    for _ in range(30):
        time.sleep(1)
        try:
            r = requests.get(f"{MPT_URL}/docs", timeout=2)
            if r.status_code == 200:
                print("  ✓ MoneyPrinterTurbo API ready")
                return True
        except requests.RequestException:
            pass

    raise RuntimeError("MoneyPrinterTurbo failed to start within 30 seconds.")


def stop_mpt():
    global _mpt_process
    if _mpt_process and _mpt_process.poll() is None:
        _mpt_process.terminate()
        _mpt_process = None


# ── Script generation for video ───────────────────────────────────

def _video_script(pick: Pick, story_highlight: str = "") -> str:
    """Generate a 30-45s spoken voiceover script for the pick."""
    from google import genai
    import time
    
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)
    
    story_hook = ""
    if story_highlight:
        story_hook = f"\n- Hook: Incorporate this founder's daily journey update: \"{story_highlight}\" as a personal narrative hook at the beginning, linking it smoothly to the prediction."
    else:
        story_hook = "\n- Hook: Start with a strong 'building in public' founder hook (e.g., 'Day 12 of coding my betting AI...' or 'Why I coded an AI because bookies always win...'). Keep the tone first-person ('I', 'my model')."

    prompt = f"""Write a 30-45 second spoken voiceover script for a TikTok/Reels video about this AI football prediction.

Match: {pick.match}
Pick: {pick.label}
Odds: {pick.odds}
AI Confidence: {pick.confidence_pct}%
Edge: +{round(pick.edge * 100, 1)}%
Tier: {pick.tier}

Rules:
- Speak in the first person ("I built this AI", "my algorithm found", etc.) as a developer/founder sharing their building-in-public journey.{story_hook}
- Keep it natural, casual, and highly engaging (like the GreenCode developer style).
- Mention the match, the pick, and the confidence.
- Explain briefly why this is a value bet (edge).
- End with a CTA: "I post our code updates and predictions daily. Follow to see if we win, or get the full picks list free at epifanii.com."
- Spoken, natural English — no stage directions, no emojis, no bullet points.
- Pure text only, as it will be fed directly to text-to-speech."""

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    max_retries = 3
    delay_secs = 10
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            return response.text.strip()
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                if attempt < max_retries - 1:
                    print(f"  ⚠ Gemini rate limited (429) during video script generation. Retrying in {delay_secs}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(delay_secs)
                    continue
            raise e


# ── MPT API interaction ───────────────────────────────────────────

def _submit_video_task(script: str, subject: str) -> str:
    """Submit a video generation task to MPT and return the task_id."""
    payload = {
        "video_subject":    subject,
        "video_script":     script,
        "video_language":   "English",
        "voice_name":       "en-US-EricNeural-Male",
        "video_source":     "pexels",
        "video_aspect":     "9:16",
        "video_clip_duration": 5,
        "subtitle_enabled": True,
        "paragraph_number": 1,
        "video_count":      1,
    }
    resp = requests.post(f"{MPT_URL}/api/v1/videos", json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["task_id"]


def _poll_task(task_id: str, timeout: int = 300) -> str:
    """Poll MPT until the task completes. Returns the local video file path."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(5)
        try:
            resp = requests.get(f"{MPT_URL}/api/v1/tasks/{task_id}", timeout=10)
            resp.raise_for_status()
            task = resp.json().get("data", {})
            state = task.get("state", 0)

            if state == 1:  # complete
                videos = task.get("videos", [])
                if videos:
                    return videos[0]
                raise RuntimeError("Task complete but no video URL returned.")
            elif state == 3:  # failed
                raise RuntimeError(f"MPT task failed: {task}")
        except requests.RequestException:
            pass

    raise TimeoutError(f"MPT task {task_id} did not complete within {timeout}s.")


def _download_video(url: str, dest: Path) -> Path:
    """Download MPT video to local path."""
    if url.startswith("http"):
        r = requests.get(url, stream=True, timeout=120)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    else:
        # MPT returned a local file path
        import shutil
        shutil.copy2(url, dest)
    return dest


# ── ffmpeg branding ───────────────────────────────────────────────

def _ffmpeg_brand(
    raw_video: Path,
    out_path: Path,
    intro_title: str = "Today's AI Pick",
    intro_subtitle: str = "from EPIFANI AI",
) -> Path:
    """
    Overlay Epifani branding on the raw MPT video:
      - Watermark (top-left, semi-transparent)
      - Intro card (0-3s): configurable title + subtitle
      - Outro card (last 5s): "Get all picks free → epifanii.com"
    """
    def _esc(text: str) -> str:
        # Escape characters that break ffmpeg drawtext
        return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")

    intro_title    = _esc(intro_title)
    intro_subtitle = _esc(intro_subtitle)

    # Watermark drawtext filter
    watermark = (
        f"drawtext=text='{WATERMARK_TEXT}':"
        f"fontcolor={FONT_COLOR}:fontsize=36:alpha=0.75:"
        f"x=20:y=20"
    )

    # Overlay text for intro (0 to INTRO_DURATION seconds)
    intro = (
        f"drawtext=text='{intro_title}':"
        f"fontcolor=white:fontsize=52:alpha=1:"
        f"x=(w-text_w)/2:y=(h/2 - 60):"
        f"enable='between(t,0,{INTRO_DURATION})',"
        f"drawtext=text='{intro_subtitle}':"
        f"fontcolor={FONT_COLOR}:fontsize=40:alpha=1:"
        f"x=(w-text_w)/2:y=(h/2 + 10):"
        f"enable='between(t,0,{INTRO_DURATION})'"
    )

    # Outro text (last OUTRO_DURATION seconds)
    outro = (
        f"drawtext=text='Get all picks free':"
        f"fontcolor=white:fontsize=44:alpha=1:"
        f"x=(w-text_w)/2:y=(h/2 - 50):"
        f"enable='gte(t,max(0\\,duration-{OUTRO_DURATION}))',"
        f"drawtext=text='epifanii.com':"
        f"fontcolor={FONT_COLOR}:fontsize=52:"
        f"x=(w-text_w)/2:y=(h/2 + 20):"
        f"enable='gte(t,max(0\\,duration-{OUTRO_DURATION}))'"
    )

    vf = f"{watermark},{intro},{outro}"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_video),
        "-vf", vf,
        "-c:a", "copy",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr}")

    return out_path


# ── Public API ────────────────────────────────────────────────────

def build_video(pick: Pick, story_highlight: str = "") -> Path:
    """
    Full pipeline for one pick: script → MPT → ffmpeg branding → branded .mp4.
    Returns path to the final branded video.
    """
    print(f"  🎬 Generating video: {pick.match}")

    script = _video_script(pick, story_highlight)
    print(f"     Script ready ({len(script.split())} words)")

    task_id = _submit_video_task(script, f"{pick.match} — {pick.label}")
    print(f"     MPT task submitted: {task_id}")

    raw_url = _poll_task(task_id)
    print(f"     MPT task complete")

    safe    = pick.match.replace(" ", "_").replace("/", "-")
    raw_mp4 = OUTPUT_DIR / f"{safe}_raw.mp4"
    out_mp4 = OUTPUT_DIR / f"{safe}_branded.mp4"

    _download_video(raw_url, raw_mp4)
    _ffmpeg_brand(raw_mp4, out_mp4)

    raw_mp4.unlink(missing_ok=True)  # clean up raw file
    print(f"     ✓ Branded video: {out_mp4.name}")
    return out_mp4


def build_all_videos(picks: list[Pick], story_highlight: str = "") -> list[dict]:
    """Build branded videos for all picks. Returns list of {pick, video_path}."""
    start_mpt()
    results = []
    for pick in picks:
        try:
            path = build_video(pick, story_highlight)
            results.append({"pick": pick, "video_path": path})
        except Exception as e:
            print(f"  ✗ Video failed for {pick.match}: {e}")
            results.append({"pick": pick, "video_path": None, "error": str(e)})
    return results


# ── Founder's Journey video (primary content) ─────────────────────

def build_journey_video(picks: list[Pick], milestone: str = "", script=None,
                        backend: str = "local", inserts: list[dict] | None = None) -> dict:
    """
    Build ONE branded Founder's Journey video for the day.

    The voiceover comes from the critic-vetted JourneyScript produced by
    script_generator.generate_journey_script. Pass a pre-generated `script`
    (e.g. the one previewed in the dashboard) to reuse it and avoid a second
    Gemini round-trip; otherwise it is generated here from `picks` + `milestone`.

    backend:
      "local" (default) — Asset Loop: local clip library + Edge-TTS + ffmpeg
                          branding. Instant, offline, the launch pipeline.
      "mpt"             — legacy MoneyPrinterTurbo stock-footage path.

    Returns {script, video_path, error?}.
    """
    from core.script_generator import generate_journey_script, JourneyScript

    if script is None:
        script = generate_journey_script(picks, milestone=milestone)
    if not isinstance(script, JourneyScript):
        raise TypeError("script must be a JourneyScript instance")

    print(f"  🎬 Building Day {script.day} journey video "
          f"(~{script.est_seconds}s, critic {script.critic_score}/10, backend={backend})")

    try:
        if backend == "local":
            from core.asset_loop import assemble_journey_video
            out_mp4 = assemble_journey_video(script, inserts=inserts)
            return {"script": script, "video_path": out_mp4}

        # ── legacy MPT backend ────────────────────────────────────
        start_mpt()
        task_id = _submit_video_task(
            script.voiceover,
            subject=f"Day {script.day} building Epifani AI football prediction engine",
        )
        print(f"     MPT task submitted: {task_id}")

        raw_url = _poll_task(task_id, timeout=600)
        print(f"     MPT task complete")

        raw_mp4 = OUTPUT_DIR / f"journey_day{script.day}_raw.mp4"
        out_mp4 = OUTPUT_DIR / f"journey_day{script.day}_branded.mp4"

        _download_video(raw_url, raw_mp4)
        _ffmpeg_brand(
            raw_mp4, out_mp4,
            intro_title=f"Day {script.day}",
            intro_subtitle="Building EPIFANI AI",
        )
        raw_mp4.unlink(missing_ok=True)

        print(f"     ✓ Journey video: {out_mp4.name}")
        return {"script": script, "video_path": out_mp4}
    except Exception as e:
        print(f"  ✗ Journey video failed: {e}")
        return {"script": script, "video_path": None, "error": str(e)}
