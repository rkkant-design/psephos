"""M_research: the engine's third instrument - an LLM research-forecaster.

Division of labor (why this script never calls a model API):
  The research pass itself - web search, source reading, base-rate hunting,
  adversarial self-critique - is performed by the LLM operator session that
  drives this repo (the same agent that runs the autopilot), following the
  protocol printed by `brief`. The LLM writes its findings as a DOSSIER json
  (forecasts/research/dossiers/<ID>.json). This script is the deterministic
  half: it validates the dossier against the protocol, applies the post-hoc
  calibration transform, writes the canonical hashed research artifact
  (forecasts/research/<ID>_research.json - the file world_predict.py reads),
  and appends to the append-only research ledger.

Usage:
  python m_research.py brief <FORECAST_ID>    print the research protocol and
                                              question list for a config
                                              (world or India)
  python m_research.py commit <dossier.json>  validate -> calibrate -> hash
                                              -> append research_ledger.csv
  python m_research.py batch <dir>            commit every *.json in <dir>
  python m_research.py tune                   fit calibration (a, b) on
                                              resolved research rows; PRINTS
                                              the fit, never writes it
                                              (parameter changes are user
                                              decisions, per AUTOPILOT.md)

Debiasing rules ENFORCED at commit (the engine's validated laws, applied to
research):
  1. Base rate first. Every question must carry base_rate_used (reference
     class + numeric value + where it came from). Narratives adjust the base
     rate; they never replace it (N=46 lesson: structure beats stories).
  2. Strongest opposing case. Required, substantive. A dossier that cannot
     state the best case against its own number is rejected.
  3. Market independence. Any betting/prediction-market or forecast-
     aggregator domain in key_sources FAILS validation, and the dossier must
     carry an explicit independence_attestation. M_research that peeks at
     M_market is one instrument wearing two hats - the dual gate's entire
     validated value (N=46: removed every false call) comes from witnesses
     that can fail independently.
  4. Neutral post-hoc calibration. p_research = sigmoid(a*logit(p_raw) + b),
     a=1, b=0 (identity) until tuned on >= MIN_TUNE_N resolved research
     questions. `tune` prints a candidate fit; adopting it (editing
     forecasts/research/calibration.json) is a user decision. New commits use
     the new parameters; already-ledgered rows are never restated.

Ledger law: forecasts/research_ledger.csv is append-only. Rows carry the
sha256 of the canonical research artifact. Only the three resolution columns
(resolved/outcome/correct) may ever be filled later, on the LATEST rows only
- the same law as ledger.csv, world_ledger.csv and matches_ledger.csv.
"""
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RDIR = ROOT / "forecasts" / "research"
DOSSIERS = RDIR / "dossiers"
LEDGER = ROOT / "forecasts" / "research_ledger.csv"
CALIB = RDIR / "calibration.json"
MIN_TUNE_N = 30

# Betting markets, prediction markets and forecast aggregators. A research
# source whose URL contains any of these is a validation failure: the
# instrument's value is independence from M_market, so it must never see a
# price or a crowd forecast. (Metaculus/GJOpen are aggregated *forecasts*,
# which anchor exactly like prices do.)
BANNED_MARKET_DOMAINS = [
    "polymarket.com", "kalshi.com", "manifold.markets", "predictit.org",
    "metaculus.com", "gjopen.com", "goodjudgment.com", "infer-pub.com",
    "betfair.", "oddschecker.", "oddsportal.", "smarkets.", "pinnacle.",
    "bet365.", "williamhill.", "ladbrokes.", "paddypower.", "skybet.",
    "betway.", "unibet.", "draftkings.", "fanduel.", "bovada.", "betmgm.",
    "olbg.com", "covers.com", "vegasinsider.",
]

LEDGER_COLS = ["forecast_id", "domain", "freeze_date", "resolve_date",
               "run_at_utc", "question", "p_raw", "p_research", "calib_a",
               "calib_b", "base_rate", "n_sources", "dossier_sha256",
               "resolved", "outcome", "correct", "resolution_source"]

