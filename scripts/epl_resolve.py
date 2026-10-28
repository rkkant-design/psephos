"""Resolve EPL match forecasts: fill resolved/outcome/correct on
forecasts/matches_ledger.csv rows whose fixture now has a final score.

Usage: python epl_resolve.py [--no-fetch]

This is the ONLY permitted write to existing matches_ledger rows, and only to
the three resolution columns - probabilities, hashes and timestamps are never
touched (same law as scripts/12_resolve_2026.py).

outcome: H / D / A per the fixture feed's final score.
correct: whether the max-probability outcome happened - DESCRIPTIVE ONLY.
         A 40% favourite losing is not an error; the real accounting is
         Brier/log in scripts/score.py, which scores the full distribution.

After resolving, run: python scripts/score.py
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "forecasts" / "world" / "epl_fixtures.json"
LEDGER = ROOT / "forecasts" / "matches_ledger.csv"
FEED_URL = "https://fixturedownload.com/feed/json/epl-2026"


def load_feed(no_fetch):
    if not no_fetch:
        try:
            req = urllib.request.Request(FEED_URL, headers={"User-Agent": "psephos/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                feed = json.loads(r.read().decode("utf-8"))
            FIXTURES.write_text(json.dumps({
                "source": FEED_URL,
                "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "fixtures": feed}, indent=1), encoding="utf-8")
            return feed
        except Exception as e:
            sys.exit(f"ABORT: fixture feed unreachable ({e}); log the failure and stop - "
                     f"never resolve from memory.")
    if not FIXTURES.exists():
        sys.exit("ABORT: no saved fixture file and --no-fetch given.")
    return json.loads(FIXTURES.read_text(encoding="utf-8"))["fixtures"]


def main(argv):
    if not LEDGER.exists():
        sys.exit("No matches ledger yet - nothing to resolve.")
    feed = load_feed("--no-fetch" in argv)
    scores = {f"EPL2627-M{m['MatchNumber']:03d}": m for m in feed
              if m["HomeTeamScore"] is not None}

    led = pd.read_csv(LEDGER, dtype={"resolved": str, "outcome": str, "correct": str})
    for c in ("resolved", "outcome", "correct"):
        led[c] = led[c].fillna("").replace("nan", "")

    today = datetime.now(timezone.utc).date().isoformat()
    n = 0
    for i, r in led.iterrows():
        if r.resolved:
            continue
        m = scores.get(r.match_id)
        if m is None:
            continue
        hs, as_ = int(m["HomeTeamScore"]), int(m["AwayTeamScore"])
        outcome = "H" if hs > as_ else ("A" if hs < as_ else "D")
        fav = max([("H", r.p_home), ("D", r.p_draw), ("A", r.p_away)], key=lambda x: x[1])[0]
        led.loc[i, ["resolved", "outcome", "correct"]] = [today, outcome, str(fav == outcome)]
        n += 1
        print(f"  {r.match_id} {r.home} {hs}-{as_} {r.away} -> {outcome} "
              f"(p assigned {dict(H=r.p_home, D=r.p_draw, A=r.p_away)[outcome]:.0%}, fav hit: {fav == outcome})")

    if n:
        led.to_csv(LEDGER, index=False)
        print(f"resolved {n} match rows. Now run: python scripts/score.py")
    else:
        print("nothing newly resolvable.")


if __name__ == "__main__":
    main(sys.argv[1:])
