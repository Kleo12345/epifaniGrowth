"""
Assert-based self-check for the weekly record check-in stats block
(script_generator._perf_stats_block / _roi_line). No network, no Gemini call. Run with:
  python core/test_record_stats_block.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import script_generator as sg

# Shape and values of the live 30-day stats (live/epifani_public.json, 2026-11-09 19:00:40).
LIVE = {
    "windowDays": 30, "sample": 537, "hitRate": 0.4823091247672253,
    "avgEdge": 0.024258082838627782, "won": 259, "lost": 278, "voids": 32,
    "units": -41.47, "roi": -0.0728822495606327,
    "tiers": {"elite": {"rate": 0.8461538461538461, "n": 26},
              "high": {"rate": 0.5963302752293578, "n": 109},
              "strong": {"rate": 0.5161290322580645, "n": 124}},
}


def test_live_block_states_negative_roi():
    block = sg._perf_stats_block(LIVE)
    assert "-7.3% ROI" in block, block
    assert "(-41.47 units)" in block, block
    assert "negative over this window" in block, block
    assert "Misses in that window: 278 of the 537" in block, block
    assert "+2% (this averages only the picks where it saw a positive edge" in block, block
    assert "Elite-tier picks: 85% over 26" in block, block


def test_negative_edge_has_no_plus_minus():
    block = sg._perf_stats_block(dict(LIVE, avgEdge=-0.015))
    assert "+-" not in block, block
    assert "-2% (this averages only" in block, block


def test_positive_roi_wording():
    line = sg._roi_line({"roi": 0.031, "units": 12.0})
    assert line.startswith("- Return at a flat 1-unit stake"), line
    assert "+3.1% ROI (+12.00 units)." in line, line
    assert "Never call the model profitable" in line, line


def test_missing_fields():
    assert sg._roi_line({}) is None
    assert sg._roi_line({"roi": None}) is None
    assert sg._roi_line({"roi": float("nan")}) is None
    assert "voids included at zero return: -7.3% ROI" in sg._perf_stats_block(LIVE)
    line = sg._roi_line({"roi": -0.05})
    assert line is not None and "-5.0% ROI." in line, line
    block = sg._perf_stats_block({k: v for k, v in LIVE.items() if k not in ("roi", "units")})
    assert "ROI" not in block, block


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all record-stats-block checks passed")
