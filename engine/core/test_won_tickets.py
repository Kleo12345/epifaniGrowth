"""Won-ticket selection and rendering.

Run: cd engine && python -m pytest core/test_won_tickets.py -q
"""
from types import SimpleNamespace

import pandas as pd
from PIL import Image

from core import won_tickets as w

BASE = dict(date="2026-10-30", league="Ligue-1-France-01", homeTeam="Nice", awayTeam="Rennes",
            market="Result (1/X/2)", prediction="H", result="Win")


def _fake_tracker(tmp_path, rows):
    csv, cfg = tmp_path / "t.csv", tmp_path / "c.json"
    pd.DataFrame(rows).to_csv(csv, index=False)
    cfg.write_text("{}")
    # select() is export_track_record's Core3 filter; identity here so the test owns the rows
    return SimpleNamespace(TRACKER=csv, CORE3=cfg, select=lambda df, _: df.to_dict("records"))


def test_top_singles_by_odds_and_voids_dont_count(tmp_path, monkeypatch):
    rows = [{**BASE, "id": f"p{i}", "homeTeam": f"t{i}", "odds": 1.5 + i / 10} for i in range(7)]
    rows += [{**BASE, "id": "loss", "odds": 9.0, "result": "Loss"},
             {**BASE, "id": "void", "odds": 8.0, "result": "Void"}]
    monkeypatch.setattr(w, "_track_record_module", lambda: _fake_tracker(tmp_path, rows))
    picks = w.settled_picks()
    assert [p["id"] for p in w.top_singles(picks, 5)] == ["p6", "p5", "p4", "p3", "p2"]
    assert w.day_record(picks, "2026-10-30") == (8, 7)


def test_one_league_cannot_take_every_slot():
    rows = [{**BASE, "id": f"fr{i}", "odds": 3.0 - i / 10} for i in range(6)]
    rows += [{**BASE, "id": "at", "league": "Bundesliga-Austria-01", "odds": 1.4},
             {**BASE, "id": "us", "league": "MLS-USA-01", "odds": 1.6}]
    top = w.top_singles(pd.DataFrame(rows), 5)
    assert [p["id"] for p in top] == ["fr0", "fr1", "fr2", "us", "at"]  # 3 leagues, odds order


def test_famous_league_outranks_bigger_odds_elsewhere():
    rows = [{**BASE, "id": "se", "league": "Allsvenskan-Sweden-01", "odds": 2.9},
            {**BASE, "id": "pl", "league": "Premier-League-England-01", "odds": 2.0},
            {**BASE, "id": "it", "league": "Serie-A-Italy", "odds": 2.1},  # id has no -01 suffix
            {**BASE, "id": "at", "league": "Bundesliga-Austria-01", "odds": 3.1}]
    assert [p["id"] for p in w.top_singles(pd.DataFrame(rows), 3)] == ["it", "at", "pl"]
    assert w.fame("Serie-A-Italy") == w.fame("Premier-League-England-01") == 1.5


def test_doubles_need_both_legs_won_and_skip_dnb():
    ou = dict(market="U/O-2.5", prediction="O")
    rows = [{**BASE, "id": "a1", "odds": 2.0}, {**BASE, **ou, "id": "a2", "odds": 1.5},       # both won
            {**BASE, "id": "b1", "homeTeam": "Lille", "odds": 2.5},
            {**BASE, **ou, "id": "b2", "homeTeam": "Lille", "odds": 1.8, "result": "Loss"},    # one leg lost
            {**BASE, "id": "c1", "homeTeam": "Metz", "odds": 2.2},
            {**BASE, "id": "c2", "homeTeam": "Metz", "market": "DNB", "odds": 1.6}]           # DNB: no double
    d = w.doubles(pd.DataFrame(rows))
    assert [x["id"] for x in d] == ["double_a1"] and abs(d[0]["odds"] - 3.0) < 1e-9


def test_build_day_is_four_singles_plus_the_double(tmp_path, monkeypatch):
    ou = dict(market="U/O-2.5", prediction="O")
    rows = [{**BASE, "id": f"s{i}", "homeTeam": f"t{i}", "odds": 2.0 + i / 10} for i in range(6)]
    rows += [{**BASE, "id": "d1", "homeTeam": "Nice", "odds": 1.9}, {**BASE, **ou, "id": "d2", "odds": 1.7}]
    monkeypatch.setattr(w, "_track_record_module", lambda: _fake_tracker(tmp_path, rows))
    monkeypatch.setattr(w, "build_ticket", lambda t, n, k: t["id"])
    tickets, n_picks, n_won = w.build_day("2026-10-30")
    assert tickets == ["s5", "s4", "s3", "s2", "double_d1"] and (n_picks, n_won) == (8, 8)


def test_stake_is_stable_and_in_range():
    assert w.stake_for("abc") == w.stake_for("abc")
    assert {w.stake_for(str(i)) for i in range(200)} <= set(w.STAKES)
    assert min(w.STAKES) == 20 and max(w.STAKES) == 500


def test_labels():
    assert w.league_name("Ligue-1-France-01") == "Ligue 1 · France"
    assert w.league_name("MLS-USA-01") == "MLS · USA"
    p = dict(homeTeam="Metz", awayTeam="Pau FC")
    assert w.pick_text({**p, "market": "DNB", "prediction": "A"}) == ("Pau FC not to lose", "Draw No Bet")
    assert w.pick_text({**p, "market": "Result (1/X/2)", "prediction": "D"}) == ("Draw", "Match result · X")
    assert w.pick_text({**p, "market": "U/O-2.5", "prediction": "U"})[0] == "Under 2.5 goals"


def test_tickets_render_as_story_jpeg(tmp_path):
    p = dict(id="2026-10-30_Bodo/Glimt_Pau FC_A_1", date="2026-10-30", league="Ligue-2-France-01",
             homeTeam="Bodo/Glimt", awayTeam="Pau FC", market="DNB", prediction="A", odds=2.55)
    path = w.build_ticket(p, 33, 20, out_dir=tmp_path)
    assert path.suffix == ".jpg" and path.parent == tmp_path and " " not in path.name
    assert Image.open(path).size == (1080, 1920)
    leg2 = {**p, "id": "x2", "market": "U/O-2.5", "prediction": "O", "odds": 1.8}
    dbl = {**p, "id": "double_x", "legs": [{**p, "market": "Result (1/X/2)"}, leg2], "odds": 2.55 * 1.8}
    assert Image.open(w.build_ticket(dbl, 33, 20, out_dir=tmp_path)).size == (1080, 1920)
