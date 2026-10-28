"""Build the multi-state AE dataset: ~46 target elections (2013-2025) + baselines.

Outputs (data/processed/):
  ae_long.csv           - (election_id, state, year, ac_no, ac_name, party, share) const-level
  state_shares_all.csv  - state-level party shares for every AE/GE we can compute
  build_validation.csv  - computed seat winners vs official tallies (meta/expected_seats.csv)

Sources are heterogeneous public mirrors (Kaggle/GitHub/OpenCity/Wikipedia); each
loader normalizes party names via PARTY_ALIASES and constituency names via norm_const.
Top-2-only sources (HR2019, BR2020, DL2020) are flagged quality='top2'.
"""
import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
MS = RAW / "multistate"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------- party normalization ----------------
PARTY_ALIASES = {
    # national
    "BHARATIYA JANATA PARTY": "BJP", "BJP": "BJP", "BHARTIYA JANTA PARTY": "BJP",
    "BHARATIYA JANTA PARTY": "BJP",
    "INDIAN NATIONAL CONGRESS": "INC", "INC": "INC", "CONGRESS": "INC",
    "BAHUJAN SAMAJ PARTY": "BSP", "BSP": "BSP",
    "COMMUNIST PARTY OF INDIA": "CPI", "CPI": "CPI",
    "COMMUNIST PARTY OF INDIA (MARXIST)": "CPM", "CPM": "CPM", "CPI(M)": "CPM",
    "COMMUNIST PARTY OF INDIA  (MARXIST)": "CPM", "CPI (M)": "CPM",
    "COMMUNIST PARTY OF INDIA (MARXIST-LENINIST) (LIBERATION)": "CPIML",
    "COMMUNIST PARTY OF INDIA  (MARXIST-LENINIST)  (LIBERATION)": "CPIML",
    "CPI(ML)": "CPIML", "CPI(ML)(L)": "CPIML", "CPI(ML)L": "CPIML",
    "NATIONALIST CONGRESS PARTY": "NCP", "NCP": "NCP",
    "NATIONALIST CONGRESS PARTY  SHARADCHANDRA PAWAR": "NCPSP",
    "NATIONALIST CONGRESS PARTY - SHARADCHANDRA PAWAR": "NCPSP", "NCP(SP)": "NCPSP",
    "AAM AADMI PARTY": "AAP", "AAP": "AAP", "AAAP": "AAP",
    "ALL INDIA MAJLIS-E-ITTEHADUL MUSLIMEEN": "AIMIM", "AIMIM": "AIMIM",
    "ALL INDIA MAJLIS-E-ITTEHAD-UL-MUSLIMEEN": "AIMIM",
    "NONE OF THE ABOVE": "NOTA", "NOTA": "NOTA",
    "INDEPENDENT": "IND", "IND": "IND",
    # UP
    "SAMAJWADI PARTY": "SP", "SP": "SP",
    "RASHTRIYA LOK DAL": "RLD", "RLD": "RLD",
    "APNA DAL (SONEYLAL)": "ADS", "APNA DAL (SONELAL)": "ADS", "APNA DAL": "ADS",
    "ADAL": "ADS", "AD(S)": "ADS",
    "SUHELDEV BHARATIYA SAMAJ PARTY": "SBSP", "SBSP": "SBSP",
    "NISHAD (NIRBAL INDIAN SHOSHIT HAMARA AAM DAL)": "NISHAD", "NISHAD": "NISHAD",
    # Bihar
    "JANATA DAL  (UNITED)": "JDU", "JANATA DAL (UNITED)": "JDU", "JD(U)": "JDU", "JDU": "JDU",
    "RASHTRIYA JANATA DAL": "RJD", "RJD": "RJD",
    "LOK JAN SHAKTI PARTY": "LJP", "LJP": "LJP", "LOK JANSHAKTI PARTY": "LJP",
    "LOK JANSHAKTI PARTY(RAM VILAS)": "LJPRV", "LJP(RV)": "LJPRV",
    "LOK JANSHAKTI PARTY (RAM VILAS)": "LJPRV",
    "RASHTRIYA LOK SAMTA PARTY": "RLSP", "RLSP": "RLSP",
    "RASHTRIYA LOK MORCHA": "RLM",
    "HINDUSTANI AWAM MORCHA (SECULAR)": "HAM", "HAM(S)": "HAM", "HAM": "HAM",
    "HINDUSTANI AWAM MORCHA  (SECULAR)": "HAM",
    "VIKASSHEEL INSAAN PARTY": "VIP", "VIP": "VIP",
    "JAN SURAAJ PARTY": "JSP",
    # Maharashtra
    "SHIV SENA": "SHS", "SHS": "SHS", "SS": "SHS",
    "SHIV SENA (UDDHAV BALASAHEB THACKREY)": "SHSUBT", "SHS(UBT)": "SHSUBT",
    "SHIV SENA (UDDHAV BALASAHEB THACKERAY)": "SHSUBT", "SHIVSENA": "SHS",
    "MAHARASHTRA NAVNIRMAN SENA": "MNS", "MNS": "MNS",
    "VANCHIT BAHUJAN AAGHADI": "VBA", "VBA": "VBA",
    "PEASANTS AND WORKERS PARTY OF INDIA": "PWP", "PWP": "PWP",
    "BAHUJAN VIKAS AAGHADI": "BVA",
    # Haryana
    "INDIAN NATIONAL LOK DAL": "INLD", "INLD": "INLD",
    "JANNAYAK JANTA PARTY": "JJP", "JJP": "JJP",
    "HARYANA JANHIT CONGRESS (BL)": "HJC", "HJC(BL)": "HJC", "HJC": "HJC", "HJCBL": "HJC",
    "HARYANA LOKHIT PARTY": "HLP",
    # Jharkhand
    "JHARKHAND MUKTI MORCHA": "JMM", "JMM": "JMM",
    "ALL JHARKHAND STUDENTS UNION": "AJSU", "AJSU": "AJSU", "AJSU PARTY": "AJSU",
    "JHARKHAND VIKAS MORCHA (PRAJATANTRIK)": "JVM", "JVM(P)": "JVM", "JVM": "JVM",
    # Karnataka
    "JANATA DAL  (SECULAR)": "JDS", "JANATA DAL (SECULAR)": "JDS", "JD(S)": "JDS", "JDS": "JDS",
    "KARNATAKA JANATHA PAKSHA": "KJP", "KJP": "KJP",
    "BADAVARA SHRAMIKARA RAITHARA CONGRESS": "BSRC", "BSRCP": "BSRC",
    # TN
    "ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM": "ADMK", "AIADMK": "ADMK", "ADMK": "ADMK",
    "DRAVIDA MUNNETRA KAZHAGAM": "DMK", "DMK": "DMK",
    "DESIYA MURPOKKU DRAVIDA KAZHAGAM": "DMDK", "DMDK": "DMDK",
    "PATTALI MAKKAL KATCHI": "PMK", "PMK": "PMK",
    "VIDUTHALAI CHIRUTHAIGAL KATCHI": "VCK", "VCK": "VCK",
    "MARUMALARCHI DRAVIDA MUNNETRA KAZHAGAM": "MDMK", "MDMK": "MDMK",
    "AMMA MAKKAL MUNNETTRA KAZAGAM": "AMMK", "AMMK": "AMMK",
    "MAKKAL NEEDHI MAIAM": "MNM", "MNM": "MNM",
    "NAAM TAMILAR KATCHI": "NTK", "NTK": "NTK",
    "INDHIYA JANANAYAGA KATCHI": "IJK",
    "TAMIL MAANILA CONGRESS (MOOPANAR)": "TMC(M)", "TMC(M)": "TMC(M)",
    # Kerala
    "INDIAN UNION MUSLIM LEAGUE": "IUML", "IUML": "IUML", "MUSLIM LEAGUE KERALA STATE COMMITTEE": "IUML", "MUL": "IUML",
    "KERALA CONGRESS (M)": "KCM", "KC(M)": "KCM", "KERALA CONGRESS  (M)": "KCM",
    "KERALA CONGRESS": "KEC", "KEC": "KEC",
    "REVOLUTIONARY SOCIALIST PARTY": "RSP", "RSP": "RSP",
    "JANATHIPATHIYA SAMRAKSHANA SAMITHY": "JSS",
    "NATIONALIST CONGRESS KERALA": "NCK",
    "BHARATH DHARMA JANA SENA": "BDJS", "BDJS": "BDJS",
    "JANADHIPATHYA KERALA CONGRESS": "JKC",
    "KERALA CONGRESS (B)": "KCB", "LOKTANTRIK JANATA DAL": "LJD",
    # WB
    "ALL INDIA TRINAMOOL CONGRESS": "AITC", "AITC": "AITC", "TMC": "AITC",
    "ALL INDIA FORWARD BLOC": "AIFB", "AIFB": "AIFB", "FBL": "AIFB",
    "REVOLUTIONARY SOCIALIST PARTY  (UNITED)": "RSP",
    "INDIAN SECULAR FRONT": "ISF", "RASHTRIYA SECULAR MAJLIS PARTY": "ISF",
    # Assam
    "ASOM GANA PARISHAD": "AGP", "AGP": "AGP",
    "ALL INDIA UNITED DEMOCRATIC FRONT": "AIUDF", "AIUDF": "AIUDF",
    "BODOLAND PEOPLES FRONT": "BPF", "BPF": "BPF", "BODOLAND PEOPLE'S FRONT": "BPF",
    "UNITED PEOPLES PARTY, LIBERAL": "UPPL", "UPPL": "UPPL",
    "UNITED PEOPLE'S PARTY, LIBERAL": "UPPL",
    "ASSAM JATIYA PARISHAD": "AJP",
    # Punjab
    "SHIROMANI AKALI DAL": "SAD", "SAD": "SAD",
    "SHIROMANI AKALI DAL (AMRITSAR)(SIMRANJIT SINGH MANN)": "SADA",
    "PUNJAB LOK CONGRESS": "PLC",
    # Gujarat
    "GUJARAT PARIVARTAN PARTY": "GPP", "GPP": "GPP",
    "BHARTIYA TRIBAL PARTY": "BTP", "BTP": "BTP",
    # Telangana / AP
    "TELANGANA RASHTRA SAMITHI": "BRS", "TRS": "BRS",
    "BHARAT RASHTRA SAMITHI": "BRS", "BRS": "BRS",
    "TELUGU DESAM": "TDP", "TELUGU DESAM PARTY": "TDP", "TDP": "TDP",
    "YUVAJANA SRAMIKA RYTHU CONGRESS PARTY": "YSRCP", "YSRCP": "YSRCP",
    # Delhi
    "SHIROMANI AKALI DAL (DELHI)": "SAD",
    # MP/CG/RJ
    "JANTA CONGRESS CHHATTISGARH (J)": "JCC", "JCC(J)": "JCC",
    "GONDVANA GANTANTRA PARTY": "GGP", "GGP": "GGP",
    "RASHTRIYA LOKTANTRIK PARTY": "RLP", "RLTP": "RLP",
    "BHARAT ADIVASI PARTY": "BAP", "BHARTIYA ADIVASI PARTY": "BAP",
    "SAMAJWADI JANATA PARTY (RASHTRIYA)": "SJP",
    # Uttarakhand / HP
    "UTTARAKHAND KRANTI DAL": "UKD", "UKD": "UKD",
    "COMMUNIST PARTY OF INDIA (MARXIST-LENINIST)  (LIBERATION)": "CPIML",
}


