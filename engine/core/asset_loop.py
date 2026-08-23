"""
Asset Loop — local Founder's Journey video assembly (no MPT / no Pexels).

Pipeline:
  1. Edge-TTS synthesizes the critic-vetted voiceover → audio.mp3 (+ word-timed .srt)
  2. A library of loopable 9:16 clips (assets/clips/*.mp4) is normalized and
     sequenced/looped to cover the audio length — falls back to an animated
     dark-tech background if the library is empty.
  3. ffmpeg muxes the voiceover, burns captions, then applies Epifani branding
     (Day X intro, watermark, epifanii.com outro).

This is the "Option A" launch pipeline from the vision recap: 100% local, instant,
and the place to drop in the Epifani character clips once they exist.
"""
import base64
import math
import os
import random
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import edge_tts
import numpy as np
import requests
from PIL import Image, ImageDraw

BASE_DIR       = Path(__file__).resolve().parent.parent
CLIPS_DIR      = BASE_DIR / "assets" / "clips"
BACKGROUND_DIR = BASE_DIR / "assets" / "background"
CHARACTER_DIR  = BASE_DIR / "assets" / "character"
OUTPUT_DIR     = BASE_DIR / "assets" / "output" / "videos"
_CACHE_DIR     = BASE_DIR / "assets" / "output" / "_clip_cache"
for _d in (CLIPS_DIR, BACKGROUND_DIR, CHARACTER_DIR, OUTPUT_DIR, _CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Character placement / animation
CHAR_HEIGHT_FRAC = 0.52    # avatar height as a fraction of the 1920 frame (smaller, calmer presence)
CHAR_MARGIN_X    = 0       # bottom-left, flush to the left edge

# Mouth position for the drawn lip-flap, as fractions of the avatar image so it
# survives scaling. Tuned to the founder avatar (character_closed.png); override
# via env if you swap the art. Only used when there is no character_open.png.
MOUTH_CX = float(os.getenv("MOUTH_CX_FRAC", "0.286"))
MOUTH_CY = float(os.getenv("MOUTH_CY_FRAC", "0.244"))
MOUTH_W  = float(os.getenv("MOUTH_W_FRAC",  "0.026"))
MOUTH_H  = float(os.getenv("MOUTH_H_FRAC",  "0.014"))

WIDTH, HEIGHT, FPS = 1080, 1920, 30
VOICE      = os.getenv("TTS_VOICE", "en-US-EricNeural")
FONT_COLOR = "0x00f2ff"   # cyan accent (matches branding)
BG_COLOR   = "0x0a0e17"   # deep navy

# ElevenLabs (preferred when ELEVENLABS_API_KEY is set)
EL_API_KEY  = os.getenv("ELEVENLABS_API_KEY", "").strip()
EL_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB").strip()  # default: Adam
EL_MODEL    = os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5").strip()


# ── helpers ───────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: str | None = None) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)}\n\n{res.stderr[-1500:]}")


def _probe_duration(path: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0


# ── 1. voiceover ──────────────────────────────────────────────────

def _fmt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _srt_from_char_alignment(chars: list[str], starts: list[float], ends: list[float],
                             max_chars: int = 28) -> str:
    """Group ElevenLabs char-level timings into short caption cues."""
    cues, buf, cue_start, idx = [], "", None, 1
    for ch, st, en in zip(chars, starts, ends):
        if cue_start is None:
            cue_start = st
        buf += ch
        flush = (len(buf) >= max_chars and ch == " ") or ch in ".!?\n"
        if flush and buf.strip():
            cues.append((idx, cue_start, en, buf.strip()))
            idx += 1
            buf, cue_start = "", None
    if buf.strip():
        cues.append((idx, cue_start or 0.0, ends[-1] if ends else 0.0, buf.strip()))
    return "\n".join(
        f"{i}\n{_fmt_ts(s)} --> {_fmt_ts(e)}\n{txt}\n" for i, s, e, txt in cues
    )


def _elevenlabs_tts(text: str, audio_path: Path, srt_path: Path) -> float:
    """ElevenLabs with-timestamps → mp3 + char-accurate SRT. Returns duration."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{EL_VOICE_ID}/with-timestamps"
    resp = requests.post(
        url,
        headers={"xi-api-key": EL_API_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": EL_MODEL,
            "voice_settings": {"stability": 0.28, "similarity_boost": 0.75,
                               "style": 0.65, "use_speaker_boost": True},
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    audio_path.write_bytes(base64.b64decode(data["audio_base64"]))
    align = data.get("alignment") or {}
    chars  = align.get("characters", [])
    starts = align.get("character_start_times_seconds", [])
    ends   = align.get("character_end_times_seconds", [])
    if chars and starts and ends:
        srt_path.write_text(_srt_from_char_alignment(chars, starts, ends), encoding="utf-8")
    else:
        srt_path.write_text("", encoding="utf-8")
    return _probe_duration(audio_path)


_EDGE_TTS_TIMEOUT = 90.0  # edge-tts's own receive_timeout (60s) doesn't reliably
                          # fire: if its background asyncio thread errors, the
                          # exception is swallowed and stream_sync() blocks on
                          # queue.get() forever. Run it on a daemon thread and
                          # give up after this many seconds instead of hanging.


def _edge_tts(text: str, audio_path: Path, srt_path: Path, voice: str) -> float:
    errors: list[BaseException] = []

    def _run() -> None:
        try:
            communicate = edge_tts.Communicate(text, voice)
            submaker = edge_tts.SubMaker()
            with open(audio_path, "wb") as f:
                for chunk in communicate.stream_sync():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    # Voices emit either Word- or SentenceBoundary; feed whichever we get.
                    elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                        submaker.feed(chunk)
            srt_path.write_text(submaker.get_srt(), encoding="utf-8")
        except BaseException as e:  # noqa: BLE001 - relayed to the caller's thread below
            errors.append(e)

    # daemon=True: if stream_sync() does stall forever, this thread is abandoned
    # rather than leaking a non-daemon thread that keeps the process alive.
    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    worker.join(_EDGE_TTS_TIMEOUT)
    if worker.is_alive():
        raise RuntimeError(
            f"Edge-TTS synthesis stalled past {_EDGE_TTS_TIMEOUT:.0f}s "
            "(the connection stopped responding) — giving up on this attempt."
        )
    if errors:
        raise errors[0]
    return _probe_duration(audio_path)


def synthesize_voiceover(text: str, audio_path: Path, srt_path: Path,
                         voice: str = VOICE) -> float:
    """Synthesize the voiceover → mp3 + SRT. Returns audio duration in seconds.

    Uses ElevenLabs (emotional, consistent voice) when ELEVENLABS_API_KEY is set,
    otherwise falls back to free Edge-TTS.
    """
    if EL_API_KEY:
        try:
            print(f"     Voice: ElevenLabs ({EL_VOICE_ID}, {EL_MODEL})")
            return _elevenlabs_tts(text, audio_path, srt_path)
        except Exception as e:
            print(f"  ⚠ ElevenLabs failed ({e}) — falling back to Edge-TTS.")
    else:
        print("     Voice: Edge-TTS (set ELEVENLABS_API_KEY in .env for the emotional voice)")
    return _edge_tts(text, audio_path, srt_path, voice)


# ── 2. visuals ────────────────────────────────────────────────────

def _normalize_clip(src: Path) -> Path:
    """Scale-crop a source clip to 1080x1920/30fps, strip audio, cache by mtime."""
    cached = _CACHE_DIR / f"{src.stem}_{int(src.stat().st_mtime)}.mp4"
    if cached.exists():
        return cached
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},fps={FPS},setsar=1"
    )
    _run([
        "ffmpeg", "-y", "-i", str(src), "-an", "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-g", str(FPS * 2), str(cached),
    ])
    return cached


_VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm")


def list_clips() -> list[Path]:
    return sorted(p for p in CLIPS_DIR.glob("*") if p.suffix.lower() in _VIDEO_EXTS)


def background_clip() -> Path | None:
    """The dedicated full-frame background (e.g. the matrix+ball render), if present."""
    found = sorted(p for p in BACKGROUND_DIR.glob("*") if p.suffix.lower() in _VIDEO_EXTS)
    return found[0] if found else None


def _loop_clip(src: Path, duration: float, out: Path) -> Path:
    """Loop a single clip to cover `duration` (normalized to 1080x1920/30fps)."""
    norm = _normalize_clip(src)
    _run([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(norm),
        "-t", f"{duration + 1.0:.2f}", "-c", "copy", str(out),
    ])
    return out


def _fallback_background(duration: float, out: Path) -> Path:
    """Animated dark-tech gradient when no clip library exists yet."""
    src = (
        f"gradients=s={WIDTH}x{HEIGHT}:c0={BG_COLOR}:c1=0x7000ff:"
        f"x0=0:y0=0:x1={WIDTH}:y1={HEIGHT}:nb_colors=3:speed=0.012:"
        f"duration={duration:.2f}:rate={FPS}"
    )
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", src, "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", str(out),
    ])
    return out


def _build_base_visual(duration: float, out: Path, audio: Path | None = None) -> Path:
    """Pick the base visual.

    Preferred: render a FRESH matrix+ball background of exactly this voiceover's
    length whose motion surges with the voice (audio-reactive) — so the ball pace
    matches the narration and there is no loop seam. Falls back to looping the
    pre-rendered clip, then a clip montage, then a gradient.
    """
    if audio is not None:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "render_background", BASE_DIR / "tools" / "render_background.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            print("     Background: growing-ball matrix (fills the ring by the end)")
            mod.render(out, duration + 0.3)
            return out
        except Exception as e:
            print(f"  ⚠ reactive background failed ({e}) — falling back to looped clip.")

    bg = background_clip()
    if bg:
        print(f"     Background: {bg.name} (looped)")
        return _loop_clip(bg, duration, out)
    return _build_montage(duration, out)


def _build_montage(duration: float, out: Path) -> Path:
    """Loop/sequence the clip library to cover `duration`. Fallback if empty."""
    clips = list_clips()
    if not clips:
        print("  ⚠ No clips in assets/clips/ — using animated fallback background.")
        return _fallback_background(duration, out)

    normalized = [_normalize_clip(c) for c in clips]
    durations  = {p: _probe_duration(p) for p in normalized}

    # Repeat the sequence until total coverage exceeds the audio length.
    sequence, total, i = [], 0.0, 0
    while total < duration + 0.5:
        clip = normalized[i % len(normalized)]
        sequence.append(clip)
        total += durations[clip]
        i += 1

    # concat demuxer — all inputs share identical codec/params, so -c copy is safe
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for clip in sequence:
            f.write(f"file '{clip.as_posix()}'\n")
        concat_list = f.name
    try:
        _run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c", "copy", str(out),
        ])
    finally:
        os.unlink(concat_list)
    return out


# ── 2b. animated character (bottom-left, lip-flap to the voiceover) ──

CHAR_POSES = ("closed", "mid", "open", "smile", "blink")


def character_assets() -> dict | None:
    """Find the avatar pose set → {pose_name: Path}. Needs at least `closed`.

    Poses (all optional except closed): closed (mouth shut / rest), mid (slightly
    open), open (mouth wide), smile (genuine smile, a rest reaction), blink (eyes
    closed). Prefers character_*, falls back to placeholder_*.
    """
    for stem in ("character", "placeholder"):
        closed = CHARACTER_DIR / f"{stem}_closed.png"
        if closed.exists():
            poses = {"closed": closed}
            for name in CHAR_POSES[1:]:
                p = CHARACTER_DIR / f"{stem}_{name}.png"
                if p.exists():
                    poses[name] = p
            return poses
    return None


def _cutout(src: Path) -> Image.Image:
    """Remove the background → RGBA, cached by source mtime."""
    cached = _CACHE_DIR / f"{src.stem}_{int(src.stat().st_mtime)}_cut.png"
    if cached.exists():
        return Image.open(cached).convert("RGBA")
    from rembg import remove  # imported lazily — heavy
    out = remove(Image.open(src).convert("RGBA"))
    out.save(cached)
    return out


def _scale_to_height(img: Image.Image, h: int) -> Image.Image:
    w = max(1, round(img.width * h / img.height))
    return img.resize((w, h), Image.LANCZOS)


def _draw_open_mouth(img: Image.Image) -> Image.Image:
    """Paint an open mouth onto the (closed) avatar → the 'speaking' frame.

    A 2D puppet lip-flap: only the mouth changes, the head/body stay perfectly
    still. Used when there is no dedicated character_open.png.
    """
    o = img.copy()
    d = ImageDraw.Draw(o)
    w, h = o.size
    cx, cy = w * MOUTH_CX, h * MOUTH_CY
    mw, mh = w * MOUTH_W, h * MOUTH_H
    d.ellipse([cx - mw, cy - mh, cx + mw, cy + mh], fill=(70, 26, 30, 255))       # open cavity
    d.ellipse([cx - mw + w * 0.003, cy - mh + h * 0.001,
               cx + mw - w * 0.003, cy - mh + h * 0.008], fill=(238, 238, 232, 255))  # upper teeth
    return o


def _frame_loudness(audio: Path, n_frames: int) -> np.ndarray:
    """Per-frame normalized RMS (0..1) of the voiceover, for lip-flap timing."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(audio), "-f", "s16le",
         "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True,
    ).stdout
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return np.zeros(n_frames)
    spf = max(1, len(samples) // n_frames)
    rms = np.array([
        float(np.sqrt(np.mean(np.square(samples[i * spf:(i + 1) * spf] / 32768.0))))
        if samples[i * spf:(i + 1) * spf].size else 0.0
        for i in range(n_frames)
    ])
    peak = rms.max() or 1.0
    return rms / peak


# Character motion. Body stays calm — only the FACE talks. The one remaining body
# motion is a slow IDLE bob (not tied to speech), so he's alive but doesn't lurch
# every time he speaks. Speech-tied whole-body motion (lean/zoom) is off by default.
CHAR_BOB_PX   = 4     # gentle idle vertical breathing (constant, NOT speech-driven)
CHAR_LEAN_PX  = 0     # speech-tied horizontal lean (0 = off — was causing "moves too much")
CHAR_PUNCH    = 0.0   # speech-tied emphasis zoom (0 = off — was causing "moves too much")
_MOUTH_HI     = 0.52  # smoothed-energy threshold → wide-open vs mid


def _build_character_layer(audio: Path, duration: float, poses: dict,
                           out: Path) -> tuple[int, int]:
    """Render an alpha video of the avatar whose face + motion track the VOICE.

    Speech-driven (not a timer): the mouth follows the smoothed audio energy —
    wide-open on emphasis, mid on softer speech, rest on real pauses — debounced
    so it never strobes. A subtle head lean/bob is driven by that same energy, so
    his motion correlates with his delivery. Uses `smile` as an occasional rest
    face and `blink` for periodic human blinks when those art frames exist.

    Returns the (width, height) of the layer so it can be positioned by overlay.
    """
    char_h = int(HEIGHT * CHAR_HEIGHT_FRAC)

    def _img(name, fallback=None):
        if name in poses:
            return _scale_to_height(_cutout(poses[name]), char_h)
        return fallback

    closed_img = _img("closed")
    open_img   = _img("open", _draw_open_mouth(closed_img))
    mid_img    = _img("mid", open_img)
    smile_img  = _img("smile", closed_img)
    blink_img  = _img("blink")   # None if no blink art → no blink

    base_w = max(closed_img.width, mid_img.width, open_img.width)
    headroom = int(char_h * CHAR_PUNCH) + 6
    canvas_w = base_w + int(base_w * CHAR_PUNCH) + 2 * CHAR_LEAN_PX + 6
    canvas_h = char_h + headroom + CHAR_BOB_PX + 2

    base_imgs = {"closed": closed_img, "mid": mid_img, "open": open_img, "smile": smile_img}
    if blink_img is not None:
        base_imgs["blink"] = blink_img
    _scale_cache: dict = {}

    def _scaled(name: str, scq: float) -> Image.Image:
        key = (name, scq)
        if key not in _scale_cache:
            img = base_imgs[name]
            if scq == 1.0:
                _scale_cache[key] = img
            else:
                _scale_cache[key] = img.resize((round(img.width * scq), round(img.height * scq)),
                                               Image.LANCZOS)
        return _scale_cache[key]

    def _place(img: Image.Image, dx: int, dy: int) -> Image.Image:
        c = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        x = (canvas_w - img.width) // 2 + dx          # centred horizontally
        y = canvas_h - img.height - CHAR_BOB_PX + dy  # anchored at the feet (zoom grows upward)
        c.alpha_composite(img, (x, y))
        return c

    n_frames = int(round(duration * FPS))
    loud = _frame_loudness(audio, n_frames)

    # voiced mask with micro-gap merge (so short between-word dips aren't "pauses")
    voiced = [bool(v > 0.12) for v in loud]
    min_pause = max(1, int(0.30 * FPS))
    i = 0
    while i < n_frames:
        if not voiced[i]:
            j = i
            while j < n_frames and not voiced[j]:
                j += 1
            if (j - i) < min_pause and i > 0 and j < n_frames:
                for k in range(i, j):
                    voiced[k] = True
            i = j
        else:
            i += 1

    # smoothed energy for both mouth openness and the lean
    e, ema = [], 0.0
    for v in loud:
        ema = 0.72 * ema + 0.28 * v
        e.append(ema)

    # blink schedule (human cadence) — only if we have blink art
    blink_frames = set()
    if blink_img is not None:
        t = random.uniform(1.5, 3.5)
        while t < duration - 0.3:
            f0 = int(t * FPS)
            blink_frames.update({f0, f0 + 1, f0 + 2})   # ~100ms blink
            t += random.uniform(2.5, 5.5)

    # pick the mouth/face pose per frame from the smoothed energy, with debounce
    frames = []
    cur_pose, want, want_run = "closed", "closed", 0
    rest_smile = False
    for k in range(n_frames):
        if voiced[k]:
            target = "open" if e[k] > _MOUTH_HI else "mid"
        else:
            target = "smile" if rest_smile else "closed"
        if target == want:
            want_run += 1
        else:
            want, want_run = target, 1
        if want_run >= 3 or (cur_pose in ("open", "mid")) != (want in ("open", "mid")):
            cur_pose = want   # switch once the target is stable (or speech↔pause flips)
        if not voiced[k] and (k == 0 or voiced[k - 1]):
            rest_smile = not rest_smile      # alternate rest face between pauses

        name = "blink" if (k in blink_frames and "blink" in base_imgs) else cur_pose
        # emphasis punch-in: zoom the avatar up slightly with speech energy (quantized+cached)
        sc = 1.0 + CHAR_PUNCH * max(0.0, min(1.0, (e[k] - 0.2) / 0.7))
        scq = round(sc / 0.008) * 0.008
        dx = int(CHAR_LEAN_PX * max(0.0, min(1.0, (e[k] - 0.25) / 0.6)))
        dy = int(CHAR_BOB_PX * math.sin(2 * math.pi * k / (FPS * 3.2)))
        frames.append(_place(_scaled(name, scq), dx, dy).tobytes())

    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{canvas_w}x{canvas_h}", "-r", str(FPS), "-i", "-",
         "-c:v", "qtrle", str(out)],
        stdin=subprocess.PIPE,
    )
    for fr in frames:
        proc.stdin.write(fr)
    proc.stdin.close()
    proc.wait()
    return canvas_w, canvas_h


