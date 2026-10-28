import json
import re
import sys
from pathlib import Path

FILES = {
    "AS2026": "AS2026__2026-03-12.json",
    "KL2026": "KL2026__2026-03-12.json",
    "TN2026": "TN2026__2026-03-26.json",
    "WB2026": "WB2026__2026-03-26.json",
}
DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "holdout2026" / "wiki_frozen"

for eid in (sys.argv[1:] or FILES):
    j = json.loads((DIR / FILES[eid]).read_text(encoding="utf8"))
    wt = j["parse"]["wikitext"]["*"]
    m = re.search(r"==\s*Parties and alliances\s*==(.*?)\n==[^=]", wt, re.S)
    if not m:
        print(f"==== {eid}: no section")
        continue
    sec = m.group(1)
    sec = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", sec, flags=re.S)
    sec = re.sub(r"\{\{(party color|party name with colou?r)[^}]*\}\}", "", sec, flags=re.I)
    sec = re.sub(r"\[\[File:[^\]]*\]\]", "", sec)
    sec = re.sub(r"\n{2,}", "\n", sec)
    print(f"==== {eid} (rev {j['_oldid']} ts {j['_ts']})")
    print(sec[:9000])
    print()