def norm_party(p):
    p = str(p).strip().upper()
    p = re.sub(r"\s+", " ", p)
    return PARTY_ALIASES.get(p, p)


def norm_const(c):
    c = str(c).upper()
    c = re.sub(r"\((SC|ST|GEN)\)", "", c)
    c = c.replace(".", " ").replace("-", " ").replace("_", " ").replace("'", "")
    c = re.sub(r"\s+", " ", c).strip()
    return c


rows_long = []   # const-level
rows_state = []  # state-level shares


def add_election(eid, state, year, df, quality="full"):
    """df: columns ac_no (nullable), ac_name, party(raw), votes. Computes shares."""
    d = df.copy()
    d = d[d["party"].notna()]
    d["party"] = d["party"].map(norm_party)
    d["ac_name"] = d["ac_name"].map(norm_const)
    d["votes"] = pd.to_numeric(d["votes"], errors="coerce").fillna(0)
    d = d[~d.party.isin(["NOTA", "NAN", "TOTAL", "NONE"])]
    key = "ac_no" if d["ac_no"].notna().all() and d["ac_no"].nunique() > 1 else "ac_name"
    tot = d.groupby(key)["votes"].sum().rename("total")
    d = d.join(tot, on=key)
    d = d[d.total > 0]
    d["share"] = 100 * d.votes / d.total
    # parties: sum same-party candidates; IND: strongest independent only
    # (summing independents would fabricate a phantom "IND" front-runner)
    g_p = d[d.party != "IND"].groupby([key, "party"], as_index=False).agg(
        share=("share", "sum"), votes=("votes", "sum"))
    g_i = d[d.party == "IND"].groupby([key, "party"], as_index=False).agg(
        share=("share", "max"), votes=("votes", "max"))
    g = pd.concat([g_p, g_i], ignore_index=True)
    names = d.groupby(key)["ac_name"].first() if key == "ac_no" else None
    for _, r in g.iterrows():
        rows_long.append({
            "election_id": eid, "state": state, "year": year,
            "ac_no": r[key] if key == "ac_no" else np.nan,
            "ac_name": names.loc[r[key]] if key == "ac_no" else r[key],
            "party": r["party"], "share": round(r["share"], 3),
            "votes": int(r["votes"]), "quality": quality,
        })
    # state shares (vote-weighted)
    tv = d.votes.sum()
    s = 100 * d.groupby("party").votes.sum() / tv
    for p, v in s.items():
        if v >= 0.3:
            rows_state.append({"election": eid, "state": state, "year": year,
                               "party": p, "share": round(v, 2)})
    n_ac = d[key].nunique()
    print(f"  {eid}: {n_ac} ACs, {len(g)} (ac,party) rows [{quality}]")


