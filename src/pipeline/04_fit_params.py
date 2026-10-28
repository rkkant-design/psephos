"""Fit the three structural parameters from the multi-state dataset.

  alpha  - GE->AE blend weight, one observation per (state, AE cycle), fit at
           state level exactly as the pilot did, then partially pooled by era
           (pre/post the 2014 nationalization regime break the pilot found).
  tau    - alliance transfer efficiency, measured at AC level: regress target
           bloc share on anchor-base and partner-base shares across matched
           constituencies; tau = partner coefficient / anchor coefficient.
  sigma  - constituency swing dispersion: sd across ACs of (party swing minus
           state swing), per state-cycle, for parties >=10% on both sides.

Outputs: alpha_obs/alpha_table, tau_obs/tau_table, sigma_obs/sigma_table (CSV).
"""
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from ms_lib import (PROC, bloc_weights, load_all, match_acs, state_share_map,
                    wide_shares)

ae, ss, el, blocs = load_all()

# ---------------- alpha ----------------
print("=" * 60, "\nALPHA: GE->AE blend weight per state-cycle\n" + "=" * 60)
ae_re = re.compile(r"^([A-Z]{2})(\d{4})$")
ge_re = re.compile(r"^GE([A-Z]{2})(\d{4})$")
ae_years, ge_years = {}, {}
for e in ss.election.unique():
    m = ae_re.match(e)
    if m:
        ae_years.setdefault(m.group(1), []).append(int(m.group(2)))
    m = ge_re.match(e)
    if m:
        ge_years.setdefault(m.group(1), []).append(int(m.group(2)))

def fit_alpha(ge_map, prev_map, targ_map):
    parties = [p for p, v in targ_map.items()
               if v >= 5 and p not in ("IND", "NOTA")]
    if len(parties) < 2:
        return None, 0
    grid = np.linspace(0, 1, 41)
    errs = []
    for a in grid:
        e = sum((a * ge_map.get(p, 0.0) + (1 - a) * prev_map.get(p, 0.0)
                 - targ_map[p]) ** 2 for p in parties)
        errs.append(e)
    return float(grid[int(np.argmin(errs))]), len(parties)

alpha_rows = []
for st, years in sorted(ae_years.items()):
    ys = sorted(set(years))
    for prev, targ in zip(ys, ys[1:]):
        if targ - prev > 7:
            continue
        ges = [g for g in ge_years.get(st, []) if prev < g <= targ]
        if not ges:
            ges = [g for g in ge_years.get(st, []) if g <= targ]
        if not ges:
            continue
        gy = max(ges)
        a, npar = fit_alpha(state_share_map(ss, f"GE{st}{gy}"),
                            state_share_map(ss, f"{st}{prev}"),
                            state_share_map(ss, f"{st}{targ}"))
        if a is None:
            continue
        era = "post2014" if gy >= 2014 else "pre2014"
        alpha_rows.append({"state": st, "cycle": f"{prev}->{targ}", "ae_year": targ,
                           "ge_used": gy, "alpha": a, "n_parties": npar, "era": era})
alpha_obs = pd.DataFrame(alpha_rows)
alpha_obs.to_csv(PROC / "alpha_obs.csv", index=False)
print(alpha_obs.groupby("era").alpha.describe().round(2).to_string())

# per-party residuals of the blend at the era-pooled alpha: these expose the
# systematic GE->AE premium (e.g. BJP polls far better in GEs than AEs) and
# the true state-level error scale of M2
era_alpha = alpha_obs.groupby("era").alpha.mean().to_dict()
resid_rows = []
for row in alpha_rows:
    st, targ = row["state"], row["ae_year"]
    prev = int(row["cycle"].split("->")[0])
    a = era_alpha[row["era"]]
    ge_map = state_share_map(ss, f"GE{st}{row['ge_used']}")
    prev_map = state_share_map(ss, f"{st}{prev}")
    targ_map = state_share_map(ss, f"{st}{targ}")
    for p, v in targ_map.items():
        if v < 5 or p in ("IND", "NOTA"):
            continue
        pred = a * ge_map.get(p, 0.0) + (1 - a) * prev_map.get(p, 0.0)
        resid_rows.append({"state": st, "ae_year": targ, "era": row["era"],
                           "party": p, "pred": round(pred, 2), "actual": v,
                           "resid": round(pred - v, 2)})
