"""World prediction engine: any-event forecasts with the same discipline as the
India election engine — two independent instruments, dual gate at 0.95,
append-only SHA-hashed pre-registration ledger.

Instruments per domain (the recipe pattern):
  M_market   : de-vigged betting/prediction-market implied probabilities
  M_model    : a domain structural model (adapters below), independent of the market
  M_research : OPTIONAL third instrument - LLM research-forecaster probabilities
               committed by scripts/m_research.py to
               forecasts/research/<ID>_research.json. Opted in per config with
               "research": true. Research never sees market prices (enforced at
               commit); that independence is what makes it a third witness.

Usage: python world_predict.py <ID>   (reads forecasts/world/<ID>.json)

Gate rules:
  Two instruments on a question (the original dual gate): CALL-YES/CALL-NO only
  when BOTH clear 0.95 the same way; p_gate = min of the two.
  Three instruments (config opted into research AND all three priced the
  question) - the 2-of-3 gate: CALL-YES when at least two instruments are
  >= 0.95 AND no instrument contradicts by more than 0.20 the other way
  (i.e. min >= 0.80); CALL-NO is the mirror (two <= 0.05 and max <= 0.20);
  p_gate = median of the three (the certifying statistic: the 2nd witness).
  Fewer than two instruments: WATCH-1INST - the engine never certifies on one.

Ledger note: world_ledger.csv's column set is frozen by the append-only law, so
p_research is NOT a ledger column here. It lives in forecasts/research_ledger.csv
(scored by scripts/score.py) and inside this script's hashed forecast payload,
which the row's forecast_sha256 covers - fully auditable, nothing restated.
"""
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WDIR = ROOT / "forecasts" / "world"
LEDGER = ROOT / "forecasts" / "world_ledger.csv"
GATE = 0.95
CONTRA = 0.20  # 2-of-3 gate: a third instrument giving the other side > 0.20 vetoes the CALL
N_SIM = 10_000
rng = np.random.default_rng(42)

def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))

# ---------------- adapters: return {question_text: p_model} ----------------

def us_house(cfg):
    m = cfg["model"]
    p_dem = phi((m["generic_ballot_margin"] - m["tipping_point"]) / m["sigma"])
    out = {}
    for q in cfg["questions"]:
        if q["model"] == "house_dem":
            out[q["q"]] = p_dem
        elif q["model"] == "house_rep":
            out[q["q"]] = 1 - p_dem
        elif q["model"] == "senate_dem" and m.get("senate_model") is not None:
            # race-level correlated Monte Carlo roll-up (scripts/usmid_races.py),
            # pasted into the config with a dated note - the Senate question's
            # structural second instrument
            out[q["q"]] = m["senate_model"]
        else:
            out[q["q"]] = None
    return out

def league_sim(cfg):
    teams = cfg["model"]["teams"]
    names = [t["team"] for t in teams]
    played = np.array([t["p"] for t in teams], float)
    pts = np.array([t["pts"] for t in teams], float)
    gd = np.array([t["gd"] for t in teams], float)
    total_games = 38
    league_avg = 1.37
    k = 12.0
    lam = played / (played + k)
    exp_ppg = lam * (pts / played) + (1 - lam) * league_avg
    p_draw = 0.24
    p_win = np.clip((exp_ppg - p_draw) / 3.0, 0.05, 0.75)
    remaining = (total_games - played).astype(int)
    champ = np.zeros(len(names))
    for _ in range(N_SIM):
        u = rng.random((len(names), remaining[0]))
        wins = (u < p_win[:, None]).sum(axis=1)
        draws = ((u >= p_win[:, None]) & (u < (p_win + p_draw)[:, None])).sum(axis=1)
        final = pts + 3 * wins + draws + gd / 1000 + rng.normal(0, 1e-6, len(names))
        champ[final.argmax()] += 1
    champ /= N_SIM
    probs = dict(zip(names, champ))
    out = {}
    for q in cfg["questions"]:
        ent = q["entity"]
        out[q["q"]] = sum(probs.get(e, 0) for e in ent) if isinstance(ent, list) else probs.get(ent, 0)
    return out, probs

def ratings_tournament(cfg):
    m = cfg["model"]
    tau = 8.0
    r = {t: v + m.get("host_bonus", {}).get(t, 0) for t, v in m["ratings"].items()}
    w = {t: math.exp(v / tau) for t, v in r.items()}
    z = sum(w.values())
    probs = {t: v / z for t, v in w.items()}
    out = {}
    for q in cfg["questions"]:
        ent = q["entity"]
        out[q["q"]] = sum(probs.get(e, 0) for e in ent) if isinstance(ent, list) else probs.get(ent, 0)
    return out, probs

# ---------------- market: de-vigged implied probabilities ----------------

def market_probs(cfg):
    mk = cfg["market"]
    if cfg["adapter"] == "us_house":
        probs = {"house_dem": mk["house_dem"], "house_rep": 1 - mk["house_dem"],
                 "senate_dem": mk["senate_dem"]}
        out = {}
        for q in cfg["questions"]:
            out[q["q"]] = probs.get(q["market"])
        return out, probs
    entity_p = {}
    if "odds" in mk:
        imp = {t: 1 / o for t, o in mk["odds"].items()}
        total = sum(imp.values()) + mk.get("others_implied", 0)
        entity_p = {t: v / total for t, v in imp.items()}
    if "bookmaker_odds" in mk:
        imp = {t: 1 / o for t, o in mk["bookmaker_odds"].items()}
        book_total = sum(imp.values()) / 0.80  # assume ~80% of total prob is listed
        book = {t: v / book_total for t, v in imp.items()}
        mani = mk.get("manifold", {})
        entity_p = {t: (book.get(t, 0) + mani.get(t, book.get(t, 0))) / 2
                    for t in set(book) | set(mani)}
    out = {}
    for q in cfg["questions"]:
        ent = q["entity"]
        out[q["q"]] = (sum(entity_p.get(e, 0) for e in ent) if isinstance(ent, list)
                       else entity_p.get(ent))
    return out, entity_p