PROTOCOL = """\
M_RESEARCH PROTOCOL (print date {today}) - follow in order, per question:
 1. Read the question text and the resolution rules below. Forecast the
    resolution criteria, not the vibe of the question.
 2. BASE RATE FIRST. Before reading any news: name the reference class
    (e.g. 'post-war midterms, president's party holds the House', 'team
    leading the table after matchday 8 wins the title'), count it, and
    write down the base rate. This number is the anchor.
 3. Research the news: recent, dated, primary-ish sources. Polls, official
    data, tables and ratings are evidence. NEVER fetch or consult betting
    odds, prediction-market prices, or forecast aggregators
    (Polymarket/Kalshi/Manifold/Metaculus/GJOpen/bookmakers) - independence
    from M_market is this instrument's entire reason to exist.
 4. Adjust the base rate with the evidence, stating each adjustment and its
    direction. Narratives that cannot cite data move the number ~nothing.
 5. STRONGEST OPPOSING CASE. Write the best argument that your current
    number is wrong, steel-manned. Adjust if it bites.
 6. Output p_raw plus the structured fields (schema below). Abstention is a
    feature: if the evidence is thin, say so in the reasoning and keep p
    near the base rate - never manufacture confidence.

Dossier schema (forecasts/research/dossiers/<ID>.json):
{{
  "forecast_id": "<ID>", "domain": "...", "freeze_date": "YYYY-MM-DD",
  "resolve_date": "...", "researched_at_utc": "...",
  "researcher": "<model/session id>",
  "independence_attestation": "No betting odds, prediction-market prices or
    forecast-aggregator numbers were fetched or consulted for this dossier.",
  "questions": [{{
     "q": "<exact ledger question text>",
     "base_rate_used": {{"reference_class": "...", "value": 0.0, "source": "..."}},
     "evidence": ["dated finding 1", "..."],
     "strongest_opposing_case": "...",
     "reasoning_summary": "base rate -> adjustments -> final number",
     "key_sources": [{{"title": "...", "url": "...", "date": "YYYY-MM-DD"}}],
     "p_raw": 0.0
  }}]
}}
Then: python scripts/m_research.py commit forecasts/research/dossiers/<ID>.json
"""


def _logit(p):
    return math.log(p / (1 - p))


def _sigmoid(x):
    return 1 / (1 + math.exp(-x))


def load_calibration():
    if not CALIB.exists():
        return {"a": 1.0, "b": 0.0}
    return json.loads(CALIB.read_text(encoding="utf-8"))


def calibrate(p_raw, cal):
    p = min(max(float(p_raw), 1e-3), 1 - 1e-3)
    return _sigmoid(cal["a"] * _logit(p) + cal["b"])


# ---------------- brief ----------------

def brief(fid):
    wpath = ROOT / "forecasts" / "world" / f"{fid}.json"
    ipath = ROOT / "forecasts" / f"{fid}.json"
    path = wpath if wpath.exists() else ipath
    if not path.exists():
        sys.exit(f"no config found for {fid} (looked in forecasts/world/ and forecasts/)")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if "questions" in cfg:  # world config
        qs = [q["q"] for q in cfg["questions"]]
    else:  # India config: mechanical bloc questions + sub_questions
        qs = [f"{b} {s}" for b in cfg["blocs"] for s in ("wins majority", "is largest")]
        qs += [s["q"] for s in cfg.get("sub_questions", [])]
    print(f"=== {fid}: {cfg['title']} ===")
    print(f"freeze {cfg['freeze_date']}  resolve {cfg.get('resolve_date') or cfg.get('expected_date')}")
    res = cfg.get("resolution") or {}
    print(f"resolution source: {res.get('source')}")
    for r in res.get("rules", []):
        print(f"  rule: {r}")
    print("questions (use EXACT text as ledger key):")
    for q in qs:
        print(f"  - {q}")
    print()
    print(PROTOCOL.format(today=datetime.now(timezone.utc).date()))


