"""WIP: 05 rewrite adding M3 (polls) + strict dual gate. NOT YET RUN.

This was about to replace 05_loo_retrodict.py when the session paused.
It extends the working 05 with:
  - M3 from data/processed/polls_blocs.csv (vote-share polls n>=3 drive the
    constituency engine with poll-implied swing; seat-projection polls n>=3
    give bloc-seat t(5) distributions directly; else no M3),
  - empirical poll-error scales (pct resid sd, seat err fraction) computed
    out-of-sample per mode, same exclusion logic as alpha/sigma,
  - gate_strict: CALL-YES iff min(p2,p3)>=.95, CALL-NO iff max(p2,p3)<=.05,
    WATCH-NOPOLL when M3 absent, WATCH-FLAG on new-entrant elections,
  - ledger columns p_m3 / m3_kind / gate_strict / strict_correct.

To resume: review, rename over 05_loo_retrodict.py, run, then write the
multi-state report (see side-session note for the full checklist).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from ms_lib import (META, PROC, bloc_weights, load_all, state_share_map,
                    wide_shares)

N_SIM = 10_000
GATE = 0.95
K_SHRINK = 2.0
TAU_PRIOR = 0.75
SIGMA_FALLBACK = 10.0
MIN_POLLS = 3

rng = np.random.default_rng(42)

ae, ss, el, blocs = load_all()
alpha_obs = pd.read_csv(PROC / "alpha_obs.csv")
alpha_resid = pd.read_csv(PROC / "alpha_resid.csv")
tau_obs = pd.read_csv(PROC / "tau_obs.csv")
sigma_obs = pd.read_csv(PROC / "sigma_obs.csv")
outcomes_manual = pd.read_csv(META / "outcomes_manual.csv")
polls = pd.read_csv(PROC / "polls_blocs.csv")
polls = polls[polls.n_polls >= MIN_POLLS]

# ---------------- phase A: actual bloc outcomes ----------------
ACTUAL = {}
for _, r in el.iterrows():
    eid = r.election_id
    out_map = {}
    for _, br in blocs[(blocs.election_id == eid)
                       & (blocs.scope.isin(["both", "ge"]))].iterrows():
        out_map[br.party] = br.bloc
    man = outcomes_manual[outcomes_manual.election_id == eid]
    if len(man):
        ACTUAL[eid] = dict(zip(man.bloc, man.seats))
        continue
    w_t = wide_shares(ae, eid)
    if w_t is None:
        continue
    winners = w_t.idxmax(axis=1)
    actual = {}
    for p in winners:
        b = out_map.get(p)
        if b:
            actual[b] = actual.get(b, 0) + 1
    ACTUAL[eid] = actual


def bloc_actual_share(eid, bloc):
    smap = state_share_map(ss, eid)
    if not smap:
        return None
    parties = blocs[(blocs.election_id == eid) & (blocs.bloc == bloc)].party.unique()
    v = sum(smap.get(p, 0.0) for p in parties)
    return v if v > 0 else None


# ---------------- phase B: poll error scales + pollster-bias ledger ----------
# flagged (new-entrant) elections are excluded from the error POOLS, consistent
# with how sigma_state excludes M2-invisible rows: the pattern flag, not the
# error scale, is what handles those elections
FLAGGED = set(el[el.new_entrant_flag == 1].election_id)
el_ix = el.set_index("election_id")


def bloc_anchor(eid, bloc):
    d = blocs[(blocs.election_id == eid) & (blocs.bloc == bloc) & (blocs.w == "1")]
    return d.party.iloc[0] if len(d) else None


pct_resid_rows, seat_err_rows, bias_rows = [], [], []
for _, pr in polls.iterrows():
    eid, bloc = pr.election_id, pr.bloc
    year = int(eid[-4:])
    if pr.kind == "pct":
        act = bloc_actual_share(eid, bloc)
        if act is not None:
            if eid not in FLAGGED:
                pct_resid_rows.append({"election_id": eid, "year": year,
                                       "resid": pr["mean"] - act})
            anchor = bloc_anchor(eid, bloc)
            if anchor:
                # pollster-error ledger (pilot design): actual minus polled,
                # keyed by state x bloc anchor party
                bias_rows.append({"state": el_ix.loc[eid, "state"], "year": year,
                                  "anchor": anchor, "err": act - pr["mean"]})
    else:
        act = ACTUAL.get(eid, {}).get(bloc)
        n_seats = int(el_ix.loc[eid, "n_seats"])
        if act is not None and eid not in FLAGGED:
            seat_err_rows.append({"election_id": eid, "year": year,
                                  "err_frac": (pr["mean"] - act) / n_seats})
pct_resid = pd.DataFrame(pct_resid_rows)
seat_err = pd.DataFrame(seat_err_rows)
bias_ledger = pd.DataFrame(bias_rows)
print(f"poll error pools (unflagged): {len(pct_resid)} pct residuals "
      f"(sd {pct_resid.resid.std():.2f}), {len(seat_err)} seat errors "
      f"(frac sd {seat_err.err_frac.std():.3f}); bias ledger {len(bias_ledger)} rows")


def poll_bias(eid, bloc, year, state):
    """Pilot-style correction: half of the most recent PRIOR same-state,
    same-anchor poll error (actual - polled). Prior elections only, so no
    leakage in either mode."""
    anchor = bloc_anchor(eid, bloc)
    if anchor is None or bias_ledger.empty:
        return 0.0
    d = bias_ledger[(bias_ledger.state == state) & (bias_ledger.anchor == anchor)
                    & (bias_ledger.year < year)]
    if d.empty:
        return 0.0
    return 0.5 * float(d.sort_values("year").iloc[-1].err)


def params_for(eid, state, year, ge_year, mode):
    era = "post2014" if ge_year >= 2014 else "pre2014"
    a = alpha_obs[alpha_obs.era == era]
    if mode == "past":
        a = a[a.ae_year < year]
    else:
        a = a[~((a.state == state) & (a.ae_year == year))]
    if len(a) == 0:
        alpha = 0.5
    else:
        mu = a.alpha.mean()
        own = a[a.state == state]
        alpha = (len(own) * own.alpha.mean() + K_SHRINK * mu) / (len(own) + K_SHRINK) \
            if len(own) else mu
    t = tau_obs[tau_obs.partner_base_mean >= 2.0]
    t = t[t.election_id != eid]
    if mode == "past":
        t = t[t.election_id.str[-4:].astype(int) < year]
    tau = float(t.tau.median()) if len(t) >= 3 else TAU_PRIOR
    s = sigma_obs[(sigma_obs.level == "bloc") & (sigma_obs.election_id != eid)]
    if mode == "past":
        s = s[s.election_id.str[-4:].astype(int) < year]
    own = s[s.state == state]
    if len(own):
        sigma = float(own.sigma_c.median())
    elif len(s):
        sigma = float(s.sigma_c.median())
    else:
        sigma = SIGMA_FALLBACK
    rr = alpha_resid[(alpha_resid.era == era) & (alpha_resid.pred >= 3)]
    if mode == "past":
        rr = rr[rr.ae_year < year]
    else:
        rr = rr[~((rr.state == state) & (rr.ae_year == year))]
    sigma_state = max(3.0, float(rr.resid.std())) if len(rr) >= 10 else 6.0
    pr = pct_resid[pct_resid.election_id != eid]
    se = seat_err[seat_err.election_id != eid]
    if mode == "past":
        pr = pr[pr.year < year]
        se = se[se.year < year]
    sigma_poll = max(3.0, float(pr.resid.std())) if len(pr) >= 8 else 5.0
    seat_frac = max(0.05, float(se.err_frac.std())) if len(se) >= 8 else 0.12
    return (round(float(alpha), 3), round(tau, 3), round(sigma, 2),
            round(sigma_state, 2), round(sigma_poll, 2), round(seat_frac, 3))


def simulate(base_mat, pred_shift, sigma_c, sigma_state):
    n_bloc, n_ac = base_mat.shape
    seats = np.zeros((n_bloc, N_SIM), dtype=np.int32)
    chunk = 1000
    for s0 in range(0, N_SIM, chunk):
        n = min(chunk, N_SIM - s0)
        shocks = rng.standard_t(5, (n_bloc, n, 1)) * (sigma_state / np.sqrt(5 / 3))
        noise = rng.normal(0, sigma_c, (n_bloc, n, n_ac))
        mat = (base_mat[:, None, :] + pred_shift[:, None, None] + shocks + noise)
        win = mat.argmax(axis=0)
        for b in range(n_bloc):
            seats[b, s0:s0 + n] = (win == b).sum(axis=1)
    return seats


def gate_of(p):
    if p >= GATE:
        return "CALL-YES"
    if p <= 1 - GATE:
        return "CALL-NO"
    return "WATCH"


ledger_rows, summary_rows = [], []

for _, r in el.iterrows():
    eid, state, year = r.election_id, r.state, r.year
    ge_year = int(r.ge_prior[-4:])
    majority = r.n_seats // 2 + 1
    w_b = wide_shares(ae, r.baseline_id)
    if w_b is None:
        print(f"!! no baseline for {eid}, skipping")
        continue
    actual = ACTUAL.get(eid, {})
    man = outcomes_manual[outcomes_manual.election_id == eid]
    flagged = bool(r.new_entrant_flag)
    ep = polls[polls.election_id == eid]
    pct_polls = ep[ep.kind == "pct"].set_index("bloc")
    seat_polls = ep[ep.kind == "seats"].set_index("bloc")

    for mode in ("loo", "past"):
        (alpha, tau, sigma_c, sigma_state,
         sigma_poll, seat_frac) = params_for(eid, state, year, ge_year, mode)
        bw_ae = bloc_weights(blocs, eid, "ae", tau)
        bw_ge = bloc_weights(blocs, eid, "ge", tau)
        names = list(bw_ae)
        base_state = state_share_map(ss, r.baseline_id)
        ge_state = state_share_map(ss, r.ge_prior)

        base_mat = np.zeros((len(names), len(w_b)))
        base_bloc, pred_bloc = {}, {}
        for i, b in enumerate(names):
            for p, w in bw_ae[b].items():
                if p in w_b.columns:
                    base_mat[i] += w * w_b[p].values
            base_bloc[b] = sum(w * base_state.get(p, 0.0) for p, w in bw_ae[b].items())
            ge_b = sum(w * ge_state.get(p, 0.0) for p, w in bw_ge[b].items())
            pred_bloc[b] = alpha * ge_b + (1 - alpha) * base_bloc[b]
        pred_shift = np.array([pred_bloc[b] - base_bloc[b] for b in names])
        seats2 = simulate(base_mat.astype(np.float32),
                          pred_shift.astype(np.float32), sigma_c, sigma_state)
        largest2 = seats2.argmax(axis=0)

        # ----- M3 -----
        m3_kind, seats3, largest3 = None, None, None
        use_pct = [b for b in names if b in pct_polls.index]
        use_seat = [b for b in names if b in seat_polls.index]
        if len(use_pct) >= 2:
            m3_kind = "pct"
            shift3 = np.array([
                (pct_polls.loc[b, "mean"] + poll_bias(eid, b, year, state)
                 - base_bloc[b]) if b in pct_polls.index
                else pred_bloc[b] - base_bloc[b] for b in names])
            seats3 = simulate(base_mat.astype(np.float32),
                              shift3.astype(np.float32), sigma_c, sigma_poll)
            largest3 = seats3.argmax(axis=0)
        elif len(use_seat) >= 2:
            m3_kind = "seats"
            draws = np.zeros((len(names), N_SIM))
            for i, b in enumerate(names):
                if b in seat_polls.index:
                    mu = seat_polls.loc[b, "mean"]
                    sd_poll = seat_polls.loc[b, "sd"]
                    sd = max(sd_poll if np.isfinite(sd_poll) else 0,
                             seat_frac * r.n_seats)
                    draws[i] = mu + rng.standard_t(5, N_SIM) * (sd / np.sqrt(5 / 3))
                else:
                    draws[i] = seats2[i]
            seats3 = np.clip(draws, 0, r.n_seats)
            largest3 = seats3.argmax(axis=0)

        for i, b in enumerate(names):
            p2_maj = float((seats2[i] >= majority).mean())
            p2_lrg = float((largest2 == i).mean())
            p3_maj = p3_lrg = np.nan
            if seats3 is not None:
                p3_maj = float((seats3[i] >= majority).mean())
                p3_lrg = float((largest3 == i).mean())
            q5, med, q95 = np.percentile(seats2[i], [5, 50, 95]).astype(int)
            act_seats = actual.get(b, 0)
            act_maj = int(act_seats >= majority)
            act_lrg = int(act_seats == max(actual.values())) if actual else np.nan
            if mode == "loo":
                summary_rows.append({
                    "election_id": eid, "bloc": b, "alpha": alpha, "tau": tau,
                    "sigma_c": sigma_c, "sigma_state": sigma_state,
                    "base_share": round(base_bloc[b], 1),
                    "pred_share": round(pred_bloc[b], 1),
                    "poll_share": round(float(pct_polls.loc[b, "mean"]), 1)
                    if b in pct_polls.index else np.nan,
                    "poll_seats": round(float(seat_polls.loc[b, "mean"]), 0)
                    if b in seat_polls.index else np.nan,
                    "seats_p5": q5, "seats_med": med, "seats_p95": q95,
                    "p_majority": round(p2_maj, 3), "p_largest": round(p2_lrg, 3),
                    "actual_seats": act_seats})
            for qname, p2, p3, act in [("majority", p2_maj, p3_maj, act_maj),
                                       ("largest", p2_lrg, p3_lrg, act_lrg)]:
                g2 = "WATCH-FLAG" if flagged else gate_of(p2)
                if flagged:
                    gs = "WATCH-FLAG"
                elif np.isnan(p3):
                    gs = "WATCH-NOPOLL"
                elif min(p2, p3) >= GATE:
                    gs = "CALL-YES"
                elif max(p2, p3) <= 1 - GATE:
                    gs = "CALL-NO"
                else:
                    gs = "WATCH"
                c2 = cs = np.nan
                if g2 == "CALL-YES":
                    c2 = int(act == 1)
                elif g2 == "CALL-NO":
                    c2 = int(act == 0)
                if gs == "CALL-YES":
                    cs = int(act == 1)
                elif gs == "CALL-NO":
                    cs = int(act == 0)
                ledger_rows.append({
                    "election_id": eid, "state": state, "year": year, "mode": mode,
                    "bloc": b, "question": qname,
                    "p_m2": round(p2, 4),
                    "p_m3": round(p3, 4) if not np.isnan(p3) else np.nan,
                    "m3_kind": m3_kind or "", "gate_m2": g2, "m2_correct": c2,
                    "gate_strict": gs, "strict_correct": cs,
                    "actual": act, "incumbent": r.incumbent_bloc == b,
                    "quality": "manual" if len(man) else "data",
                    "sigma_state": sigma_state})

ledger = pd.DataFrame(ledger_rows)
summary = pd.DataFrame(summary_rows)
ledger.to_csv(PROC / "precision_ledger.csv", index=False)
summary.to_csv(PROC / "election_summaries.csv", index=False)

# ---------------- calibration (loo, unflagged) ----------------
cal_rows = []
d = ledger[(ledger["mode"] == "loo") & ledger.actual.notna()
           & (ledger.gate_m2 != "WATCH-FLAG")]
bins = [0, .05, .2, .4, .6, .8, .95, 1.0001]
labels = ["0-5", "5-20", "20-40", "40-60", "60-80", "80-95", "95-100"]
d = d.assign(bin=pd.cut(d.p_m2, bins, labels=labels, right=False))
for bn, g in d.groupby("bin", observed=True):
    cal_rows.append({"claimed_bin_pct": bn, "n": len(g),
                     "mean_claimed": round(g.p_m2.mean(), 3),
                     "realized_freq": round(g.actual.mean(), 3)})
cal = pd.DataFrame(cal_rows)
cal.to_csv(PROC / "calibration_table.csv", index=False)

# ---------------- console summary ----------------
for mode in ("loo", "past"):
    dm = ledger[ledger["mode"] == mode]
    print(f"\n===== mode: {mode} =====")
    for gcol, ccol, gname in [("gate_m2", "m2_correct", "M2-only"),
                              ("gate_strict", "strict_correct", "STRICT dual")]:
        for sign, lab in [("CALL-YES", "positive"), ("CALL-NO", "negative")]:
            c = dm[dm[gcol] == sign]
            n, ok = len(c), c[ccol].sum()
            print(f"  {gname:12s} {lab:8s}: {n:3d} calls, {int(ok):3d} correct "
                  f"({ok / n * 100 if n else 0:.1f}%)")
    cov = dm[dm.p_m3.notna()].election_id.nunique()
    print(f"  poll coverage: {cov} elections with M3")
print("\nCalibration (loo M2, unflagged):")
print(cal.to_string(index=False))
print("\nWrong STRICT calls:")
bad = ledger[ledger.strict_correct == 0]
print(bad[["election_id", "mode", "bloc", "question", "p_m2", "p_m3",
           "gate_strict", "actual"]].to_string(index=False) if len(bad) else "  none")
print("\nWrong M2 calls (loo):")
bad2 = ledger[(ledger.m2_correct == 0) & (ledger["mode"] == "loo")]
print(bad2[["election_id", "bloc", "question", "p_m2", "p_m3", "actual"]]
      .to_string(index=False) if len(bad2) else "  none")
