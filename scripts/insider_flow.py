"""Insider-flow module: politicians are informed insiders, and their movements
are costly signals (cost-to-fake principle). Track defections, ticket demand
and campaign-resource allocation; score net weighted flow per state.

Status: REPORTED SIGNAL, not a gate instrument. It becomes one only after the
2027 cycle resolves against today's pre-registered signal values (the UP2017
retrodiction says this signal would have flipped that WATCH to an early CALL;
2027 is the forward test).

Event ledger: forecasts/insider_events.csv (append-only), columns:
  date, state, event_type (defection|ticket_demand|campaign_allocation|
  morale), actor, from_bloc, to_bloc, weight (1-5), source, note
Weights (stated rubric, fixed before any scoring):
  5 sitting MLA/MP or state-level leader with own base
  4 former MLA/MP or prominent district leader
  3 serious ticket aspirant / block-level organization
  2 local notable
  1 symbolic / cadre-level
Direction: to_bloc gains +weight, from_bloc gains -weight.

Signal per state = net flow / gross flow over the trailing window (default
180 days): +1.0 = all movement one way. Labels: |s|>=0.6 & gross>=10 strong;
|s|>=0.3 & gross>=6 moderate; else weak/neutral.

Usage:
  python insider_flow.py score [--window 180]   - score all states, write
      data/processed/insider_signal.csv and print; signal rows are also
      SHA-hashed into forecasts/research_ledger-style pre-registration via
      a signal ledger (forecasts/insider_signal_ledger.csv, append-only).
"""
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "forecasts" / "insider_events.csv"
SIGLED = ROOT / "forecasts" / "insider_signal_ledger.csv"
OUT = ROOT / "data" / "processed" / "insider_signal.csv"

def score(window_days=180):
    ev = pd.read_csv(EVENTS, parse_dates=["date"])
    cutoff = pd.Timestamp(datetime.now(timezone.utc).date() - timedelta(days=window_days))
    ev = ev[ev.date >= cutoff]
    rows = []
    for st, g in ev.groupby("state"):
        flows = {}
        gross = 0
        for r in g.itertuples():
            w = int(r.weight)
            gross += w
            if isinstance(r.to_bloc, str) and r.to_bloc:
                flows[r.to_bloc] = flows.get(r.to_bloc, 0) + w
            if isinstance(r.from_bloc, str) and r.from_bloc:
                flows[r.from_bloc] = flows.get(r.from_bloc, 0) - w
        if not flows or gross == 0:
            continue
        top = max(flows, key=flows.get)
        net = flows[top]
        s = net / gross
        label = ("strong" if abs(s) >= 0.6 and gross >= 10 else
                 "moderate" if abs(s) >= 0.3 and gross >= 6 else "weak")
        rows.append({"state": st, "window_days": window_days,
                     "beneficiary": top, "net": net, "gross": gross,
                     "signal": round(s, 3), "label": label,
                     "n_events": len(g),
                     "flows": json.dumps({k: v for k, v in sorted(flows.items())})})
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    # pre-register today's signal values (append-only, hashed)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    led_rows = []
    for r in rows:
        payload = json.dumps({**r, "asof_utc": stamp}, sort_keys=True)
        led_rows.append({**{k: r[k] for k in ("state", "beneficiary", "net",
                                              "gross", "signal", "label")},
                         "asof_utc": stamp,
                         "sha256": hashlib.sha256(payload.encode()).hexdigest(),
                         "resolved": "", "outcome": "", "validated": ""})
    pd.DataFrame(led_rows).to_csv(SIGLED, mode="a", header=not SIGLED.exists(),
                                  index=False)
    print(df.drop(columns=["flows"]).to_string(index=False) if len(df) else "no events in window")
    print(f"\nsignal rows pre-registered -> {SIGLED.name}")

if __name__ == "__main__":
    w = 180
    if "--window" in sys.argv:
        w = int(sys.argv[sys.argv.index("--window") + 1])
    score(w)