# ---------------- validation ----------------

def _fail(errors, msg):
    errors.append(msg)


def validate(d):
    errors = []
    for f in ("forecast_id", "domain", "freeze_date", "questions",
              "independence_attestation"):
        if not d.get(f):
            _fail(errors, f"missing top-level field: {f}")
    if errors:
        return errors
    att = d["independence_attestation"].lower()
    if "no" not in att or ("market" not in att and "odds" not in att):
        _fail(errors, "independence_attestation must explicitly attest that no "
                      "market prices/odds/aggregator forecasts were consulted")
    for i, q in enumerate(d["questions"]):
        tag = f"questions[{i}] ({q.get('q', '?')!r})"
        for f in ("q", "base_rate_used", "strongest_opposing_case",
                  "reasoning_summary", "key_sources", "p_raw"):
            if q.get(f) in (None, "", [], {}):
                _fail(errors, f"{tag}: missing field {f}")
                continue
        p = q.get("p_raw")
        if not isinstance(p, (int, float)) or not (0 < float(p) < 1):
            _fail(errors, f"{tag}: p_raw must be a probability strictly in (0,1)")
        br = q.get("base_rate_used") or {}
        if not isinstance(br, dict) or br.get("value") is None or not br.get("reference_class"):
            _fail(errors, f"{tag}: base_rate_used needs reference_class + numeric value (rule 1: base rate first)")
        if len(str(q.get("reasoning_summary", ""))) < 150:
            _fail(errors, f"{tag}: reasoning_summary too thin (<150 chars) - show the base rate and each adjustment")
        if len(str(q.get("strongest_opposing_case", ""))) < 80:
            _fail(errors, f"{tag}: strongest_opposing_case too thin (<80 chars) - steel-man it (rule 2)")
        srcs = q.get("key_sources") or []
        if len(srcs) < 2:
            _fail(errors, f"{tag}: need >= 2 key_sources")
        for s in srcs:
            url = str(s.get("url", "")).lower()
            for dom in BANNED_MARKET_DOMAINS:
                if dom in url:
                    _fail(errors, f"{tag}: BANNED market/aggregator source {url} "
                                  f"(matched {dom}) - rule 3, independence from M_market")
        text = (str(q.get("reasoning_summary", "")) + " "
                + str(q.get("strongest_opposing_case", ""))).lower()
        for dom in BANNED_MARKET_DOMAINS:
            if dom in text:
                _fail(errors, f"{tag}: reasoning cites banned domain {dom} - rule 3")
    return errors


# ---------------- commit ----------------

