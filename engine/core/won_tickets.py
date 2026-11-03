"""
"Won tickets" for Instagram Stories: winning public picks drawn as betting-slip
style cards with an example stake.

Daily: yesterday's top singles (odds weighted by league fame, one per league first)
plus the best same-match double (the match's 1X2 call and its Over/Under call both landed).
Monthly recap: the month's top singles and doubles in one batch.

Picks come from the Epifani engine's own tracker through the same Core3 filter
that feeds the public track record (scripts/export_track_record.py), so every
leg is a real call the site published. Stakes are examples and every card says
so; each month's highlight also opens with build_disclaimer().
"""
import importlib.util
import json
import os
import random
import re
from datetime import date
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

from core.image_builder import (BG, CYAN, GREEN, MUTED, OUTPUT_DIR, PURPLE, SUBTLE, WHITE,
                                _font, _glow_layer, _overlay_rect, _shadow_text, _tlen)

EPIFANI_ROOT = Path(os.getenv("EPIFANI_ROOT", str(Path.home() / "epifani")))
TICKETS_DIR = OUTPUT_DIR / "tickets"
TOP_N = 5                         # tickets per daily batch (one is a double when there is one)
RECAP_SINGLES, RECAP_DOUBLES = 10, 3
# Amounts people actually type into a slip, not uniform noise.
STAKES = [20, 25, 30, 40, 50, 60, 75, 100, 120, 150, 200, 250, 300, 400, 500]
W, H, PAD = 1080, 1920, 80
# Odds multiplier: a win in a league people follow convinces more than a slightly bigger
# one nobody watches. At 1.5 a 2.00 in the Premier League outranks anything under 3.00
# from an unlisted league. Tune here; keys are league ids without the "-01" suffix.
LEAGUE_FAME = {
    **dict.fromkeys(["Premier-League-England", "La-Liga-Spain", "Serie-A-Italy",
                     "Bundesliga-1-Germany", "Ligue-1-France"], 1.5),
    **dict.fromkeys(["Serie-B-Italy", "Championship-England", "Liga-1-Portugal",
                     "Eredivisie-Netherlands", "Super-Lig-Turkey", "Serie-A-Brazil",
                     "Primera-Division-Argentina", "MLS-USA", "Liga-MX-Mexico"], 1.2),
}


