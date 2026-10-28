"""Fetch PRE-ELECTION frozen Wikipedia revisions for the 2026 holdout states.

Protocol guard: the 2026 results must NOT be seen before the forecasts are
pre-registered. Therefore this script only ever requests revisions with
rvstart <= FREEZE (rvdir=older), i.e. the last revision ON OR BEFORE the
freeze timestamp. It never fetches a current revision.

Usage: python 09_fetch_2026_frozen.py <freeze_iso_date>  [title_suffix]
Saves data/raw/holdout2026/wiki_frozen/<slug>__<freeze>.json (parse HTML+meta).
"""
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "holdout2026" / "wiki_frozen"
OUT.mkdir(parents=True, exist_ok=True)

TITLES = {
    "WB2026": "2026 West Bengal Legislative Assembly election",
    "TN2026": "2026 Tamil Nadu Legislative Assembly election",
    "KL2026": "2026 Kerala Legislative Assembly election",
    "AS2026": "2026 Assam Legislative Assembly election",
    "WB2026op": "Opinion polling for the 2026 West Bengal Legislative Assembly election",
    "TN2026op": "Opinion polling for the 2026 Tamil Nadu Legislative Assembly election",
    "KL2026op": "Opinion polling for the 2026 Kerala Legislative Assembly election",
    "AS2026op": "Opinion polling for the 2026 Assam Legislative Assembly election",
}


def api(params):
    url = "https://en.wikipedia.org/w/api.php?format=json&" + urllib.parse.urlencode(params)
    for _ in range(3):
        r = subprocess.run(["curl", "-s", "--max-time", "60", url],
                           capture_output=True, text=True, encoding="utf8",
                           errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(2)
    return None


def fetch_frozen(slug, title, freeze):
    f = OUT / f"{slug}__{freeze}.json"
    if f.exists():
        j = json.loads(f.read_text(encoding="utf8"))
        print(f"{slug}: cached rev {j.get('_oldid')} ts {j.get('_ts')}")
        return
    rv = api({"action": "query", "prop": "revisions", "titles": title,
              "rvlimit": 1, "rvdir": "older", "redirects": 1,
              "rvstart": freeze + "T23:59:59Z", "rvprop": "ids|timestamp"})
    if not rv:
        print(f"{slug}: API FAIL")
        return
    pg = next(iter(rv["query"]["pages"].values()))
    if "revisions" not in pg:
        print(f"{slug}: no revision on/before {freeze} (article may not exist yet: {pg.get('title')})")
        return
    oldid = pg["revisions"][0]["revid"]
    ts = pg["revisions"][0]["timestamp"]
    j = api({"action": "parse", "prop": "text|wikitext", "oldid": oldid})
    if not j or "parse" not in j:
        print(f"{slug}: parse FAIL for oldid {oldid}")
        return
    j["_oldid"], j["_ts"], j["_title"], j["_freeze"] = oldid, ts, title, freeze
    f.write_text(json.dumps(j), encoding="utf8")
    print(f"{slug}: saved rev {oldid} ts {ts} (frozen at {freeze})")


if __name__ == "__main__":
    freeze = sys.argv[1]
    only = sys.argv[2:] or list(TITLES)
    for slug in only:
        fetch_frozen(slug, TITLES[slug], freeze)
