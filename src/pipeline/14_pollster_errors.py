"""Build the per-state pollster-error ledger — the N=46 report's #1 priority.

For every (election, bloc) with a curated final-window vote-share poll mean
(polls_blocs.csv, kind='voteshare') and a known actual vote share
(election_summaries.csv pred rows carry base/actual seats; actual SHARES come
from state_shares_all.csv via the bloc compositions), compute:

    error = actual_share - polled_share   (positive = polls UNDERstated)

Outputs data/processed/pollster_errors.csv with per-observation rows and
data/processed/pollster_corrections.csv with per-state aggregates:
    correction = shrink * mean(error per bloc-type), shrink = n/(n+2)
    sigma_poll = measured sd of errors per state (floor 4.0, the rated prior)

Bloc-type mapping: errors are aggregated per (state, bloc_class) where
bloc_class is 'incumbent_natl' (BJP-led blocs), 'rival' (main opposition
bloc), 'third' (everything else) — party-specific histories are too sparse
at N<=3 per state; class-level pooling is the honest middle ground, and the
UP pilot's successful 2022 correction was exactly this kind of class error.

predict.py reads pollster_corrections.csv automatically when a config's
poll_corrections has "auto": true.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

polls = pd.read_csv(PROC / "polls_blocs.csv")
vs = polls[polls.kind == "pct"].copy()
es = pd.read_csv(PROC / "election_summaries.csv")

# actual bloc vote shares: compose from state_shares_all (party-level actuals)
# and blocs.csv weights, same convention as the pipeline (1 / t=tau / h=tau/2)
ss = pd.read_csv(PROC / "state_shares_all.csv")
blocs = pd.read_csv(ROOT / "data" / "raw" / "multistate" / "meta" / "blocs.csv")
TAU = float(pd.read_csv(PROC / "tau_table.csv").tau_median.iloc[0])
WMAP = {"1": 1.0, "t": TAU, "h": TAU / 2}

share_map = {(r.election, r.party): r.share for r in ss.itertuples()}

def bloc_actual(eid, bloc):
    comp = blocs[(blocs.election_id == eid) & (blocs.bloc == bloc)
                 & (blocs.scope.isin(["ae", "both"]))]
    if comp.empty:
        return None
    tot, found = 0.0, False
    for r in comp.itertuples():
        v = share_map.get((eid, r.party))
        if v is not None:
            tot += WMAP[str(r.w)] * v
            found = True
    return tot if found else None

vs["actual"] = [bloc_actual(r.election_id, r.bloc) for r in vs.itertuples()]
m = vs.dropna(subset=["actual"]).copy()
act_col = "actual"
m["error"] = m[act_col] - m["mean"]
m["state"] = m.election_id.str[:2]

NATL = {"BJPA", "NDA", "BJP"}
def bloc_class(row):
    b = row.bloc.upper()
    if b in NATL:
        return "bjp_led"
    return "rival_or_third"

m["bloc_class"] = m.apply(bloc_class, axis=1)
m[["election_id", "state", "bloc", "bloc_class", "mean", act_col, "error", "n_polls"]].round(2)\
    .to_csv(PROC / "pollster_errors.csv", index=False)

rows = []
for (st, bc), g in m.groupby(["state", "bloc_class"]):
    n = len(g)
    shrink = n / (n + 2)
    rows.append({"state": st, "bloc_class": bc, "n_obs": n,
                 "mean_error": round(g.error.mean(), 2),
                 "sd_error": round(g.error.std(ddof=0), 2),
                 "correction": round(shrink * g.error.mean(), 2)})
agg = pd.DataFrame(rows)
# per-state sigma for M3: pooled sd of errors, floored at rated prior 4.0
sig = m.groupby("state").error.apply(lambda s: max(4.0, float(np.std(s)))).round(2)
agg = agg.merge(sig.rename("sigma_poll_measured"), on="state")
agg.to_csv(PROC / "pollster_corrections.csv", index=False)

print(f"\n{len(m)} (election, bloc) error observations across "
      f"{m.state.nunique()} states -> pollster_errors.csv")
print(agg.to_string(index=False))
nat = m.error
print(f"\nNational: mean error {nat.mean():+.2f} (polls {'under' if nat.mean()>0 else 'over'}state "
      f"actual shares), sd {nat.std(ddof=0):.2f} — compare the unrated prior sigma 6.0")
