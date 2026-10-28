"""Assemble one JSON for the searchable prediction app (site/app_data.json).

Combines: 46 retrodictions (election_summaries + precision_ledger strict verdicts),
2026 holdout + live 2027 forecasts (forecasts/*_forecast.json + forecasts/ledger.csv),
and not-yet-forecastable 2027 placeholders.
"""
import json
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FDIR = ROOT / "forecasts"
OUT = ROOT / "site" / "app_data.json"

def _r(x):
    return None if pd.isna(x) else round(float(x), 2)

def _i(x):
    return None if pd.isna(x) else int(x)

STATES = {
    "AS": "Assam", "BR": "Bihar", "CG": "Chhattisgarh", "DL": "Delhi", "GJ": "Gujarat",
    "HP": "Himachal Pradesh", "HR": "Haryana", "JH": "Jharkhand", "KA": "Karnataka",
    "KL": "Kerala", "MH": "Maharashtra", "MP": "Madhya Pradesh", "PB": "Punjab",
    "RJ": "Rajasthan", "TG": "Telangana", "TN": "Tamil Nadu", "UK": "Uttarakhand",
    "UP": "Uttar Pradesh", "WB": "West Bengal", "GA": "Goa", "MN": "Manipur",
}
MAJ = {"UP": 202, "PB": 59, "UK": 36}

es = pd.read_csv(PROC / "election_summaries.csv")
pl = pd.read_csv(PROC / "precision_ledger.csv")
pl = pl[pl["mode"] == "loo"]
fl = pd.read_csv(FDIR / "ledger.csv")
for c in ("resolved", "outcome", "correct"):
    fl[c] = fl[c].fillna("").astype(str).replace("nan", "")
# keep latest run per (forecast_id, question)
fl = fl.sort_values("run_at_utc").drop_duplicates(["forecast_id", "question"], keep="last")

elections = []

# ---------- 46 retrodictions ----------
for eid, g in es.groupby("election_id"):
    st, yr = eid[:2], int(eid[2:])
    blocs = []
    for _, r in g.iterrows():
        blocs.append({
            "name": r.bloc, "base": _r(r.base_share), "m2": _r(r.pred_share),
            "m3": _r(r.poll_share), "p5": _i(r.seats_p5), "med": _i(r.seats_med),
            "p95": _i(r.seats_p95), "p_maj": _r(r.p_majority), "p_largest": _r(r.p_largest),
            "actual": _i(r.actual_seats),
        })
    qs = []
    for _, r in pl[pl.election_id == eid].iterrows():
        qs.append({
            "q": f"{r.bloc} {'wins majority' if r.question == 'majority' else 'is largest'}",
            "p2": _r(r.p_m2), "p3": _r(r.p_m3), "verdict": r.gate_strict,
            "outcome": "YES" if r.actual == 1 else "NO",
            "correct": (None if pd.isna(r.strict_correct) else bool(r.strict_correct)),
        })
    elections.append({
        "id": eid, "state": STATES.get(st, st), "st": st, "year": yr,
        "status": "retrodiction", "title": f"{STATES.get(st, st)} Assembly {yr}",
        "blocs": blocs, "questions": qs, "flags": [], "tripwires": [], "sha": None,
        "freeze": None,
    })

# ---------- forward forecasts (2026 holdout resolved + 2027 live) ----------
for fid in sorted(fl.forecast_id.unique()):
    fj = FDIR / f"{fid}_forecast.json"
    if not fj.exists():
        continue
    d = json.loads(fj.read_text(encoding="utf-8"))
    st = fid[:2]
    yr = int(fid[2:])
    rows = fl[fl.forecast_id == fid]
    resolved = rows.resolved.astype(str).str.len().gt(0).any() and rows.outcome.astype(str).str.len().gt(0).any()
    blocs = []
    r2, r3 = d.get("seats_m2", {}), d.get("seats_m3", {})
    shares = d.get("state_shares", {})
    for b in shares.get("m2_pred", {}):
        a, c = r2.get(b, {}), r3.get(b, {})
        use = c if c else a
        blocs.append({
            "name": b, "base": shares.get("baseline", {}).get(b),
            "m2": shares.get("m2_pred", {}).get(b), "m3": shares.get("m3_pred", {}).get(b),
            "p5": use.get("p5"), "med": use.get("med"), "p95": use.get("p95"),
            "p_maj": use.get("p_majority"), "p_largest": use.get("p_largest"),
            "actual": None,
        })
    qs = []
    for _, r in rows.iterrows():
        qs.append({
            "q": r.question, "p2": _r(r.p_m2), "p3": _r(r.p_m3), "verdict": r.verdict,
            "outcome": (str(r.outcome) if resolved and str(r.outcome) not in ("", "nan") else None),
            "correct": (str(r.correct).lower() == "true" if resolved and str(r.correct) not in ("", "nan") else None),
        })
    elections.append({
        "id": fid, "state": STATES.get(st, st), "st": st, "year": yr,
        "status": "resolved-forward" if resolved else "live",
        "title": d.get("title", fid), "freeze": d.get("freeze_date"),
        "blocs": blocs, "questions": qs,
        "flags": d.get("quality_flags", []),
        "nef": d.get("new_entrant_flag", {}),
        "tripwires": d.get("tripwires", []),
        "resolution": d.get("resolution"),
        "sha": rows.forecast_sha256.iloc[0] if len(rows) else None,
    })

