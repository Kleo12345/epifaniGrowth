"""
Fetches today's predictions from the Epifani portal API and filters
them down to the picks worth posting.
"""
import os
from dataclasses import dataclass, field
from typing import Optional
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("EPIFANI_API_URL", "http://localhost:3000/api/predictions")
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.60"))
VALUE_BETS_ONLY = os.getenv("VALUE_BETS_ONLY", "true").lower() == "true"

# Local JSON written by the portal's Python exporter — used as fallback
_LOCAL_JSON = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "web_portalEpifani", "public", "data", "predictions.json"
)

# Confidence tiers (probability thresholds)
TIER_ELITE  = 0.90
TIER_HIGH   = 0.75
TIER_STRONG = 0.60

TIER_COLORS = {
    "ELITE SIGNAL":    "#00ff88",
    "HIGH CONFIDENCE": "#00f2ff",
    "STRONG SIGNAL":   "#7000ff",
}

# Human-readable market/outcome labels
_MARKET_LABELS = {
    ("U/O-2.5", "O"):                    "Over 2.5 Goals",
    ("U/O-2.5", "U"):                    "Under 2.5 Goals",
    ("BTTS",    "Yes"):                  "Both Teams Score",
    ("BTTS",    "No"):                   "Both Teams Don't Score",
    ("Result (1/X/2)", "H"):             "Home Win",
    ("Result (1/X/2)", "D"):             "Draw",
    ("Result (1/X/2)", "A"):             "Away Win",
    ("Double Chance", "1X"):             "Double Chance: Home or Draw",
    ("Double Chance", "X2"):             "Double Chance: Draw or Away",
    ("Double Chance", "12"):             "Double Chance: Home or Away",
    ("DNB", "H"):                        "Draw No Bet: Home",
    ("DNB", "A"):                        "Draw No Bet: Away",
    ("Corners (Dynamic Line)", "O"):     "Corners Over Line",
    ("Corners (Dynamic Line)", "U"):     "Corners Under Line",
}

# Maps portal tab names → market strings used in the data
MARKET_TABS = {
    "1X2":     "Result (1/X/2)",
    "U/O":     "U/O-2.5",
    "BTTS":    "BTTS",
    "DNB":     "DNB",
    "DC":      "Double Chance",
    "Corners": "Corners (Dynamic Line)",
}


@dataclass
class Pick:
    match_id: str
    league: str
    match: str
    home_team: str
    away_team: str
    time_str: str
    market: str
    outcome: str
    odds: float
    probability: float
    edge: float
    tier: str
    tier_color: str
    label: str          # human-readable pick label
    confidence_pct: int # 0–100

    @property
    def cta_url(self) -> str:
        source = os.getenv("UTM_SOURCE", "twitter")
        return f"epifanii.com/?ref={source}"


def _tier(probability: float) -> tuple[str, str]:
    if probability >= TIER_ELITE:
        return "ELITE SIGNAL", TIER_COLORS["ELITE SIGNAL"]
    if probability >= TIER_HIGH:
        return "HIGH CONFIDENCE", TIER_COLORS["HIGH CONFIDENCE"]
    return "STRONG SIGNAL", TIER_COLORS["STRONG SIGNAL"]


def _label(market: str, outcome: str) -> str:
    return _MARKET_LABELS.get((market, outcome), f"{market}: {outcome}")


