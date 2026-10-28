"""Measure cross-instrument error correlation — the number that justifies the
dual gate and that single-instrument forecasters never publish.

If two instruments' errors were independent, requiring both to clear 95% would
make a joint false-call vanishingly rare. They are NOT independent (both drink
partly from the same information ecosystem); the honest gate math needs the
measured correlation. This script computes it from every resolved question
where both M2 (structure) and M3 (polls) issued probabilities:

  error_i = p_i - outcome      (signed; same sign = failing together)

Sources: N=46 leave-one-out ledger (precision_ledger.csv, loo mode) + resolved
forward rows (forecasts/ledger.csv). Outputs:
  data/processed/instrument_correlation.csv  (per-source and pooled rows)
  appends a "correlation" block into data/processed/scores_summary.json so the
  public app displays it (openness is the point).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

frames = []

pl = pd.read_csv(PROC / "precision_ledger.csv")
pl = pl[(pl["mode"] == "loo") & pl.p_m2.notna() & pl.p_m3.notna() & pl.actual.notna()]
if len(pl):
    frames.append(pd.DataFrame({
        "source": "retrodiction_n46",
        "e2": pl.p_m2 - pl.actual, "e3": pl.p_m3 - pl.actual,
    }))

fl = pd.read_csv(ROOT / "forecasts" / "ledger.csv")
for c in ("resolved", "outcome"):
    fl[c] = fl[c].fillna("").astype(str).replace("nan", "")
fl = fl.sort_values("run_at_utc").drop_duplicates(["forecast_id", "question"], keep="last")
fr = fl[(fl.resolved.str.len() > 0) & fl.p_m2.notna() & fl.p_m3.notna()
        & fl.outcome.isin(["YES", "NO"])]
if len(fr):
    y = (fr.outcome == "YES").astype(float)
    frames.append(pd.DataFrame({
        "source": "forward_resolved",
        "e2": fr.p_m2.astype(float) - y, "e3": fr.p_m3.astype(float) - y,
    }))

all_df = pd.concat(frames, ignore_index=True)

rows = []
for src, g in list(all_df.groupby("source")) + [("pooled", all_df)]:
    n = len(g)
    r = float(np.corrcoef(g.e2, g.e3)[0, 1]) if n >= 3 else np.nan
    same_sign = float(((g.e2 > 0) == (g.e3 > 0)).mean())
    # joint large-miss rate: both instruments off by >0.5 the same way
    joint_bad = float(((g.e2.abs() > 0.5) & (g.e3.abs() > 0.5)
                       & ((g.e2 > 0) == (g.e3 > 0))).mean())
    indep_pred = float((g.e2.abs() > 0.5).mean() * (g.e3.abs() > 0.5).mean())
    rows.append({"source": src, "n": n, "error_corr": round(r, 3),
                 "same_sign_rate": round(same_sign, 3),
                 "joint_large_miss": round(joint_bad, 4),
                 "independent_would_predict": round(indep_pred, 4)})

out = pd.DataFrame(rows)
out.to_csv(PROC / "instrument_correlation.csv", index=False)
print(out.to_string(index=False))

pooled = rows[-1]
ssp = PROC / "scores_summary.json"
if ssp.exists():
    ss = json.loads(ssp.read_text(encoding="utf-8"))
    ss["correlation"] = {
        "n": pooled["n"], "error_corr": pooled["error_corr"],
        "same_sign_rate": pooled["same_sign_rate"],
        "joint_large_miss": pooled["joint_large_miss"],
        "independent_would_predict": pooled["independent_would_predict"],
        "note": ("Measured on every resolved question where both instruments "
                 "forecast. This is why the gate requires BOTH: errors "
                 "correlate, so one instrument's 95% is not 95%."),
    }
    ssp.write_text(json.dumps(ss, indent=1), encoding="utf-8")
    print("\ncorrelation block added to scores_summary.json")
print(f"\nInterpretation: error correlation {pooled['error_corr']}, same-sign "
      f"{pooled['same_sign_rate']*100:.0f}% (independent would be ~50%). Joint "
      f"large-miss rate {pooled['joint_large_miss']*100:.1f}% vs "
      f"{pooled['independent_would_predict']*100:.1f}% if independent — the gap is the "
      f"common-mode risk the dual gate prices in and a single instrument hides.")