# ---------- world forecasts (market + model dual gate) ----------
WDIR = FDIR / "world"
wl_path = FDIR / "world_ledger.csv"
if wl_path.exists():
    wl = pd.read_csv(wl_path)
    for c in ("resolved", "outcome", "correct"):
        wl[c] = wl[c].fillna("").astype(str).replace("nan", "")
    wl = wl.sort_values("run_at_utc").drop_duplicates(["forecast_id", "question"], keep="last")
    for fid in sorted(wl.forecast_id.unique()):
        fj = WDIR / f"{fid}_forecast.json"
        if not fj.exists():
            continue
        d = json.loads(fj.read_text(encoding="utf-8"))
        rows = wl[wl.forecast_id == fid]
        resolved = rows.resolved.str.len().gt(0).any()
        em, eo = d["entity_probs"].get("market", {}), d["entity_probs"].get("model", {})
        ents = sorted(set(em) | set(eo), key=lambda t: -(max(em.get(t, 0), eo.get(t, 0))))[:8]
        blocs = [{"name": t, "base": None, "m2": None, "m3": None, "p5": None, "med": None,
                  "p95": None, "p_maj": None, "p_largest": None, "actual": None,
                  "p_market": em.get(t), "p_model": eo.get(t)} for t in ents]
        qs = [{"q": r.question, "p2": _r(r.p_model), "p3": _r(r.p_market), "verdict": r.verdict,
               "outcome": (r.outcome if resolved and r.outcome else None),
               "correct": (r.correct.lower() == "true" if resolved and r.correct else None)}
              for _, r in rows.iterrows()]
        elections.append({
            "id": fid, "state": d["title"], "st": "", "year": int(str(d.get("resolve_date", "2027"))[:4]),
            "status": "resolved-forward" if resolved else "live", "domain": d.get("domain", "World"),
            "title": d["title"], "freeze": d.get("freeze_date"), "blocs": blocs, "questions": qs,
            "flags": d.get("quality_flags", []), "tripwires": d.get("tripwires", []),
            "resolution": d.get("resolution"),
            "sha": rows.forecast_sha256.iloc[0] if len(rows) else None,
            "instruments": d.get("instruments", {}), "resolve_date": d.get("resolve_date"),
        })

# ---------- US midterm race-level board (attached to the USMID2026 entry) ----------
rl_path = WDIR / "usmid_races_ledger.csv"
rj_path = WDIR / "USMIDRACES2026_forecast.json"
rl = None
if rl_path.exists() and rj_path.exists():
    rl = pd.read_csv(rl_path)
    for c in ("resolved", "outcome", "correct"):
        rl[c] = rl[c].fillna("").astype(str).replace("nan", "")
    rl = rl.sort_values("run_at_utc").drop_duplicates(["race_id"], keep="last")
    rd = json.loads(rj_path.read_text(encoding="utf-8"))
    note_by_race = {x["race_id"]: x.get("note") for x in rd.get("races", [])}

    def _r4(x):
        return None if pd.isna(x) else round(float(x), 4)

    races = [{
        "race_id": r.race_id, "state": r.state, "office": r.office, "seat": r.seat,
        "p_market": _r4(r.p_market), "p_model": _r4(r.p_model),
        "verdict": r.verdict, "disagreement": _r4(r.disagreement),
        "inc_party": r.inc_party, "inc_running": r.inc_running,
        "note": note_by_race.get(r.race_id),
        "outcome": (r.outcome if r.resolved and r.outcome else None),
        "correct": (r.correct.lower() == "true" if r.resolved and r.correct else None),
    } for _, r in rl.iterrows()]
    host = next((e for e in elections if e["id"] == "USMID2026"), None)
    if host:
        host["races"] = races
        host["races_sha"] = str(rl.forecast_sha256.iloc[-1])
        host["races_freeze"] = str(rl.freeze_date.iloc[-1])
        host["senate_control"] = rd.get("senate_control")
        host["governor_wins"] = rd.get("governor_wins")
        host["house_seats"] = rd.get("house_seats")
        hb = rd.get("house_band_markets")
        host["house_bands"] = ({"fetched": hb.get("fetched_utc"), "events": hb.get("events")}
                               if hb else None)
        host["races_market_source"] = rd.get("instruments", {}).get("market_source")