def add_state_shares_only(eid, state, year, df):
    d = df.copy()
    d["party"] = d["party"].map(norm_party)
    d["votes"] = pd.to_numeric(d["votes"], errors="coerce").fillna(0)
    d = d[d.party != "NOTA"]
    tv = d.votes.sum()
    if tv <= 0:
        return
    s = 100 * d.groupby("party").votes.sum() / tv
    for p, v in s.items():
        if v >= 0.3:
            rows_state.append({"election": eid, "state": state, "year": year,
                               "party": p, "share": round(v, 2)})


STATE_CODE = {
    "Karnataka": "KA", "Madhya Pradesh": "MP", "Rajasthan": "RJ", "Chhattisgarh": "CG",
    "National Capital Territory Of Delhi": "DL", "NCT OF Delhi": "DL", "Delhi": "DL",
    "Maharashtra": "MH", "Haryana": "HR", "Jharkhand": "JH", "Bihar": "BR",
    "Assam": "AS", "Kerala": "KL", "Tamil Nadu": "TN", "West Bengal": "WB",
    "Uttar Pradesh": "UP", "Punjab": "PB", "Uttarakhand": "UK", "Gujarat": "GJ",
    "Himachal Pradesh": "HP", "Telangana": "TG",
}

print("=== datameet (2008-2012 baselines; exact vs official) ===")
dm_all = pd.read_csv(RAW / "datameet_assembly.csv", encoding="latin-1", low_memory=False)
dm_all["YEAR"] = pd.to_numeric(dm_all.YEAR, errors="coerce")
DM_CONST = [
    ("Karnataka", 2008), ("Madhya Pradesh", 2008), ("Rajasthan", 2008),
    ("Chhattisgarh", 2008), ("Delhi", 2008),
    ("Maharashtra", 2009), ("Haryana", 2009), ("Jharkhand", 2009),
    ("Bihar", 2010),
    ("Assam", 2011), ("Kerala", 2011), ("Tamil Nadu", 2011), ("West Bengal", 2011),
    ("Punjab", 2012), ("Uttarakhand", 2012), ("Himachal Pradesh", 2012),
    ("Uttar Pradesh", 2012),
]
for st, yr in DM_CONST:
    d = dm_all[(dm_all.ST_NAME == st) & (dm_all.YEAR == yr)]
    code = STATE_CODE[st]
    add_election(code + str(yr), code, yr, d.rename(columns={
        "AC_NO": "ac_no", "AC_NAME": "ac_name", "PARTY": "party",
        "VOTES": "votes"})[["ac_no", "ac_name", "party", "votes"]])