# ── 3. assemble ───────────────────────────────────────────────────

# Note: ffmpeg renders SRT in a ~288px-tall virtual canvas, then scales to the
# real frame (×~6.7 for 1920). So Fontsize/MarginV here are in that small space:
# Fontsize=11 → ~73px on screen; MarginV=30 → ~200px above the bottom edge
# (smaller captions, sitting low — per the requested style).
_SUB_STYLE = (
    "FontName=DejaVu Sans,Fontsize=11,Bold=1,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
    "Alignment=2,MarginV=30"
)

INTRO_DURATION = 3
OUTRO_DURATION = 5
WATERMARK_TEXT = "EPIFANI AI"

# Visual inserts (code cards / screenshots) — a framed card in the upper-right,
# next to where the avatar's hand gestures. Scaled to INSERT_W wide, faded in/out.
INSERT_W      = 680
INSERT_MARGIN = 40
INSERT_Y      = 250
INSERT_FADE   = 0.3


def _brand_and_caption(base: Path, audio: Path, srt: Path, duration: float,
                       intro_title: str, intro_subtitle: str, out: Path,
                       char_layer: Path | None = None,
                       inserts: list[dict] | None = None) -> Path:
    """Single pass: composite character (if any), trim to audio, mux voiceover,
    burn captions + branding.

    ffmpeg runs with cwd = srt.parent so the subtitles filter can reference the
    file by bare name (libass absolute-path escaping is unreliable).
    """
    def esc(t: str) -> str:
        return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")

    intro_title, intro_subtitle = esc(intro_title), esc(intro_subtitle)

    filters = []
    # Captions only if we actually have timed subtitle events
    if srt.exists() and srt.stat().st_size > 0:
        filters.append(f"subtitles={srt.name}:force_style='{_SUB_STYLE}'")
    filters += [
        f"drawtext=text='{WATERMARK_TEXT}':fontcolor={FONT_COLOR}:fontsize=36:"
        f"alpha=0.75:x=20:y=20",
        # Intro/outro cards sit in the upper third (above the character's head)
        f"drawtext=text='{intro_title}':fontcolor=white:fontsize=80:"
        f"x=(w-text_w)/2:y=(h*0.16):enable='between(t,0,{INTRO_DURATION})'",
        f"drawtext=text='{intro_subtitle}':fontcolor={FONT_COLOR}:fontsize=46:"
        f"x=(w-text_w)/2:y=(h*0.16+95):enable='between(t,0,{INTRO_DURATION})'",
        f"drawtext=text='Get all picks free':fontcolor=white:fontsize=52:"
        f"x=(w-text_w)/2:y=(h*0.16):enable='gte(t,{duration - OUTRO_DURATION:.2f})'",
        f"drawtext=text='epifanii.com':fontcolor={FONT_COLOR}:fontsize=64:"
        f"x=(w-text_w)/2:y=(h*0.16+100):enable='gte(t,{duration - OUTRO_DURATION:.2f})'",
    ]
    post = ",".join(filters)

    # Inputs: base(0) → [character] → [insert sources…] → audio(last). Image
    # inserts are `-loop 1` (timeline already matches output); video-clip inserts
    # are shifted with setpts so they appear at their start time.
    inserts = inserts or []
    cmd = ["ffmpeg", "-y", "-i", str(base.resolve())]
    idx = 1
    char_idx = None
    if char_layer:
        cmd += ["-i", str(char_layer.resolve())]
        char_idx = idx
        idx += 1
    insert_idx = []
    for ins in inserts:
        if ins.get("kind") == "clip":
            cmd += ["-i", str(Path(ins["path"]).resolve())]
        else:
            cmd += ["-loop", "1", "-i", str(Path(ins["path"]).resolve())]
        insert_idx.append(idx)
        idx += 1
    cmd += ["-i", str(audio.resolve())]
    audio_idx = idx

    fc, cur = [], "[0:v]"
    if char_idx is not None:
        # motion (bob + energy lean) is baked into the character layer itself
        fc.append(f"[0:v][{char_idx}:v]overlay=x={CHAR_MARGIN_X}:y=H-h:format=auto[c]")
        cur = "[c]"
    for k, (ins, i_idx) in enumerate(zip(inserts, insert_idx)):
        w = ins.get("width") or INSERT_W
        x = WIDTH - w - INSERT_MARGIN
        s, e = float(ins["start"]), float(ins["end"])
        fout = max(s, e - INSERT_FADE)
        shift = f",setpts=PTS-STARTPTS+{s:.2f}/TB" if ins.get("kind") == "clip" else ""
        fc.append(
            f"[{i_idx}:v]scale={w}:-1,format=rgba{shift},"
            f"fade=t=in:st={s:.2f}:d={INSERT_FADE}:alpha=1,"
            f"fade=t=out:st={fout:.2f}:d={INSERT_FADE}:alpha=1[ins{k}]"
        )
        fc.append(f"{cur}[ins{k}]overlay=x={x}:y={INSERT_Y}:"
                  f"enable='between(t,{s:.2f},{e:.2f})'[iv{k}]")
        cur = f"[iv{k}]"
    fc.append(f"{cur}{post}[v]")

    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", f"{audio_idx}:a"]
    cmd += [
        "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "128k", str(out.resolve()),
    ]
    _run(cmd, cwd=str(srt.parent))
    return out


