"""Step 2 (post-registration ONLY): fetch CURRENT revisions of the 2026 articles
to resolve the pre-registered ledger. Run only after predict.py has written the
WB/TN/KL/AS 2026 rows to forecasts/ledger.csv."""
import json
import subprocess
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "holdout2026" / "wiki_current"
OUT.mkdir(parents=True, exist_ok=True)

TITLES = {
    "WB2026": "2026 West Bengal Legislative Assembly election",
    "TN2026": "2026 Tamil Nadu Legislative Assembly election",
    "KL2026": "2026 Kerala Legislative Assembly election",
    "AS2026": "2026 Assam Legislative Assembly election",
}

ledger = (ROOT / "forecasts" / "ledger.csv").read_text(encoding="utf8")
for fid in TITLES:
    assert f"{fid}," in ledger, f"{fid} not pre-registered in ledger.csv - refusing to fetch results"


def api(params):
    url = "https://en.wikipedia.org/w/api.php?format=json&" + urllib.parse.urlencode(params)
    for _ in range(3):
        r = subprocess.run(["curl", "-s", "--max-time", "60", url],
                           capture_output=True, text=True, encoding="utf8", errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(2)
    return None


for eid, title in TITLES.items():
    f = OUT / f"{eid}_current.json"
    if f.exists():
        print(f"{eid}: cached")
        continue
    j = api({"action": "parse", "prop": "text|wikitext", "page": title, "redirects": 1})
    if not j or "parse" not in j:
        print(f"{eid}: FETCH FAIL")
        continue
    f.write_text(json.dumps(j), encoding="utf8")
    print(f"{eid}: saved current revision")