print("=== harivpatel (2013-2015) ===")
hv = pd.read_csv(MS / "ind-vidhan-sabha.csv", low_memory=False)
hv = hv.dropna(subset=["year"])
hv["year"] = hv.year.astype(int)
HV_CONST = [
    ("Karnataka", 2013),
    ("Madhya Pradesh", 2013), ("Rajasthan", 2013), ("Chhattisgarh", 2013),
    ("National Capital Territory Of Delhi", 2013),
    ("National Capital Territory Of Delhi", 2015),
    ("Maharashtra", 2014), ("Haryana", 2014), ("Jharkhand", 2014),
]
for st, yr in HV_CONST:
    d = hv[(hv.st_name == st) & (hv.year == yr)]
    eid = STATE_CODE[st] + str(yr)
    add_election(eid, STATE_CODE[st], yr, d.rename(columns={
        "ac_no": "ac_no", "ac_name": "ac_name", "partyabbre": "party",
        "totvotpoll": "votes"})[["ac_no", "ac_name", "party", "votes"]])

# state-level only, for alpha pooling (older cycles)
for (st, yr), d in hv[hv.year.between(2002, 2015)].groupby(["st_name", "year"]):
    if st not in STATE_CODE:
        continue
    eid = STATE_CODE[st] + str(yr)
    if (st, yr) not in HV_CONST:
        add_state_shares_only(eid, STATE_CODE[st], yr,
                              d.rename(columns={"partyabbre": "party", "totvotpoll": "votes"}))

