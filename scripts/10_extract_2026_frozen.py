"""Extract alliances + opinion-poll tables from the 2026 freeze-date frozen revisions.

Prints alliance section party lists and dumps poll tables (vote-share) found by
the same agency-pattern heuristic as 06_fetch_polls.py. Also writes
data/raw/holdout2026/polls_2026_raw.csv for audit.
"""
import io
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "raw" / "holdout2026" / "wiki_frozen"

FILES = {
    "AS2026": "AS2026__2026-03-12.json",
    "KL2026": "KL2026__2026-03-12.json",
    "TN2026": "TN2026__2026-03-26.json",
    "WB2026": "WB2026__2026-03-26.json",
}

AGENCY_PAT = re.compile(
    r"poll(ing)?\s*(agency|organisation|organization|firm)|pollster|agency|"
    r"survey(ing)?\s*(agency|organisation)?", re.I)


def flat_cols(t):
    out = []
    for c in t.columns:
        if isinstance(c, tuple):
            parts = [str(x) for x in c if not str(x).startswith("Unnamed")]
            out.append(" | ".join(dict.fromkeys(parts)))
        else:
            out.append(str(c))
    return out


def alliances(wt):
    """Print the 'Parties and alliances' section headings + party rows."""
    sec = re.search(r"==\s*Parties and alliances\s*==(.*?)(\n==[^=]|\Z)", wt, re.S)
    if not sec:
        print("  (no alliances section)")
        return
    txt = sec.group(1)
    for h in re.finditer(r"===\s*(.*?)\s*===", txt):
        print(f"  ALLIANCE: {h.group(1)}")
    # party links inside tables: rows like |[[Party Name]] or {{abbr}}
    for m in re.finditer(r"\[\[([^|\]]*?(?:party|congress|front|kazhagam|league|munnetra|federation|bloc|samithi|katchi|parishad|akali|janata|communist|aitc|bjp)[^|\]]*?)(?:\|([^\]]*))?\]\]", txt, re.I):
        pass  # too noisy; rely on manual section dump below


rows = []
for eid, fn in FILES.items():
    j = json.loads((DIR / fn).read_text(encoding="utf8"))
    html = j["parse"]["text"]["*"]
    wt = j["parse"]["wikitext"]["*"]
    print("=" * 25, eid, "rev", j["_oldid"], "ts", j["_ts"])
    try:
        tables = pd.read_html(io.StringIO(html), flavor="html5lib")
    except ValueError:
        tables = []
    for ti, t in enumerate(tables):
        cols = flat_cols(t)
        joined = " ".join(cols).lower()
        if not AGENCY_PAT.search(joined):
            continue
        if re.search(r"exit poll", joined, re.I):
            print(f"  table {ti}: SKIPPED (exit poll table)")
            continue
        print(f"  poll table {ti}: cols = {cols}")
        print(t.to_string(max_rows=40))
        t2 = t.copy()
        t2.columns = cols
        t2["election_id"] = eid
        t2["table"] = ti
        rows.append(t2)

out = ROOT / "data" / "raw" / "holdout2026" / "polls_2026_raw.csv"
if rows:
    pd.concat(rows, ignore_index=True).to_csv(out, index=False)
    print("saved", out)
