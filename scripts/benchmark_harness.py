"""Benchmark-entry harness: run M_research on external benchmark question sets
(ForecastBench, Metaculus bot tournaments) and build their submission files.

Pipeline (see docs/benchmark_entry.md for the full account/deadline details):
  1. Get questions
       fetch-metaculus : pull open binary questions from a Metaculus
                         tournament via the public API (anonymous read works;
                         METACULUS_TOKEN env var used if set)
       ForecastBench   : download the question set file yourself from
                         github.com/forecastingresearch/forecastbench-datasets
                         (datasets/question_sets/<due_date>-llm.json, published
                         00:00 UTC on the due date)
  2. normalize <file>   : convert either format into dossier SKELETONS under
                          forecasts/research/dossiers/benchmarks/, chunked, each
                          question carrying a `benchmark` passthrough block
                          ({source, id, ...}) that m_research.py preserves.
  3. The LLM operator session fills each skeleton following the m_research
     protocol (base rate first, opposing case, NO market prices - and note
     that ForecastBench MARKET questions ask you to predict a market's
     resolution, which is fine; you still never look up its current price),
     then commits: python scripts/m_research.py batch <dir>
     -> every benchmark forecast lands in research_ledger.csv, hashed,
        scoreable by scripts/score.py like everything else.
  4. Build the submission
       submission forecastbench <question_set.json> --org ORG --model MODEL
           -> data/benchmarks/<due_date>.<org>.1.json (upload to the GCP
              folder ForecastBench assigns at registration)
       submission metaculus
           -> data/benchmarks/metaculus_payload.json: a list of
              {question, source:"api", probability_yes, ...} objects plus
              reasoning comments, ready to POST to
              https://www.metaculus.com/api/questions/forecast/
              with header "Authorization: Token $METACULUS_TOKEN".
              Pass --post to actually submit (requires METACULUS_TOKEN).

Unfilled questions: a skeleton question whose p_raw is null is skipped at
normalize->submission time and reported. ForecastBench requires >= 95%
coverage to be ranked; the report tells you how far you are.

Honest-accounting notes:
  - Benchmark forecasts enter research_ledger.csv at commit, BEFORE outcomes
    are knowable - the same pre-registration law as every other ledger.
  - ForecastBench dataset questions ask for up to 8 horizons (due date +7,
    +30, +90, +180, +365, +1095, +1825, +3650 days). The skeleton creates one
    sub-question per horizon, suffixed " | horizon <date>".
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RDIR = ROOT / "forecasts" / "research"
BDOSS = RDIR / "dossiers" / "benchmarks"
BDATA = ROOT / "data" / "benchmarks"
MC_API = "https://www.metaculus.com/api"
FB_HORIZON_DAYS = [7, 30, 90, 180, 365, 1095, 1825, 3650]
CHUNK = 25  # questions per dossier skeleton


def _get(url, token=None):
    req = urllib.request.Request(url, headers={
        # Metaculus' WAF 403s non-browser user agents on anonymous reads
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) psephos-harness/1.0",
        "Accept": "application/json",
        **({"Authorization": f"Token {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            sys.exit(f"HTTP {e.code} from {url.split('?')[0]} - Metaculus refused the "
                     f"request. Anonymous API reads are often blocked; set METACULUS_TOKEN "
                     f"(bot-account token, see docs/benchmark_entry.md) and retry.")
        raise


def _skeleton_q(qtext, benchmark, note=""):
    return {
        "q": qtext,
        "benchmark": benchmark,
        "resolution_note": note,
        "base_rate_used": {"reference_class": None, "value": None, "source": None},
        "evidence": [],
        "strongest_opposing_case": None,
        "reasoning_summary": None,
        "key_sources": [],
        "p_raw": None,
    }


def _write_skeletons(fid_prefix, domain, resolve_date, questions, due_date):
    BDOSS.mkdir(parents=True, exist_ok=True)
    chunks = [questions[i:i + CHUNK] for i in range(0, len(questions), CHUNK)]
    for n, chunk in enumerate(chunks, 1):
        fid = f"{fid_prefix}-{n:03d}"
        out = BDOSS / f"{fid}.json"
        out.write_text(json.dumps({
            "forecast_id": fid, "domain": domain,
            "freeze_date": due_date, "resolve_date": resolve_date,
            "researcher": "FILL: model/session id",
            "resolution_source": "per-question benchmark resolution criteria (see each question's benchmark block)",
            "independence_attestation": "FILL after research: attest that no betting odds, prediction-market prices or forecast-aggregator numbers were consulted.",
            "questions": chunk,
        }, indent=1), encoding="utf-8")
        print(f"  skeleton -> {out.relative_to(ROOT)}  ({len(chunk)} questions)")
    print(f"{len(questions)} questions in {len(chunks)} skeleton(s). Fill p_raw + "
          f"required fields per the m_research protocol, then:\n"
          f"  python scripts/m_research.py batch {BDOSS.relative_to(ROOT)}")


# ---------------- fetch: metaculus ----------------

def fetch_metaculus(tournament, limit):
    token = os.environ.get("METACULUS_TOKEN")
    url = (f"{MC_API}/posts/?limit={limit}&offset=0&order_by=-hotness"
           f"&forecast_type=binary&tournaments={tournament}&statuses=open"
           f"&include_description=true")
    data = _get(url, token)
    posts = data.get("results", [])
    BDATA.mkdir(parents=True, exist_ok=True)
    raw_out = BDATA / f"metaculus_t{tournament}_raw.json"
    raw_out.write_text(json.dumps(data, indent=1), encoding="utf-8")
    questions = []
    for p in posts:
        q = p.get("question") or {}
        if q.get("type") != "binary":
            continue
        questions.append(_skeleton_q(
            q.get("title") or p.get("title"),
            {"source": "metaculus", "question_id": q.get("id"),
             "post_id": p.get("id"), "tournament": tournament,
             "scheduled_close": q.get("scheduled_close_time")},
            note=(q.get("resolution_criteria") or "")[:500]))
    print(f"fetched {len(posts)} posts, {len(questions)} open binary questions "
          f"-> {raw_out.relative_to(ROOT)}")
    if questions:
        _write_skeletons(f"MC{tournament}", "Metaculus tournament",
                         None, questions, str(date.today()))


# ---------------- normalize: forecastbench ----------------

def normalize_forecastbench(path):
    qs = json.loads(Path(path).read_text(encoding="utf-8"))
    due = qs["forecast_due_date"]
    due_d = date.fromisoformat(due)
    questions = []
    for q in qs["questions"]:
        if isinstance(q.get("id"), list):
            continue  # combination questions: dropped per current FB rules
        bench = {"source": q["source"], "id": q["id"],
                 "question_set": qs["question_set"], "forecast_due_date": due}
        is_market = q.get("source") in ("kalshi", "manifold", "metaculus", "polymarket")
        if is_market:
            questions.append(_skeleton_q(
                q.get("question", str(q["id"])),
                dict(bench, resolution_date=None),
                note=(q.get("resolution_criteria") or "")[:500]))
        else:
            # use the question's own listed resolution_dates when present
            # (observed 2026-10-25: sets list 5 horizons, not all 8)
            rds = q.get("resolution_dates") or [
                str(due_d + timedelta(days=d)) for d in FB_HORIZON_DAYS]
            for rd in rds:
                questions.append(_skeleton_q(
                    f"{q.get('question', q['id'])} | horizon {rd}",
                    dict(bench, resolution_date=rd),
                    note=(q.get("resolution_criteria") or "")[:500]))
    print(f"{due}: {len(questions)} forecastable (question, horizon) pairs "
          f"(market questions 1 each, dataset questions up to {len(FB_HORIZON_DAYS)} horizons)")
    _write_skeletons(f"FB{due}", "ForecastBench", None, questions, due)


# ---------------- submissions ----------------

def _committed_benchmark_forecasts(prefix):
    """All committed research artifacts whose forecast_id starts with prefix."""
    rows = {}
    for f in sorted(RDIR.glob(f"{prefix}*_research.json")):
        art = json.loads(f.read_text(encoding="utf-8"))
        for q in art["questions"]:
            b = q.get("benchmark")
            if b and q.get("p_research") is not None:
                key = (str(b["id"]), b.get("resolution_date"))
                rows[key] = (b, q)
    return rows


def submission_forecastbench(question_set_path, org, model, n=1):
    qs = json.loads(Path(question_set_path).read_text(encoding="utf-8"))
    due = qs["forecast_due_date"]
    committed = _committed_benchmark_forecasts(f"FB{due}")
    forecasts, missing = [], 0
    for q in qs["questions"]:
        if isinstance(q.get("id"), list):
            continue
        is_market = q.get("source") in ("kalshi", "manifold", "metaculus", "polymarket")
        dates = [None] if is_market else (
            q.get("resolution_dates") or [
                str(date.fromisoformat(due) + timedelta(days=d)) for d in FB_HORIZON_DAYS])
        for rd in dates:
            hit = committed.get((str(q["id"]), rd))
            if not hit:
                missing += 1
                continue
            b, rq = hit
            forecasts.append({"id": q["id"], "source": q["source"],
                              "forecast": rq["p_research"],
                              "resolution_date": rd,
                              "reasoning": rq["reasoning_summary"]})
    out = {"organization": org, "model": model, "model_organization": org,
           "question_set": qs["question_set"], "forecasts": forecasts}
    BDATA.mkdir(parents=True, exist_ok=True)
    path = BDATA / f"{due}.{org}.{n}.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    total = len(forecasts) + missing
    print(f"submission -> {path.relative_to(ROOT)}")
    print(f"covered {len(forecasts)}/{total} (ForecastBench needs >= 95% of each "
          f"question type to rank; missing forecasts impute 0.5)")
    print(f"UPLOAD: copy this file into the team GCP folder (from registration) "
          f"by 23:59:59 UTC on {due}.")


def submission_metaculus(post=False):
    committed = _committed_benchmark_forecasts("MC")
    payload, comments = [], []
    for (qid, _), (b, rq) in committed.items():
        payload.append({"question": int(qid), "source": "api",
                        "probability_yes": rq["p_research"],
                        "probability_yes_per_category": None,
                        "continuous_cdf": None})
        comments.append({"text": rq["reasoning_summary"], "parent": None,
                         "included_forecast": True, "is_private": True,
                         "on_post": b["post_id"]})
    BDATA.mkdir(parents=True, exist_ok=True)
    out = BDATA / "metaculus_payload.json"
    out.write_text(json.dumps({"forecasts": payload, "comments": comments},
                              indent=1), encoding="utf-8")
    print(f"{len(payload)} forecasts -> {out.relative_to(ROOT)}")
    if not post:
        print("dry run. To submit: set METACULUS_TOKEN and re-run with --post, or POST "
              "forecasts to /api/questions/forecast/ and each comment to /api/comments/create/.")
        return
    token = os.environ.get("METACULUS_TOKEN")
    if not token:
        sys.exit("--post requires the METACULUS_TOKEN environment variable (bot account token)")
    for i, fc in enumerate(payload):
        req = urllib.request.Request(
            f"{MC_API}/questions/forecast/", method="POST",
            data=json.dumps([fc]).encode(),
            headers={"Authorization": f"Token {token}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"  q{fc['question']}: HTTP {r.status}")
        creq = urllib.request.Request(
            f"{MC_API}/comments/create/", method="POST",
            data=json.dumps(comments[i]).encode(),
            headers={"Authorization": f"Token {token}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(creq, timeout=60) as r:
            pass


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    cmd = args[0]
    if cmd == "fetch-metaculus":
        t = args[args.index("--tournament") + 1] if "--tournament" in args else "33121"
        lim = args[args.index("--limit") + 1] if "--limit" in args else "50"
        fetch_metaculus(t, lim)
    elif cmd == "normalize":
        normalize_forecastbench(args[1])
    elif cmd == "submission":
        if args[1] == "forecastbench":
            org = args[args.index("--org") + 1]
            model = args[args.index("--model") + 1]
            n = int(args[args.index("--n") + 1]) if "--n" in args else 1
            submission_forecastbench(args[2], org, model, n)
        elif args[1] == "metaculus":
            submission_metaculus(post="--post" in args)
        else:
            sys.exit("submission forecastbench|metaculus")
    else:
        sys.exit(f"unknown command {cmd}; see docstring")
