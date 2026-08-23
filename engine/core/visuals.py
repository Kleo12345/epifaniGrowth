"""
Visual inserts for journey videos — the b-roll layer.

An "insert" is a small framed image (a code card, a screenshot, a diagram) that
pops into the upper-right for a few seconds while the founder talks about it, so
the video isn't just a talking head. This module resolves a list of lightweight
insert specs into concrete {image, start, end} the renderer can composite.

Insert spec (dict) — supply ONE source and a time anchor:
    source (one of):
        "code":  "<snippet>"          → auto-rendered branded code card
        "image": "<library-id | path>" → a file from assets/visuals/ or a path
    timing:
        "at":    <seconds:float>  OR  "<phrase>"  (anchored to when it's spoken)
        "secs":  <duration on screen>            (optional; default 3.0)
    code-card extras: "lang" (default "python"), "title" (title-bar filename)

Phrase anchoring uses the voiceover SRT (char-accurate from ElevenLabs), so an
insert lands exactly when its phrase is spoken.
"""
import json
import re
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
VISUALS_DIR = BASE_DIR / "assets" / "visuals"
LIBRARY_JSON = VISUALS_DIR / "library.json"

DEFAULT_SECS = 3.0
LEAD_SECS    = 0.2   # bring the card up a hair before the phrase lands


def load_library() -> dict:
    """Return the library entries dict ({} if none)."""
    if not LIBRARY_JSON.exists():
        return {}
    try:
        return json.loads(LIBRARY_JSON.read_text()).get("entries", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _resolve_image(ref: str) -> Path | None:
    """Resolve an image ref to a file: library id → path → assets/visuals/<ref>."""
    if not ref:
        return None
    lib = load_library()
    if ref in lib:
        p = VISUALS_DIR / lib[ref]["file"]
        return p if p.exists() else None
    p = Path(ref)
    if p.is_absolute() and p.exists():
        return p
    for cand in (VISUALS_DIR / ref, BASE_DIR / ref):
        if cand.exists():
            return cand
    return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def match_library(text: str) -> str | None:
    """Best library id whose tags/description overlap `text` (for AI screenshot cues).

    Returns the id with the most shared words, or None if nothing overlaps.
    """
    lib = load_library()
    if not lib or not text:
        return None
    words = set(_norm(text).split())
    best, best_score = None, 0
    for lib_id, entry in lib.items():
        hay = set(_norm(" ".join(entry.get("tags", [])) + " " + entry.get("description", "")).split())
        hay.update(_norm(lib_id).split())
        score = len(words & hay)
        if score > best_score:
            best, best_score = lib_id, score
    return best


def _parse_srt(srt_path: Path) -> list[tuple[float, str]]:
    """Parse an SRT into [(start_seconds, text), ...] in order."""
    if not srt_path or not srt_path.exists():
        return []

    def _ts(t: str) -> float:
        h, m, rest = t.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    cues, block = [], srt_path.read_text(encoding="utf-8").strip().split("\n\n")
    for b in block:
        lines = [ln for ln in b.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        tline = next((ln for ln in lines if "-->" in ln), None)
        if not tline:
            continue
        start = _ts(tline.split("-->")[0].strip())
        text = " ".join(lines[lines.index(tline) + 1:])
        cues.append((start, text))
    return cues


def _find_phrase_time(cues: list[tuple[float, str]], phrase: str) -> float | None:
    """Earliest cue start whose caption text contains the phrase's opening words."""
    if not cues:
        return None
    key = _norm(phrase)
    words = key.split()
    probe = " ".join(words[:4]) if words else ""     # first few words are enough
    if not probe:
        return None
    for start, text in cues:
        if probe in _norm(text):
            return start
    # looser: match just the first distinctive word
    first = words[0]
    for start, text in cues:
        if first in _norm(text).split():
            return start
    return None


INTRO_GUARD = 3.5   # keep inserts clear of the "Day X" intro card
OUTRO_GUARD = 5.0   # ...and the "epifanii.com" outro card


def resolve_inserts(inserts, srt_path, work_dir, duration: float) -> list[dict]:
    """Turn insert specs into [{path, start, end}] ready for compositing.

    Inserts are kept clear of the intro/outro title windows, and unresolvable
    ones (missing image / phrase not found) are skipped with a warning rather
    than failing the whole render.
    """
    if not inserts:
        return []
    cues = _parse_srt(Path(srt_path)) if srt_path else []
    work_dir = Path(work_dir)
    resolved = []

    for n, spec in enumerate(inserts):
        # ── source: code card / static image / video clip ─────────
        kind = "image"
        if spec.get("code"):
            from core.code_card import render_code_card
            path = work_dir / f"insert_code_{n}.png"
            render_code_card(spec["code"], path,
                             lang=spec.get("lang", "python"), title=spec.get("title"))
        elif spec.get("clip"):
            path = _resolve_image(spec["clip"])   # same lookup (library id / path)
            if not path:
                print(f"  ⚠ insert #{n}: clip '{spec.get('clip')}' not found — skipped.")
                continue
            kind = "clip"
        else:
            path = _resolve_image(spec.get("image", ""))
            if not path:
                print(f"  ⚠ insert #{n}: image '{spec.get('image')}' not found — skipped.")
                continue

        # ── timing ────────────────────────────────────────────────
        at = spec.get("at")
        if isinstance(at, (int, float)):
            start = float(at)
        elif isinstance(at, str):
            t = _find_phrase_time(cues, at)
            if t is None:
                print(f"  ⚠ insert #{n}: phrase '{at}' not found in captions — skipped.")
                continue
            start = t
        else:
            print(f"  ⚠ insert #{n}: no 'at' (seconds or phrase) — skipped.")
            continue

        secs = float(spec.get("secs", DEFAULT_SECS))
        start = max(0.0, start - LEAD_SECS)
        # keep clear of the intro/outro title cards
        start = max(start, INTRO_GUARD)
        max_end = duration - OUTRO_GUARD
        if start >= max_end:
            print(f"  ⚠ insert #{n}: no room outside the intro/outro windows — skipped.")
            continue
        end = min(start + secs, max_end)
        if end - start < 1.0:
            continue
        resolved.append({"path": str(path), "start": round(start, 2),
                         "end": round(end, 2), "width": spec.get("width"), "kind": kind})

    resolved.sort(key=lambda r: r["start"])
    return resolved
