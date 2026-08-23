"""
Generates branded prediction cards using Pillow.
Design mirrors the Epifani portal export card: dark bg · radial cyan glow ·
EPIFANI AI wordmark · pick details · confidence bar · CTA footer.
"""
import math
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from core.prediction_fetcher import Pick

BASE_DIR   = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "assets" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Fonts ─────────────────────────────────────────────────────────
# Bundled in-repo so rendering is identical on Linux, macOS, and Windows —
# don't rely on system font paths (Ubuntu Sans only ships on Ubuntu).
_FONT_PATH = BASE_DIR / "assets" / "fonts" / "UbuntuSans-VariableFont.ttf"

def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(_FONT_PATH), size)
    except OSError:
        return ImageFont.load_default()

# ── Palette ───────────────────────────────────────────────────────
BG     = (10,  10,  12,  255)   # #0a0a0c
CYAN   = (0,   242, 255, 255)   # #00f2ff
GREEN  = (0,   255, 136, 255)   # #00ff88
PURPLE = (112, 0,   255, 255)   # #7000ff
WHITE  = (255, 255, 255, 255)
MUTED  = (255, 255, 255, 100)   # ~40 % white
SUBTLE = (255, 255, 255, 25)    # ~10 % white

def _tier_rgb(hex_color: str) -> tuple:
    c = hex_color.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))

def _tlen(draw: ImageDraw.Draw, text: str, font) -> int:
    return int(draw.textlength(text, font=font))


# ── Glow layer (radial, top-right corner) ─────────────────────────
def _glow_layer(W: int, H: int, color: tuple, intensity: float = 0.07) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    r, g, b = color[:3]
    max_r = int(W * 0.8)
    for i in range(max_r, 0, -6):
        alpha = int(255 * intensity * (1 - i / max_r) ** 2)
        draw.ellipse([W - i, -i, W + i, i], fill=(r, g, b, alpha))
    return layer


