"""Scoring layer: proper scores for every resolved probability the engine has
ever pre-registered — WATCH rows included, not just CALLs. Hit-rate on CALLs is
gameable (abstain except on gimmes); Brier/log on everything is not.

Inputs  : forecasts/ledger.csv (India, instruments M2/M3),
          forecasts/world_ledger.csv (instruments model/market),
          forecasts/matches_ledger.csv (EPL fixtures, three-way model probs),
          forecasts/research_ledger.csv (M_research, instrument research -
          the calibrated p_research is the scored number; p_raw is kept in
          the ledger for the calibration tuner, not scored here).
Rule    : latest run per (forecast_id, question) — a re-run supersedes by
          timestamp, same convention as the app. Only rows with a filled
          `resolved` date and a usable outcome are scored.
Outputs : data/processed/scores.csv          (one row per scored probability)
          data/processed/scores_summary.json (block the app displays)

Scores (binary rows, one per instrument that existed on the question):
  brier = (p - o)^2            in [0,1], lower is better, 0.25 = coin flip
  log   = ln(p_realized)        p clipped to [1e-4, 1-1e-4]; a pre-registered
                                0.0 that happens eats the full -9.21 penalty.
Match rows are three-way: brier = sum_i (p_i - o_i)^2 in [0,2] (coin ref 0.667),
log = ln(p of realized outcome). Reported separately — never averaged into the
binary pool (different scale).

Calibration: claimed-probability bins vs realized frequency, pooled over all
binary scored probabilities (match W/D/A events enter as three binary events
for calibration only, flagged, to avoid double-counting in Brier means).

Skill: world-ledger questions where BOTH instruments existed and resolved —
mean Brier of p_model vs p_market on the identical question set. n=0 until the
first world event resolves; the table exists so the comparison is locked in
before anyone sees which instrument it flatters.

Match skill (from MW9 / model v2): matches_ledger rows carry de-vigged
bookmaker probabilities (market_ph/pd/pa, source + date recorded at freeze)
alongside the model's. Each resolved matchweek with market columns gets a
model-vs-market 3-way-Brier line — the weekly skill score. The market is
benchmark instrument #2: the published pick stays the model's. If after >= 5
matchweeks the market consistently wins, this report SAYS so (recommendation
line); switching or blending the pick source is a user decision, never made
here. Market rows also land in scores.csv (ledger=matches, instrument=market)
but are excluded from the model's Brier means and from calibration (the
calibration table audits the engine's own claims, not the books').
"""
import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FDIR = ROOT / "forecasts"
PROC = ROOT / "data" / "processed"
EPS = 1e-4

BINS = [0.0, 0.05, 0.20, 0.40, 0.60, 0.80, 0.95, 1.0000001]
BIN_LABELS = ["0-5%", "5-20%", "20-40%", "40-60%", "60-80%", "80-95%", "95-100%"]


def _latest(df):
    return df.sort_values("run_at_utc").drop_duplicates(["forecast_id", "question"], keep="last")


def _clean(df):
    for c in ("resolved", "outcome", "correct"):
        df[c] = df[c].fillna("").astype(str).replace("nan", "")
    return df


def binary_rows(path, instruments, ledger_name):
    """Yield one scored row per (resolved question, existing instrument)."""
    if not path.exists():
        return []
    df = _clean(_latest(pd.read_csv(path)))
    df = df[(df.resolved.str.len() > 0) & df.outcome.isin(["YES", "NO"])]
    out = []
    for _, r in df.iterrows():
        o = 1.0 if r.outcome == "YES" else 0.0
        for col, label in instruments:
            p = r.get(col)
            if pd.isna(p):
                continue
            p = float(p)
            pc = min(max(p, EPS), 1 - EPS)
            out.append({
                "ledger": ledger_name, "forecast_id": r.forecast_id,
                "question": r.question, "freeze_date": r.freeze_date,
                "run_at_utc": r.run_at_utc, "instrument": label,
                "verdict": r.get("verdict", "INSTRUMENT"), "p": p, "outcome": int(o),
                "brier": round((p - o) ** 2, 6),
                "log_score": round(math.log(pc if o == 1 else 1 - pc), 4),
                "resolved_date": r.resolved,
            })
    return out


