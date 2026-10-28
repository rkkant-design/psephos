"""UP retrodiction pilot: predict 2017 and 2022 from pre-election data only.

Ensemble members:
  M1 Fundamentals  - anti-incumbency base rate (no polls, no GE)
  M2 LS-blend      - alpha*GE_share + (1-alpha)*lastAE_share, alpha fit on prior cycle
  M3 Polls         - final-window poll average; bias-corrected for 2022 using 2017 errors
                     (no correction available for 2017 -> flagged as data gap)

Seat conversion: constituency-level Monte Carlo on the baseline election's shares
with per-bloc state shocks + per-AC noise. Gate: CALL iff P(outcome) >= 0.95 in
BOTH M2- and M3-driven simulations (M1 reported as a directional prior).

All parameters fixed ex-ante and printed; see OVERFITTING NOTE in the report.
"""
from pathlib import Path
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

N_SIM = 10_000
SIGMA_STATE = 3.0   # state-level per-bloc shock (pts), ~ historical poll-share error
TAU = 0.75          # alliance vote-transfer efficiency (prior; measured later)
MAJORITY = 202

ae2012 = pd.read_csv(PROC / "ae2012.csv")
ae2017 = pd.read_csv(PROC / "ae2017.csv")
ae2022 = pd.read_csv(PROC / "ae2022.csv")
state = pd.read_csv(PROC / "state_shares.csv").set_index(["election", "party"]).share
polls = pd.read_csv(RAW / "polls_up.csv")

def shares_wide(df):
    w = df.pivot_table(index="const", columns="party", values="share", aggfunc="sum").fillna(0)
    return w

def state_share(el, p):
    try:
        return float(state.loc[(el, p)])
    except KeyError:
        return 0.0

# ---------- measured quantities ----------
# sigma_c: dispersion of constituency-level swing around state swing, 2012->2017 (BJP)
w12, w17 = shares_wide(ae2012), shares_wide(ae2017)
common = w12.index.intersection(w17.index)
sw = (w17.loc[common, "BJP"] - w12.loc[common, "BJP"]) if "BJP" in w12 else None
SIGMA_C_MEASURED = float(sw.std())
SIGMA_C_ASSUMED = 6.0  # used for 2017 retrodiction (no post-delim prior cycle to measure)

# alpha for M2, fit per retrodiction on the PRIOR cycle
def fit_alpha(ge_el, ae_prev_el, ae_target_el, parties):
    best, best_err = 0.5, 1e9
    for a in np.linspace(0, 1, 21):
        err = 0.0
        for p in parties:
            pred = a * state_share(ge_el, p) + (1 - a) * state_share(ae_prev_el, p)
            err += (pred - state_share(ae_target_el, p)) ** 2
        if err < best_err:
            best, best_err = a, err
    return best

# 2007 AE state shares (pre-delimitation; aggregate only) for alpha-fitting of 2017
dm = pd.read_csv(RAW / "datameet_assembly.csv", encoding="latin-1", low_memory=False)
dm07 = dm[(dm.ST_NAME == "Uttar Pradesh") & (dm.YEAR.astype(str) == "2007")].copy()
dm07["VOTES"] = pd.to_numeric(dm07.VOTES, errors="coerce").fillna(0)
tot07 = dm07.VOTES.sum()
for p_raw, p in [("SP", "SP"), ("BSP", "BSP"), ("BJP", "BJP"), ("INC", "INC")]:
    v = 100 * dm07[dm07.PARTY == p_raw].VOTES.sum() / tot07
    state.loc[("AE2007", p)] = v

PARTIES = ["BJP", "SP", "BSP", "INC"]

# ---------- simulation ----------
def simulate(baseline_wide, blocs, pred_state_share, base_state_share, sigma_c, label):
    """blocs: {bloc_name: {party: transfer_weight}} on baseline columns.
    pred/base_state_share: {bloc: pts}. Returns seat count array per bloc."""
    acs = baseline_wide.index
    base = {}
    for b, comp in blocs.items():
        v = np.zeros(len(acs))
        for p, wgt in comp.items():
            if p in baseline_wide.columns:
                v += wgt * baseline_wide[p].values
        base[b] = v
    names = list(blocs)
    seats = {b: np.zeros(N_SIM, dtype=int) for b in names}
    for s in range(N_SIM):
        shocks = {b: rng.normal(0, SIGMA_STATE) for b in names}
        mat = np.column_stack([
            base[b] + (pred_state_share[b] - base_state_share[b]) + shocks[b]
            + rng.normal(0, sigma_c, len(acs))
            for b in names
        ])
        win = mat.argmax(axis=1)
        for i, b in enumerate(names):
            seats[b][s] = (win == i).sum()
    out = {}
    for b in names:
        q = np.percentile(seats[b], [5, 50, 95]).astype(int)
        out[b] = dict(p5=int(q[0]), med=int(q[1]), p95=int(q[2]),
                      p_major=float((seats[b] >= MAJORITY).mean()),
                      p_largest=float((np.column_stack([seats[x] for x in names]).argmax(axis=1)
                                       == names.index(b)).mean()))
    return out, seats