def _track_record_module():
    spec = importlib.util.spec_from_file_location(
        "export_track_record", EPIFANI_ROOT / "scripts" / "export_track_record.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def settled_picks() -> pd.DataFrame:
    """All settled (non-void) public Core3 picks."""
    tr = _track_record_module()
    with open(tr.CORE3) as f:
        picks = pd.DataFrame(tr.select(pd.read_csv(tr.TRACKER), json.load(f)))
    return picks if picks.empty else picks[picks.result != "Void"]


def fame(league: str) -> float:
    return LEAGUE_FAME.get(league.removesuffix("-01"), 1.0)


def top_singles(picks: pd.DataFrame, n: int) -> list[dict]:
    """Winners by fame-weighted odds, best per league first so one busy league can't take
    every slot."""
    wins = picks[picks.result == "Win"]
    wins = wins.assign(score=wins.odds * wins.league.map(fame)).sort_values("score", ascending=False)
    per_league = wins.drop_duplicates("league")
    top = pd.concat([per_league, wins.drop(per_league.index)]).head(n)
    return top.sort_values("score", ascending=False).drop(columns="score").to_dict("records")


def doubles(picks: pd.DataFrame) -> list[dict]:
    """Same-match doubles, best fame-weighted odds first: the match's 1X2 call and O/U call, both won.
    DNB is left out: with the 1X2 call on the same match it's nearly the same bet twice."""
    out = []
    for (day, home, away), m in picks.groupby(["date", "homeTeam", "awayTeam"]):
        legs = [m[m.market.str.startswith("Result")], m[m.market == "U/O-2.5"]]
        if all(len(leg) == 1 and leg.iloc[0].result == "Win" for leg in legs):
            legs = [leg.iloc[0].to_dict() for leg in legs]
            out.append({"id": f"double_{legs[0]['id']}", "date": day, "league": legs[0]["league"],
                        "homeTeam": home, "awayTeam": away, "legs": legs,
                        "odds": legs[0]["odds"] * legs[1]["odds"]})
    return sorted(out, key=lambda d: -d["odds"] * fame(d["league"]))


def day_record(picks: pd.DataFrame, day: str) -> tuple[int, int]:
    d = picks[picks.date == day]
    return len(d), int((d.result == "Win").sum())


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


def build_ticket(t: dict, n_picks: int, n_won: int, out_dir: Path = TICKETS_DIR) -> Path:
    """1080x1920 story slip for a winning single (a pick) or same-match double (has 'legs')."""
    legs = t.get("legs") or [t]
    double = len(legs) > 1
    stake = stake_for(str(t["id"]))
    played = date.fromisoformat(t["date"])
    leg_h = 140 if double else 170
    legs_h = len(legs) * leg_h + (len(legs) - 1) * 16
    top, x0, x1 = 340, PAD, W - PAD
    bot = top + 430 + legs_h + 378 + 60
    inner = x1 - x0 - 88

    img = _canvas()
    draw = ImageDraw.Draw(img)
    _logo(draw, PAD)
    draw.text((PAD, PAD + 70), "WON TICKETS", font=_font(22), fill=MUTED)

    # Slip panel + header
    img = _overlay_rect(img, (x0, top, x1, bot), (255, 255, 255, 14), radius=28,
                        outline_rgba=(255, 255, 255, 40), outline_width=2)
    img = _overlay_rect(img, (x0, top, x1, top + 110), (0, 255, 136, 34), radius=28)
    draw = ImageDraw.Draw(img)
    draw.text((x0 + 44, top + 34), "SAME-MATCH DOUBLE" if double else "SINGLE", font=_font(34), fill=WHITE)
    badge, fb = "✓ WON", _font(34)
    draw.text((x1 - 44 - _tlen(draw, badge, fb), top + 34), badge, font=fb, fill=GREEN)

    y = top + 160
    draw.text((x0 + 44, y), f"{league_name(t['league']).upper()}  ·  {played:%a %d %b}", font=_font(26), fill=MUTED)
    y += 60
    _shadow_text(draw, (x0 + 44, y), t["homeTeam"], _fit(draw, t["homeTeam"], 56, inner), WHITE)
    draw.text((x0 + 44, y + 70), "vs", font=_font(28), fill=MUTED)
    _shadow_text(draw, (x0 + 44, y + 108), t["awayTeam"], _fit(draw, t["awayTeam"], 56, inner), WHITE)
    y += 210

    # One panel per leg
    fo = _font(56 if double else 64)
    for leg in legs:
        call, market = pick_text(leg)
        img = _overlay_rect(img, (x0 + 44, y, x1 - 44, y + leg_h), (0, 242, 255, 22), radius=18,
                            outline_rgba=(0, 242, 255, 90))
        draw = ImageDraw.Draw(img)
        draw.text((x0 + 76, y + 24), market.upper(), font=_font(24), fill=CYAN)
        _shadow_text(draw, (x0 + 76, y + (58 if double else 70)), call,
                     _fit(draw, call, 46 if double else 50, inner - 260), WHITE)
        lo = f"{leg['odds']:.2f}"
        draw.text((x1 - 76 - _tlen(draw, lo, fo), y + (leg_h - 64) // 2), lo, font=fo, fill=WHITE)
        y += leg_h + 16
    y += 44

    for i in range(x0 + 44, x1 - 44, 28):  # tear line
        draw.line([(i, y), (i + 14, y)], fill=(255, 255, 255, 60), width=3)
    y += 50
    odds = f"≈ {t['odds']:.2f}" if double else f"{t['odds']:.2f}"
    fr, fv = _font(34), _font(40)
    for label, value in (("Stake", _money(stake)), ("Combined odds" if double else "Odds", odds)):
        draw.text((x0 + 44, y), label, font=fr, fill=MUTED)
        draw.text((x1 - 44 - _tlen(draw, value, fv), y - 4), value, font=fv, fill=WHITE)
        y += 74
    y += 10
    won = _money(stake * t["odds"])
    fw = _fit(draw, won, 92, inner - 200)
    draw.text((x0 + 44, y + 22), "Won", font=_font(44), fill=WHITE)
    _shadow_text(draw, (x1 - 44 - _tlen(draw, won, fw), y), won, fw, GREEN)

    # Day record + CTA + disclosure
    ry = max(1510, bot + 70)
    _center(draw, ry, f"{played:%a %d %b}: {n_won}/{n_picks} calls landed", _font(40), WHITE)
    _center(draw, ry + 60, "Every call is public at epifanii.com", _font(32), CYAN)
    img = _overlay_rect(img, (PAD, 1700, W - PAD, 1701), SUBTLE, radius=0)
    draw = ImageDraw.Draw(img)
    note = "Example stake · not a real bet · 18+"
    if double:
        note = "Example stake · not a real bet · odds multiplied, approx. · 18+"
    _center(draw, 1745, note, _font(26), MUTED)

    out_dir.mkdir(parents=True, exist_ok=True)
    # id already starts with the date; team names can hold '/' (Bodo/Glimt) or spaces
    path = out_dir / f"ticket_{re.sub(r'[^A-Za-z0-9._-]+', '_', str(t['id']))}.jpg"
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


def _pick_tickets(picks: pd.DataFrame, total: int, max_doubles: int) -> list[dict]:
    """Up to max_doubles doubles, the rest singles from other matches (no match shown twice)."""
    dbl = doubles(picks)[:max_doubles]
    taken = {(d["date"], d["homeTeam"], d["awayTeam"]) for d in dbl}
    rest = picks[[k not in taken for k in zip(picks.date, picks.homeTeam, picks.awayTeam)]]
    return top_singles(rest, total - len(dbl)) + dbl


def build_day(day: str) -> tuple[list[Path], int, int]:
    """One day's batch: top singles + the best double (if any), TOP_N tickets total."""
    picks = settled_picks()
    if picks.empty:
        return [], 0, 0
    n_picks, n_won = day_record(picks, day)
    tickets = _pick_tickets(picks[picks.date == day], TOP_N, 1)
    return [build_ticket(t, n_picks, n_won) for t in tickets], n_picks, n_won


def build_recap(month: str) -> list[Path]:
    """'2026-10' -> the month's top singles + top doubles, each with its own day's record."""
    picks = settled_picks()
    m = picks[picks.date.str.startswith(month)] if not picks.empty else picks
    if m.empty:
        return []
    tickets = _pick_tickets(m, RECAP_SINGLES + RECAP_DOUBLES, RECAP_DOUBLES)
    return [build_ticket(t, *day_record(picks, t["date"])) for t in tickets]