def match_rows(path):
    """Three-way match forecasts: one scored row per resolved match (multiclass),
    the three implied binary events for the calibration pool only, and — where
    the row carries de-vigged market probabilities (v2, MW9+) — a parallel
    market-instrument row scored on the identical outcome."""
    if not path.exists():
        return [], [], []
    df = pd.read_csv(path)
    for c in ("resolved", "outcome", "correct"):
        df[c] = df[c].fillna("").astype(str).replace("nan", "")
    df = df.sort_values("run_at_utc").drop_duplicates(["match_id"], keep="last")
    df = df[(df.resolved.str.len() > 0) & df.outcome.isin(["H", "D", "A"])]
    scored, market_scored, calib = [], [], []
    has_market = "market_ph" in df.columns
    for _, r in df.iterrows():
        probs = {"H": float(r.p_home), "D": float(r.p_draw), "A": float(r.p_away)}
        o = {k: 1.0 if r.outcome == k else 0.0 for k in probs}
        brier = sum((probs[k] - o[k]) ** 2 for k in probs)
        p_real = min(max(probs[r.outcome], EPS), 1 - EPS)
        base = {
            "ledger": "matches", "forecast_id": r.match_id,
            "question": f"{r.home} v {r.away} (MW{r.matchweek})",
            "freeze_date": r.freeze_date, "run_at_utc": r.run_at_utc,
            "resolved_date": r.resolved,
        }
        scored.append({
            **base, "instrument": "model",
            "verdict": f"SCORED-{r.get('model_version') if isinstance(r.get('model_version'), str) else 'v1'}",
            "p": round(probs[r.outcome], 4), "outcome": 1,
            "brier": round(brier, 6), "log_score": round(math.log(p_real), 4),
            "matchweek": int(r.matchweek),
        })
        if has_market and pd.notna(r.market_ph):
            mp = {"H": float(r.market_ph), "D": float(r.market_pd), "A": float(r.market_pa)}
            mb = sum((mp[k] - o[k]) ** 2 for k in mp)
            mp_real = min(max(mp[r.outcome], EPS), 1 - EPS)
            market_scored.append({
                **base, "instrument": "market", "verdict": "BENCHMARK",
                "p": round(mp[r.outcome], 4), "outcome": 1,
                "brier": round(mb, 6), "log_score": round(math.log(mp_real), 4),
                "matchweek": int(r.matchweek),
            })
        for k in probs:
            calib.append({"p": probs[k], "outcome": o[k], "source": "matches"})
    return scored, market_scored, calib


def match_skill_table(model_rows, market_rows):
    """Per-matchweek model-vs-market 3-way Brier on the matches where both
    exist — the weekly skill score. Market = benchmark instrument #2; the
    published pick stays the model's regardless of this table."""
    mk = {r["forecast_id"]: r for r in market_rows}
    paired = [(r, mk[r["forecast_id"]]) for r in model_rows if r["forecast_id"] in mk]
    if not paired:
        return {"n_matches": 0, "matchweeks": [],
                "note": "no resolved match carries market columns yet (v2 starts MW9)"}
    per_mw = {}
    for mo, ma in paired:
        per_mw.setdefault(mo["matchweek"], []).append((mo["brier"], ma["brier"]))
    weeks = []
    for mw in sorted(per_mw):
        bs = per_mw[mw]
        bm = float(np.mean([b[0] for b in bs]))
        bk = float(np.mean([b[1] for b in bs]))
        weeks.append({"matchweek": mw, "n": len(bs),
                      "brier_model": round(bm, 4), "brier_market": round(bk, 4),
                      "edge": round(bk - bm, 4),
                      "winner": "model" if bm < bk else ("market" if bk < bm else "tie")})
    all_b = [b for bs in per_mw.values() for b in bs]
    bm_all = float(np.mean([b[0] for b in all_b]))
    bk_all = float(np.mean([b[1] for b in all_b]))
    out = {"n_matches": len(all_b), "n_matchweeks": len(weeks),
           "brier_model": round(bm_all, 4), "brier_market": round(bk_all, 4),
           "edge": round(bk_all - bm_all, 4), "matchweeks": weeks,
           "note": "3-way Brier (0-2 scale) on identical matches; edge > 0 means the model beats the de-vigged market"}
    market_wins = sum(1 for w in weeks if w["winner"] == "market")
    if len(weeks) >= 5 and market_wins > len(weeks) / 2 and out["edge"] < 0:
        out["recommendation"] = ("market has beaten the model in most matchweeks over >= 5 weeks - "
                                 "consider blending model and market for the published pick "
                                 "(USER decision; pick source unchanged until then)")
    return out