# ---------- EPL match forecasts (one entry per matchweek) ----------
ml_path = FDIR / "matches_ledger.csv"
if ml_path.exists():
    ml = pd.read_csv(ml_path)
    for c in ("resolved", "outcome", "correct"):
        ml[c] = ml[c].fillna("").astype(str).replace("nan", "")
    ml = ml.sort_values("run_at_utc").drop_duplicates(["match_id"], keep="last")
    for mw, g in ml.groupby("matchweek"):
        g = g.sort_values("date_utc")
        res_g = g[g.resolved.str.len() > 0]
        all_resolved = len(res_g) == len(g)
        matches, briers = [], []
        for _, r in g.iterrows():
            m = {"home": r.home, "away": r.away, "date": str(r.date_utc)[:10],
                 "pH": _r(r.p_home), "pD": _r(r.p_draw), "pA": _r(r.p_away),
                 "outcome": r.outcome or None, "brier": None, "fav_hit": None}
            if r.outcome in ("H", "D", "A"):
                probs = {"H": r.p_home, "D": r.p_draw, "A": r.p_away}
                b = sum((probs[k] - (1.0 if r.outcome == k else 0.0)) ** 2 for k in probs)
                m["brier"] = round(float(b), 3)
                m["fav_hit"] = str(r.correct).lower() == "true"
                briers.append(b)
            matches.append(m)
        elections.append({
            "id": f"EPLMW{int(mw):02d}", "state": "Premier League", "st": "", "year": 2027,
            "status": "resolved-forward" if all_resolved else "live",
            "domain": "Football", "kind": "matches",
            "title": f"Premier League 2026-27 · Matchweek {int(mw)}",
            "freeze": g.freeze_date.iloc[0], "blocs": [], "questions": [],
            "matches": matches,
            "mw_summary": ({"n": len(briers),
                            "brier3": round(float(np.mean(briers)), 3),
                            "fav_hits": int(sum(1 for m in matches if m["fav_hit"]))}
                           if briers else None),
            "flags": ["Single-instrument model forecasts (shrunk-PPG Poisson, stated priors): scored on Brier/log, never gate-CALLed.",
                      "Three-way Brier scale 0-2; uniform guess scores 0.667."],
            "tripwires": [], "resolution": {"source": g.resolution_source.iloc[0], "rules": []},
            "sha": g.forecast_sha256.iloc[0],
        })

# ---------- placeholders ----------
for fid, reason in [
    ("GJ2027", "No constituency-level 2022 baseline in the dataset yet (only hand-entered official tallies). Ingest GJ2022 AC-level results to unlock."),
    ("HP2027", "No constituency-level 2022 baseline in the dataset yet. Ingest HP2022 AC-level results to unlock."),
    ("GA2027", "Goa is outside the N=46 dataset (small-state exclusion). Needs baseline ingestion and a small-state sigma estimate."),
    ("MN2027", "Manipur is outside the N=46 dataset. Needs baseline ingestion; 2022 baseline predates current political realignment."),
]:
    st, yr = fid[:2], int(fid[2:])
    elections.append({
        "id": fid, "state": STATES[st], "st": st, "year": yr, "status": "nodata",
        "title": f"{STATES[st]} Assembly {yr}", "freeze": None, "blocs": [], "questions": [],
        "flags": [reason], "tripwires": [], "sha": None,
    })

# ---------- track record ----------
def _score(df, vcol, ccol):
    calls = df[df[vcol].astype(str).str.startswith("CALL")]
    ok = calls[ccol].astype(str).str.lower().isin(["true", "1", "1.0"]).sum()
    return int(len(calls)), int(ok)

