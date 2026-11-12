"""Golden-output regression test for the deterministic forecasting core.

Why (audit finding #9): the engines are seeded and reproducible, but nothing
pinned their outputs, so a NumPy/Python upgrade could silently shift every
probability and no one would notice. This test pins representative outputs of
each deterministic instrument. A FAILURE means the math moved -- investigate it
as a real regression, or, if an intended dependency bump changed a seeded RNG
stream, re-baseline the affected value deliberately (and say so).

Covered via src/engine/world_predict.py, the any-event engine whose adapters are
instances of every math family the project uses:
  gate_verdict       - dual + 2-of-3 + WATCH-1INST certification logic (pure)
  market_probs       - de-vigging implied odds (stdlib)
  ratings_tournament - softmax championship share (stdlib exp), incl. the REAL
                       forecasts/world/IPL2027.json config (config + math drift)
  us_house           - probit on generic ballot vs tipping point (stdlib erf)
  league_sim         - the seeded shrunk-PPG Monte Carlo (NumPy RNG drift sentinel)

Run: python src/tests/test_golden.py     (also works under pytest)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "engine"))

import numpy as np          # noqa: E402
import world_predict as wp  # noqa: E402

TOL = 1e-6


def _close(a, b, tol=TOL):
    assert abs(a - b) <= tol, f"{a} != {b} (tol {tol})"


def test_gate_verdict():
    # dual gate (2 instruments)
    assert wp.gate_verdict([0.96, 0.97]) == ("CALL-YES", 0.96)
    assert wp.gate_verdict([0.90, 0.97]) == ("WATCH", 0.90)
    assert wp.gate_verdict([0.02, 0.03]) == ("CALL-NO", 0.02)
    # never certify on one instrument
    assert wp.gate_verdict([0.96]) == ("WATCH-1INST", None)
    # 2-of-3 gate
    assert wp.gate_verdict([0.96, 0.97, 0.99]) == ("CALL-YES", 0.97)
    assert wp.gate_verdict([0.50, 0.96, 0.97]) == ("WATCH", 0.96)   # min < 0.80 vetoes
    assert wp.gate_verdict([0.02, 0.03, 0.50]) == ("WATCH", 0.03)   # max > 0.20 vetoes


def test_market_devig():
    out, _ = wp.market_probs({
        "adapter": "ratings_tournament",
        "market": {"odds": {"A": 2.0, "B": 4.0}, "others_implied": 0.0},
        "questions": [{"q": "A", "entity": "A"}, {"q": "B", "entity": "B"}]})
    _close(out["A"], 0.666667, 1e-5)
    _close(out["B"], 0.333333, 1e-5)


def test_ratings_softmax():
    out, _ = wp.ratings_tournament({
        "model": {"ratings": {"A": 100, "B": 90}, "tau": 10},
        "questions": [{"q": "A", "entity": "A"}]})
    _close(out["A"], 0.731059)


def test_us_house_probit():
    out = wp.us_house({
        "adapter": "us_house",
        "model": {"generic_ballot_margin": 2.0, "tipping_point": 0.0,
                  "sigma": 5.0, "senate_model": None},
        "questions": [{"q": "H", "model": "house_dem"}]})
    _close(out["H"], 0.655422)


def test_ipl2027_real_config():
    cfg = json.loads((ROOT / "forecasts" / "world" / "IPL2027.json").read_text(encoding="utf-8"))
    _, probs = wp.ratings_tournament(cfg)
    _close(probs["Royal Challengers Bengaluru"], 0.153298, 1e-5)
    _close(probs["Lucknow Super Giants"], 0.062326, 1e-5)
    assert abs(sum(probs.values()) - 1.0) <= 1e-9  # a proper distribution


def test_league_sim_seeded():
    wp.rng = np.random.default_rng(42)  # reset so the test is call-order independent
    _, probs = wp.league_sim({
        "model": {"teams": [{"team": "A", "p": 10, "pts": 25, "gd": 10},
                            {"team": "B", "p": 10, "pts": 15, "gd": -5}]},
        "questions": [{"q": "A", "entity": "A"}]})
    _close(probs["A"], 0.9905, 1e-4)  # NumPy RNG stream sentinel


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    fails = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            fails += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\nGOLDEN: {'OK' if not fails else 'FAILED'} ({len(tests) - fails}/{len(tests)} passed)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