def calibration_table(pool):
    """pool: list of {p, outcome} dicts (binary events)."""
    if not pool:
        return []
    df = pd.DataFrame(pool)
    df["bin"] = pd.cut(df.p, BINS, labels=BIN_LABELS, right=False, include_lowest=True)
    rows = []
    for lab in BIN_LABELS:
        g = df[df.bin == lab]
        if not len(g):
            rows.append({"bin": lab, "n": 0, "claimed": None, "realized": None})
            continue
        rows.append({"bin": lab, "n": int(len(g)),
                     "claimed": round(float(g.p.mean()), 3),
                     "realized": round(float(g.outcome.mean()), 3)})
    return rows


def skill_table(world_path, research_path=None):
    """Model-vs-market Brier on world questions where both instruments resolved.
    When the research ledger covers the same (forecast_id, question), a third
    column scores M_research on the identical set - outcome taken from the
    world ledger's resolution, so all instruments face the same truth."""
    empty = {"n_questions": 0, "brier_model": None, "brier_market": None,
             "edge": None, "note": "no world question with both instruments has resolved yet"}
    if not world_path.exists():
        return empty
    df = _clean(_latest(pd.read_csv(world_path)))
    df = df[(df.resolved.str.len() > 0) & df.outcome.isin(["YES", "NO"])
            & df.p_model.notna() & df.p_market.notna()]
    if not len(df):
        return empty
    o = (df.outcome == "YES").astype(float)
    bm = float(((df.p_model - o) ** 2).mean())
    bk = float(((df.p_market - o) ** 2).mean())
    out = {"n_questions": int(len(df)), "brier_model": round(bm, 4),
           "brier_market": round(bk, 4), "edge": round(bk - bm, 4),
           "note": "edge > 0 means the structural model beats the market on identical questions"}
    if research_path is not None and research_path.exists():
        rl = (pd.read_csv(research_path).sort_values("run_at_utc")
                .drop_duplicates(["forecast_id", "question"], keep="last")
                .set_index(["forecast_id", "question"]).p_research)
        joined = df.set_index(["forecast_id", "question"])
        common = joined.index.intersection(rl.index)
        if len(common):
            sub = joined.loc[common]
            oc = (sub.outcome == "YES").astype(float)
            out["n_with_research"] = int(len(common))
            out["brier_research_common"] = round(float(((rl.loc[common] - oc) ** 2).mean()), 4)
            out["brier_market_common"] = round(float(((sub.p_market - oc) ** 2).mean()), 4)
            out["brier_model_common"] = round(float(((sub.p_model - oc) ** 2).mean()), 4)
            out["research_note"] = "common-subset Briers: all three instruments on identical resolved questions"
    return out


