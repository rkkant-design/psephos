"""Fixture-level EPL forecasts: per-match win/draw/loss probabilities for one
Premier League matchweek, pre-registered in forecasts/matches_ledger.csv under
the same SHA-256 + append-only law as every other ledger.

Why this exists: a title race resolves once a year; 10 matches resolve every
week. Match-level forecasts compound the scored record (Brier/log via
scripts/score.py) ~50x faster than waiting for elections.

Usage: python epl_matches.py [matchweek] [--no-fetch]
       default matchweek = earliest round with no played result.

MODEL v2 (from MW9, 2026-10-24; prospective only - MW1-8 rows were made by v1
and are scored as v1 forecasts forever; model_version column says which):

  v1 -> v2 changes, each fixing a structural blind spot surfaced by the MW8
  miss review (Villa-City, Ipswich draw), not tuned on those results:

  1. TEAM-SPECIFIC PRIORS (replaces shrinkage to the league mean).
     v1 shrank every team's current-season PPG toward the league mean 1.37,
     which mistreats strong teams starting slowly (it dragged Man City to
     mid-table strength). v2 shrinks toward each club's OWN prior:
         strength_t = lam_t * ppg_t + (1 - lam_t) * prior_t
         lam_t      = p_t / (p_t + K_PRIOR),  K_PRIOR = 12 (unchanged)
     where ppg_t = current-season points per game over p_t played matches, and
         prior_t = club's 2025-26 final PPG (final table, Wikipedia
                   "2025-26 Premier League", fetched 2026-10-24; pts/38)
                   for the 17 returning clubs;
         prior_t = 1.05 (historical promoted-side average PPG, stated prior)
                   for the promoted clubs Hull, Ipswich, Coventry.
     Any team missing from TEAM_PRIORS falls back to LEAGUE_PPG with a loud
     warning (should never happen in 2026-27).

  2. MARKET INSTRUMENT PER FIXTURE (benchmark instrument #2).
     Before pre-registration the operator writes dated 1X2 bookmaker odds to
     forecasts/world/EPL_MWxx_context.json (source + fetch date recorded).
     The script de-vigs them (p_i proportional to 1/decimal_odds, normalized
     to 1) and stores market pH/pD/pA + overround + source + date in the
     ledger row and the hashed payload. THE PUBLISHED PICK STAYS THE MODEL'S:
     the market is a benchmark the model must beat, scored side by side in
     scripts/score.py (per-matchweek skill table). If after >= 5 matchweeks
     the market consistently wins, the score report will say so - switching
     or blending the pick source is a user decision, never automatic.
     Missing context file or missing odds for a fixture never blocks
     pre-registration: market columns stay empty, warning printed.

  3. CONGESTION FLAG (measured, NOT yet modeled).
     From the same context file's midweek_matches list (European/domestic cup
     matches), a team is flagged congested when it played a listed midweek
     match within the 4 calendar days before the fixture's kickoff date
     (0 < kickoff_date - midweek_date <= 4 days). Stored as ledger columns
     congestion_home/congestion_away (yes/no) + congestion_note so the effect
     can be MEASURED on resolved matches first; v2 deliberately does NOT
     adjust probabilities by it. Measure first, model later - a congestion
     coefficient without data would be exactly the kind of unstated fitted
     parameter the engine forbids.

  Unchanged from v1 (all priors stated, none fitted on this season):
  - Table recomputed from played matches in the fixture feed.
  - Expected goal margin for home i vs away j:
        delta = C * (s_i - s_j) + HOME_ADV
    C = 1.5 goals per PPG point (league regression heuristic
    points ~ 52 + 0.65*GD over 38 games => gd/game ~ 1.54*(ppg-1.37));
    HOME_ADV = 0.35 goals (long-run PL home edge, stated prior).
  - Total goals MU = 2.75 per match (recent PL seasons, stated prior).
  - lambda_home = (MU+delta)/2, lambda_away = (MU-delta)/2, floored at 0.15;
    independent Poisson scorelines => P(H/D/A) analytically (goals 0..12).

Known coarseness (flagged, not hidden): independent Poisson slightly
underprices draws (no Dixon-Coles correction); no injuries, no rotation
adjustment (congestion is recorded, not priced). Match rows are SCORED
forecasts, never gate CALLs (the model is the published instrument; the
market column is the benchmark instrument - two instruments scored, one
published, zero certified).

Integrity rules: a match whose kickoff (UTC) is already past at run time is
NEVER pre-registered - it is skipped and reported. Pre-registration after
kickoff would corrupt the ledger's whole point. Parameter changes are
prospective only: old ledger rows keep the model_version that made them and
are never re-registered or re-scored under a newer model.
"""
import hashlib
import json
import math
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WDIR = ROOT / "forecasts" / "world"
FIXTURES = WDIR / "epl_fixtures.json"
LEDGER = ROOT / "forecasts" / "matches_ledger.csv"
FEED_URL = "https://fixturedownload.com/feed/json/epl-2026"