n46_calls = pl[pl.gate_strict.astype(str).str.startswith("CALL")]
n46_total = len(n46_calls)
n46_ok = int(n46_calls.strict_correct.fillna(0).astype(float).sum())
res_rows = fl[(fl.resolved.astype(str).str.len() > 0) & fl.verdict.astype(str).str.startswith("CALL")]
fwd_total = len(res_rows)
fwd_ok = int(res_rows.correct.astype(str).str.lower().eq("true").sum())
track = {
    "retrodiction_calls": n46_total, "retrodiction_correct": n46_ok,
    "forward_calls": fwd_total, "forward_correct": fwd_ok,
    "lifetime_calls": n46_total + fwd_total, "lifetime_correct": n46_ok + fwd_ok,
    "live_open_calls": int(len(fl[(fl.resolved.astype(str).str.len() == 0)
                                  & fl.verdict.astype(str).str.startswith("CALL")])),
}
if wl_path.exists():
    wl_open = wl[(wl.resolved.str.len() == 0) & wl.verdict.str.startswith("CALL")]
    wl_res = wl[(wl.resolved.str.len() > 0) & wl.verdict.str.startswith("CALL")]
    track["live_open_calls"] += int(len(wl_open))
    track["forward_calls"] += int(len(wl_res))
    track["forward_correct"] += int(wl_res.correct.str.lower().eq("true").sum())
    track["lifetime_calls"] += int(len(wl_res))
    track["lifetime_correct"] += int(wl_res.correct.str.lower().eq("true").sum())
if rl is not None:
    rl_open = rl[(rl.resolved.str.len() == 0) & rl.verdict.str.startswith("CALL")]
    rl_res = rl[(rl.resolved.str.len() > 0) & rl.verdict.str.startswith("CALL")]
    track["live_open_calls"] += int(len(rl_open))
    track["forward_calls"] += int(len(rl_res))
    track["forward_correct"] += int(rl_res.correct.str.lower().eq("true").sum())
    track["lifetime_calls"] += int(len(rl_res))
    track["lifetime_correct"] += int(rl_res.correct.str.lower().eq("true").sum())

# ---------- scoring summary (scripts/score.py) ----------
scoring = None
ss_path = PROC / "scores_summary.json"
if ss_path.exists():
    scoring = json.loads(ss_path.read_text(encoding="utf-8"))

# ---------- changelog (autopilot log blocks + ledger-derived events) ----------
TITLES = {e["id"]: e["title"] for e in elections}
_chg = {}  # date "YYYY-MM-DD" -> [{title, items, kind}]

def _add_chg(d, title, items, kind):
    d = str(d)[:10]
    if not re.match(r"\d{4}-\d{2}-\d{2}$", d):
        return
    _chg.setdefault(d, []).append({"title": title, "items": items, "kind": kind})

def _squash(s, lim=240):
    s = re.sub(r"\*\*|`", "", s).strip()
    s = re.sub(r"\s+\S+:$", "", s)  # drop a trailing "Watched:"-style lead-in to sub-bullets
    if len(s) > lim:
        s = s[:lim].rsplit(" ", 1)[0] + " ..."
    return s

# 1) dated blocks of forecasts/autopilot_log.md
log_path = FDIR / "autopilot_log.md"
if log_path.exists():
    for block in re.split(r"(?m)^## ", log_path.read_text(encoding="utf-8"))[1:]:
        head, _, body = block.partition("\n")
        m = re.match(r"(\d{4}-\d{2}-\d{2})\s*[–—-]*\s*(.*)", head.strip())
        if not m:
            continue
        items = []
        for ln in body.splitlines():
            m2 = re.match(r"\*\*(.+?)\*\*:?\s*(.+)", ln.strip())
            if m2:
                items.append(_squash(m2.group(1).rstrip(":") + ": " + m2.group(2)))
        _add_chg(m.group(1), m.group(2).strip() or "Autopilot run", items, "run")