def main():
    india = binary_rows(FDIR / "ledger.csv", [("p_m2", "M2"), ("p_m3", "M3")], "india")
    world = binary_rows(FDIR / "world_ledger.csv",
                        [("p_model", "model"), ("p_market", "market")], "world")
    races = binary_rows(FDIR / "world" / "usmid_races_ledger.csv",
                        [("p_model", "model"), ("p_market", "market")], "us_races")
    research = binary_rows(FDIR / "research_ledger.csv",
                           [("p_research", "research")], "research")
    matches, match_market, match_calib = match_rows(FDIR / "matches_ledger.csv")

    all_rows = india + world + races + research + matches + match_market
    out_csv = PROC / "scores.csv"
    pd.DataFrame(all_rows, columns=[
        "ledger", "forecast_id", "question", "freeze_date", "run_at_utc",
        "instrument", "verdict", "p", "outcome", "brier", "log_score",
        "resolved_date"]).to_csv(out_csv, index=False)

    binary = india + world + races + research
    calib_pool = ([{"p": r["p"], "outcome": r["outcome"], "source": r["ledger"]}
                   for r in binary] + match_calib)

    def block(rows):
        if not rows:
            return {"n": 0, "brier": None, "log": None}
        b = [r["brier"] for r in rows]
        l = [r["log_score"] for r in rows]
        return {"n": len(rows), "brier": round(float(np.mean(b)), 4),
                "log": round(float(np.mean(l)), 4)}

    def per_instrument(rows):
        out = {}
        for inst in sorted({r["instrument"] for r in rows}):
            out[inst] = block([r for r in rows if r["instrument"] == inst])
        return out

    summary = {
        "generated": str(date.today()),
        "overall_binary": block(binary),
        "india": {**block(india), "by_instrument": per_instrument(india)},
        "world": {**block(world), "by_instrument": per_instrument(world)},
        "us_races": {**block(races), "by_instrument": per_instrument(races),
                     "note": "race-level US midterm rows (usmid_races_ledger.csv); dual instruments scored per race"},
        "skill_model_vs_market_us_races": skill_table(FDIR / "world" / "usmid_races_ledger.csv"),
        "research": {**block(research),
                     "note": "M_research (LLM research-forecaster) scored on calibrated p_research; same questions may also appear under india/world via their own instruments - each instrument answers for itself"},
        "matches": {**block(matches),
                    "note": "three-way Brier, scale 0-2 (uniform ref 0.667); never pooled with binary"},
        "matches_skill_model_vs_market": match_skill_table(matches, match_market),
        "calibration": calibration_table(calib_pool),
        "skill_model_vs_market": skill_table(FDIR / "world_ledger.csv",
                                             FDIR / "research_ledger.csv"),
        "notes": [
            "Every resolved pre-registered probability is scored - WATCH rows included. Hit-rate on CALLs alone is gameable by abstention; this table is not.",
            "Binary Brier: 0 perfect, 0.25 = always saying 50%, 1 = certain and wrong. Log scores use p clipped at 1e-4.",
            "Latest run per question is the scored row (re-runs supersede by timestamp, same rule as the ledger).",
        ],
    }
    out_json = PROC / "scores_summary.json"
    out_json.write_text(json.dumps(summary, indent=1), encoding="utf-8")

    print(f"scored {len(all_rows)} rows -> {out_csv.name}")
    print(f"binary: n={summary['overall_binary']['n']} brier={summary['overall_binary']['brier']} log={summary['overall_binary']['log']}")
    print(f"india by instrument: { {k: v['brier'] for k, v in summary['india']['by_instrument'].items()} }")
    print(f"research: n={summary['research']['n']} brier={summary['research']['brier']}")
    print(f"matches: {summary['matches']}")
    ms = summary["matches_skill_model_vs_market"]
    if ms["n_matches"]:
        print(f"match skill: n={ms['n_matches']} model {ms['brier_model']} vs market {ms['brier_market']} (edge {ms['edge']})")
        for w in ms["matchweeks"]:
            print(f"  MW{w['matchweek']}: n={w['n']} model {w['brier_model']} vs market {w['brier_market']} -> {w['winner']}")
        if "recommendation" in ms:
            print(f"  RECOMMENDATION: {ms['recommendation']}")
    else:
        print(f"match skill: {ms['note']}")
    print(f"skill: {summary['skill_model_vs_market']}")
    for r in summary["calibration"]:
        print(f"  {r['bin']:>8}  n={r['n']:3d}  claimed={r['claimed']}  realized={r['realized']}")


if __name__ == "__main__":
    main()