def report(title, res):
    print(f"\n--- {title} ---")
    for b, r in res.items():
        print(f"  {b:8s} seats {r['p5']:3d}-{r['p95']:3d} (med {r['med']:3d})  "
              f"P(majority)={r['p_major']:.3f}  P(largest)={r['p_largest']:.3f}")

print("=" * 70)
print("RETRODICTION A: UP 2017 (freeze ~Feb 2017; baseline AE2012)")
print("=" * 70)

alpha17 = fit_alpha("GE2009", "AE2007", "AE2012", PARTIES)
print(f"alpha (fit on GE2009/AE2007 -> AE2012): {alpha17:.2f}")
print(f"sigma_c: {SIGMA_C_ASSUMED} (assumed; no measurable post-delim prior cycle)")

blocs17 = {
    "BJP+": {"BJP": 1.0, "AD": TAU},
    "SP+INC": {"SP": 1.0, "INC": TAU},
    "BSP": {"BSP": 1.0},
}
base17 = {b: sum(state_share("AE2012", p) * w for p, w in c.items())
          for b, c in blocs17.items()}

# M1 fundamentals
print("\nM1 Fundamentals: incumbent (SP) retention base rate since 1989: 0/6 -> "
      "P(SP+ majority) ~ 0.11 (Laplace). Strongest challenger by last GE: BJP (42.2%).")

# M2
m2_pred17 = {
    "BJP+": alpha17 * (state_share("GE2014", "BJP") + TAU * state_share("GE2014", "AD"))
    + (1 - alpha17) * base17["BJP+"],
    "SP+INC": alpha17 * (state_share("GE2014", "SP") + TAU * state_share("GE2014", "INC"))
    + (1 - alpha17) * base17["SP+INC"],
    "BSP": alpha17 * state_share("GE2014", "BSP") + (1 - alpha17) * base17["BSP"],
}
print("M2 predicted state shares:", {k: round(v, 1) for k, v in m2_pred17.items()})
res2_17, _ = simulate(w12, blocs17, m2_pred17, base17, SIGMA_C_ASSUMED, "M2")
report("2017 M2 (LS-blend) simulation", res2_17)

# M3 polls: final-window average (Dec 2016 - Jan 2017), vote shares where given
p17 = polls[(polls.election == 2017) & (polls.date >= "2016-12-01")]
vs = p17[["bjp_vs", "sp_vs", "bsp_vs"]].mean()
m3_pred17 = {"BJP+": float(vs.bjp_vs), "SP+INC": float(vs.sp_vs), "BSP": float(vs.bsp_vs)}
print("\nM3 poll-average state shares (UNCORRECTED - no prior-poll ledger available):",
      {k: round(v, 1) for k, v in m3_pred17.items()})
res3_17, _ = simulate(w12, blocs17, m3_pred17, base17, SIGMA_C_ASSUMED, "M3")
report("2017 M3 (polls) simulation", res3_17)

print("\nGATE 2017:")
for outcome in ["BJP+ majority", "BJP+ largest"]:
    key = "p_major" if "majority" in outcome else "p_largest"
    p2, p3 = res2_17["BJP+"][key], res3_17["BJP+"][key]
    call = "CALL" if min(p2, p3) >= 0.95 else "WATCH"
    print(f"  {outcome:16s} M2={p2:.3f} M3={p3:.3f} -> {call}")
print("  M1 prior agrees direction (anti-incumbent, BJP strongest challenger).")
print("  ACTUAL: BJP+ 325 (BJP 312), SP+INC 54, BSP 19")

print()
print("=" * 70)
print("RETRODICTION B: UP 2022 (freeze ~Jan 2022; baseline AE2017)")
print("=" * 70)

alpha22 = fit_alpha("GE2014", "AE2012", "AE2017", PARTIES)
print(f"alpha (fit on GE2014/AE2012 -> AE2017): {alpha22:.2f}")
print(f"sigma_c (measured 2012->2017 BJP swing dispersion): {SIGMA_C_MEASURED:.1f}")