# 2) ledger-derived events: registrations, verdict changes, resolutions
def _ledger_events(path, kind_label):
    if not path.exists():
        return
    df = pd.read_csv(path)
    for c in ("resolved", "outcome", "correct"):
        df[c] = df[c].fillna("").astype(str).replace("nan", "")
    df["d"] = df["run_at_utc"].astype(str).str[:10]
    for fid, g in df.groupby("forecast_id"):
        name = TITLES.get(fid, fid)
        dates = sorted(g["d"].unique())
        prev = None
        for d in dates:
            cur = g[g["d"] == d].sort_values("run_at_utc").drop_duplicates("question", keep="last")
            calls = cur[cur["verdict"].astype(str).str.startswith("CALL")]
            if prev is None:
                item = (f"{len(cur)} question probabilities hash-stamped ({kind_label})"
                        + (f"; {len(calls)} certified CALL{'s' if len(calls) > 1 else ''} issued"
                           if len(calls) else "; all verdicts WATCH - gate not cleared"))
                fz = str(cur["freeze_date"].iloc[0])
                if fz and fz < d:
                    item += f"; inputs frozen {fz}"
                _add_chg(d, f"Pre-registered {name}", [item], "ledger")
            else:
                pm = prev.set_index("question")["verdict"].astype(str)
                changes = [f"{r.question}: {pm[r.question]} -> {r.verdict}"
                           for _, r in cur.iterrows()
                           if r.question in pm.index and pm[r.question] != str(r.verdict)]
                if changes:
                    _add_chg(d, f"Verdict changed on {name}", changes, "ledger")
                else:
                    _add_chg(d, f"Re-registered {name}",
                             [f"{len(cur)} probabilities re-hashed; no verdict changed"], "ledger")
            prev = cur
        latest = g.sort_values("run_at_utc").drop_duplicates("question", keep="last")
        res = latest[latest["resolved"].str.len() > 0]
        if len(res):
            rd = str(res["resolved"].iloc[0])[:10]
            rcalls = res[res["verdict"].astype(str).str.startswith("CALL")]
            ok = int(rcalls["correct"].str.lower().eq("true").sum())
            item = (f"{len(res)} probabilities scored at resolution"
                    + (f"; calls {ok}/{len(rcalls)} right" if len(rcalls)
                       else "; no calls had been issued"))
            if rd <= dates[0]:
                # holdout-style: scored against an already-declared result at registration
                _add_chg(dates[0],
                         f"Scored {name}" + ("" if "holdout" in name.lower() else " (holdout)"),
                         [item + f"; result date {rd}, forecast frozen "
                          f"{str(latest['freeze_date'].iloc[0])} from pre-election data only"], "ledger")
            else:
                _add_chg(rd, f"Resolved {name}", [item], "ledger")

_ledger_events(FDIR / "ledger.csv", "dual gate: model + corrected polls")
_ledger_events(FDIR / "world_ledger.csv", "market + model gate")
TITLES.setdefault("USMIDRACES2026", "US Midterms 2026 race board")
_ledger_events(FDIR / "world" / "usmid_races_ledger.csv", "per-race dual gate: market + structural model")

# matches ledger: one entry per matchweek registration, one per resolution date
if ml_path.exists():
    mdf = pd.read_csv(ml_path)
    for c in ("resolved", "outcome", "correct"):
        mdf[c] = mdf[c].fillna("").astype(str).replace("nan", "")
    mdf = mdf.sort_values("run_at_utc").drop_duplicates(["match_id"], keep="last")
    for mw, g in mdf.groupby("matchweek"):
        d = str(g["run_at_utc"].iloc[0])[:10]
        _add_chg(d, f"Pre-registered Premier League matchweek {int(mw)}",
                 [f"{len(g)} fixtures, probabilities locked before kickoff "
                  f"(sha {str(g['forecast_sha256'].iloc[0])[:8]}...)"], "ledger")
        res = g[g["outcome"].isin(["H", "D", "A"])]
        for rd, rg in res.groupby(res["resolved"].str[:10]):
            briers = []
            for _, r in rg.iterrows():
                probs = {"H": r.p_home, "D": r.p_draw, "A": r.p_away}
                briers.append(sum((probs[k] - (1.0 if r.outcome == k else 0.0)) ** 2 for k in probs))
            fav = int(rg["correct"].str.lower().eq("true").sum())
            _add_chg(rd, f"Scored Premier League matchweek {int(mw)}",
                     [f"{len(rg)} fixtures resolved: favourites {fav}/{len(rg)}, "
                      f"mean 3-way Brier {float(np.mean(briers)):.3f} (0.667 = guessing)"], "ledger")

# research ledger: one entry per (forecast, day)
rl_path = FDIR / "research_ledger.csv"
if rl_path.exists():
    rdf = pd.read_csv(rl_path)
    rdf["d"] = rdf["run_at_utc"].astype(str).str[:10]
    for (fid, d), g in rdf.groupby(["forecast_id", "d"]):
        nq = g["question"].nunique()
        _add_chg(d, f"Research instrument priced {TITLES.get(fid, fid)}",
                 [f"{nq} question{'s' if nq != 1 else ''}, dossier hash-stamped "
                  f"(sha {str(g['dossier_sha256'].iloc[0])[:8]}...); "
                  "written blind to market prices"], "ledger")

changelog = [{"date": d,
              "entries": sorted(v, key=lambda e: 0 if e["kind"] == "run" else 1)}
             for d, v in sorted(_chg.items(), reverse=True)]

out = {"generated": str(date.today()), "track": track, "scoring": scoring,
       "changelog": changelog,
       "elections": sorted(elections, key=lambda e: (-e["year"], e["state"]))}
OUT.write_text(json.dumps(out, indent=0), encoding="utf-8")
print(f"written {OUT} | elections: {len(elections)} | track: {track}")
