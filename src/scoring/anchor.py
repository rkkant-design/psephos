"""External anchoring of Psephos' pre-registration ledgers via OpenTimestamps.

Why: the ledgers' SHA-256 hashes prove internally that forecasts weren't edited
after the fact — but only to someone who trusts us. OpenTimestamps anchors a
manifest of those hashes into the Bitcoin blockchain through public calendar
servers (free, accountless), making "this forecast existed before resolution"
provable by anyone, trusting no one.

Usage:
  python anchor.py stamp     - build manifest of all ledgers' current state,
                               write forecasts/anchors/manifest_<utc>.json,
                               stamp it (creates .ots proof alongside)
  python anchor.py upgrade   - upgrade pending .ots proofs (Bitcoin attestation
                               typically lands within hours; run on later days)
  python anchor.py verify    - verify every manifest against its .ots proof
                               and re-check the recorded forecast hashes still
                               exist in the ledgers (append-only audit)

Manifest contents: sha256 of each ledger FILE (point-in-time state) plus the
sorted set of all distinct forecast_sha256 values seen in each ledger. A later
auditor checks: (a) the .ots proof shows the manifest existed at time T
(Bitcoin block), (b) every hash in it appears in today's ledger (nothing
removed), (c) a forecast's hash appears in a manifest stamped before the
event resolved. Ledgers stay append-only; manifests accumulate, never change.
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FDIR = ROOT / "forecasts"
ADIR = FDIR / "anchors"
ADIR.mkdir(exist_ok=True)

LEDGERS = ["ledger.csv", "world_ledger.csv", "research_ledger.csv", "matches_ledger.csv",
           "world/usmid_races_ledger.csv"]

def sha256_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def build_manifest():
    man = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "ledgers": {}}
    for name in LEDGERS:
        p = FDIR / name
        if not p.exists():
            continue
        df = pd.read_csv(p)
        col = "forecast_sha256" if "forecast_sha256" in df.columns else None
        man["ledgers"][name] = {
            "file_sha256": sha256_file(p),
            "rows": int(len(df)),
            "forecast_hashes": sorted(df[col].dropna().unique().tolist()) if col else [],
        }
    return man

def ots(args):
    shim = Path(__file__).resolve().parent / "_ots_run.py"
    return subprocess.run([sys.executable, str(shim)] + args,
                          capture_output=True, text=True, timeout=120)

def cmd_stamp():
    man = build_manifest()
    ts = man["created_utc"].replace(":", "").replace("-", "")[:15]
    mp = ADIR / f"manifest_{ts}.json"
    mp.write_text(json.dumps(man, indent=1), encoding="utf-8")
    print(f"manifest: {mp.name} | sha256 {sha256_file(mp)}")
    r = ots(["stamp", str(mp)])
    print(r.stdout.strip() or r.stderr.strip())
    if (mp.with_suffix(mp.suffix + ".ots")).exists():
        print(f"PROOF CREATED: {mp.name}.ots (pending Bitcoin attestation; "
              f"run 'python anchor.py upgrade' in a day to finalize)")
    else:
        print("WARNING: no .ots produced - calendar servers unreachable? "
              "Manifest still written; re-run stamp later. The manifest itself "
              "remains internally verifiable meanwhile.")

def cmd_upgrade():
    for p in sorted(ADIR.glob("*.ots")):
        r = ots(["upgrade", str(p)])
        print(p.name, "->", (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else "ok")

def cmd_verify():
    ok = True
    current = {}
    for name in LEDGERS:
        p = FDIR / name
        if p.exists():
            df = pd.read_csv(p)
            col = "forecast_sha256" if "forecast_sha256" in df.columns else None
            current[name] = set(df[col].dropna().unique()) if col else set()
    for mp in sorted(ADIR.glob("manifest_*.json")):
        man = json.loads(mp.read_text(encoding="utf-8"))
        missing = []
        for name, info in man["ledgers"].items():
            gone = [h for h in info["forecast_hashes"] if h not in current.get(name, set())]
            missing += [(name, h) for h in gone]
        if missing:
            ok = False
            print(f"APPEND-ONLY VIOLATION in {mp.name}: {len(missing)} anchored "
                  f"hashes no longer present: {missing[:3]}...")
        else:
            print(f"{mp.name}: all {sum(len(i['forecast_hashes']) for i in man['ledgers'].values())} "
                  f"anchored hashes still present")
        otsp = Path(str(mp) + ".ots")
        if otsp.exists():
            r = ots(["verify", "-f", str(mp), str(otsp)])
            out = (r.stdout + r.stderr).strip()
            tail = out.splitlines()[-1] if out else "no output"
            print(f"  ots: {tail}")
        else:
            print(f"  ots: NO PROOF FILE (stamp failed or pending)")
    print("VERIFY:", "OK" if ok else "FAILED")

if __name__ == "__main__":
    {"stamp": cmd_stamp, "upgrade": cmd_upgrade, "verify": cmd_verify}[sys.argv[1]]()