# 2022 blocs ON 2017 BASELINE: SBSP switched BJP->SP; RLD with SP; AD+NISHAD with BJP
blocs22 = {
    "BJP+": {"BJP": 1.0, "AD": TAU, "NISHAD": TAU},
    "SP+": {"SP": 1.0, "RLD": TAU, "SBSP": TAU},
    "BSP": {"BSP": 1.0},
    "INC": {"INC": 1.0},
}
base22 = {b: sum(state_share("AE2017", p) * w for p, w in c.items())
          for b, c in blocs22.items()}

print("\nM1 Fundamentals: incumbent (BJP) retention base rate since 1989: 0/7 -> "
      "P(BJP+ majority) ~ 0.10. NOTE: pattern-validity flag - DBT-welfare era, "
      "2019 GE 49.6% for BJP contradicts the rotation prior.")

m2_pred22 = {
    "BJP+": alpha22 * (state_share("GE2019", "BJP") + TAU * state_share("GE2019", "AD"))
    + (1 - alpha22) * base22["BJP+"],
    "SP+": alpha22 * (state_share("GE2019", "SP") + TAU * state_share("GE2019", "RLD"))
    + (1 - alpha22) * base22["SP+"],
    "BSP": alpha22 * state_share("GE2019", "BSP") + (1 - alpha22) * base22["BSP"],
    "INC": alpha22 * state_share("GE2019", "INC") + (1 - alpha22) * base22["INC"],
}
print("M2 predicted state shares:", {k: round(v, 1) for k, v in m2_pred22.items()})
res2_22, _ = simulate(w17, blocs22, m2_pred22, base22, SIGMA_C_MEASURED, "M2")
report("2022 M2 (LS-blend) simulation", res2_22)

# M3 polls with bias correction learned from 2017:
# 2017 final-poll vote-share error: BJP actual 39.7 vs polled ~31.9 -> +7.8 under-estimate
p17f = polls[(polls.election == 2017) & (polls.date >= "2016-12-01")]
err_bjp = 39.67 - float(p17f.bjp_vs.mean())
err_sp = 28.07 - float(p17f.sp_vs.mean())   # SP+INC combined actual
err_bsp = 22.23 - float(p17f.bsp_vs.mean())
print(f"\n2017 poll-error ledger (actual - polled): BJP {err_bjp:+.1f}, "
      f"SP-bloc {err_sp:+.1f}, BSP {err_bsp:+.1f}")
p22 = polls[(polls.election == 2022) & (polls.date >= "2021-11-01")]
m3_raw22 = {"BJP+": float(p22.bjp_vs.mean()), "SP+": float(p22.sp_vs.mean()),
            "BSP": float(p22.bsp_vs.mean()), "INC": 5.0}
# apply HALF the 2017 error as correction (shrinkage: one observation only)
m3_pred22 = {"BJP+": m3_raw22["BJP+"] + err_bjp / 2, "SP+": m3_raw22["SP+"] + err_sp / 2,
             "BSP": m3_raw22["BSP"] + err_bsp / 2, "INC": 5.0}
print("M3 raw poll avg (Nov21-Jan22):", {k: round(v, 1) for k, v in m3_raw22.items()})
print("M3 bias-corrected (0.5x 2017 error):", {k: round(v, 1) for k, v in m3_pred22.items()})
res3_22, _ = simulate(w17, blocs22, m3_pred22, base22, SIGMA_C_MEASURED, "M3")
report("2022 M3 (corrected polls) simulation", res3_22)

print("\nGATE 2022:")
for outcome in ["BJP+ majority", "BJP+ largest"]:
    key = "p_major" if "majority" in outcome else "p_largest"
    p2, p3 = res2_22["BJP+"][key], res3_22["BJP+"][key]
    call = "CALL" if min(p2, p3) >= 0.95 else "WATCH"
    print(f"  {outcome:16s} M2={p2:.3f} M3={p3:.3f} -> {call}")
print("  M1 prior DISAGREES (rotation says BJP out) -> pattern-validity question is live.")
print("  ACTUAL: BJP+ 273 (BJP 255), SP+ 125, BSP 1, INC 2")

# decomposed sub-questions, 2022
print("\nSub-question gate (2022, M3 sims):")
_, seats3 = simulate(w17, blocs22, m3_pred22, base22, SIGMA_C_MEASURED, "M3b")
subq = {
    "BSP under 20 seats": (seats3["BSP"] < 20).mean(),
    "INC under 15 seats": (seats3["INC"] < 15).mean(),
    "SP+ gains 40+ seats (>=87)": (seats3["SP+"] >= 87).mean(),
    "Winner in {BJP+, SP+}": 1.0 - ((seats3["BSP"] + seats3["INC"])
                                    > (seats3["BJP+"] + seats3["SP+"])).mean(),
}
for q, p in subq.items():
    print(f"  {q:28s} P={p:.3f} -> {'CALL' if p >= 0.95 else 'WATCH'}")