# ---------------- research instrument ----------------

def research_probs(cfg, fid):
    """Committed M_research probabilities, if the config opts in."""
    if not cfg.get("research"):
        return {}, None
    rf = ROOT / "forecasts" / "research" / f"{fid}_research.json"
    if not rf.exists():
        sys.exit(f"{fid}: config has \"research\": true but {rf} is missing - "
                 f"run scripts/m_research.py commit on a dossier first")
    art = json.loads(rf.read_text(encoding="utf-8"))
    return {x["q"]: x["p_research"] for x in art["questions"]}, art.get("dossier_sha256")


def gate_verdict(ps):
    """ps: the instrument probabilities that exist on this question.
    Returns (verdict, p_gate). Dual rule for 2, 2-of-3 rule for 3."""
    if len(ps) < 2:
        return "WATCH-1INST", None
    if len(ps) == 2:
        pg = min(ps)
        if pg >= GATE:
            return "CALL-YES", pg
        if (1 - max(ps)) >= GATE:
            return "CALL-NO", pg
        return "WATCH", pg
    pg = sorted(ps)[1]  # median of three: the second witness
    if sum(p >= GATE for p in ps) >= 2 and min(ps) >= 1 - CONTRA:
        return "CALL-YES", pg
    if sum(p <= 1 - GATE for p in ps) >= 2 and max(ps) <= CONTRA:
        return "CALL-NO", pg
    return "WATCH", pg


# ---------------- gate + ledger ----------------

def main(fid):
    cfg = json.loads((WDIR / f"{fid}.json").read_text(encoding="utf-8"))
    adapter = {"us_house": us_house, "league_sim": league_sim,
               "ratings_tournament": ratings_tournament}[cfg["adapter"]]
    res = adapter(cfg)
    model_p, entity_model = (res, {}) if isinstance(res, dict) else res
    mkt_p, entity_mkt = market_probs(cfg)
    rsch_p, rsch_sha = research_probs(cfg, fid)

    questions = []
    for q in cfg["questions"]:
        pm = mkt_p.get(q["q"])
        pd_ = model_p.get(q["q"])
        pr = rsch_p.get(q["q"]) if rsch_p else None
        avail = [p for p in (pm, pd_, pr) if p is not None]
        verdict, pg = gate_verdict(avail)
        questions.append({"q": q["q"], "p_market": None if pm is None else round(pm, 4),
                          "p_model": None if pd_ is None else round(pd_, 4),
                          "p_research": None if pr is None else round(pr, 4),
                          "p_gate": None if pg is None else round(pg, 4), "verdict": verdict})

    result = {
        "forecast_id": fid, "title": cfg["title"], "domain": cfg["domain"],
        "freeze_date": cfg["freeze_date"], "resolve_date": cfg.get("resolve_date"),
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "instruments": {"market_source": cfg["market"]["source"],
                        "model_note": cfg["model"].get("note") or cfg["model"].get("margin_source"),
                        "research_sha256": rsch_sha},
        "gate_rule": ("2-of-3: CALL when >=2 instruments clear 0.95 the same way and none "
                      "contradicts by >0.20 the other way; p_gate = median"
                      if rsch_p else "dual: both instruments must clear 0.95; p_gate = min"),
        "entity_probs": {"market": {k: round(v, 4) for k, v in entity_mkt.items() if isinstance(v, float)},
                         "model": {k: round(v, 4) for k, v in entity_model.items()}},
        "questions": questions,
        "quality_flags": cfg["quality_flags"], "tripwires": cfg["tripwires"],
        "resolution": cfg.get("resolution"),
    }
    payload = json.dumps(result, indent=1, sort_keys=True)
    (WDIR / f"{fid}_forecast.json").write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode()).hexdigest()

    res_src = (cfg.get("resolution") or {}).get("source", "")
    rows = [{"forecast_id": fid, "domain": cfg["domain"], "freeze_date": cfg["freeze_date"],
             "resolve_date": cfg.get("resolve_date"), "run_at_utc": result["run_at_utc"],
             "question": x["q"], "p_market": x["p_market"], "p_model": x["p_model"],
             "p_gate": x["p_gate"], "verdict": x["verdict"], "forecast_sha256": digest,
             "resolved": "", "outcome": "", "correct": "",
             "resolution_source": res_src} for x in questions]
    pd.DataFrame(rows).to_csv(LEDGER, mode="a", header=not LEDGER.exists(), index=False)

    print(f"{fid}: sha256 {digest}")
    for x in questions:
        extra = f" research={x['p_research']}" if x.get("p_research") is not None else ""
        print(f"  {x['q']:46s} market={x['p_market']} model={x['p_model']}{extra} -> {x['verdict']}")

if __name__ == "__main__":
    main(sys.argv[1])
