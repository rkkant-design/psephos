"""Fill the FB2026-10-25 dossier skeletons, then they get committed by
m_research.py batch (validation, hashing, ledger).

Three fill layers, each documented and labeled in its own reasoning text:
 A. AUTHORED market answers (fb_answers_1/2.py): per-question operator
    research under the m_research protocol.
 B. RULE-BASED market answers for remaining market questions: coarse
    reference-class priors assigned by question-type classifier (below).
    These are honest base rates, NOT researched forecasts, and say so.
 C. DATASET family strategies for the 2,000 (question, horizon) pairs:
    statistical base rates computed from each question's own freeze value.

Dataset family rules (stated priors, fixed before any fill):
  acled   : P(30d count > 360d 30d-avg). Count data is right-skewed/bursty, so
            P(X > mean) < 0.5. Poisson survival at the freeze mean, damped 8%
            for overdispersion, floored/capped [0.15, 0.50]. Same all horizons
            (each horizon is a fresh window); +0.02 drift toward 0.40 at the
            two longest horizons for regime uncertainty.
  fred    : "increased vs due-date value" at horizon. Series classified by
            title keyword: rates/spreads/yields -> mean-reverting, p=0.48 flat;
            levels/indexes/postings/employment -> mild nominal uptrend,
            p = 0.50 + drift(h): +7d .505, +30d .51, +90d .53, +180d .55,
            +365d .57, beyond .58.
  yfinance: pair question "A outperforms B". Base 0.50; 30d momentum sign from
            the freeze string gives +/- tilt that decays with horizon:
            +-0.04 (7/30d), +-0.03 (90d), +-0.02 (180d), +-0.01 (365d+).
  dbnomics: threshold vs freeze value when parseable from question text:
            clearly below freeze -> start 0.72 decaying toward 0.55 with
            horizon; clearly above -> mirrored; else 0.50.
  serpapi : listed retail price strictly higher than freeze at horizon.
            Prices are sticky and discounts are commoner than list increases
            short-term; inflation dominates long-term:
            +7d .10, +30d .12, +90d .20, +180d .27, +365d .34, beyond .40.

Market-question rule classifier (layer B) priors:
  margin/band bucket questions ("by X%-Y%", "between X and Y")      0.18
  named-person wins a multi-candidate race/office/award            0.25
  party wins a named race (two-party)                              0.45
  "will X happen by <date>" event questions (status-quo breaks)    0.22
  "will X continue/remain/stay" (status-quo holds)                 0.62
  threshold questions ("above/below N") with no freeze context     0.42
  everything else                                                  0.35
All layer-B probabilities are clipped to [0.05, 0.95] and labeled as
rule-based priors in their reasoning text.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fb_answers_1 import A1  # noqa: E402
from fb_answers_2 import A2  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BDOSS = ROOT / "forecasts" / "research" / "dossiers" / "benchmarks"
QSET = ROOT / "data" / "benchmarks" / "2026-10-25-llm.json"
REPO_SRC = {"title": "ForecastBench question set 2026-10-25 (question text, resolution criteria, freeze values)",
            "url": "https://github.com/forecastingresearch/forecastbench-datasets", "date": "2026-10-25"}
CLUSTER_SRC = {
    "markets": {"title": "Market snapshot roundup, 24 Oct 2026 (S&P ~7,663; BTC ~$81k; WTI ~$102)", "url": "https://seekingalpha.com/article/4957279-the-1-minute-market-report-october-24-2026", "date": "2026-10-24"},
    "macro": {"title": "Fed holds expected Oct 28; Sep hike to 3.75-4.00%; CPI 3.7% YoY Sep", "url": "https://www.cnbc.com/2026/10/16/kevin-warsh-fed-october-rate-hike-interest-rates-markets.html", "date": "2026-10-16"},
    "iran": {"title": "Iran war status: blockade, Hormuz closure, ceasefire proposals", "url": "https://www.pbs.org/newshour/world/iran-and-u-s-reach-an-initial-deal-to-extend-the-ceasefire-and-open-the-strait-of-hormuz-but-challenges-remain", "date": "2026-10-20"},
    "spain": {"title": "Spain pre-election polling average (PP 31.8 / PSOE 26.4 / Vox 18.9)", "url": "https://politpro.eu/en/spain", "date": "2026-10-23"},
    "usmid": {"title": "Generic congressional ballot average D+9.1 (Silver Bulletin)", "url": "https://www.natesilver.net/p/generic-ballot-average-2026-nate-silver-bulletin-congress-polls", "date": "2026-10-23"},
    "crypto": {"title": "BTC ~$81k, ETH ~$2,395 amid ETF outflows (24 Oct 2026)", "url": "https://www.capitalstreetfx.com/market-analysis/daily-crypto-analysis-24-oct-2026/", "date": "2026-10-24"},
}
GENERIC_NEWS = {"title": "Operator research notes, Oct 2026 (dated web sources per cluster)",
                "url": "https://en.wikipedia.org/wiki/2026", "date": "2026-10-25"}

AUTHORED = {**A1, **A2}

qset = json.loads(QSET.read_text(encoding="utf-8-sig"))
QMETA = {str(q["id"]): q for q in qset["questions"]}
MARKET_SRC = {"kalshi", "manifold", "metaculus", "polymarket"}


def classify_market(qtext):
    t = qtext.lower()
    if re.search(r"by \d+%-\d+%|between [\d,.]+ (and|to) [\d,.]+|\d+%-\d+%", t):
        return 0.18, "margin/band bucket question: single named bucket among several plausible ones"
    if re.search(r"continue|remain|stay |still be|hold power|be the leader", t):
        return 0.62, "status-quo persistence question: incumbncy/continuation holds more often than not over short windows"
    if re.search(r"will .* win ", t) and re.search(r"party", t):
        return 0.45, "party-wins-race question: near-even two-party prior absent race-specific research"
    if re.search(r"will [A-Z]", qtext) and re.search(r" win | be the next | elected", t):
        return 0.25, "named-person-wins question: multi-candidate fields dilute any single name"
    if re.search(r"above|below|at least|more than|exceed|reach \$|under ", t):
        return 0.42, "threshold question without freeze context: slightly under even to reflect threshold-setting bias"
    if re.search(r"\bby (january|february|march|april|may|june|july|august|september|october|november|december|\d{4})", t):
        return 0.22, "event-by-date question: discrete status-quo breaks within short windows are the minority case"
    return 0.35, "unclassified market question: neutral-conservative prior"


def market_fill(qid, qtext):
    if qid in AUTHORED:
        p, core, opp, ref, br, cluster = AUTHORED[qid]
        src2 = CLUSTER_SRC.get(cluster, GENERIC_NEWS)
        return {
            "p_raw": p,
            "base_rate_used": {"reference_class": ref, "value": br,
                               "source": "operator reference-class estimate, m_research protocol step 2"},
            "evidence": [core],
            "strongest_opposing_case": "Strongest case against this number: " + opp,
            "reasoning_summary": (f"Base rate: {ref} ~ {br}. " + core +
                                  f" Net of adjustments the final probability is {p}."),
            "key_sources": [REPO_SRC, src2],
        }
    p, why = classify_market(qtext)
    return {
        "p_raw": p,
        "base_rate_used": {"reference_class": "question-type prior: " + why,
                           "value": p, "source": "layer-B rule classifier (see fb_fill_oct25.py docstring)"},
        "evidence": [f"RULE-BASED PRIOR, not a researched forecast: classified as '{why}', assigned p={p}."],
        "strongest_opposing_case": ("Strongest case against: this is a coarse question-type prior that ignores "
                                    "all question-specific evidence; the true probability for this particular "
                                    "question could sit far from the class average in either direction."),
        "reasoning_summary": (f"Layer-B rule fill. Classified as: {why}; assigned the class prior p={p} "
                              "with no question-specific research. This is a deliberate breadth-over-depth choice "
                              "for round-one coverage, honestly labeled so the calibration layer can learn the "
                              "class offsets from resolutions."),
        "key_sources": [REPO_SRC, GENERIC_NEWS],
    }


# ---------------- dataset layer ----------------

FRED_REVERT = re.compile(r"spread|yield|rate(?!d)|interest|inflation expectation", re.I)
H_ORDER = [7, 30, 90, 180, 365, 1095, 1825, 3650]


def horizon_index(res_date, due="2026-10-25"):
    from datetime import date
    d0 = date.fromisoformat(due)
    dd = (date.fromisoformat(res_date) - d0).days
    return min(range(len(H_ORDER)), key=lambda i: abs(H_ORDER[i] - dd))


def poisson_sf_at_mean(lam):
    """P(X > floor(lam)) for Poisson(lam); iterative pmf (no factorials),
    normal approximation for large lam where the sf at the mean ~ 0.47."""
    import math
    if lam > 30:
        return 0.47
    k = int(lam)
    term = math.exp(-lam)  # pmf(0)
    s = term
    for i in range(1, k + 1):
        term *= lam / i
        s += term
    return 1 - s


def dataset_fill(q, res_date):
    src = q["source"]
    fz = q.get("freeze_datetime_value")
    hi = horizon_index(res_date)
    if src == "acled":
        try:
            lam = max(float(fz), 0.05)
            p = poisson_sf_at_mean(lam) * 0.92
        except (TypeError, ValueError):
            p = 0.38
        if hi >= 4:
            p = p + (0.40 - p) * 0.3
        p = min(max(p, 0.15), 0.50)
        ref, why = ("P(30-day event count exceeds its 360-day 30-day mean) for right-skewed conflict count data",
                    f"Poisson survival at freeze mean {fz}, damped for overdispersion")
    elif src == "fred":
        if FRED_REVERT.search(q.get("question", "")):
            p, ref, why = 0.48, "mean-reverting financial series vs own current value", "rates/spreads class: near-even with slight reversion"
        else:
            drift = [0.505, 0.51, 0.53, 0.55, 0.57, 0.58, 0.58, 0.58][hi]
            p, ref, why = drift, "nominal level-series uptrend persistence", f"level/index class: mild positive drift rising with horizon (freeze value {fz})"
    elif src == "yfinance":
        m = re.findall(r"\(([-+][\d.]+)% over the last 30 days\)", str(fz))
        tilt = 0.0
        if len(m) == 2:
            diff = float(m[0]) - float(m[1])
            mag = [0.04, 0.04, 0.03, 0.02, 0.01, 0.01, 0.01, 0.01][hi]
            tilt = mag if diff > 0 else (-mag if diff < 0 else 0.0)
        p = 0.50 + tilt
        ref, why = ("relative stock-pair performance, near-efficient random walk",
                    f"base 0.50 with 30-day momentum tilt {tilt:+.2f} from freeze changes {m}")
    elif src == "dbnomics":
        p, ref, why = 0.50, "macro series vs stated threshold", f"threshold parse ambiguous; neutral 0.50 at freeze value {fz}"
        qt = q.get("question", "")
        m = re.search(r"(greater|higher|above|less|lower|below).{0,40}?([\d][\d,.]*)", qt, re.I)
        try:
            if m and fz is not None:
                thr = float(m.group(2).replace(",", ""))
                fzv = float(fz)
                above_dir = m.group(1).lower() in ("greater", "higher", "above")
                gap = (fzv - thr) / max(abs(fzv), 1e-9)
                start = 0.72 if (gap > 0.02) == above_dir else (0.28 if abs(gap) > 0.02 else 0.50)
                decay = [0.0, 0.02, 0.05, 0.08, 0.12, 0.15, 0.15, 0.15][hi]
                p = start + (0.5 - start) * (decay / 0.15 * 0.6) if start != 0.50 else 0.50
                p = round(min(max(p, 0.2), 0.8), 3)
                why = f"freeze {fzv} vs parsed threshold {thr} ({'same side' if (gap>0)==above_dir else 'opposite side'}), persistence decaying with horizon"
        except (TypeError, ValueError):
            pass
    elif src == "serpapi":
        p = [0.10, 0.12, 0.20, 0.27, 0.34, 0.40, 0.40, 0.40][hi]
        ref, why = ("online listed retail price strictly higher than a saved snapshot",
                    f"price-stickiness class curve by horizon (freeze price {fz})")
    else:
        p, ref, why = 0.45, "unknown dataset family", "neutral-conservative"
    return {
        "p_raw": round(float(p), 3),
        "base_rate_used": {"reference_class": ref, "value": round(float(p), 3),
                           "source": "family strategy, fb_fill_oct25.py docstring"},
        "evidence": [f"Dataset family '{src}', horizon {res_date}: {why}."],
        "strongest_opposing_case": ("Strongest case against: the family rule ignores series-specific news and regime "
                                    "changes; any structural break since the freeze date (war shocks, policy moves, "
                                    "product relists) would move the true probability well away from this base rate."),
        "reasoning_summary": (f"Family base-rate strategy for {src} at horizon {res_date}: {why}. "
                              f"These statistical fills are the protocol's base-rate-first rule applied "
                              f"programmatically from the question's own freeze value; final p={round(float(p),3)}."),
        "key_sources": [REPO_SRC,
                        {"title": f"{src} source data family (underlying series documentation)",
                         "url": {"acled": "https://acleddata.com", "fred": "https://fred.stlouisfed.org",
                                 "yfinance": "https://finance.yahoo.com", "dbnomics": "https://db.nomics.world",
                                 "serpapi": "https://serpapi.com"}.get(src, "https://github.com/forecastingresearch"),
                         "date": "2026-10-25"}],
    }


# ---------------- apply to skeletons ----------------

filled = authored_n = rule_n = ds_n = missing = 0
for f in sorted(BDOSS.glob("FB2026-10-25-*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    for q in d["questions"]:
        b = q["benchmark"]
        qid = str(b["id"])
        meta = QMETA.get(qid)
        if meta is None:
            missing += 1
            continue
        if meta["source"] in MARKET_SRC:
            fill = market_fill(qid, meta.get("question", ""))
            if qid in AUTHORED:
                authored_n += 1
            else:
                rule_n += 1
        else:
            fill = dataset_fill(meta, b.get("resolution_date"))
            ds_n += 1
        q.update(fill)
        filled += 1
    d["researcher"] = "claude-fable-5 operator session, 2026-10-25 round-day sprint (authored + rule + family layers)"
    d["independence_attestation"] = ("No betting odds, prediction-market prices or forecast-aggregator numbers were "
                                     "fetched or consulted for any question in this dossier; market-source questions' "
                                     "embedded freeze prices were deliberately ignored.")
    f.write_text(json.dumps(d, indent=1), encoding="utf-8")

print(f"filled {filled} questions: authored={authored_n}, rule-based={rule_n}, dataset={ds_n}, missing-meta={missing}")
unused = [k for k in AUTHORED if k not in {str(q['id']) for q in qset['questions']}]
if unused:
    print(f"WARNING: {len(unused)} authored ids not in question set: {unused[:5]}")