MODEL_VERSION = "v2"
K_PRIOR = 12.0
LEAGUE_PPG = 1.37          # fallback only in v2 (v1 shrank everyone to this)
PROMOTED_PRIOR = 1.05      # historical promoted-side average PPG, stated prior
C_GOALS_PER_PPG = 1.5
HOME_ADV = 0.35
MU_TOTAL = 2.75
MAX_GOALS = 12
RESOLUTION = ("fixturedownload.com epl-2026 feed final score; league result after "
              "90min+stoppage; abandoned match resolves on the completed restaging; "
              "awarded/forfeited results count as the official score")

# 2025-26 final Premier League table (Wikipedia "2025-26 Premier League",
# final standings, fetched 2026-10-24): prior_t = points / 38.
# Champions: Arsenal. Relegated: West Ham (39), Burnley (22), Wolves (20) -
# replaced in 2026-27 by promoted Hull, Ipswich, Coventry (PROMOTED_PRIOR).
PRIOR_SOURCE = "Wikipedia 2025-26 Premier League final table (fetched 2026-10-24); promoted sides 1.05 stated prior"
TEAM_PRIORS = {
    "Arsenal":         85 / 38,   # 2.237
    "Man City":        78 / 38,   # 2.053
    "Man Utd":         71 / 38,   # 1.868
    "Aston Villa":     65 / 38,   # 1.711
    "Liverpool":       60 / 38,   # 1.579
    "Bournemouth":     57 / 38,   # 1.500
    "Sunderland":      54 / 38,   # 1.421
    "Brighton":        53 / 38,   # 1.395
    "Brentford":       53 / 38,   # 1.395
    "Chelsea":         52 / 38,   # 1.368
    "Fulham":          52 / 38,   # 1.368
    "Newcastle":       49 / 38,   # 1.289
    "Everton":         49 / 38,   # 1.289
    "Leeds":           47 / 38,   # 1.237
    "Crystal Palace":  45 / 38,   # 1.184
    "Nott'm Forest":   44 / 38,   # 1.158
    "Spurs":           41 / 38,   # 1.079
    "Hull":            PROMOTED_PRIOR,
    "Ipswich":         PROMOTED_PRIOR,
    "Coventry":        PROMOTED_PRIOR,
}

LEDGER_COLS = ["match_id", "matchweek", "date_utc", "home", "away",
               "p_home", "p_draw", "p_away", "lambda_home", "lambda_away",
               "freeze_date", "run_at_utc", "forecast_sha256",
               "resolution_source", "resolved", "outcome", "correct",
               "model_version", "market_ph", "market_pd", "market_pa",
               "market_overround", "market_source", "market_date",
               "congestion_home", "congestion_away", "congestion_note"]


def fetch_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "psephos/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        feed = json.loads(r.read().decode("utf-8"))
    FIXTURES.write_text(json.dumps({
        "source": FEED_URL,
        "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fixtures": feed}, indent=1), encoding="utf-8")
    return feed


def load_feed(no_fetch):
    if not no_fetch:
        try:
            return fetch_feed()
        except Exception as e:
            sys.exit(f"ABORT: fixture feed unreachable ({e}); never substitute memory for a fetch. "
                     f"Re-run with --no-fetch to use the last saved copy ONLY if you accept its staleness.")
    if not FIXTURES.exists():
        sys.exit("ABORT: no saved fixture file and --no-fetch given.")
    return json.loads(FIXTURES.read_text(encoding="utf-8"))["fixtures"]


def table_from(feed):
    pts, played = {}, {}
    for m in feed:
        if m["HomeTeamScore"] is None:
            continue
        h, a, hs, as_ = m["HomeTeam"], m["AwayTeam"], m["HomeTeamScore"], m["AwayTeamScore"]
        for t in (h, a):
            pts.setdefault(t, 0), played.setdefault(t, 0)
        played[h] += 1
        played[a] += 1
        if hs > as_:
            pts[h] += 3
        elif hs < as_:
            pts[a] += 3
        else:
            pts[h] += 1
            pts[a] += 1
    strength, priors_used = {}, {}
    for t in pts:
        prior = TEAM_PRIORS.get(t)
        if prior is None:
            print(f"WARNING: no team prior for {t!r} - falling back to league mean {LEAGUE_PPG}")
            prior = LEAGUE_PPG
        lam = played[t] / (played[t] + K_PRIOR)
        strength[t] = lam * (pts[t] / played[t]) + (1 - lam) * prior
        priors_used[t] = round(prior, 4)
    return strength, pts, played, priors_used


