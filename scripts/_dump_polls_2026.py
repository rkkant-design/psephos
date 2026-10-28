import io
import json
import sys
from pathlib import Path

import pandas as pd

pd.set_option("display.width", 300)
pd.set_option("display.max_columns", 25)

FILES = {
    "AS2026": "AS2026__2026-04-08.json",
    "KL2026": "KL2026__2026-04-08.json",
    "TN2026": "TN2026__2026-04-22.json",
    "WB2026": "WB2026__2026-04-22.json",
}
DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "holdout2026" / "wiki_frozen"

for eid in (sys.argv[1:] or FILES):
    j = json.loads((DIR / FILES[eid]).read_text(encoding="utf8"))
    html = j["parse"]["text"]["*"]
    tables = pd.read_html(io.StringIO(html), flavor="html5lib")
    print("=" * 20, eid)
    for ti, t in enumerate(tables):
        txt = " ".join(str(v) for v in t.head(2).to_numpy().ravel()) + " ".join(str(c) for c in t.columns)
        if "Polling agency" in txt or "Polling Agency" in txt:
            print(f"--- table {ti} shape {t.shape}")
            print(t.to_string(max_rows=30))
