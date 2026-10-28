"""Fetch pre-election opinion-poll tables from Wikipedia PRE-ELECTION revisions.

Post-election articles often delete the opinion-poll section, so for each
election we resolve the last revision BEFORE polling day and parse that.
Using the frozen revision is also the honest thing to do: nothing edited in
after the result can leak into M3.

Raw extraction (one row per pollster x column cell, kind=pct|seats|num) goes
to data/raw/multistate/polls_wiki_raw.csv for audit. 07 curates it to blocs.
"""
import io
import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MS = ROOT / "data" / "raw" / "multistate"
CACHE = MS / "wiki_cache_frozen"
CACHE.mkdir(exist_ok=True)

# (article title, first polling day)
ARTICLES = {
    "KA2013": ("2013 Karnataka Legislative Assembly election", "2013-05-05"),
    "MP2013": ("2013 Madhya Pradesh Legislative Assembly election", "2013-11-25"),
    "RJ2013": ("2013 Rajasthan Legislative Assembly election", "2013-12-01"),
    "CG2013": ("2013 Chhattisgarh Legislative Assembly election", "2013-11-11"),
    "DL2013": ("2013 Delhi Legislative Assembly election", "2013-12-04"),
    "MH2014": ("2014 Maharashtra Legislative Assembly election", "2014-10-15"),
    "HR2014": ("2014 Haryana Legislative Assembly election", "2014-10-15"),
    "JH2014": ("2014 Jharkhand Legislative Assembly election", "2014-11-25"),
    "DL2015": ("2015 Delhi Legislative Assembly election", "2015-02-07"),
    "BR2015": ("2015 Bihar Legislative Assembly election", "2015-10-12"),
    "AS2016": ("2016 Assam Legislative Assembly election", "2016-04-04"),
    "KL2016": ("2016 Kerala Legislative Assembly election", "2016-05-16"),
    "TN2016": ("2016 Tamil Nadu Legislative Assembly election", "2016-05-16"),
    "WB2016": ("2016 West Bengal Legislative Assembly election", "2016-04-04"),
    "UP2017": ("2017 Uttar Pradesh Legislative Assembly election", "2017-02-11"),
    "PB2017": ("2017 Punjab Legislative Assembly election", "2017-02-04"),
    "UK2017": ("2017 Uttarakhand Legislative Assembly election", "2017-02-15"),
    "GJ2017": ("2017 Gujarat Legislative Assembly election", "2017-12-09"),
    "HP2017": ("2017 Himachal Pradesh Legislative Assembly election", "2017-11-09"),
    "KA2018": ("2018 Karnataka Legislative Assembly election", "2018-05-12"),
    "MP2018": ("2018 Madhya Pradesh Legislative Assembly election", "2018-11-28"),
    "RJ2018": ("2018 Rajasthan Legislative Assembly election", "2018-12-07"),
    "CG2018": ("2018 Chhattisgarh Legislative Assembly election", "2018-11-12"),
    "TG2018": ("2018 Telangana Legislative Assembly election", "2018-12-07"),
    "MH2019": ("2019 Maharashtra Legislative Assembly election", "2019-10-21"),
    "HR2019": ("2019 Haryana Legislative Assembly election", "2019-10-21"),
    "JH2019": ("2019 Jharkhand Legislative Assembly election", "2019-11-30"),
    "DL2020": ("2020 Delhi Legislative Assembly election", "2020-02-08"),
    "BR2020": ("2020 Bihar Legislative Assembly election", "2020-10-28"),
    "AS2021": ("2021 Assam Legislative Assembly election", "2021-03-27"),
    "KL2021": ("2021 Kerala Legislative Assembly election", "2021-04-06"),
    "TN2021": ("2021 Tamil Nadu Legislative Assembly election", "2021-04-06"),
    "WB2021": ("2021 West Bengal Legislative Assembly election", "2021-03-27"),
    "UP2022": ("2022 Uttar Pradesh Legislative Assembly election", "2022-02-10"),
    "PB2022": ("2022 Punjab Legislative Assembly election", "2022-02-20"),
    "UK2022": ("2022 Uttarakhand Legislative Assembly election", "2022-02-14"),
    "GJ2022": ("2022 Gujarat Legislative Assembly election", "2022-12-01"),
    "KA2023": ("2023 Karnataka Legislative Assembly election", "2023-05-10"),
    "MP2023": ("2023 Madhya Pradesh Legislative Assembly election", "2023-11-17"),
    "RJ2023": ("2023 Rajasthan Legislative Assembly election", "2023-11-25"),
    "CG2023": ("2023 Chhattisgarh Legislative Assembly election", "2023-11-07"),
    "TG2023": ("2023 Telangana Legislative Assembly election", "2023-11-30"),
    "MH2024": ("2024 Maharashtra Legislative Assembly election", "2024-11-20"),
    "HR2024": ("2024 Haryana Legislative Assembly election", "2024-10-05"),
    "DL2025": ("2025 Delhi Legislative Assembly election", "2025-02-05"),
    "BR2025": ("2025 Bihar Legislative Assembly election", "2025-11-06"),
}

AGENCY_PAT = re.compile(
    r"poll(ing)?\s*(agency|organisation|organization|firm)|pollster|agency|"
    r"survey(ing)?\s*(agency|organisation)?", re.I)