def poisson_pmf(lam, kmax=MAX_GOALS):
    out, p = [], math.exp(-lam)
    for k in range(kmax + 1):
        out.append(p)
        p *= lam / (k + 1)
    return out


def match_probs(s_home, s_away):
    delta = C_GOALS_PER_PPG * (s_home - s_away) + HOME_ADV
    lh = max(0.15, (MU_TOTAL + delta) / 2)
    la = max(0.15, (MU_TOTAL - delta) / 2)
    ph_, pa_ = poisson_pmf(lh), poisson_pmf(la)
    pw = pl = pd_ = 0.0
    for i, pi in enumerate(ph_):
        for j, pj in enumerate(pa_):
            pr = pi * pj
            if i > j:
                pw += pr
            elif i < j:
                pl += pr
            else:
                pd_ += pr
    z = pw + pd_ + pl  # renormalize truncation remainder (~1e-6)
    return pw / z, pd_ / z, pl / z, lh, la


def frac_to_decimal(odds_str):
    """'11/13' -> 1 + 11/13; plain decimals ('1.85') pass through."""
    s = str(odds_str).strip()
    if "/" in s:
        num, den = s.split("/")
        return 1.0 + float(num) / float(den)
    return float(s)


def devig(odds):
    """odds: {'home','draw','away'} fractional/decimal strings.
    Returns (ph, pd, pa, overround): implied probs normalized to 1."""
    imp = {k: 1.0 / frac_to_decimal(odds[k]) for k in ("home", "draw", "away")}
    s = sum(imp.values())
    return (round(imp["home"] / s, 4), round(imp["draw"] / s, 4),
            round(imp["away"] / s, 4), round(s - 1.0, 4))


def load_context(mw):
    """forecasts/world/EPL_MWxx_context.json: dated market odds + midweek match
    list, written by the operator before pre-registration. Optional - its
    absence never blocks the model (market columns stay empty)."""
    p = WDIR / f"EPL_MW{mw:02d}_context.json"
    if not p.exists():
        print(f"WARNING: no context file {p.name} - market + congestion columns will be empty this matchweek.")
        return None
    ctx = json.loads(p.read_text(encoding="utf-8"))
    if ctx.get("matchweek") != mw:
        sys.exit(f"ABORT: {p.name} says matchweek {ctx.get('matchweek')}, expected {mw}.")
    return ctx


def congestion_for(team, kickoff_utc, ctx):
    """yes/no + note: did `team` play a listed midweek match in the 4 calendar
    days before kickoff (0 < kickoff_date - match_date <= 4)? Recorded for
    measurement only - v2 does not adjust probabilities by it."""
    if not ctx or "midweek_matches" not in ctx:
        return "", ""
    ko_date = kickoff_utc.date()
    for m in ctx["midweek_matches"]["matches"]:
        if team not in m["teams"]:
            continue
        d = datetime.strptime(m["date"], "%Y-%m-%d").date()
        gap = (ko_date - d).days
        if 0 < gap <= 4:
            return "yes", f"{m['competition']} {m['date']} ({gap}d before)"
    return "no", ""