print("=== whenamancodes (2015-2017) ===")
wa = pd.read_csv(MS / "whenamancodes_2013_2017.csv", low_memory=False)
WA_LOAD = [("Bihar", 2015), ("Assam", 2016), ("Kerala", 2016), ("Tamil Nadu", 2016),
           ("West Bengal", 2016), ("Punjab", 2017), ("Uttarakhand", 2017)]
for st, yr in WA_LOAD:
    d = wa[(wa.ST_NAME == st) & (wa.YEAR == yr)].copy()
    d["ac_no"] = np.nan
    add_election(STATE_CODE[st] + str(yr), STATE_CODE[st], yr, d.rename(columns={
        "AC_NAME": "ac_name", "PARTYABBRE": "party",
        "TOTALVALIDVOTESPOLLED": "votes"})[["ac_no", "ac_name", "party", "votes"]])

print("=== Telangana 2014 baseline (united-AP election, ACs 1-119) ===")
ap14 = hv[(hv.st_name == "Andhra Pradesh") & (hv.year == 2014) & (hv.ac_no <= 119)]
add_election("TG2014", "TG", 2014, ap14.rename(columns={
    "partyabbre": "party", "totvotpoll": "votes"})[["ac_no", "ac_name", "party", "votes"]])

print("=== TCPD Gujarat / UP ===")
for f, st, years in [(MS / "tcpd_gujarat.csv", "Gujarat", [2012, 2017]),
                     (RAW / "up2017" / "TCPD_AE_Uttar_Pradesh_2021-10-3.csv", "Uttar Pradesh", [2017])]:
    tc = pd.read_csv(f, low_memory=False)
    for yr in years:
        d = tc[tc.Year == yr].copy()
        d = d.rename(columns={"Constituency_No": "ac_no", "Constituency_Name": "ac_name",
                              "Party": "party", "Votes": "votes"})
        add_election(STATE_CODE[st] + str(yr), STATE_CODE[st], yr,
                     d[["ac_no", "ac_name", "party", "votes"]])