def _overlay_rect(base: Image.Image, box: tuple, fill_rgba: tuple, radius: int = 12,
                  outline_rgba: tuple = None, outline_width: int = 1) -> Image.Image:
    """Draw a rounded-rectangle with RGBA fill onto the base image via compositing."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=radius, fill=fill_rgba)
    if outline_rgba:
        d.rounded_rectangle(box, radius=radius, outline=outline_rgba, width=outline_width)
    return Image.alpha_composite(base, layer)


def _shadow_text(draw: ImageDraw.Draw, xy, text, font, fill):
    x, y = xy
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 140))
    draw.text((x, y), text, font=font, fill=fill)


# ── Main card builder ─────────────────────────────────────────────
def _estimate_match_height(draw: ImageDraw.Draw, pick: Pick, f_match, f_match_s, max_w: int) -> int:
    """Returns pixel height consumed by the match name block."""
    if _tlen(draw, pick.match, f_match) <= max_w:
        return 70
    return 54 + 40 + 56  # home + vs + away


def build_card(pick: Pick, size: str = "square") -> Path:
    """
    Build a branded prediction card.

    Args:
        pick: Pick from prediction_fetcher
        size: "square" (1080×1080) or "story" (1080×1920)

    Returns:
        Path to saved PNG file.
    """
    W, H = (1080, 1080) if size == "square" else (1080, 1920)
    PAD  = 80

    tier_rgb = _tier_rgb(pick.tier_color)

    # ── Base canvas + glow ────────────────────────────────────────
    img = Image.new("RGBA", (W, H), BG)
    img = Image.alpha_composite(img, _glow_layer(W, H, CYAN[:3], intensity=0.07))

    # Bottom-left purple glow for depth on story
    if size == "story":
        bl_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bl_draw  = ImageDraw.Draw(bl_layer)
        pr, pg, pb = PURPLE[:3]
        for i in range(int(W * 0.6), 0, -8):
            alpha = int(255 * 0.05 * (1 - i / (W * 0.6)) ** 2)
            bl_draw.ellipse([-i, H - i, i, H + i], fill=(pr, pg, pb, alpha))
        img = Image.alpha_composite(img, bl_layer)

    draw = ImageDraw.Draw(img)

    # ── Constants for the scrolling content layout ────────────────
    logo_sz   = 52 if size == "square" else 58
    f_logo    = _font(logo_sz)
    f_sub     = _font(13)
    f_badge   = _font(17)
    f_league  = _font(21)
    f_match   = _font(54 if size == "square" else 60)
    f_match_s = _font(40)
    panel_h   = 220
    bar_h     = 10
    max_w     = W - PAD * 2

    # Header block height (logo + divider)
    header_h = logo_sz + 38 + 1 + 36   # logo + gap-to-divider + divider + gap-after

    # Content block height (league + match + pick panel + bar + bar label)
    match_h   = _estimate_match_height(draw, pick, f_match, f_match_s, max_w)
    content_h = 40 + match_h + 28 + panel_h + 32 + bar_h + 12 + 28

    # Footer block height
    footer_h = 1 + 16 + 30 + PAD   # divider + "discover" + CTA + bottom pad

    # For story: vertically center the content between header and footer
    if size == "story":
        header_top   = PAD
        footer_top   = H - PAD - 86
        available    = footer_top - (PAD + header_h)
        content_start = PAD + header_h + max(0, (available - content_h) // 2)
    else:
        content_start = PAD + header_h

    # ── EPIFANI AI logo ───────────────────────────────────────────
    y = PAD
    prefix = "EPIFANI "
    ew = _tlen(draw, prefix, f_logo)
    _shadow_text(draw, (PAD, y), prefix, f_logo, WHITE)
    _shadow_text(draw, (PAD + ew, y), "AI", f_logo, CYAN)
    draw.text((PAD, y + logo_sz + 8), "PROFESSIONAL SELECTIONS", font=f_sub, fill=MUTED)

    # ── Tier badge (top-right) ────────────────────────────────────
    badge_lbl = pick.tier
    bw = _tlen(draw, badge_lbl, f_badge) + 32
    bh = 38
    bx = W - PAD - bw
    by = y + 4

    img = _overlay_rect(
        img,
        box           = (bx, by, bx + bw, by + bh),
        fill_rgba     = tier_rgb + (30,),
        radius        = 8,
        outline_rgba  = tier_rgb + (180,),
        outline_width = 1,
    )
    draw = ImageDraw.Draw(img)
    draw.text((bx + 16, by + 10), badge_lbl, font=f_badge, fill=WHITE)

    # ── Top divider ───────────────────────────────────────────────
    div_y = PAD + logo_sz + 38
    img   = _overlay_rect(img, (PAD, div_y, W - PAD, div_y + 1), fill_rgba=SUBTLE, radius=0)
    draw  = ImageDraw.Draw(img)

    # ── Content block (vertically positioned) ────────────────────
    y = content_start

    draw.text((PAD, y), f"{pick.league.upper()}  ·  {pick.time_str}", font=f_league, fill=MUTED)
    y += 40

    # Match name
    if _tlen(draw, pick.match, f_match) <= max_w:
        _shadow_text(draw, (PAD, y), pick.match, f_match, WHITE)
        y += 70
    else:
        _shadow_text(draw, (PAD, y), pick.home_team, f_match_s, WHITE)
        y += 54
        draw.text((PAD, y), "vs", font=_font(26), fill=MUTED)
        y += 40
        _shadow_text(draw, (PAD, y), pick.away_team, f_match_s, WHITE)
        y += 56

    y += 28

    # ── Pick panel ────────────────────────────────────────────────
    border_w = 5

    img = _overlay_rect(
        img,
        box       = (PAD, y, W - PAD, y + panel_h),
        fill_rgba = tier_rgb + (15,),
        radius    = 14,
    )
    img = _overlay_rect(
        img,
        box       = (PAD, y, PAD + border_w, y + panel_h),
        fill_rgba = tier_rgb + (230,),
        radius    = 3,
    )
    draw = ImageDraw.Draw(img)

    px = PAD + border_w + 24
    py = y + 22

    draw.text((px, py), "TODAY'S PICK", font=_font(16), fill=MUTED)
    py += 32

    f_pick = _font(44)
    _shadow_text(draw, (px, py), pick.label.upper(), f_pick, CYAN)
    py += 58

    f_odds = _font(30)
    f_edge = _font(20)
    odds_str = f"@ {pick.odds:.2f}"
    edge_str = f"+{round(pick.edge * 100, 1)}% EDGE"
    _shadow_text(draw, (px, py), odds_str, f_odds, WHITE)
    edge_x = W - PAD - _tlen(draw, edge_str, f_edge) - 24
    draw.text((edge_x, py + 6), edge_str, font=f_edge, fill=tier_rgb + (200,))

    y += panel_h + 32

    # ── Confidence bar ────────────────────────────────────────────
    bar_w  = W - PAD * 2
    img = _overlay_rect(img, (PAD, y, PAD + bar_w, y + bar_h), fill_rgba=SUBTLE, radius=5)
    fill_w = max(bar_h, int(bar_w * min(pick.probability, 0.88)))
    img = _overlay_rect(img, (PAD, y, PAD + fill_w, y + bar_h), fill_rgba=tier_rgb + (210,), radius=5)
    draw = ImageDraw.Draw(img)

    y += bar_h + 12
    f_pct = _font(19)
    draw.text((PAD, y), "AI CONFIDENCE", font=_font(19), fill=MUTED)
    pct_str = f"{pick.confidence_pct}%"
    draw.text((PAD + bar_w - _tlen(draw, pct_str, f_pct), y), pct_str, font=f_pct, fill=tier_rgb + (255,))

    # ── Footer ────────────────────────────────────────────────────
    foot_y = H - PAD - 86
    img = _overlay_rect(img, (PAD, foot_y, W - PAD, foot_y + 1), fill_rgba=SUBTLE, radius=0)
    draw = ImageDraw.Draw(img)

    draw.text((PAD, foot_y + 16), "DISCOVER THE EDGE AT", font=_font(19), fill=MUTED)
    _shadow_text(draw, (PAD, foot_y + 46), pick.cta_url.upper(), _font(30), CYAN)

    # ── Save ──────────────────────────────────────────────────────
    safe = pick.match.replace(" ", "_").replace("/", "-")
    out  = OUTPUT_DIR / f"{safe}_{size}.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out


def build_all_cards(picks: list[Pick]) -> list[dict]:
    results = []
    for pick in picks:
        square = build_card(pick, size="square")
        story  = build_card(pick, size="story")
        results.append({"pick": pick, "square": square, "story": story})
        print(f"  ✓ {pick.match}  [{pick.tier}]")
    return results
