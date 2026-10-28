"""Fetch Polymarket per-race winner markets for the 2026 US midterms (M_market).

Sweeps every state x {governor, senate} through the anonymous gamma-api
public-search endpoint and records, for each race that has an open
party-winner event, the de-vigged P(Democrats win the race).

Event patterns observed 2026-10-24:
  governor : slug like "georgia-governor-winner-2026" /
             "<state>-governor-election-winner"
  senate   : slug like "ohio-senate-election-winner"
  Each carries binary markets "Will the Democrats win the <State> <office>
  race in 2026?" and the Republican mirror. De-vig:
  p_dem = dem_yes / (dem_yes + rep_yes).

Liquidity rule (stated before fetching): a race's market is admitted as an
instrument only when the winner event's liquidity >= $10,000; below that the
race is recorded but carries market=null (WATCH-1INST at the gate). Combo,
margin-of-victory and primary events are never used.

Outputs:
  data/raw/polymarket_usmid2026/<state>_<office>.json  (raw API responses)
  data/usmid2026_markets.json  (one record per race found, with source+date)

Usage: python usmid_fetch_markets.py
"""
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "polymarket_usmid2026"
OUT = ROOT / "data" / "usmid2026_markets.json"
RAW.mkdir(parents=True, exist_ok=True)

LIQUIDITY_MIN = 10_000.0

STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming",
]


def fetch(query, dest):
    url = f"https://gamma-api.polymarket.com/public-search?q={query.replace(' ', '+')}"
    for attempt in range(4):
        r = subprocess.run(["curl", "-s", "--max-time", "30", url, "-o", str(dest)],
                           capture_output=True, text=True)
        if r.returncode == 0 and dest.exists() and dest.stat().st_size > 2:
            try:
                return json.loads(dest.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError:
                pass
        time.sleep(2 * (attempt + 1))
    return None


def winner_event(data, state_slug, office):
    """The open party-winner event for this state+office, or None."""
    pat = re.compile(rf"^{state_slug}-{office}(-election)?(-winner)?(-winner-2026|-winner|-2026)?$")
    best = None
    for e in data.get("events", []):
        slug = e.get("slug", "")
        if e.get("closed") or not e.get("active"):
            continue
        if not slug.startswith(state_slug + "-" + office):
            continue
        if not ("winner" in slug or pat.match(slug)):
            continue
        if any(k in slug for k in ("primary", "margin", "combo", "turnout", "runoff", "2027")):
            continue  # 2027 = next cycle's race (e.g. Kentucky governor), never 2026
        liq = float(e.get("liquidity") or 0)
        if best is None or liq > best[0]:
            best = (liq, e)
    return best


def party_prices(event):
    """(p_dem_yes, p_rep_yes) from the paired binary markets, else None."""
    dem = rep = None
    for m in event.get("markets") or []:
        q = (m.get("question") or "").lower()
        prices = m.get("outcomePrices")
        if isinstance(prices, str):
            prices = json.loads(prices)
        if not prices:
            continue
        p_yes = float(prices[0])
        if "will the democrats win" in q:
            dem = p_yes
        elif "will the republicans win" in q:
            rep = p_yes
    if dem is None or rep is None or dem + rep <= 0:
        return None
    return dem, rep


def main():
    fetched_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    records = []
    for state in STATES:
        slug = state.lower().replace(" ", "-")
        for office in ("governor", "senate"):
            dest = RAW / f"{slug}_{office}.json"
            data = fetch(f"{state} {office}", dest)
            if data is None:
                print(f"FETCH FAILED {state} {office}", file=sys.stderr)
                continue
            found = winner_event(data, slug, office)
            if not found:
                # combo/margin events can crowd the winner event out of the
                # search's first page; retry with a sharper query
                data = fetch(f"{state} {office} election winner", dest)
                found = winner_event(data, slug, office) if data else None
            if not found:
                continue
            liq, ev = found
            pp = party_prices(ev)
            if not pp:
                continue
            dem, rep = pp
            records.append({
                "state": state, "office": office, "event_slug": ev["slug"],
                "p_dem_raw": dem, "p_rep_raw": rep,
                "p_dem_devig": round(dem / (dem + rep), 4),
                "liquidity": round(liq, 2),
                "volume": round(float(ev.get("volume") or 0), 2),
                "liquid": liq >= LIQUIDITY_MIN,
            })
            print(f"{state:15s} {office:8s} {ev['slug']:50s} "
                  f"dem={dem:.3f} rep={rep:.3f} devig={dem/(dem+rep):.4f} liq={liq:,.0f}")
            time.sleep(0.4)
    out = {
        "source": "Polymarket gamma-api public-search (anonymous)",
        "fetched_utc": fetched_utc,
        "devig_rule": "p_dem = dem_yes / (dem_yes + rep_yes) from the paired party winner markets",
        "liquidity_min_usd": LIQUIDITY_MIN,
        "races": records,
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\n{len(records)} race markets -> {OUT}")


if __name__ == "__main__":
    main()
