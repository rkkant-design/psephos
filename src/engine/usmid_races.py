"""Race-level US midterms 2026: dual-instrument forecasts for every governor
race and every Senate seat up, plus a correlated Monte Carlo roll-up that gives
the Senate-control question a structural second instrument.

Instruments per race (the world-engine recipe):
  M_market : de-vigged Polymarket per-race winner prices
             (data/usmid2026_markets.json, scripts/usmid_fetch_markets.py;
             races with no liquid market carry market=null -> WATCH-1INST)
  M_model  : structural probit below. Reads NO polls-of-the-race and NO prices;
             its only national input is the generic-ballot average.

STRUCTURAL MODEL - every parameter is a stated prior, chosen before seeing any
per-race market price, not fitted to 2026 data:

  mu_dem(race) = w_lean * rel_lean + GB + inc_adj          (Dem margin, points)
  P(Dem win)   = Phi(mu_dem / sigma_total)                  (probit, us_house style)

  rel_lean = state 2024 presidential margin - national 2024 margin (-1.5)
             (data/usmid2026_pres_margins.json, Wikipedia certified results)
  GB       = generic-ballot average from forecasts/world/USMID2026.json
             (model.generic_ballot_margin; refreshed with a dated source)
  w_lean   = 0.9 for Senate, 0.6 for governors. Stated prior: federal races
             track presidential partisanship closely; governor races much less
             (Vermont/Kansas-style crossover wins are routine).
  inc_adj  = points toward the incumbent's party when an incumbent is on the
             ballot. Senate: elected +/-3.0, appointed +/-1.0. Governor:
             elected +/-5.0, appointed/successor +/-1.5. Stated priors from
             the incumbency-advantage literature: gubernatorial incumbency
             runs roughly twice senatorial, and appointees show little of
             either. 0 for open seats.
  no-Dem rule: where no Democratic nominee is on the November ballot
             (dem_on_ballot=false in the roster: ID/SD/NE Senate), the
             structural number is meaningless for the registered question, so
             p_model = 0.01 by rule, flagged.

  Error structure (margins, points) - one SHARED national error eps_n plus
  independent per-race noise eps_r, which is what correlates the Monte Carlo:
             eps_n ~ N(0, 5.0)   national polling/environment error
             Senate:   margin = mu + 1.0*eps_n + N(0, 5.0)   -> total sd 7.07
             Governor: margin = mu + 0.7*eps_n + N(0, 10.0)  -> total sd 10.60
  Stated priors: 5 pts national error matches the historical generic-ballot
  miss; governor races load less on the national swing (0.7) and carry much
  more idiosyncratic candidate variance (10) - a candidate-blind structural
  read of a governor race is simply less informative, and the sigma says so.
  Known, accepted blindness: popular crossover incumbents (a Phil Scott type)
  will be scored misses for M_model; the market instrument carries that
  information and the skill table measures the difference. The model is never
  hand-adjusted for a named candidate.

SENATE ROLL-UP (the new second instrument for USMID2026's Senate question):
  100,000 sims; Dem seats = 34 held-not-up + sum(margin_i > 0 over 35 races).
  Control: Dems need 51 (VP is Republican; 50-50 controls R). The printed
  p_dem_control is pasted into USMID2026.json model.senate_model with a dated
  note, then world_predict.py USMID2026 re-runs - append-only, new rows
  supersede.

HOUSE SEAT-TOTAL DISTRIBUTION (chamber stays chamber-level; no district models):
  E[Dem seats] = 217.5 + spp * (GB_true - tipping);  GB_true ~ N(GB, sigma_gb)
  spp = 4.5 seats per margin point (post-redistricting responsiveness
  estimates run 4-6; stated prior, not fitted), tipping and sigma_gb from
  USMID2026.json (2.5 / 3.5), plus N(0, 8) seat noise. P(Dem >= 218) is a
  consistency check against the registered probit, not a new ledger row.

GATE per race - the standard dual rule: CALL-YES when both instruments
>= 0.95, CALL-NO when both <= 0.05, WATCH otherwise, WATCH-1INST when the
market is missing. Instrument disagreement is recorded per row.

LEDGER: forecasts/world/usmid_races_ledger.csv - append-only, SHA-256 of the
full forecast payload stamped on every row, same law as every other ledger.
Resolution per race: AP-called winner; uncalled races wait for the state's
certified result. "Democrats win" = the Democratic nominee wins the seat
(an independent winning resolves NO regardless of caucus intent).

Usage: python usmid_races.py
"""
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
WDIR = ROOT / "forecasts" / "world"
LEDGER = WDIR / "usmid_races_ledger.csv"