def assemble_journey_video(script, out_path: Path | None = None,
                           voice: str = VOICE, inserts: list[dict] | None = None) -> Path:
    """Build a branded journey video locally from a JourneyScript. Returns the mp4 path.

    `inserts` is an optional list of visual-insert specs (code cards / screenshots
    shown in the upper-right while he talks about them) — see core.visuals.
    """
    day = getattr(script, "day", 0)
    out_path = out_path or (OUTPUT_DIR / f"journey_day{day}_branded.mp4")

    work = Path(tempfile.mkdtemp(prefix="epifani_journey_"))
    try:
        audio = work / "voice.mp3"
        srt   = work / "captions.srt"
        print("  🎙️  Synthesizing voiceover...")
        duration = synthesize_voiceover(script.voiceover, audio, srt, voice)
        if duration <= 0:
            raise RuntimeError("Voiceover synthesis produced no audio.")
        print(f"     Voiceover: {duration:.1f}s")

        resolved_inserts = []
        if inserts:
            from core.visuals import resolve_inserts
            resolved_inserts = resolve_inserts(inserts, srt, work, duration)
            print(f"  🖼️  Visual inserts: {len(resolved_inserts)} placed"
                  + (f" (of {len(inserts)} requested)" if len(resolved_inserts) != len(inserts) else ""))

        montage = work / "montage.mp4"
        print("  🎞️  Assembling visuals...")
        _build_base_visual(duration, montage, audio=audio)

        char_layer = None
        poses = character_assets()
        if poses:
            extra = [p for p in ("mid", "open", "smile", "blink") if p in poses]
            print(f"  🧑‍💻 Compositing character: {poses['closed'].name} — "
                  f"speech-driven face ({'+'.join(['closed'] + extra)})")
            char_layer = work / "character.mov"
            _build_character_layer(audio, duration, poses, char_layer)

        print("  🏷️  Burning captions + Epifani branding...")
        _brand_and_caption(
            montage, audio, srt, duration,
            intro_title=f"Day {day}",
            intro_subtitle="Building EPIFANI AI",
            out=out_path,
            char_layer=char_layer,
            inserts=resolved_inserts,
        )
        print(f"     ✓ Journey video: {out_path.name}")
        return out_path
    finally:
        shutil.rmtree(work, ignore_errors=True)