def main(argv):
    no_fetch = "--no-fetch" in argv
    args = [a for a in argv if not a.startswith("--")]
    feed = load_feed(no_fetch)
    strength, pts, played, priors_used = table_from(feed)

    if args:
        mw = int(args[0])
    else:
        unplayed = [m["RoundNumber"] for m in feed if m["HomeTeamScore"] is None]
        if not unplayed:
            sys.exit("Season complete: no unplayed fixtures.")
        mw = min(unplayed)

    ctx = load_context(mw)
    market_meta = (ctx or {}).get("market", {})
    market_odds = market_meta.get("odds", {})
    market_source = market_meta.get("source", "")
    market_date = market_meta.get("odds_date", "")

    now = datetime.now(timezone.utc)
    run_at = now.isoformat(timespec="seconds")
    freeze = now.date().isoformat()

    already = set()
    if LEDGER.exists():
        header = LEDGER.read_text(encoding="utf-8").splitlines()[0].split(",")
        if header != LEDGER_COLS:
            sys.exit("ABORT: matches_ledger.csv header does not match the v2 schema. "
                     "New columns are appended trailing, once, by a migration that never "
                     "edits existing cells - do that first, never rewrite rows.")
        led = pd.read_csv(LEDGER)
        already = set(led[led.matchweek == mw].match_id)

    matches, skipped = [], []
    for m in sorted((x for x in feed if x["RoundNumber"] == mw), key=lambda x: x["DateUtc"]):
        mid = f"EPL2627-M{m['MatchNumber']:03d}"
        ko = datetime.strptime(m["DateUtc"], "%Y-%m-%d %H:%M:%SZ").replace(tzinfo=timezone.utc)
        if mid in already:
            skipped.append((mid, "already pre-registered this matchweek"))
            continue
        if ko <= now or m["HomeTeamScore"] is not None:
            skipped.append((mid, f"kickoff {m['DateUtc']} already past - NEVER pre-registered post-hoc"))
            continue
        pw, pd_, pl, lh, la = match_probs(strength[m["HomeTeam"]], strength[m["AwayTeam"]])

        if mid in market_odds:
            mph, mpd, mpa, over = devig(market_odds[mid])
            msrc, mdate = market_source, market_date
        else:
            if ctx:
                print(f"WARNING: no market odds for {mid} in context file - market columns empty.")
            mph = mpd = mpa = over = ""
            msrc = mdate = ""

        ch, ch_note = congestion_for(m["HomeTeam"], ko, ctx)
        ca, ca_note = congestion_for(m["AwayTeam"], ko, ctx)
        notes = "; ".join(x for x in (f"home: {ch_note}" if ch_note else "",
                                      f"away: {ca_note}" if ca_note else "") if x)

        matches.append({
            "match_id": mid, "matchweek": mw, "date_utc": m["DateUtc"],
            "home": m["HomeTeam"], "away": m["AwayTeam"],
            "p_home": round(pw, 4), "p_draw": round(pd_, 4), "p_away": round(pl, 4),
            "lambda_home": round(lh, 3), "lambda_away": round(la, 3),
            "model_version": MODEL_VERSION,
            "market_ph": mph, "market_pd": mpd, "market_pa": mpa,
            "market_overround": over, "market_source": msrc, "market_date": mdate,
            "congestion_home": ch, "congestion_away": ca, "congestion_note": notes,
        })

    if not matches:
        print(f"MW{mw}: nothing to pre-register ({len(skipped)} skipped).")
        for mid, why in skipped:
            print(f"  skipped {mid}: {why}")
        return

    payload_obj = {
        "forecast_id": f"EPL2627-MW{mw:02d}", "matchweek": mw,
        "model_version": MODEL_VERSION,
        "freeze_date": freeze, "run_at_utc": run_at,
        "priors": {"k": K_PRIOR, "team_priors_used": {t: priors_used[t] for t in sorted(priors_used)},
                   "prior_source": PRIOR_SOURCE, "promoted_prior": PROMOTED_PRIOR,
                   "league_ppg_fallback": LEAGUE_PPG,
                   "c_goals_per_ppg": C_GOALS_PER_PPG,
                   "home_adv_goals": HOME_ADV, "mu_total": MU_TOTAL,
                   "note": ("v2: shrink to club's own prior (last season final PPG / promoted avg), "
                            "independent Poisson, no Dixon-Coles draw correction; market column is "
                            "benchmark instrument #2 (pick stays the model's); congestion recorded, "
                            "not priced - measure first, model later")},
        "market": {"source": market_source, "source_url": market_meta.get("source_url", ""),
                   "odds_date": market_date, "fetched_utc": market_meta.get("fetched_utc", ""),
                   "raw_odds": market_odds},
        "congestion_basis": (ctx or {}).get("midweek_matches", {}),
        "table_basis": {t: {"p": played[t], "pts": pts[t], "prior": priors_used[t],
                            "ppg_shrunk": round(strength[t], 4)}
                        for t in sorted(strength, key=lambda x: -pts[x])},
        "resolution": RESOLUTION,
        "matches": matches,
    }
    payload = json.dumps(payload_obj, indent=1, sort_keys=True)
    out_json = WDIR / f"EPL_MW{mw:02d}_forecast.json"
    out_json.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode()).hexdigest()

    rows = [{**m, "freeze_date": freeze, "run_at_utc": run_at, "forecast_sha256": digest,
             "resolution_source": RESOLUTION, "resolved": "", "outcome": "", "correct": ""}
            for m in matches]
    pd.DataFrame(rows, columns=LEDGER_COLS).to_csv(
        LEDGER, mode="a", header=not LEDGER.exists(), index=False)

    print(f"MW{mw}: pre-registered {len(rows)} matches ({MODEL_VERSION}) -> {out_json.name}; ledger +{len(rows)} rows")
    print(f"sha256: {digest}")
    for m in matches:
        mkt = (f"  mkt H {m['market_ph']:.0%}/D {m['market_pd']:.0%}/A {m['market_pa']:.0%}"
               if m["market_ph"] != "" else "  mkt -")
        cong = "".join(c for c, f in (("H", m["congestion_home"]), ("A", m["congestion_away"])) if f == "yes")
        print(f"  {m['home']:16s} v {m['away']:16s} H {m['p_home']:.0%} / D {m['p_draw']:.0%} / A {m['p_away']:.0%}"
              f"{mkt}{'  cong:' + cong if cong else ''}")
    for mid, why in skipped:
        print(f"  skipped {mid}: {why}")


if __name__ == "__main__":
    main(sys.argv[1:])
