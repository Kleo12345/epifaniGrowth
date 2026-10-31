"""
"Won tickets" for Instagram Stories: yesterday's top-5 winning public picks
(highest odds first) drawn as betting-slip style cards with an example stake.

Picks come from the Epifani engine's own tracker through the same Core3 filter
that feeds the public track record (scripts/export_track_record.py), so every
ticket is a real call the site published. Stakes are simulated and every card
says so; the monthly highlight also opens with build_disclaimer().
"""
import importlib.util
import json
import os
import random
from datetime import date
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

from core.image_builder import (BG, CYAN, GREEN, MUTED, OUTPUT_DIR, PURPLE, SUBTLE, WHITE,
                                _font, _glow_layer, _overlay_rect, _shadow_text, _tlen)

EPIFANI_ROOT = Path(os.getenv("EPIFANI_ROOT", str(Path.home() / "epifani")))
TICKETS_DIR = OUTPUT_DIR / "tickets"
TOP_N = 5
# Amounts people actually type into a slip, not uniform noise.
STAKES = [20, 25, 30, 40, 50, 60, 75, 100, 120, 150, 200, 250, 300, 400, 500]
W, H, PAD = 1080, 1920, 80


def _track_record_module():
    spec = importlib.util.spec_from_file_location(
        "export_track_record", EPIFANI_ROOT / "scripts" / "export_track_record.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def day_results(day: str) -> tuple[list[dict], int, int]:
    """(top-N winners by odds, settled picks that day, wins that day) from the public Core3 picks."""
    tr = _track_record_module()
    with open(tr.CORE3) as f:
        picks = pd.DataFrame(tr.select(pd.read_csv(tr.TRACKER), json.load(f)))
    if picks.empty:
        return [], 0, 0
    picks = picks[(picks.date == day) & (picks.result != "Void")]
    wins = picks[picks.result == "Win"].sort_values("odds", ascending=False)
    return wins.head(TOP_N).to_dict("records"), len(picks), len(wins)


def stake_for(pick_id: str) -> int:
    """Seeded by the pick, so a re-render of the same ticket shows the same stake."""
    return random.Random(pick_id).choice(STAKES)


def league_name(league_id: str) -> str:
    """'Ligue-1-France-01' -> 'Ligue 1 · France'."""
    parts = league_id.removesuffix("-01").split("-")
    return f"{' '.join(parts[:-1])} · {parts[-1]}" if len(parts) > 1 else parts[0]


def pick_text(p: dict) -> tuple[str, str]:
    """(the call in plain words, slip market line)."""
    team = {"H": p["homeTeam"], "A": p["awayTeam"]}.get(p["prediction"])
    if p["market"] == "DNB":
        return f"{team} not to lose", "Draw No Bet"
    if p["market"].startswith("Result"):
        sign = {"H": "1", "D": "X", "A": "2"}[p["prediction"]]
        return (f"{team} to win" if team else "Draw"), f"Match result · {sign}"
    side = "Over" if p["prediction"] == "O" else "Under"
    return f"{side} 2.5 goals", "Total goals"


def _money(x: float) -> str:
    return f"€{x:,.2f}"


def _canvas() -> Image.Image:
    img = Image.new("RGBA", (W, H), BG)
    img = Image.alpha_composite(img, _glow_layer(W, H, CYAN[:3], intensity=0.07))
    bl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(bl)
    for i in range(int(W * 0.6), 0, -8):
        d.ellipse([-i, H - i, i, H + i], fill=PURPLE[:3] + (int(255 * 0.05 * (1 - i / (W * 0.6)) ** 2),))
    return Image.alpha_composite(img, bl)


def _logo(draw: ImageDraw.Draw, y: int) -> None:
    f = _font(58)
    _shadow_text(draw, (PAD, y), "EPIFANI ", f, WHITE)
    _shadow_text(draw, (PAD + _tlen(draw, "EPIFANI ", f), y), "AI", f, CYAN)


def _center(draw, y, text, font, fill):
    draw.text(((W - _tlen(draw, text, font)) // 2, y), text, font=font, fill=fill)


def _fit(draw, text, size, max_w):
    while size > 30 and _tlen(draw, text, _font(size)) > max_w:
        size -= 2
    return _font(size)


def build_ticket(p: dict, n_picks: int, n_won: int, out_dir: Path = TICKETS_DIR) -> Path:
    """1080x1920 story: a settled single slip for one winning pick."""
    stake = stake_for(str(p["id"]))
    call, market = pick_text(p)
    played = date.fromisoformat(p["date"])

    img = _canvas()
    draw = ImageDraw.Draw(img)
    _logo(draw, PAD)
    draw.text((PAD, PAD + 70), "WON TICKETS", font=_font(22), fill=MUTED)

    # Slip panel
    top, bot, x0, x1 = 340, 1400, PAD, W - PAD
    img = _overlay_rect(img, (x0, top, x1, bot), (255, 255, 255, 14), radius=28,
                        outline_rgba=(255, 255, 255, 40), outline_width=2)
    img = _overlay_rect(img, (x0, top, x1, top + 110), (0, 255, 136, 34), radius=28)
    draw = ImageDraw.Draw(img)
    draw.text((x0 + 44, top + 34), "SINGLE", font=_font(34), fill=WHITE)
    badge = "✓ WON"
    fb = _font(34)
    draw.text((x1 - 44 - _tlen(draw, badge, fb), top + 34), badge, font=fb, fill=GREEN)

    y = top + 160
    draw.text((x0 + 44, y), f"{league_name(p['league']).upper()}  ·  {played:%a %d %b}", font=_font(26), fill=MUTED)
    y += 60
    inner = x1 - x0 - 88
    _shadow_text(draw, (x0 + 44, y), p["homeTeam"], _fit(draw, p["homeTeam"], 56, inner), WHITE)
    draw.text((x0 + 44, y + 70), "vs", font=_font(28), fill=MUTED)
    _shadow_text(draw, (x0 + 44, y + 108), p["awayTeam"], _fit(draw, p["awayTeam"], 56, inner), WHITE)
    y += 210
    img = _overlay_rect(img, (x0 + 44, y, x1 - 44, y + 170), (0, 242, 255, 22), radius=18,
                        outline_rgba=(0, 242, 255, 90))
    draw = ImageDraw.Draw(img)
    draw.text((x0 + 76, y + 28), market.upper(), font=_font(24), fill=CYAN)
    _shadow_text(draw, (x0 + 76, y + 70), call, _fit(draw, call, 50, inner - 260), WHITE)
    fo = _font(64)
    odds = f"{p['odds']:.2f}"
    draw.text((x1 - 76 - _tlen(draw, odds, fo), y + 52), odds, font=fo, fill=WHITE)
    y += 230

    for i in range(x0 + 44, x1 - 44, 28):  # tear line
        draw.line([(i, y), (i + 14, y)], fill=(255, 255, 255, 60), width=3)
    y += 50
    fr, fv = _font(34), _font(40)
    for label, value in (("Stake", _money(stake)), ("Odds", odds)):
        draw.text((x0 + 44, y), label, font=fr, fill=MUTED)
        draw.text((x1 - 44 - _tlen(draw, value, fv), y - 4), value, font=fv, fill=WHITE)
        y += 74
    y += 10
    won = _money(stake * p["odds"])
    fw = _fit(draw, won, 92, inner - 200)
    draw.text((x0 + 44, y + 22), "Won", font=_font(44), fill=WHITE)
    _shadow_text(draw, (x1 - 44 - _tlen(draw, won, fw), y), won, fw, GREEN)

    # Day record + CTA + disclaimer
    _center(draw, 1510, f"{played:%a %d %b}: {n_won}/{n_picks} calls landed", _font(40), WHITE)
    _center(draw, 1570, "Every call is public at epifanii.com", _font(32), CYAN)
    img = _overlay_rect(img, (PAD, 1690, W - PAD, 1691), SUBTLE, radius=0)
    draw = ImageDraw.Draw(img)
    _center(draw, 1715, "Simulated stake · not a real bet", _font(30), MUTED)
    _center(draw, 1758, "What following the model would have returned. 18+", _font(26), MUTED)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"ticket_{str(p['id']).replace(' ', '_')}.jpg"  # id already starts with the date
    img.convert("RGB").save(path, "JPEG", quality=92)  # Instagram's API only takes JPEG
    return path


def build_disclaimer(month: date, out_dir: Path = TICKETS_DIR) -> Path:
    """First story of each month's highlight."""
    img = _canvas()
    draw = ImageDraw.Draw(img)
    _logo(draw, PAD)
    _center(draw, 640, f"WON TICKETS · {month:%B %Y}".upper(), _font(40), CYAN)
    lines = ["These tickets are not real bets.", "",
             "Every pick is a real call the model",
             "posted publicly before kickoff.", "",
             "The stakes are examples: what you",
             "would have won following the model", "that day."]
    y = 780
    for line in lines:
        _center(draw, y, line, _font(46), WHITE)
        y += 66
    _center(draw, y + 60, "Losing calls stay public too: epifanii.com", _font(34), MUTED)
    _center(draw, 1758, "18+ · Play responsibly", _font(28), MUTED)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"disclaimer_{month:%Y-%m}.jpg"
    img.convert("RGB").save(path, "JPEG", quality=92)
    return path


def build_day(day: str) -> tuple[list[Path], int, int]:
    """Tickets for one day's winners (may be empty), plus that day's record."""
    winners, n_picks, n_won = day_results(day)
    return [build_ticket(p, n_picks, n_won) for p in winners], n_picks, n_won