def api(params):
    url = "https://en.wikipedia.org/w/api.php?format=json&" + urllib.parse.urlencode(params)
    for _ in range(3):
        r = subprocess.run(["curl", "-s", "--max-time", "40", url],
                           capture_output=True, text=True, encoding="utf8",
                           errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(2)
    return None


def frozen_html(eid, title, poll_date):
    f = CACHE / f"{eid}.json"
    if f.exists():
        j = json.loads(f.read_text(encoding="utf8"))
    else:
        rv = api({"action": "query", "prop": "revisions", "titles": title,
                  "rvlimit": 1, "rvdir": "older",
                  "rvstart": poll_date + "T00:00:00Z", "rvprop": "ids|timestamp"})
        if not rv:
            return None, None
        pages = rv["query"]["pages"]
        pg = next(iter(pages.values()))
        if "revisions" not in pg:
            return None, None
        oldid = pg["revisions"][0]["revid"]
        ts = pg["revisions"][0]["timestamp"]
        j = api({"action": "parse", "prop": "text", "oldid": oldid})
        if not j or "parse" not in j:
            return None, None
        j["_oldid"], j["_ts"] = oldid, ts
        f.write_text(json.dumps(j), encoding="utf8")
    if "parse" not in j:
        return None, None
    return j["parse"]["text"]["*"], j.get("_ts", "")


def flat_cols(t):
    out = []
    for c in t.columns:
        if isinstance(c, tuple):
            parts = [str(x) for x in c if not str(x).startswith("Unnamed")]
            out.append(" | ".join(dict.fromkeys(parts)))
        else:
            out.append(str(c))
    return out


def current_html(eid, title):
    """Fallback: current revision (some articles only gained their poll
    tables after the election; noted as rev=current in the raw file)."""
    f = CACHE / f"{eid}_current.json"
    if f.exists():
        j = json.loads(f.read_text(encoding="utf8"))
    else:
        j = api({"action": "parse", "prop": "text", "page": title})
        if not j or "parse" not in j:
            return None
        f.write_text(json.dumps(j), encoding="utf8")
    if "parse" not in j:
        return None
    return j["parse"]["text"]["*"]


def extract(eid, html, rev, rows):
    try:
        tables = pd.read_html(io.StringIO(html), flavor="html5lib")
    except ValueError:
        return 0
    n_found = 0
    for ti, t in enumerate(tables):
        cols = flat_cols(t)
        joined = " ".join(cols).lower()
        if not AGENCY_PAT.search(joined):
            # headerless table (rowspan markup): look for the header in the
            # first rows and promote it
            promoted = False
            for hr in range(min(2, len(t))):
                rowvals = [str(v) for v in t.iloc[hr].tolist()]
                if AGENCY_PAT.search(" ".join(rowvals)):
                    t = t.iloc[hr + 1:].copy()
                    t.columns = rowvals
                    cols = flat_cols(t)
                    joined = " ".join(cols).lower()
                    promoted = True
                    break
            if not promoted:
                continue
        if len(t) < 1 or len(cols) < 3:
            continue
        for ri, r in t.iterrows():
            vals, agency, date = {}, "", ""
            for c, cname in zip(t.columns, cols):
                v = str(r[c]).strip()
                if AGENCY_PAT.search(cname) and not re.search(r"date|sample", cname, re.I):
                    agency = v if v.lower() != "nan" else agency
                elif re.search(r"date|month|published", cname, re.I):
                    date = v if v.lower() != "nan" else date
                elif re.search(r"sample|margin of error|error|method|ref|source|lead",
                               cname, re.I):
                    continue
                else:
                    vals[cname] = v
            if not agency:
                continue
            for cname, v in vals.items():
                v = (v.replace("–", "-").replace("−", "-")
                      .replace("—", "-"))
                pct = re.search(r"(\d+(?:\.\d+)?)\s*%", v)
                clean = re.sub(r"\[\d+\]", "", v).replace("%", "").strip()
                rng = re.fullmatch(r"(\d+)\s*-\s*(\d+)", clean)
                num = re.fullmatch(r"\d+(?:\.\d+)?", clean)
                if pct:
                    rows.append({"election_id": eid, "table": ti, "agency": agency,
                                 "date": date, "col": cname, "kind": "pct",
                                 "value": float(pct.group(1))})
                elif rng:
                    rows.append({"election_id": eid, "table": ti, "agency": agency,
                                 "date": date, "col": cname, "kind": "seats",
                                 "value": (int(rng.group(1)) + int(rng.group(2))) / 2})
                elif num:
                    rows.append({"election_id": eid, "table": ti, "agency": agency,
                                 "date": date, "col": cname, "kind": "num",
                                 "value": float(clean)})
            n_found += 1
    for rrow in rows:
        if rrow["election_id"] == eid and "rev" not in rrow:
            rrow["rev"] = rev
    return n_found


rows = []
for eid, (title, pdate) in ARTICLES.items():
    html, ts = frozen_html(eid, title, pdate)
    n = 0
    if html is not None:
        n = extract(eid, html, "frozen", rows)
    if n == 0:
        html2 = current_html(eid, title)
        if html2 is not None:
            n = extract(eid, html2, "current", rows)
            src = "current rev (frozen had none)"
        else:
            src = "NO REVISION AVAILABLE"
    else:
        src = f"frozen rev {ts[:10] if ts else '?'}"
    print(f"{eid}: {n} pollster-rows ({src})")

raw = pd.DataFrame(rows)
raw.to_csv(MS / "polls_wiki_raw.csv", index=False)
print(f"\ntotal cells: {len(raw)} across {raw.election_id.nunique() if len(raw) else 0} elections")