print("=== Dec 2018 five states ===")
v18 = pd.read_csv(MS / "vs2018_results.csv")
v18["ac_name"] = v18.const_name.str.split(" - ").str[-1]
for st in ["Madhya Pradesh", "Rajasthan", "Chhattisgarh", "Telangana"]:
    d = v18[v18.state == st].copy()
    d["ac_no"] = np.nan
    add_election(STATE_CODE[st] + "2018", STATE_CODE[st], 2018,
                 d[["ac_no", "ac_name", "party", "votes"]])

print("=== Karnataka 2018 ===")
k18 = pd.read_csv(MS / "ka2018_candidates.csv")
k18 = k18.rename(columns={"Constituency-code": "ac_no", "Constituency": "ac_name",
                          "Party": "party", "Votes": "votes"})
add_election("KA2018", "KA", 2018, k18[["ac_no", "ac_name", "party", "votes"]],
             quality="approx")  # near-final ECI trends scrape: shares within ~1pt, 5 seats off

print("=== Maharashtra 2019 ===")
import ast
mh19 = pd.read_excel(MS / "mh2019.xlsx")
recs = []
for _, r in mh19.iterrows():
    try:
        cands = ast.literal_eval(r["Candidates"])
    except Exception:
        continue
    for c in cands:
        recs.append({"ac_no": r["AC_No"], "ac_name": r["AC"], "party": c[1], "votes": c[2]})
add_election("MH2019", "MH", 2019, pd.DataFrame(recs))

print("=== Haryana 2019 (top-2) ===")
h19 = pd.read_csv(MS / "hr2019_top2.csv")
recs = []
for _, r in h19.iterrows():
    recs.append({"ac_no": r.AC_No, "ac_name": r.AC_Name, "party": r.Winner_Party, "votes": r.Winner_Votes})
    recs.append({"ac_no": r.AC_No, "ac_name": r.AC_Name, "party": r.RunnerUp_Party, "votes": r.RunnerUp_Votes})
add_election("HR2019", "HR", 2019, pd.DataFrame(recs), quality="top2")

print("=== Bihar 2020 (top-2 from ECI summary) ===")
x = pd.ExcelFile(MS / "br2020_summary.xlsx")
recs = []
for sh in x.sheet_names:
    m = re.match(r"S04-(\d+)-(.+)", sh)
    if not m:
        continue
    d = x.parse(sh, header=None)
    sub = d[d[1].isin(["Winner", "Runner-Up"])]
    for _, r in sub.iterrows():
        recs.append({"ac_no": int(m.group(1)), "ac_name": m.group(2),
                     "party": r[3], "votes": r[5]})
add_election("BR2020", "BR", 2020, pd.DataFrame(recs), quality="top2")

print("=== Delhi 2020 (top-2 from Wikipedia) ===")
dw = pd.read_csv(MS / "dl2020_wiki_top2.csv")
dw = dw[pd.to_numeric(dw["Assembly Constituency_#"], errors="coerce").notna()]
recs = []
for _, r in dw.iterrows():
    recs.append({"ac_no": int(r["Assembly Constituency_#"]), "ac_name": r["Assembly Constituency_Name"],
                 "party": r["Winner_Party.1"], "votes": r["Winner_Votes"]})
    recs.append({"ac_no": int(r["Assembly Constituency_#"]), "ac_name": r["Assembly Constituency_Name"],
                 "party": r["Runner-up_Party.1"], "votes": r["Runner-up_Votes"]})
add_election("DL2020", "DL", 2020, pd.DataFrame(recs), quality="top2")

print("=== May 2021 four states (wide ECI scrape) ===")
for code, f in [("AS", "ae2021_AS_wide.csv"), ("KL", "ae2021_KL_wide.csv"),
                ("TN", "ae2021_TN_wide.csv"), ("WB", "ae2021_WB_wide.csv")]:
    d = pd.read_csv(MS / f, encoding="latin-1")
    d = d[pd.to_numeric(d["Constituency ID"], errors="coerce").notna()]
    recs = []
    partycols = [c for c in d.columns if c not in
                 ("Constituency ID", "Constituency_Name", "Winning_Margin")]
    for _, r in d.iterrows():
        for pc in partycols:
            v = pd.to_numeric(r[pc], errors="coerce")
            if pd.notna(v) and v > 0:
                recs.append({"ac_no": int(r["Constituency ID"]),
                             "ac_name": r["Constituency_Name"], "party": pc, "votes": v})
    add_election(code + "2021", code, 2021, pd.DataFrame(recs))

