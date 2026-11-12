"""Resolve the pre-registered 2026 holdout forecasts against actual results.

Actuals hand-entered from the current Wikipedia results-by-alliance tables
(fetched by 11_fetch_2026_results.py, cached in data/raw/holdout2026/wiki_current/),
bloc'd exactly as the forecast configs define them.
Fills resolved/outcome/correct in forecasts/ledger.csv (rows never deleted) and
writes data/raw/holdout2026/actuals_2026.csv + a scoring summary to stdout.
"""
import csv
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FDIR = ROOT / "forecasts"

MAJ = {"WB2026": 148, "TN2026": 118, "KL2026": 71, "AS2026": 64}
SEATS = {
    "WB2026": {"AITC": 80, "BJP": 208, "LF": 2, "INC": 2},
    "TN2026": {"SPA": 73, "NDA": 53, "TVK": 108},
    "KL2026": {"LDF": 35, "UDF": 102, "NDA": 3},
    "AS2026": {"NDA": 102, "ASOM": 21, "AIUDF": 2},
}
SHARES = {
    "WB2026": {"AITC": 40.96, "BJP": 45.92, "LF": 6.77, "INC": 2.96},
    "TN2026": {"SPA": 31.40, "NDA": 27.21, "TVK": 35.02},
    "KL2026": {"LDF": 37.64, "UDF": 46.55, "NDA": 14.20},
    "AS2026": {"NDA": 48.02, "ASOM": 35.95, "AIUDF": 5.46},
}
RESOLVED = "2026-05-04"  # counting day (all four states)


def outcome(fid, q):
    seats, maj = SEATS[fid], MAJ[fid]
    largest = max(seats, key=seats.get)
    m = re.fullmatch(r"(\w+) wins majority", q)
    if m:
        return "YES" if seats[m.group(1)] >= maj else "NO"
    m = re.fullmatch(r"(\w+) is largest", q)
    if m:
        return "YES" if m.group(1) == largest else "NO"
    m = re.fullmatch(r"Winner \(largest\) in \{(.+)\}", q)
    if m:
        blocs = [b.strip() for b in m.group(1).split(",")]
        return "YES" if largest in blocs else "NO"
    m = re.fullmatch(r"(\w+) under (\d+) seats", q)
    if m:
        return "YES" if seats[m.group(1)] < int(m.group(2)) else "NO"
    raise ValueError(f"unparsed question: {q}")


def sanity_check_actuals():
    """Catch transcription typos in the hand-entered actuals before they touch the
    ledger (finding #4)."""
    for fid in SEATS:
        seats, maj, shares = SEATS[fid], MAJ[fid], SHARES[fid]
        assert set(seats) == set(shares), f"{fid}: SEATS and SHARES list different blocs"
        assert all(isinstance(v, int) and v >= 0 for v in seats.values()), f"{fid}: bad seat count"
        assert maj > 0, f"{fid}: bad majority threshold"
        tot = sum(shares.values())
        assert 0 < tot <= 100.5, f"{fid}: vote shares sum to {tot} (out of range)"
    cache = ROOT / "data" / "raw" / "holdout2026" / "wiki_current"
    if not cache.exists():
        print(f"WARNING: cached results source {cache} not found - the hand-entered "
              f"actuals could not be cross-checked against the fetched source")


# --- guarded, line-surgical resolution: fill ONLY resolved/outcome/correct on the
#     holdout rows; every other line of ledger.csv stays byte-identical (no pandas
#     round-trip of unrelated rows), and a row already resolved to a DIFFERENT
#     outcome aborts rather than silently rewriting history. ---
sanity_check_actuals()
LED_PATH = FDIR / "ledger.csv"
with open(LED_PATH, "r", encoding="utf-8", newline="") as f:
    lines = f.read().splitlines(keepends=True)
header = next(csv.reader([lines[0]]))
ci = {c: header.index(c) for c in ("forecast_id", "question", "verdict",
                                   "resolved", "outcome", "correct")}