FID = "USMIDRACES2026"
RESOLVE_DATE = "2026-11-03"
GATE = 0.95
N_SIM = 100_000

# stated priors (see docstring)
W_LEAN = {"senate": 0.9, "governor": 0.6}
INC_ADJ = {"senate": {"elected": 3.0, "appointed": 1.0, "none": 0.0},
           "governor": {"elected": 5.0, "appointed": 1.5, "none": 0.0}}
SIGMA_NATL = 5.0
NATL_LOAD = {"senate": 1.0, "governor": 0.7}
SIGMA_RACE = {"senate": 5.0, "governor": 10.0}
P_MODEL_NO_DEM = 0.01
DEM_SEATS_NEEDED = 51  # VP is Republican; 50-50 controls R
HOUSE_SPP = 4.5        # seats per generic-ballot margin point
HOUSE_SEAT_NOISE = 8.0

rng = np.random.default_rng(42)


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def gate_verdict(pm, pd_):
    if pm is None:
        return "WATCH-1INST", None
    pg = min(pm, pd_)
    if pg >= GATE:
        return "CALL-YES", pg
    if 1 - max(pm, pd_) >= GATE:
        return "CALL-NO", pg
    return "WATCH", pg


def main():
    roster = json.loads((DATA / "usmid2026_races.json").read_text(encoding="utf-8"))
    pres = json.loads((DATA / "usmid2026_pres_margins.json").read_text(encoding="utf-8"))
    mkts = json.loads((DATA / "usmid2026_markets.json").read_text(encoding="utf-8"))
    chamber_cfg = json.loads((WDIR / "USMID2026.json").read_text(encoding="utf-8"))
    bands_p = DATA / "usmid2026_house_bands.json"
    house_bands = json.loads(bands_p.read_text(encoding="utf-8")) if bands_p.exists() else None

    gb = chamber_cfg["model"]["generic_ballot_margin"]
    gb_src = chamber_cfg["model"]["margin_source"]
    natl = pres["national_margin"]
    margins = pres["margins"]
    mkt_by_race = {(r["state"], r["office"]): r for r in mkts["races"]}

    freeze = datetime.now(timezone.utc).date().isoformat()
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    races = []
    for office, key in (("governor", "governors"), ("senate", "senate")):
        for r in roster[key]:
            st = r["state"]
            rel = margins[st] - natl
            sign = 1.0 if r["inc_party"] == "D" else -1.0
            inc = INC_ADJ[office][r["inc_running"]] * (sign if r["inc_running"] != "none" else 0.0)
            mu = W_LEAN[office] * rel + gb + inc
            sd = math.hypot(NATL_LOAD[office] * SIGMA_NATL, SIGMA_RACE[office])
            no_dem = r.get("dem_on_ballot") is False
            p_model = P_MODEL_NO_DEM if no_dem else phi(mu / sd)
            m = mkt_by_race.get((st, office))
            p_market = m["p_dem_devig"] if (m and m["liquid"]) else None
            verdict, pg = gate_verdict(p_market, p_model)
            seat = r.get("seat", "regular") if office == "senate" else "regular"
            label = ("Senate special" if seat == "special"
                     else "Senate race" if office == "senate" else "governor race")
            races.append({
                "race_id": ("GOV-" if office == "governor" else "SEN-") +
                           st.upper().replace(" ", "")[:12] + ("-SP" if seat == "special" else ""),
                "state": st, "office": office, "seat": seat,
                "question": f"Democrats win the 2026 {st} {label}",
                "inc_party": r["inc_party"], "inc_running": r["inc_running"],
                "rel_lean": round(rel, 1), "mu_dem": round(mu, 2), "sigma": round(sd, 2),
                "no_dem_on_ballot": no_dem,
                "p_model": round(p_model, 4),
                "p_market": None if p_market is None else round(p_market, 4),
                "market_slug": m["event_slug"] if m else None,
                "market_liquidity": m["liquidity"] if m else None,
                "disagreement": (None if p_market is None
                                 else round(abs(p_market - p_model), 4)),
                "p_gate": None if pg is None else round(pg, 4),
                "verdict": verdict,
                "note": r["note"],
            })

    # ---- correlated Monte Carlo: Senate control + win-count distributions ----
    sen = [x for x in races if x["office"] == "senate"]
    gov = [x for x in races if x["office"] == "governor"]

    def simulate(group):
        mus = np.array([x["mu_dem"] for x in group])
        load = np.array([NATL_LOAD[x["office"]] for x in group])
        sig_r = np.array([SIGMA_RACE[x["office"]] for x in group])
        eps_n = rng.normal(0, SIGMA_NATL, N_SIM)
        wins = np.empty((N_SIM, len(group)), dtype=bool)
        for j in range(len(group)):
            m_j = mus[j] + load[j] * eps_n + rng.normal(0, sig_r[j], N_SIM)
            wins[:, j] = m_j > 0
            if group[j]["no_dem_on_ballot"]:
                wins[:, j] = rng.random(N_SIM) < P_MODEL_NO_DEM
        return wins

    sen_wins = simulate(sen)
    dem_seats = roster["senate_not_up"]["dem_aligned"] + sen_wins.sum(axis=1)
    p_sen_control = float((dem_seats >= DEM_SEATS_NEEDED).mean())
    sen_dist = {"p5": int(np.percentile(dem_seats, 5)), "med": int(np.median(dem_seats)),
                "p95": int(np.percentile(dem_seats, 95)),
                "p_dem_control": round(p_sen_control, 4),
                "seats_needed": DEM_SEATS_NEEDED,
                "held_not_up": roster["senate_not_up"]["dem_aligned"]}

    gov_wins = simulate(gov).sum(axis=1)
    gov_dist = {"p5": int(np.percentile(gov_wins, 5)), "med": int(np.median(gov_wins)),
                "p95": int(np.percentile(gov_wins, 95)),
                "mean": round(float(gov_wins.mean()), 2), "n_races": len(gov)}

    # ---- House seat-total distribution (chamber-level; no district models) ----
    tipping = chamber_cfg["model"]["tipping_point"]
    sigma_gb = chamber_cfg["model"]["sigma"]
    gb_true = rng.normal(gb, sigma_gb, N_SIM)
    house_seats = np.clip(np.rint(217.5 + HOUSE_SPP * (gb_true - tipping)
                                  + rng.normal(0, HOUSE_SEAT_NOISE, N_SIM)), 0, 435)
    house_dist = {"p5": int(np.percentile(house_seats, 5)), "med": int(np.median(house_seats)),
                  "p95": int(np.percentile(house_seats, 95)),
                  "p_dem_majority": round(float((house_seats >= 218).mean()), 4),
                  "spp": HOUSE_SPP, "tipping": tipping, "sigma_gb": sigma_gb,
                  "seat_noise": HOUSE_SEAT_NOISE,
                  "note": ("seats-votes curve from the generic ballot; consistency check "
                           "against the registered chamber probit, not a new ledger row")}

    result = {
        "forecast_id": FID, "title": "US Midterms 2026 - race-level board",
        "domain": "US elections", "freeze_date": freeze, "resolve_date": RESOLVE_DATE,
        "run_at_utc": run_at,
        "instruments": {
            "market_source": f"{mkts['source']}, fetched {mkts['fetched_utc']}",
            "model_note": (f"structural probit: lean (w {W_LEAN}) x 2024 pres margins + "
                           f"generic ballot ({gb_src}) + incumbency {INC_ADJ}; "
                           f"sigma natl {SIGMA_NATL}, race {SIGMA_RACE}, loads {NATL_LOAD}"),
        },
        "gate_rule": "dual: both instruments must clear 0.95; p_gate = min; market missing -> WATCH-1INST",
        "parameters": {
            "generic_ballot_margin": gb, "national_2024_margin": natl,
            "w_lean": W_LEAN, "inc_adj": INC_ADJ, "sigma_natl": SIGMA_NATL,
            "natl_load": NATL_LOAD, "sigma_race": SIGMA_RACE,
            "p_model_no_dem": P_MODEL_NO_DEM, "n_sim": N_SIM, "seed": 42,
        },
        "races": races,
        "senate_control": sen_dist,
        "governor_wins": gov_dist,
        "house_seats": house_dist,
        "house_band_markets": house_bands,
        "resolution": {
            "source": ("AP race calls per race; any race uncalled by 2026-12-01 resolves by the "
                       "state-certified winner. Inherits USMID2026 conventions."),
            "resolve_by": "2027-01-03",
            "rules": [
                "Each row resolves YES iff the Democratic nominee wins that seat; an independent or third-party winner resolves NO regardless of later caucus choice",
                "AP-called winner resolves a row immediately; uncalled races wait for state certification - no row resolves on an election-night lead",
                "Runoffs (e.g. Georgia-style) resolve on the runoff's final result; the row stays open until then",
                "Recounts and litigation: resolution waits for certified outcomes; no row resolves on a contested margin",
            ],
        },
        "quality_flags": [
            "User brief said 34 governor races; the verified official roster is 36 states (Wikipedia, fetched 2026-10-24).",
            "M_model is deliberately candidate-blind (no race polls): markets see candidate quality, the model sees structure - disagreement between them is information, not error.",
            "ID/SD/NE Senate have no Democratic nominee on the ballot: p_model = 0.01 by rule; the registered question (Democrats win) stays resolvable.",
            "Races without a liquid Polymarket winner market (liquidity < $10k) run single-instrument and can never be CALLed.",
            "Alaska (governor + Senate) and California governor have only candidate-level Polymarket events (ranked-choice/top-two races): the party-pair de-vig rule does not admit them, so those races run market=null rather than hand-mapping candidates to parties.",
        ],
        "tripwires": [
            {"watch": "Generic-ballot average moves 3+ points before Nov 3", "effect": "re-run all races"},
            {"watch": "Any registered race's market moves 10+ points", "effect": "re-run that race set"},
        ],
    }
    payload = json.dumps(result, indent=1, sort_keys=True)
    (WDIR / f"{FID}_forecast.json").write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode()).hexdigest()

    rows = [{
        "forecast_id": FID, "race_id": x["race_id"], "domain": "US elections",
        "state": x["state"], "office": x["office"], "seat": x["seat"],
        "question": x["question"], "freeze_date": freeze, "resolve_date": RESOLVE_DATE,
        "run_at_utc": run_at, "inc_party": x["inc_party"], "inc_running": x["inc_running"],
        "p_market": x["p_market"], "p_model": x["p_model"], "p_gate": x["p_gate"],
        "verdict": x["verdict"], "disagreement": x["disagreement"],
        "market_liquidity": x["market_liquidity"], "forecast_sha256": digest,
        "resolved": "", "outcome": "", "correct": "",
        "resolution_source": result["resolution"]["source"],
    } for x in races]
    pd.DataFrame(rows).to_csv(LEDGER, mode="a", header=not LEDGER.exists(), index=False)

    nm = sum(1 for x in races if x["p_market"] is not None)
    calls = [x for x in races if x["verdict"].startswith("CALL")]
    print(f"{FID}: {len(races)} races ({len(gov)} governor, {len(sen)} senate), "
          f"{nm} with liquid markets | sha256 {digest}")
    print(f"verdicts: {sum(1 for x in races if x['verdict']=='CALL-YES')} CALL-YES, "
          f"{sum(1 for x in races if x['verdict']=='CALL-NO')} CALL-NO, "
          f"{sum(1 for x in races if x['verdict']=='WATCH')} WATCH, "
          f"{sum(1 for x in races if x['verdict']=='WATCH-1INST')} WATCH-1INST")
    print(f"SENATE CONTROL (structural MC): P(Dem control) = {p_sen_control:.4f} | "
          f"Dem seats p5/med/p95 = {sen_dist['p5']}/{sen_dist['med']}/{sen_dist['p95']}")
    print(f"  -> paste into USMID2026.json model.senate_model with a dated note, then re-run world_predict.py USMID2026")
    print(f"GOVERNORS: Dem wins p5/med/p95 = {gov_dist['p5']}/{gov_dist['med']}/{gov_dist['p95']} of {len(gov)}")
    print(f"HOUSE seats: p5/med/p95 = {house_dist['p5']}/{house_dist['med']}/{house_dist['p95']}, "
          f"P(Dem >= 218) = {house_dist['p_dem_majority']} (probit check: "
          f"{phi((gb - tipping) / sigma_gb):.4f})")
    for x in races:
        if x["verdict"] == "WATCH" and x["disagreement"] and x["disagreement"] > 0.25:
            print(f"  DISAGREE>{0.25}: {x['question']}: market {x['p_market']} vs model {x['p_model']}")


if __name__ == "__main__":
    main()
