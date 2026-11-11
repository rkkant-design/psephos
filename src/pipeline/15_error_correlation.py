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

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

frames = []

pl = pd.read_csv(PROC / "precision_ledger.csv")
pl = pl[(pl["mode"] == "loo") & pl.p_m2.notna() & pl.p_m3.notna() & pl.actual.notna()]
if len(pl):
    frames.append(pd.DataFrame({
        "source": "retrodiction_n46",
        "e2": pl.p_m2 - pl.actual, "e3": pl.p_m3 - pl.actual,
        "p2": pl.p_m2.astype(float).values, "p3": pl.p_m3.astype(float).values,
        "o": pl.actual.astype(float).values,
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
        "p2": fr.p_m2.astype(float).values, "p3": fr.p_m3.astype(float).values,
        "o": y.values,
    }))

# Outcomes here are binary (0/1). The sign of a signed residual e = p - outcome is
# therefore MECHANICAL: for any binary outcome both instruments' residuals share its
# side (both <= 0 when outcome=1, both >= 0 when outcome=0), so a raw "same-sign rate"
# is ~1.0 by construction and has no 50% baseline. We do NOT report it. Instead we use
# a directional co-miss with a MATCHED independence baseline:
#   wrong_i   = instrument i put p_i on the wrong side of 0.5 (backed the wrong winner)
#   co_miss   = P(wrong_2 AND wrong_3)                 -- both back the wrong side
#   independent baseline = P(wrong_2) * P(wrong_3)     -- if their errors were independent
# ratio > 1 means the instruments fail together more than chance. Pearson r of the signed
# residuals is reported too, labelled as residual correlation (it carries a common-mode
# floor from sharing the same realized outcome, which is exactly the risk being measured).
all_df = pd.concat(frames, ignore_index=True)

def _codir(g):
    w2 = (g.p2 > 0.5) != (g.o == 1)   # instrument 2 backed the wrong winner
    w3 = (g.p3 > 0.5) != (g.o == 1)
    both = float((w2 & w3).mean())
    indep = float(w2.mean() * w3.mean())
    return float(w2.mean()), float(w3.mean()), both, indep

rows = []
for src, g in list(all_df.groupby("source")) + [("pooled", all_df)]:
    n = len(g)
    r = float(np.corrcoef(g.e2, g.e3)[0, 1]) if n >= 3 else float("nan")
    w2r, w3r, both, indep = _codir(g)
    rows.append({"source": src, "n": n, "error_corr": round(r, 3),
                 "wrong_dir_m2": round(w2r, 4), "wrong_dir_m3": round(w3r, 4),
                 "codir_miss": round(both, 4),
                 "codir_independent": round(indep, 4),
                 "codir_ratio": round(both / indep, 2) if indep else None})

out = pd.DataFrame(rows)
out.to_csv(PROC / "instrument_correlation.csv", index=False)
print(out.to_string(index=False))

pooled = rows[-1]
ssp = PROC / "scores_summary.json"
if ssp.exists():
    ss = json.loads(ssp.read_text(encoding="utf-8"))
    ss["correlation"] = {
        "n": pooled["n"],
        "error_corr": pooled["error_corr"],
        "codir_miss": pooled["codir_miss"],
        "codir_independent": pooled["codir_independent"],
        "codir_ratio": pooled["codir_ratio"],
        "formula": ("error_i = p_i - outcome (outcome in {0,1}); 'backed the wrong winner' = "
                    "p_i on the wrong side of 0.5. Co-miss = P(both wrong), baseline = "
                    "P(M2 wrong) x P(M3 wrong) under independence. error_corr is the Pearson "
                    "correlation of the signed residuals (carries a common-mode floor from "
                    "sharing the realized outcome - the very risk being measured)."),
        "note": ("Measured on every resolved question where both instruments forecast. "
                 "The directional co-miss has a matched independence baseline; we do not "
                 "report a raw same-sign rate because for binary outcomes it is mechanical."),
        "by_cohort": [{"source": r["source"], "n": r["n"], "error_corr": r["error_corr"],
                       "codir_miss": r["codir_miss"], "codir_independent": r["codir_independent"],
                       "codir_ratio": r["codir_ratio"]} for r in rows],
    }
    ssp.write_text(json.dumps(ss, indent=1), encoding="utf-8")
    print("\ncorrelation block added to scores_summary.json")
print(f"\nInterpretation: when one instrument backs the wrong winner the other does too "
      f"{pooled['codir_miss']*100:.1f}% of the time vs {pooled['codir_independent']*100:.1f}% "
      f"if independent ({pooled['codir_ratio']}x). Pearson residual correlation {pooled['error_corr']}. "
      f"This common-mode risk is what the dual gate prices in and a single instrument hides.")
