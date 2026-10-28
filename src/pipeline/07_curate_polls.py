"""Curate raw Wikipedia poll cells into bloc-level M3 inputs.

polls_wiki_raw.csv (one row per pollster x column) ->
polls_blocs.csv (election_id, bloc, kind, mean, sd, n_polls)

Rules
- column names map to blocs via the election's blocs.csv parties, bloc names,
  or alliance synonyms (NDA/UPA/MGB/...); unmapped columns are logged.
- final-window filter: polls dated within 120 days before polling day; rows
  whose date cannot be parsed are kept (the frozen revision already guarantees
  pre-election) but counted as undated.
- vote-share (pct) preferred; seat projections (seats) kept as fallback kind.
- 'num' cells are ambiguous (plain numbers): treated as seats when <= n_seats
  and the table had no pct cells for that election.
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from ms_lib import META, PROC

MS = META.parent

raw = pd.read_csv(MS / "polls_wiki_raw.csv")
blocs = pd.read_csv(META / "blocs.csv")
el = pd.read_csv(META / "elections.csv").set_index("election_id")

# import the party normalizer from the build script's table
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "b3", Path(__file__).parent / "03_build_multistate.py")

# lift PARTY_ALIASES without executing the build
src = (Path(__file__).parent / "03_build_multistate.py").read_text(encoding="utf8")
ns = {}
exec(src[src.index("PARTY_ALIASES = {"):src.index("def norm_party")], ns)
PARTY_ALIASES = ns["PARTY_ALIASES"]

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
     "nov", "dec"])}

ALLIANCE_SYN = {
    "NDA": "BJP", "NDA+": "BJP", "BJP+": "BJP", "BJP +": "BJP",
    "UPA": "INC", "INC+": "INC", "CONG": "INC", "CONGRESS": "INC",
    "INDIA": "INC", "MGB": "RJD", "MAHAGATHBANDHAN": "RJD", "GA": "RJD",
    "SP+": "SP", "SAD+": "SAD", "LEFT": "CPM", "LEFT FRONT": "CPM",
    "LF": "CPM", "TMC": "AITC", "TMC+": "AITC", "AITC+": "AITC",
    "MVA": "SHSUBT", "MAHAYUTI": "SHS", "AJSU+": "AJSU", "JMM+": "JMM",
    "AIADMK+": "ADMK", "ADMK+": "ADMK", "DMK+": "DMK", "AAP+": "AAP",
    "TRS+": "BRS", "TRS": "BRS", "BRS+": "BRS", "JDS+": "JDS",
    "LDF": "CPM", "UDF": "INC", "SDF": "INC",
    "MAHA VIKAS AGHADI": "INC", "MAHA YUTI": "BJP", "SAD BJP": "SAD",
    "AITC": "AITC", "SM": "CPM", "BHARATIYA JANATA PARTY": "BJP",
    "INDIAN NATIONAL CONGRESS": "INC", "AAM AADMI PARTY": "AAP",
    "SAMAJWADI PARTY": "SP", "BAHUJAN SAMAJ PARTY": "BSP",
    "SHIROMANI AKALI DAL": "SAD", "MAHAJOT": "INC",
    "ALL INDIA TRINAMOOL CONGRESS": "AITC",
    "ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM": "ADMK",
    "DRAVIDA MUNNETRA KAZHAGAM": "DMK",
    "LEFT DEMOCRATIC FRONT (KERALA)": "CPM", "LEFT DEMOCRATIC FRONT": "CPM",
    "UNITED DEMOCRATIC FRONT (KERALA)": "INC", "UNITED DEMOCRATIC FRONT": "INC",
    "NATIONAL DEMOCRATIC ALLIANCE (INDIA)": "BJP",
    "NATIONAL DEMOCRATIC ALLIANCE": "BJP",
    "UNITED PROGRESSIVE ALLIANCE": "INC",
}


def parse_date(s):
    s = str(s).lower()
    yr = re.search(r"(20\d\d)", s)
    mo = None
    for m, i in MONTHS.items():
        if m in s:
            mo = i
    if yr and mo:
        return int(yr.group(1)), mo
    return None


def col_to_bloc(eid, colname):
    c = str(colname)
    if c.lower() == "nan":
        return None
    # wikitable color markup: party name hides inside Template:<name>/meta/color
    tmpl = re.findall(r"Template:([^/]+)/meta/color", c)
    tail = re.split(r"\|", c)[-1].strip()          # '... | | NDA' -> 'NDA'
    head = re.split(r"\|", c)[0].strip()           # 'BJP | style=...' -> 'BJP'
    if "Template:" in c or "style=" in c.lower() or "bgcolor" in c.lower():
        for cand in ([head] if "style" in c.lower() or "bgcolor" in c.lower() else []) \
                + [tail] + tmpl:
            cand = cand.strip()
            if cand and "=" not in cand and "Template" not in cand \
                    and cand.lower() != "nan":
                b = col_to_bloc(eid, cand)
                if b:
                    return b
        return None
    c = re.sub(r"\[\d+\]", "", c)
    c = re.sub(r"\.\d+$", "", c)
    c = re.sub(r"(?i)vote share|\bseats?\b|projection|\(.*?\)", " ", c)
    c = c.replace("|", " ").replace("-", " ").strip().upper()
    c = re.sub(r"\s+", " ", c)
    if not c or c in ("OTHERS", "OTH", "OTHERS+", "HUNG", "LEAD", "MARGIN",
                      "UNDECIDED", "NOTA", "DON'T KNOW", "SAMPLE SIZE"):
        return None
    eb = blocs[blocs.election_id == eid]
    bloc_names = set(eb.bloc)
    # direct bloc name
    if c in bloc_names:
        return c
    c2 = c.rstrip("+").strip()
    if c2 in bloc_names:
        return c2
    # party code / full name -> bloc
    party = PARTY_ALIASES.get(c, PARTY_ALIASES.get(c2, c2))
    hit = eb[eb.party == party]
    if len(hit):
        return hit.iloc[0].bloc
    # alliance synonym -> anchor party -> bloc
    anchor = ALLIANCE_SYN.get(c, ALLIANCE_SYN.get(c2))
    if anchor:
        hit = eb[eb.party == anchor]
        if len(hit):
            return hit.iloc[0].bloc
    return None


out_rows, unmapped = [], {}
for eid, d in raw.groupby("election_id"):
    if eid not in el.index:
        continue
    pyear = int(eid[-4:])
    pdate_month = None  # use freeze_note month
    note = str(el.loc[eid, "freeze_note"])
    pd_parse = parse_date(note + f" {pyear}")
    if pd_parse:
        pdate_month = pd_parse[1]
    n_seats = int(el.loc[eid, "n_seats"])
    d = d.copy()
    d["bloc"] = [col_to_bloc(eid, c) for c in d.col]
    for c in d[d.bloc.isna()].col.unique():
        unmapped.setdefault(eid, set()).add(str(c))
    d = d[d.bloc.notna()]
    # date window
    keep = []
    for _, r in d.iterrows():
        dt = parse_date(r.date)
        if dt is None:
            keep.append(True)      # undated: keep (frozen rev is pre-election)
            continue
        yy, mm = dt
        months_before = (pyear - yy) * 12 + (pdate_month or 1) - mm
        keep.append(-1 <= months_before <= 4)
    d = d[pd.Series(keep, index=d.index)]
    if d.empty:
        continue
    # prefer the tight final window (within ~2 months, dated) when it has
    # enough polls; multi-month tracker tables otherwise smuggle stale rows in
    tight = []
    for _, r in d.iterrows():
        dt = parse_date(r.date)
        if dt is None:
            tight.append(False)
            continue
        yy, mm = dt
        months_before = (pyear - yy) * 12 + (pdate_month or 1) - mm
        tight.append(-1 <= months_before <= 2)
    tight = pd.Series(tight, index=d.index)
    if (d[tight].groupby(["bloc", "kind"]).agency.nunique() >= 3).any():
        d = d[tight]
    # num -> seats when plausible and no pct for that (election, bloc)
    has_pct = set(d[d.kind == "pct"].bloc)
    d.loc[(d.kind == "num") & (~d.bloc.isin(has_pct)) & (d.value <= n_seats)
          & (d.value > 1), "kind"] = "seats"
    d.loc[(d.kind == "num") & (d.value <= 70) & (d.bloc.isin(has_pct)), "kind"] = "pct"
    d = d[d.kind.isin(["pct", "seats"])]
    for (bloc, kind), g in d.groupby(["bloc", "kind"]):
        # one value per agency (same agency may appear in several tables)
        g2 = g.groupby("agency").value.mean()
        sd = float(g2.std(ddof=1)) if len(g2) > 1 else np.nan
        # incoherent vote-share extraction (pollsters within 1-2 months do not
        # genuinely disagree by 8+ pts on a share) -> parse artifact, drop
        if kind == "pct" and np.isfinite(sd) and sd > 8:
            continue
        out_rows.append({"election_id": eid, "bloc": bloc, "kind": kind,
                         "mean": round(float(g2.mean()), 2),
                         "sd": round(sd, 2) if np.isfinite(sd) else np.nan,
                         "n_polls": len(g2)})

out = pd.DataFrame(out_rows)
out.to_csv(PROC / "polls_blocs.csv", index=False)
print(out.to_string(index=False))
print("\nelections with usable polls:", out.election_id.nunique())
print("\nunmapped columns (check for misses):")
for eid, cols in sorted(unmapped.items()):
    print(f"  {eid}: {sorted(cols)[:8]}")