def commit(dossier_path):
    d = json.loads(Path(dossier_path).read_text(encoding="utf-8"))
    errors = validate(d)
    if errors:
        print(f"REJECTED {dossier_path}:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    cal = load_calibration()
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fid = d["forecast_id"]

    artifact = {
        "forecast_id": fid, "domain": d["domain"],
        "freeze_date": d["freeze_date"], "resolve_date": d.get("resolve_date"),
        "committed_at_utc": run_at, "researcher": d.get("researcher"),
        "independence_attestation": d["independence_attestation"],
        "calibration": {"a": cal["a"], "b": cal["b"]},
        "questions": [{
            "q": q["q"], "p_raw": round(float(q["p_raw"]), 4),
            "p_research": round(calibrate(q["p_raw"], cal), 4),
            "base_rate_used": q["base_rate_used"],
            "evidence": q.get("evidence", []),
            "strongest_opposing_case": q["strongest_opposing_case"],
            "reasoning_summary": q["reasoning_summary"],
            "key_sources": q["key_sources"],
            # passthrough for benchmark_harness.py: original question id/source
            # so committed research can be turned into a submission file
            **({"benchmark": q["benchmark"]} if q.get("benchmark") else {}),
        } for q in d["questions"]],
        "resolution_source": d.get("resolution_source", ""),
    }
    payload = json.dumps(artifact, indent=1, sort_keys=True)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    artifact_with_sha = dict(artifact, dossier_sha256=digest)
    RDIR.mkdir(parents=True, exist_ok=True)
    out = RDIR / f"{fid}_research.json"
    out.write_text(json.dumps(artifact_with_sha, indent=1, sort_keys=True),
                   encoding="utf-8")

    rows = [{
        "forecast_id": fid, "domain": d["domain"],
        "freeze_date": d["freeze_date"], "resolve_date": d.get("resolve_date"),
        "run_at_utc": run_at, "question": q["q"],
        "p_raw": q["p_raw"], "p_research": q["p_research"],
        "calib_a": cal["a"], "calib_b": cal["b"],
        "base_rate": q["base_rate_used"].get("value"),
        "n_sources": len(q["key_sources"]), "dossier_sha256": digest,
        "resolved": "", "outcome": "", "correct": "",
        "resolution_source": d.get("resolution_source", ""),
    } for q in artifact["questions"]]
    pd.DataFrame(rows, columns=LEDGER_COLS).to_csv(
        LEDGER, mode="a", header=not LEDGER.exists(), index=False)

    print(f"{fid}: sha256 {digest}")
    print(f"  artifact -> {out.relative_to(ROOT)}  (+{len(rows)} ledger rows)")
    for q in artifact["questions"]:
        print(f"  {q['q']:46s} p_raw={q['p_raw']:.3f} p_research={q['p_research']:.3f} "
              f"(base rate {q['base_rate_used'].get('value')})")


def batch(dirpath):
    files = sorted(Path(dirpath).glob("*.json"))
    if not files:
        sys.exit(f"no *.json dossiers in {dirpath}")
    for f in files:
        commit(f)


# ---------------- tune (prints only; never writes) ----------------

def tune():
    if not LEDGER.exists():
        sys.exit("no research ledger yet")
    df = pd.read_csv(LEDGER)
    for c in ("resolved", "outcome"):
        df[c] = df[c].fillna("").astype(str).replace("nan", "")
    df = (df.sort_values("run_at_utc")
            .drop_duplicates(["forecast_id", "question"], keep="last"))
    df = df[(df.resolved.str.len() > 0) & df.outcome.isin(["YES", "NO"])]
    n = len(df)
    if n == 0:
        sys.exit("no resolved research questions yet - nothing to tune on")
    o = (df.outcome == "YES").astype(float).values
    praw = df.p_raw.clip(1e-3, 1 - 1e-3).values
    x = [_logit(p) for p in praw]
    best = None
    import numpy as np
    for a in np.arange(0.5, 3.01, 0.05):
        for b in np.arange(-1.0, 1.01, 0.05):
            pc = np.clip([_sigmoid(a * xi + b) for xi in x], 1e-4, 1 - 1e-4)
            ll = -float(np.mean(o * np.log(pc) + (1 - o) * np.log(1 - pc)))
            if best is None or ll < best[0]:
                best = (ll, round(float(a), 2), round(float(b), 2))
    neutral = -float(np.mean(o * np.log(np.clip(praw, 1e-4, 1)) +
                             (1 - o) * np.log(np.clip(1 - praw, 1e-4, 1))))
    print(f"resolved research questions: n={n}"
          + ("" if n >= MIN_TUNE_N else f"  (< {MIN_TUNE_N}: fit is NOISE, do not adopt)"))
    print(f"neutral (a=1,b=0) mean log loss: {neutral:.4f}")
    print(f"best grid fit: a={best[1]} b={best[2]}  mean log loss {best[0]:.4f}")
    print("This tool never writes. Adopting a fit = user edits "
          "forecasts/research/calibration.json (new commits only; old rows stand).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "brief":
        brief(sys.argv[2])
    elif cmd == "commit":
        commit(sys.argv[2])
    elif cmd == "batch":
        batch(sys.argv[2])
    elif cmd == "tune":
        tune()
    else:
        sys.exit(f"unknown command {cmd}; see docstring")