print("=== March 2022 three states ===")
cw = pd.read_csv(RAW / "up2022" / "constwise.csv")
for st in ["Punjab", "Uttar Pradesh", "Uttarakhand"]:
    d = cw[cw.state == st].copy()
    d["ac_no"] = np.nan
    add_election(STATE_CODE[st] + "2022", STATE_CODE[st], 2022, d.rename(
        columns={"constituency": "ac_name", "total_votes": "votes"})
        [["ac_no", "ac_name", "party", "votes"]])

print("=== Dec 2023 four states (azadecon xlsx) ===")
for code, sub in [("MP", "mp"), ("RJ", "raj"), ("CG", "cg"), ("TG", "ts")]:
    recs = []
    folder = MS / "az2023" / sub
    for f in sorted(folder.glob("*.xlsx"), key=lambda p: int(p.stem)):
        d = pd.read_excel(f)
        d.columns = [str(c).strip() for c in d.columns]
        name_col = "constituency" if "constituency" in d.columns else d.columns[-1]
        for _, r in d.iterrows():
            recs.append({"ac_no": int(f.stem), "ac_name": str(r[name_col]),
                         "party": r["party"], "votes": r["total_votes"]})
    df = pd.DataFrame(recs)
    # azadecon ac_name column holds the AC number again in some files; use file stem as number
    df["ac_name"] = df.ac_no.astype(str)
    add_election(code + "2023", code, 2023, df)

print("=== Karnataka 2023 (json) ===")
j = json.load(open(MS / "ka2023_constituencyWise.json", encoding="utf8"))
recs = []
for ac, cands in j.items():
    for c in cands:
        recs.append({"ac_no": np.nan, "ac_name": ac, "party": c["Party"],
                     "votes": float(str(c["Total Votes"]).replace(",", ""))})
add_election("KA2023", "KA", 2023, pd.DataFrame(recs))

print("=== 2024-2025 (ECI mirrors) ===")
for code, f, yr in [("MH", "2024Assembly-MH.csv", 2024), ("HR", "2024Assembly-HR.csv", 2024),
                    ("JH", "2024Assembly-JH.csv", 2024), ("BR", "2025Assembly-BR.csv", 2025),
                    ("DL", "2025Assembly-DL.csv", 2025)]:
    d = pd.read_csv(MS / f)
    d["votes"] = d.evm_votes.fillna(0) + d.postal_votes.fillna(0)
    add_election(code + str(yr), code, yr, d.rename(columns={
        "constituency_no": "ac_no", "constituency": "ac_name"})
        [["ac_no", "ac_name", "party", "votes"]])

print("=== GE state shares ===")
ge = pd.read_csv(RAW / "All_States_GE.csv", low_memory=False)
GE_STATES = {"Uttar_Pradesh": "UP", "Bihar": "BR", "West_Bengal": "WB", "Maharashtra": "MH",
             "Karnataka": "KA", "Madhya_Pradesh": "MP", "Rajasthan": "RJ", "Gujarat": "GJ",
             "Punjab": "PB", "Tamil_Nadu": "TN", "Kerala": "KL", "Assam": "AS",
             "Chhattisgarh": "CG", "Jharkhand": "JH", "Haryana": "HR", "Uttarakhand": "UK",
             "Delhi": "DL", "NCT_Of_Delhi": "DL", "Himachal_Pradesh": "HP",
             "Telangana": "TG", "Andhra_Pradesh": "AP"}
for (st, yr), d in ge[ge.Year.isin([2004, 2009, 2014, 2019])].groupby(["State_Name", "Year"]):
    if st not in GE_STATES:
        continue
    code = GE_STATES[st]
    add_state_shares_only(f"GE{code}{yr}", code, yr,
                          d.rename(columns={"Party": "party", "Votes": "votes"}))