def _load_local_json() -> dict:
    """Read the portal's local predictions.json as a fallback."""
    import json
    path = os.path.normpath(_LOCAL_JSON)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Local predictions file not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_picks(
    exclude_corners: bool = False,
    top: int = None,
    exclude_markets: frozenset = frozenset(),
    value_bets_only: bool | None = None,
) -> list[Pick]:
    """
    Calls the Epifani predictions API and returns one Pick per match
    (the single highest-confidence value bet per match that isn't excluded).

    When a market is excluded the match falls back to its next-best qualifying
    pick rather than disappearing from the list entirely.

    Falls back to the portal's local predictions.json when the API is unreachable.
    """
    data = None
    try:
        resp = requests.get(API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        try:
            data = _load_local_json()
            print("  ⚠  Portal API unreachable — using local predictions.json")
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Portal API unreachable and no local fallback found.\n"
                f"Start the portal (npm run dev) or ensure predictions.json exists.\n{e}"
            )

    # Build the full exclusion set from both sources
    _excluded = set(exclude_markets)
    if exclude_corners:
        _excluded.add("Corners (Dynamic Line)")

    # Resolve value_bets_only: parameter overrides .env setting
    _value_only = value_bets_only if value_bets_only is not None else VALUE_BETS_ONLY

    picks: list[Pick] = []

    from datetime import datetime, date

    # ── Smart date selection ──────────────────────────────────────
    # If no matches exist for today, use the most recent day available.
    all_matches = data.get("predictions", [])
    today = date.today()

    # Collect all unique dates present in the data
    available_dates = set()
    for m in all_matches:
        ts = m.get("timestamp")
        if ts:
            available_dates.add(datetime.fromtimestamp(ts).date())

    if today in available_dates:
        target_date = today
    elif available_dates:
        # Fall back to the most recent date
        target_date = max(available_dates)
        print(f"  ⚠  No predictions for today ({today}). Using most recent: {target_date}")
    else:
        target_date = today  # no dates at all — will just return empty

    for match in all_matches:
        # Filter to only the target day's matches
        match_ts = match.get("timestamp")
        if match_ts:
            match_date = datetime.fromtimestamp(match_ts).date()
            if match_date != target_date:
                continue

        candidates = []
        for p in match.get("predictions", []):
            mkt = p["market"]
            if mkt == "Draw No Bet":
                mkt = "DNB"
            if (p["probability"] >= MIN_CONFIDENCE
                and (not _value_only or p.get("is_value", False))
                and mkt not in _excluded):
                p_copy = dict(p)
                p_copy["market"] = mkt
                candidates.append(p_copy)

        if not candidates:
            continue

        # Best single pick for this match (after exclusions)
        best = max(candidates, key=lambda p: p["probability"])
        tier_name, tier_color = _tier(best["probability"])

        picks.append(Pick(
            match_id    = match["id"],
            league      = match["league"].replace("-", " ").title(),
            match       = match["match"],
            home_team   = match["home_team"],
            away_team   = match["away_team"],
            time_str    = match.get("time_str", ""),
            market      = best["market"],
            outcome     = best["outcome"],
            odds        = round(best["odds"], 2),
            probability = best["probability"],
            edge        = round(max(0.0, min(best["probability"], 0.88) - (1.0 / best["odds"])), 4),
            tier        = tier_name,
            tier_color  = tier_color,
            label       = _label(best["market"], best["outcome"]),
            confidence_pct = min(round(best["probability"] * 100), 88),
        ))

    picks.sort(key=lambda p: p.probability, reverse=True)

    if top is not None:
        picks = picks[:top]

    return picks


# ── Model track record (for the "Model Track Record" video format) ──

def _api_base() -> str:
    """Derive the portal's /api base from EPIFANI_API_URL."""
    if "/api/" in API_URL:
        return API_URL.split("/api/")[0] + "/api"
    if API_URL.rstrip("/").endswith("/api"):
        return API_URL.rstrip("/")
    return API_URL.rsplit("/", 1)[0]


def fetch_performance() -> dict | None:
    """GET the model's public 30-day track record from /api/performance/stats.

    Returns {windowDays, sample, hitRate, avgEdge, tiers:{elite/high/strong:{rate,n}}}
    or None if unreachable. Public endpoint, no auth.
    """
    url = os.getenv("EPIFANI_PERF_URL", f"{_api_base()}/performance/stats")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def fetch_recent_winners() -> list[dict]:
    """GET the model's recent winning picks from /api/performance/winners.

    Returns a list of winner dicts (with edge/probability) or [] if unreachable.
    """
    url = os.getenv("EPIFANI_WINNERS_URL", f"{_api_base()}/performance/winners")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except requests.RequestException:
        return []