alpha_resid = pd.DataFrame(resid_rows)
alpha_resid.to_csv(PROC / "alpha_resid.csv", index=False)
top = alpha_resid.groupby(["era", "party"]).resid.agg(["mean", "count"])
print("\nM2 blend residual (pred - actual) by party/era, n>=4:")
print(top[top["count"] >= 4].round(2).to_string())

K = 2.0  # prior strength for partial pooling
tab = []
for era, d in alpha_obs.groupby("era"):
    mu = d.alpha.mean()
    for st, ds in d.groupby("state"):
        tab.append({"era": era, "state": st, "n": len(ds),
                    "alpha_raw": round(ds.alpha.mean(), 3),
                    "alpha_shrunk": round((len(ds) * ds.alpha.mean() + K * mu)
                                          / (len(ds) + K), 3)})
    tab.append({"era": era, "state": "_POOLED_", "n": len(d),
                "alpha_raw": round(mu, 3), "alpha_shrunk": round(mu, 3)})
alpha_table = pd.DataFrame(tab)
alpha_table.to_csv(PROC / "alpha_table.csv", index=False)
print(alpha_table[alpha_table.state == "_POOLED_"].to_string(index=False))

# ---------------- tau ----------------
print("\n" + "=" * 60, "\nTAU: alliance transfer efficiency (AC-level regression)\n" + "=" * 60)
tau_rows = []
for _, r in el.iterrows():
    bl_ae = blocs[(blocs.election_id == r.election_id) & (blocs.scope.isin(["ae", "both"]))]
    w_t = wide_shares(ae, r.election_id)
    w_b = wide_shares(ae, r.baseline_id)
    if w_t is None or w_b is None:
        continue
    pairs = match_acs(w_b, w_t)
    if len(pairs) < 30:
        continue
    bk = [p[0] for p in pairs]
    tk = [p[1] for p in pairs]
    for bloc, d in bl_ae.groupby("bloc"):
        anchors = d[d.w == "1"].party.tolist()
        partners = d[d.w.isin(["t"])].party.tolist()
        if not partners or not anchors:
            continue
        pb = sum(w_b[p].loc[bk].values for p in partners if p in w_b)
        if np.isscalar(pb) or pb.sum() < 1:
            continue
        ab = sum(w_b[p].loc[bk].values for p in anchors if p in w_b)
        tgt_parties = [p for p in list(d.party) if p in w_t]
        ts = sum(w_t[p].loc[tk].values for p in tgt_parties)
        if np.isscalar(ab) or np.isscalar(ts):
            continue
        X = np.column_stack([np.ones(len(bk)), ab, pb])
        beta, *_ = np.linalg.lstsq(X, ts, rcond=None)
        resid = ts - X @ beta
        r2 = 1 - resid.var() / ts.var() if ts.var() > 0 else np.nan
        if beta[1] > 0.2:
            tau_rows.append({"election_id": r.election_id, "bloc": bloc,
                             "partners": "+".join(partners),
                             "partner_base_mean": round(float(np.mean(pb)), 2),
                             "b_anchor": round(float(beta[1]), 3),
                             "b_partner": round(float(beta[2]), 3),
                             "tau": round(float(np.clip(beta[2] / beta[1], -0.5, 1.5)), 3),
                             "n_ac": len(bk), "r2": round(float(r2), 3)})
tau_obs = pd.DataFrame(tau_rows)
tau_obs.to_csv(PROC / "tau_obs.csv", index=False)
print(tau_obs.to_string(index=False))
meaningful = tau_obs[tau_obs.partner_base_mean >= 2.0]
tau_med = float(meaningful.tau.median())
tau_table = pd.DataFrame([{
    "n_alliances": len(meaningful), "tau_median": round(tau_med, 2),
    "tau_q25": round(float(meaningful.tau.quantile(.25)), 2),
    "tau_q75": round(float(meaningful.tau.quantile(.75)), 2),
    "pilot_prior": 0.75,
    "note": "partner_base_mean>=2pt alliances only; tau=b_partner/b_anchor",
}])
tau_table.to_csv(PROC / "tau_table.csv", index=False)
print("\n", tau_table.to_string(index=False))