# Telangana GE2014: united-AP election, Telangana PCs are 1-17
ap_ge14 = ge[(ge.State_Name == "Andhra_Pradesh") & (ge.Year == 2014) & (ge.Constituency_No <= 17)]
add_state_shares_only("GETG2014", "TG", 2014,
                      ap_ge14.rename(columns={"Party": "party", "Votes": "votes"}))

g24 = pd.read_csv(MS / "ge2024_results.csv")
g24["votes"] = pd.to_numeric(g24["Total Votes"].astype(str).str.replace(",", ""), errors="coerce")
G24_STATES = {"Uttar Pradesh": "UP", "Bihar": "BR", "West Bengal": "WB", "Maharashtra": "MH",
              "Karnataka": "KA", "Madhya Pradesh": "MP", "Rajasthan": "RJ", "Gujarat": "GJ",
              "Punjab": "PB", "Tamil Nadu": "TN", "Kerala": "KL", "Assam": "AS",
              "Chhattisgarh": "CG", "Jharkhand": "JH", "Haryana": "HR", "Uttarakhand": "UK",
              "NCT OF Delhi": "DL", "Himachal Pradesh": "HP", "Telangana": "TG"}
for st, d in g24.groupby("State"):
    if st in G24_STATES:
        add_state_shares_only(f"GE{G24_STATES[st]}2024", G24_STATES[st], 2024,
                              d.rename(columns={"Party": "party"}))

print("=== datameet pre-2008 state shares (alpha pooling) ===")
dm = pd.read_csv(RAW / "datameet_assembly.csv", encoding="latin-1", low_memory=False)
dm["YEAR"] = pd.to_numeric(dm.YEAR, errors="coerce")
DM_STATES = {"Karnataka": "KA", "Madhya Pradesh": "MP", "Rajasthan": "RJ",
             "Chhattisgarh": "CG", "Delhi": "DL", "Maharashtra": "MH", "Haryana": "HR",
             "Jharkhand": "JH", "Bihar": "BR", "Assam": "AS", "Kerala": "KL",
             "Tamil Nadu": "TN", "West Bengal": "WB", "Uttar Pradesh": "UP",
             "Punjab": "PB", "Uttarakhand": "UK", "Gujarat": "GJ", "Himachal Pradesh": "HP"}
for (st, yr), d in dm[dm.YEAR.between(2002, 2008)].groupby(["ST_NAME", "YEAR"]):
    if st not in DM_STATES:
        continue
    eid = DM_STATES[st] + str(int(yr))
    existing = {r["election"] for r in rows_state}
    if eid in existing:
        continue
    add_state_shares_only(eid, DM_STATES[st], int(yr),
                          d.rename(columns={"PARTY": "party", "VOTES": "votes"}))

# ---------------- write ----------------
ae_long = pd.DataFrame(rows_long)
state_shares = pd.DataFrame(rows_state).drop_duplicates(subset=["election", "party"])
ae_long.to_csv(OUT / "ae_long.csv", index=False)
state_shares.to_csv(OUT / "state_shares_all.csv", index=False)
print(f"\nae_long: {len(ae_long)} rows, {ae_long.election_id.nunique()} elections")
print(f"state_shares_all: {len(state_shares)} rows, {state_shares.election.nunique()} elections")

# ---------------- validation vs official tallies ----------------
exp_path = MS / "meta" / "expected_seats.csv"
if exp_path.exists():
    exp = pd.read_csv(exp_path)
    print("\n=== validation: computed winner seats vs official ===")
    bad = 0
    for _, r in exp.iterrows():
        d = ae_long[ae_long.election_id == r.election_id]
        if d.empty:
            continue
        key = "ac_no" if d.ac_no.notna().all() else "ac_name"
        idx = d.groupby(key).share.idxmax()
        seats = d.loc[idx].party.value_counts()
        got = int(seats.get(r.party, 0))
        flag = "OK" if got == r.seats else f"MISMATCH (official {r.seats})"
        if got != r.seats:
            bad += 1
        print(f"  {r.election_id} {r.party}: computed {got} {flag}")
    print(f"validation mismatches: {bad}")