conflicts, changed = [], 0
for i, line in enumerate(lines[1:], start=1):
    if not line.strip():
        continue
    row = next(csv.reader([line.rstrip("\r\n")]))
    fid = row[ci["forecast_id"]]
    if fid not in SEATS:
        continue
    out = outcome(fid, row[ci["question"]])
    v = row[ci["verdict"]]
    corr = str(out == "YES") if v == "CALL-YES" else (str(out == "NO") if v == "CALL-NO" else "")
    if row[ci["resolved"]].strip():  # already resolved
        if row[ci["outcome"]].strip() != out:
            conflicts.append((fid, row[ci["question"]], row[ci["outcome"]], out))
        continue  # idempotent: leave an already-resolved row untouched
    row[ci["resolved"]] = RESOLVED
    row[ci["outcome"]] = out
    row[ci["correct"]] = corr
    end = line[len(line.rstrip("\r\n")):]
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(row)
    lines[i] = buf.getvalue() + end
    changed += 1
if conflicts:
    print("ABORT: rows already resolved to a DIFFERENT outcome - refusing to rewrite history:")
    for fid, q, old, new in conflicts:
        print(f"  {fid} | {q} | ledger={old!r} computed={new!r}")
    sys.exit(1)
if changed:
    with open(LED_PATH, "w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))
    print(f"resolved {changed} holdout rows (line-surgical; only 3 columns touched).")
else:
    print("no newly resolvable holdout rows (all already resolved identically).")
led = pd.read_csv(LED_PATH)

# actuals audit file
rows = []
for fid in SEATS:
    for b in SEATS[fid]:
        rows.append({"forecast_id": fid, "bloc": b, "seats": SEATS[fid][b],
                     "vote_share_pct": SHARES[fid][b], "majority": MAJ[fid],
                     "counting_day": RESOLVED,
                     "source": "Wikipedia current rev results-by-alliance table"})
pd.DataFrame(rows).to_csv(ROOT / "data" / "raw" / "holdout2026" / "actuals_2026.csv", index=False)

# ---- scoring ----
h = led[led.forecast_id.isin(SEATS)].copy()
calls = h[h.verdict.isin(["CALL-YES", "CALL-NO"])]
print(f"ledger rows resolved: {len(h)}  |  CALLs: {len(calls)}  "
      f"correct: {int(calls.correct.sum())}  precision: {calls.correct.mean():.3f}")
print(calls[["forecast_id", "question", "p_gate", "verdict", "outcome", "correct"]].to_string(index=False))

# calibration: all rows with probabilities
h["y"] = (h.outcome == "YES").astype(int)
for col in ["p_m2", "p_m3", "p_gate"]:
    d = h.dropna(subset=[col])
    print(f"\n{col}: n={len(d)}  mean p={d[col].mean():.3f}  realized={d.y.mean():.3f}  "
          f"Brier={((d[col]-d.y)**2).mean():.3f}")

# seat-interval coverage from forecast jsons
print("\nseat-interval coverage (p5-p95):")
cov = {"m2": [0, 0], "m3": [0, 0]}
for fid in SEATS:
    fj = json.loads((FDIR / f"{fid}_forecast.json").read_text(encoding="utf8"))
    for mk, key in (("m2", "seats_m2"), ("m3", "seats_m3")):
        for b, st in fj[key].items():
            if b not in SEATS[fid]:
                continue
            a = SEATS[fid][b]
            hit = st["p5"] <= a <= st["p95"]
            cov[mk][0] += hit
            cov[mk][1] += 1
            print(f"  {fid} {b:6s} {mk}: [{st['p5']},{st['p95']}] med {st['med']} actual {a} {'HIT' if hit else 'MISS'}")
print(f"M2 coverage: {cov['m2'][0]}/{cov['m2'][1]}   M3 coverage: {cov['m3'][0]}/{cov['m3'][1]}")
