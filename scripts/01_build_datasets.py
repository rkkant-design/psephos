"""Build processed constituency-level datasets for UP retrodiction pilot.

Outputs (data/processed/):
  ae2012.csv, ae2017.csv, ae2022.csv  - one row per (constituency, party) with vote share
  state_shares.csv                    - state-level party vote shares per election (AE + GE)
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

MAIN = {"BJP", "SP", "BSP", "INC", "RLD", "AD", "ADAL", "SBSP", "NISHAD", "NINSHAD"}

def norm_party(p):
    p = str(p).strip().upper()
    aliases = {
        "APNA DAL (SONEYLAL)": "AD", "APNA DAL": "AD", "ADAL": "AD", "AD(S)": "AD",
        "APNA DAL (SONELAL)": "AD",
        "SUHELDEV BHARATIYA SAMAJ PARTY": "SBSP",
        "NISHAD (NIRBAL INDIAN SHOSHIT HAMARA AAM DAL)": "NISHAD", "NINSHAD": "NISHAD",
        "RASHTRIYA LOK DAL": "RLD",
        "SAMAJWADI PARTY": "SP", "BAHUJAN SAMAJ PARTY": "BSP",
        "BHARATIYA JANATA PARTY": "BJP", "INDIAN NATIONAL CONGRESS": "INC",
    }
    return aliases.get(p, p)

def norm_const(c):
    return (
        str(c).upper().replace(".", " ").replace("-", " ").replace("(SC)", "").replace("(ST)", "")
        .replace("_", " ").strip()
    )

# ---------- 2012 (DataMeet, candidate level) ----------
dm = pd.read_csv(RAW / "datameet_assembly.csv", encoding="latin-1", low_memory=False)
dm = dm[(dm.ST_NAME == "Uttar Pradesh") & (dm.YEAR.astype(str) == "2012")].copy()
dm["VOTES"] = pd.to_numeric(dm.VOTES, errors="coerce").fillna(0)
dm["party"] = dm.PARTY.map(norm_party)
dm["const"] = dm.AC_NAME.map(norm_const)
tot = dm.groupby("AC_NO").VOTES.sum().rename("total")
dm = dm.join(tot, on="AC_NO")
dm["share"] = 100 * dm.VOTES / dm.total
ae2012 = dm.groupby(["AC_NO", "const", "party"], as_index=False).agg(share=("share", "sum"))
ae2012.rename(columns={"AC_NO": "ac_no"}, inplace=True)
ae2012.to_csv(OUT / "ae2012.csv", index=False)

# ---------- 2017 (TCPD, candidate level) ----------
tc = pd.read_csv(RAW / "up2017" / "TCPD_AE_Uttar_Pradesh_2021-10-3.csv", low_memory=False)
tc = tc[tc.Year == 2017].copy()
tc["party"] = tc.Party.map(norm_party)
tc["const"] = tc.Constituency_Name.map(norm_const)
tc["share"] = pd.to_numeric(tc.Vote_Share_Percentage, errors="coerce").fillna(0)
ae2017 = tc.groupby(["Constituency_No", "const", "party"], as_index=False).agg(share=("share", "sum"))
ae2017.rename(columns={"Constituency_No": "ac_no"}, inplace=True)
ae2017.to_csv(OUT / "ae2017.csv", index=False)

# ---------- 2022 (ECI via Kaggle, candidate level) ----------
e22 = pd.read_csv(RAW / "up2022" / "upresults.csv", low_memory=False)
e22["votes"] = pd.to_numeric(e22.total_votes, errors="coerce").fillna(0)
e22["party"] = e22.party.map(norm_party)
e22["const"] = e22.constituency.map(norm_const)
tot22 = e22.groupby("const").votes.sum().rename("total")
e22 = e22.join(tot22, on="const")
e22["share"] = 100 * e22.votes / e22.total
ae2022 = e22.groupby(["const", "party"], as_index=False).agg(share=("share", "sum"))
ae2022.to_csv(OUT / "ae2022.csv", index=False)

# ---------- state-level shares ----------
rows = []
for name, df in (("AE2012", ae2012), ("AE2017", ae2017), ("AE2022", ae2022)):
    # national-vote-weighted: average of constituency shares (equal weight per AC is fine for pilot)
    n_ac = df.groupby("const").ngroups if "ac_no" not in df.columns else df.ac_no.nunique()
    s = df.groupby("party").share.sum() / n_ac
    for p, v in s.items():
        rows.append({"election": name, "party": p, "share": round(v, 2)})

ge = pd.read_csv(RAW / "All_States_GE.csv", low_memory=False)
ge = ge[(ge.State_Name == "Uttar_Pradesh") & (ge.Year.isin([2009, 2014, 2019]))].copy()
ge["party"] = ge.Party.map(norm_party)
ge["Votes"] = pd.to_numeric(ge.Votes, errors="coerce").fillna(0)
for y in (2009, 2014, 2019):
    gy = ge[ge.Year == y]
    tv = gy.Votes.sum()
    s = 100 * gy.groupby("party").Votes.sum() / tv
    for p, v in s.items():
        rows.append({"election": f"GE{y}", "party": p, "share": round(v, 2)})

state = pd.DataFrame(rows)
state = state[state.share > 0.5]
state.to_csv(OUT / "state_shares.csv", index=False)

# ---------- sanity report ----------
def winners(df):
    idx = df.groupby("const").share.idxmax()
    return df.loc[idx].party.value_counts()

print("AE2012 ACs:", ae2012.const.nunique(), "| winners:", dict(winners(ae2012).head(6)))
print("AE2017 ACs:", ae2017.const.nunique(), "| winners:", dict(winners(ae2017).head(6)))
print("AE2022 ACs:", ae2022.const.nunique(), "| winners:", dict(winners(ae2022).head(8)))
print("\nState shares (main parties):")
piv = state[state.party.isin(["BJP", "SP", "BSP", "INC", "RLD", "AD"])].pivot(index="party", columns="election", values="share")
print(piv.to_string())
