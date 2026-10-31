"""Won-ticket selection and rendering.

Run: cd engine && python -m pytest core/test_won_tickets.py -q
"""
from types import SimpleNamespace

import pandas as pd
from PIL import Image

from core import won_tickets as w


def _fake_tracker(tmp_path, rows):
    csv, cfg = tmp_path / "t.csv", tmp_path / "c.json"
    pd.DataFrame(rows).to_csv(csv, index=False)
    cfg.write_text("{}")
    # select() is export_track_record's Core3 filter; identity here so the test owns the rows
    return SimpleNamespace(TRACKER=csv, CORE3=cfg, select=lambda df, _: df.to_dict("records"))


def test_day_results_top_winners_by_odds(tmp_path, monkeypatch):
    base = dict(date="2026-10-30", league="Ligue-1-France-01", homeTeam="Nice",
                awayTeam="Rennes", market="Result (1/X/2)", prediction="H")
    rows = [{**base, "id": f"p{i}", "odds": 1.5 + i / 10, "result": "Win"} for i in range(7)]
    rows += [{**base, "id": "loss", "odds": 9.0, "result": "Loss"},
             {**base, "id": "void", "odds": 8.0, "result": "Void"},
             {**base, "id": "other_day", "odds": 7.0, "result": "Win", "date": "2026-10-29"}]
    monkeypatch.setattr(w, "_track_record_module", lambda: _fake_tracker(tmp_path, rows))
    top, n_picks, n_won = w.day_results("2026-10-30")
    assert [p["id"] for p in top] == ["p6", "p5", "p4", "p3", "p2"]
    assert (n_picks, n_won) == (8, 7)  # the void doesn't count as a call


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


def test_ticket_renders_as_story_jpeg(tmp_path):
    p = dict(id="2026-10-30_Metz_Pau FC_A_1", date="2026-10-30", league="Ligue-2-France-01",
             homeTeam="Metz", awayTeam="Pau FC", market="DNB", prediction="A", odds=2.55)
    path = w.build_ticket(p, 33, 20, out_dir=tmp_path)
    assert path.suffix == ".jpg" and " " not in path.name
    assert Image.open(path).size == (1080, 1920)
