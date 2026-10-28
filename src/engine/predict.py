"""Forward prediction tool: forecast an upcoming election from a config file.

Usage:  python predict.py <forecast_id>          (reads forecasts/<id>.json)

Engine = the N=46-validated stack:
  M2  alpha-blend of last AE + last GE bloc shares (alpha from alpha_table,
      state-shock sigma = measured out-of-sample residual sd, not the naive 3.0)
  M3  final-window poll average + ledger bias correction (sigma inflated for
      unrated agencies)
  Monte Carlo on the baseline AE's constituency shares (sigma_c from sigma_table,
  tau from tau_table) -> seat distributions -> dual gate min(M2,M3) >= 0.95.

Every run writes forecasts/<id>_forecast.{json,md} and appends a SHA256-hashed,
timestamped row per question to forecasts/ledger.csv (pre-registration: rows are
append-only; a re-run gets a new timestamp, superseding but never erasing).
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from ms_lib import load_all, wide_shares  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
FDIR = ROOT / "forecasts"
N_SIM = 10_000
GATE = 0.95

def main(fid):
    cfg = json.loads((FDIR / f"{fid}.json").read_text(encoding="utf-8"))
    rng = np.random.default_rng(42)
    ae, ss, _, _ = load_all()

    alpha_t = pd.read_csv(PROC / "alpha_table.csv")
    sigma_t = pd.read_csv(PROC / "sigma_table.csv")
    tau = float(pd.read_csv(PROC / "tau_table.csv").tau_median.iloc[0])
    st = cfg["state"]
    alpha = float(alpha_t[(alpha_t.state == st) & (alpha_t.era == "post2014")].alpha_shrunk.iloc[0])
    sigma_c = float(sigma_t[sigma_t.state == st].sigma_median.iloc[0])

    w = wide_shares(ae, cfg["baseline_ae"])
    ge = ss[ss.election == cfg["ge_election"]].set_index("party").share
    base_ae = ss[ss.election == cfg["baseline_ae"]].set_index("party").share

    wmap = {"1": 1.0, "t": tau}
    blocs = list(cfg["blocs"])
    base_c, base_s, ge_s = {}, {}, {}
    for b, spec in cfg["blocs"].items():
        v = np.zeros(len(w))
        bs = 0.0
        for p, code in spec["ae_base"].items():
            wt = wmap[code]
            if p in w.columns:
                v += wt * w[p].values
            bs += wt * float(base_ae.get(p, 0.0))
        base_c[b], base_s[b] = v, bs
        ge_s[b] = sum(wmap[c] * float(ge.get(p, 0.0)) for p, c in spec["ge"].items())

    # --- M2 ---
    m2 = {b: alpha * ge_s[b] + (1 - alpha) * base_s[b] for b in blocs}

    # --- M3 ---
    polls = pd.DataFrame(cfg["polls"])
    polls["date"] = pd.to_datetime(polls.date)
    cutoff = pd.to_datetime(cfg["freeze_date"]) - pd.Timedelta(days=cfg["poll_window_days"])
    fin = polls[polls.date >= cutoff]
    corr = cfg["poll_corrections"]
    if corr.get("auto"):
        # per-state class-level corrections from the measured pollster-error
        # ledger (14_pollster_errors.py); bloc class by BJP membership
        pc_path = PROC / "pollster_corrections.csv"
        auto = {}
        if pc_path.exists():
            pc = pd.read_csv(pc_path)
            pc = pc[pc.state == st]
            for b, spec in cfg["blocs"].items():
                cls = "bjp_led" if "BJP" in spec["ae_base"] else "rival_or_third"
                row = pc[pc.bloc_class == cls]
                auto[b] = float(row.correction.iloc[0]) if len(row) else 0.0
        corr = {**auto, "rule": f"auto from pollster_corrections.csv ({st}): {auto}"}
        print(f"auto poll corrections ({st}): {auto}")
    m3 = {b: float(fin[b].dropna().mean()) + float(corr.get(b, 0.0))
          for b in blocs if b in fin.columns and fin[b].notna().any()}
    any_rated = bool(fin.get("rated", pd.Series(dtype=bool)).fillna(False).any())
    sig3 = cfg["sigma_state_m3_rated"] if any_rated else cfg["sigma_state_m3_unrated"]
    sig2 = cfg["sigma_state_m2"]

    def simulate(pred, sig_state):
        names = [b for b in blocs if b in pred]
        if not names:
            return [], {}
        seats = {b: np.zeros(N_SIM, dtype=int) for b in names}
        for s in range(N_SIM):
            mat = np.column_stack([
                base_c[b] + (pred[b] - base_s[b]) + rng.normal(0, sig_state)
                + rng.normal(0, sigma_c, len(w))
                for b in names
            ])
            win = mat.argmax(axis=1)
            for i, b in enumerate(names):
                seats[b][s] = (win == i).sum()
        return names, seats

    n2, s2 = simulate(m2, sig2)
    n3, s3 = simulate(m3, sig3)
    maj = cfg["majority"]

    # New-entrant governance flag (ported from 05_loo_retrodict after TN2026):
    # a serious contender invisible to both baseline AE and prior GE forces
    # WATCH-FLAG on every would-be CALL in this election.
    nef = cfg.get("new_entrant_flag", {})
    flag_on = bool(nef.get("triggered", False))

    def stats(names, seats):
        if not names:
            return {}
        order = np.column_stack([seats[b] for b in names])
        largest = order.argmax(axis=1)
        out = {}
        for i, b in enumerate(names):
            q = np.percentile(seats[b], [5, 50, 95]).astype(int)
            out[b] = {
                "p5": int(q[0]), "med": int(q[1]), "p95": int(q[2]),
                "p_majority": round(float((seats[b] >= maj).mean()), 4),
                "p_largest": round(float((largest == i).mean()), 4),
            }
        return out

    r2, r3 = stats(n2, s2), stats(n3, s3)

    # --- gated question set (mechanical: every bloc x {majority, largest} + config subs) ---
    questions = []
    for b in blocs:
        for kind, key in (("wins majority", "p_majority"), ("is largest", "p_largest")):
            p2 = r2.get(b, {}).get(key)
            p3 = r3.get(b, {}).get(key)
            pg = None if (p2 is None or p3 is None) else min(p2, p3)
            if pg is None:
                verdict = "WATCH-NOPOLL"
            elif pg >= GATE:
                verdict = "CALL-YES"
            elif max(p2, p3) <= 1 - GATE and min(p2, p3) is not None and (1 - max(p2, p3)) >= GATE:
                verdict = "CALL-NO"
            else:
                verdict = "WATCH"
            if flag_on and verdict.startswith("CALL"):
                verdict = "WATCH-FLAG"
            questions.append({"question": f"{b} {kind}", "p_m2": p2, "p_m3": p3,
                              "p_gate": pg, "verdict": verdict})

    def sub_p(seats, names, sq):
        if sq["bloc"] == "__top2__":
            order = np.column_stack([seats[b] for b in names])
            largest = order.argmax(axis=1)
            idx = [names.index(b) for b in sq["threshold"] if b in names]
            return float(np.isin(largest, idx).mean())
        b = sq["bloc"]
        if b not in seats:
            return None
        if sq["op"] == "<":
            return float((seats[b] < sq["threshold"]).mean())
        return float((seats[b] >= sq["threshold"]).mean())

    for sq in cfg.get("sub_questions", []):
        p2 = sub_p(s2, n2, sq)
        p3 = sub_p(s3, n3, sq)
        pg = None if (p2 is None or p3 is None) else min(p2, p3)
        if pg is None:
            verdict = "WATCH-NOPOLL"
        elif pg >= GATE:
            verdict = "CALL-YES"
        elif (1 - max(p2, p3)) >= GATE:
            verdict = "CALL-NO"
        else:
            verdict = "WATCH"
        if verdict.startswith("CALL") and (
            flag_on
            or (sq["bloc"] == "__top2__"
                and any(base_s.get(b, 0.0) < 1.0 for b in blocs))
        ):
            # flag, or a top-2 certainty resting on a zero-baseline bloc
            # (TN2026 lesson: that certainty is model closure, not evidence)
            verdict = "WATCH-FLAG"
        questions.append({"question": sq["q"], "p_m2": None if p2 is None else round(p2, 4),
                          "p_m3": None if p3 is None else round(p3, 4),
                          "p_gate": None if pg is None else round(pg, 4), "verdict": verdict})

    result = {
        "forecast_id": fid, "title": cfg["title"], "freeze_date": cfg["freeze_date"],
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": {"alpha": alpha, "sigma_c": sigma_c, "tau": tau,
                   "sigma_state_m2": sig2, "sigma_state_m3": sig3,
                   "poll_agencies_rated": any_rated, "n_sim": N_SIM, "seed": 42},
        "state_shares": {"m2_pred": {k: round(v, 2) for k, v in m2.items()},
                         "m3_pred": {k: round(v, 2) for k, v in m3.items()},
                         "ge": {k: round(v, 2) for k, v in ge_s.items()},
                         "baseline": {k: round(v, 2) for k, v in base_s.items()}},
        "seats_m2": r2, "seats_m3": r3, "questions": questions,
        "new_entrant_flag": nef,
        "quality_flags": cfg["quality_flags"], "tripwires": cfg["tripwires"],
        "resolution": cfg.get("resolution"),
    }
    out_json = FDIR / f"{fid}_forecast.json"
    payload = json.dumps(result, indent=1, sort_keys=True)
    out_json.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode()).hexdigest()

    # --- append-only pre-registration ledger ---
    ledger = FDIR / "ledger.csv"
    res_src = (cfg.get("resolution") or {}).get("source", "")
    rows = []
    for q in questions:
        rows.append({"forecast_id": fid, "freeze_date": cfg["freeze_date"],
                     "run_at_utc": result["run_at_utc"], "question": q["question"],
                     "p_m2": q["p_m2"], "p_m3": q["p_m3"], "p_gate": q["p_gate"],
                     "verdict": q["verdict"], "forecast_sha256": digest,
                     "resolved": "", "outcome": "", "correct": "",
                     "resolution_source": res_src})
    pd.DataFrame(rows).to_csv(ledger, mode="a", header=not ledger.exists(),
                              index=False)

    # --- markdown ---
    md = [f"# Forecast: {cfg['title']}",
          f"\n**Freeze:** {cfg['freeze_date']} · **Run:** {result['run_at_utc']} · "
          f"**SHA256:** `{digest[:16]}…` (full hash in ledger.csv)\n",
          f"Params: α={alpha} σ_c={sigma_c} τ={tau} σ_state M2={sig2} "
          f"M3={sig3} ({'rated' if any_rated else 'UNRATED agencies'})\n",
          "## Predicted state vote shares (pts)\n",
          "| bloc | baseline (reblocked) | GE | M2 | M3 (corrected polls) |",
          "|---|---|---|---|---|"]
    for b in blocs:
        md.append(f"| {b} | {base_s[b]:.1f} | {ge_s[b]:.1f} | {m2[b]:.1f} | "
                  f"{m3.get(b, float('nan')):.1f} |")
    md += ["\n## Seat simulations (10k runs)\n",
           "| bloc | M2 5–95% (med) | P_maj | P_largest | M3 5–95% (med) | P_maj | P_largest |",
           "|---|---|---|---|---|---|---|"]
    for b in blocs:
        a, c = r2.get(b), r3.get(b)
        md.append(f"| {b} | {a['p5']}–{a['p95']} ({a['med']}) | {a['p_majority']:.2f} | "
                  f"{a['p_largest']:.2f} | {c['p5']}–{c['p95']} ({c['med']}) | "
                  f"{c['p_majority']:.2f} | {c['p_largest']:.2f} |" if a and c else f"| {b} | — |")
    md += ["\n## Gate verdicts (dual, min(M2,M3) ≥ 0.95)\n",
           "| question | P M2 | P M3 | gate | verdict |", "|---|---|---|---|---|"]
    for q in questions:
        f = lambda x: "—" if x is None else f"{x:.3f}"
        md.append(f"| {q['question']} | {f(q['p_m2'])} | {f(q['p_m3'])} | "
                  f"{f(q['p_gate'])} | **{q['verdict']}** |")
    md += ["\n## Quality flags\n"] + [f"- {x}" for x in cfg["quality_flags"]]
    md += ["\n## Tripwires (re-run on trigger)\n"] + [
        f"- **{t['watch']}** → {t['effect']}" for t in cfg["tripwires"]]
    (FDIR / f"{fid}_forecast.md").write_text("\n".join(md), encoding="utf-8")

    print(f"written: {out_json.name}, {fid}_forecast.md; ledger +{len(rows)} rows")
    print(f"sha256: {digest}")
    for q in questions:
        print(f"  {q['question']:32s} gate={q['p_gate']} -> {q['verdict']}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "UP2027")