# ---------------- sigma ----------------
print("\n" + "=" * 60, "\nSIGMA: constituency swing dispersion\n" + "=" * 60)
sig_rows = []
for _, r in el.iterrows():
    w_t = wide_shares(ae, r.election_id)
    w_b = wide_shares(ae, r.baseline_id)
    if w_t is None or w_b is None:
        continue
    pairs = match_acs(w_b, w_t)
    if len(pairs) < 30:
        continue
    bk = [p[0] for p in pairs]
    tk = [p[1] for p in pairs]
    tmap, bmap = state_share_map(ss, r.election_id), state_share_map(ss, r.baseline_id)
    # party-level: only ACs the party contested both times (share>=2% twice),
    # else seat-sharing churn shows up as phantom +/-40pt swings
    for p in w_t.columns:
        if p in ("IND",) or p not in w_b.columns:
            continue
        if tmap.get(p, 0) < 10 or bmap.get(p, 0) < 10:
            continue
        tv = w_t[p].loc[tk].values
        bv = w_b[p].loc[bk].values
        mask = (tv >= 2) & (bv >= 2)
        if mask.sum() < 30:
            continue
        delta = tv[mask] - bv[mask]
        sig_rows.append({"election_id": r.election_id, "state": r.state,
                         "level": "party", "unit": p,
                         "sigma_c": round(float(np.std(delta, ddof=1)), 2),
                         "state_swing": round(tmap.get(p, 0) - bmap.get(p, 0), 2),
                         "n_ac": int(mask.sum())})
    # bloc-level: dispersion of (target bloc share - composed baseline bloc
    # share) across ACs -- exactly the simulator's noise term
    TAU_MEAS = 0.6
    bw_ae = bloc_weights(blocs, r.election_id, "ae", TAU_MEAS)
    for bloc, comp in bw_ae.items():
        base_v = np.zeros(len(bk))
        for p, w in comp.items():
            if p in w_b.columns:
                base_v += w * w_b[p].loc[bk].values
        tgt_parties = [p for p in comp if p in w_t.columns]
        tgt_v = np.zeros(len(tk))
        for p in tgt_parties:
            tgt_v += w_t[p].loc[tk].values
        if base_v.mean() < 8 or tgt_v.mean() < 5:
            continue
        delta = tgt_v - base_v
        sig_rows.append({"election_id": r.election_id, "state": r.state,
                         "level": "bloc", "unit": bloc,
                         "sigma_c": round(float(np.std(delta, ddof=1)), 2),
                         "state_swing": round(float(np.mean(delta)), 2),
                         "n_ac": len(bk)})
sigma_obs = pd.DataFrame(sig_rows)
sigma_obs.to_csv(PROC / "sigma_obs.csv", index=False)
for lvl in ["party", "bloc"]:
    d = sigma_obs[sigma_obs.level == lvl]
    print(f"\n-- {lvl}-level sigma_c by state --")
    print(d.groupby("state").sigma_c.describe().round(1).to_string())
    print(f"{lvl} national median: {d.sigma_c.median():.2f}")
blocsig = sigma_obs[sigma_obs.level == "bloc"]
state_sig = blocsig.groupby("state").sigma_c.median().round(2)
nat = round(float(blocsig.sigma_c.median()), 2)
sigma_table = state_sig.reset_index().rename(columns={"sigma_c": "sigma_median"})
sigma_table.loc[len(sigma_table)] = ["_NATIONAL_", nat]
sigma_table.to_csv(PROC / "sigma_table.csv", index=False)
print(f"\nsigma_table written (bloc-level medians); national {nat} "
      "(pilot: measured 6.8 UP party-level, assumed 6.0)")
