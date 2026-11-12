"""Deep integrity audit: reconcile every ledger row against its hashed forecast
payload, and the hashes against the OpenTimestamps anchors.

Why this exists (finding #1 of the 2026-11-12 architecture audit):
  The ledgers carry a `forecast_sha256` (or `dossier_sha256`) per row, and
  anchor.py proves those hash STRINGS existed before the event and were never
  removed. But nothing re-derived those hashes from the actual forecast files,
  and nothing checked that the probability shown and scored (the ledger row's
  p_* columns) still equals the probability inside the hashed payload. So a
  drift in any pre-registered number -- a manual slip, an autopilot edit, a
  pandas round-trip during resolution -- was undetectable, yet the app presents
  it under a "verified, before the event" banner.

What a PASS here actually proves, per LATEST-run row (the rows that score.py
scores and the app displays):
  (a) the on-disk forecast payload re-hashes to EXACTLY the hash stored on the
      row  -> the hash is an honest fingerprint of this payload, not a label;
  (b) the row's p_* and verdict equal the payload's for the same question
      -> the number you see and score is the number that was hashed;
  (c) that hash appears in an anchored manifest (else: flagged "pending anchor"
      -- expected only for rows newer than the last stamp run).
Superseded rows (older runs whose payload was overwritten on disk) can't be
re-hashed from disk; they are covered by anchor.py's append-only presence audit
and reported here as "superseded (hash-presence only)". score.py and the app
use only the latest run, so the deep check covers exactly what is published.

Hashing note: every engine hashes json.dumps(obj, indent=1, sort_keys=True);
Path.write_text may translate newlines on Windows, so we recompute by
re-canonicalizing the LOADED json (newline-proof), never by hashing raw bytes.
m_research writes the artifact WITH a dossier_sha256 key that was added AFTER
hashing, so that key is stripped before rehashing.

Usage: python verify_ledger.py            (audits all five ledgers)
       python verify_ledger.py --quiet     (summary + failures only)
Exit code 0 = OK, 1 = at least one integrity failure (red alert).
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FDIR = ROOT / "forecasts"
ADIR = FDIR / "anchors"
TOL = 1e-6  # all probabilities are stored rounded to 4 dp

# Per-ledger spec. sha_col: the row's hash column. group_by: what maps a set of
# rows to one forecast payload file. payload_list/payload_key: where the payload
# keeps its per-question entries and how to key them. row_key: the ledger column
# whose value matches payload_key. fields: (ledger_col, payload_field) pairs to
# reconcile. strip_key: a key written into the file AFTER hashing (research only).
LEDGERS = {
    "india": {
        "path": FDIR / "ledger.csv", "sha_col": "forecast_sha256",
        "group_by": "forecast_id",
        "jpath": lambda row: FDIR / f"{row['forecast_id']}_forecast.json",
        "payload_list": "questions", "payload_key": "question", "row_key": "question",
        "fields": [("p_m2", "p_m2"), ("p_m3", "p_m3"), ("p_gate", "p_gate"), ("verdict", "verdict")],
        "strip_key": None,
    },
    "world": {
        "path": FDIR / "world_ledger.csv", "sha_col": "forecast_sha256",
        "group_by": "forecast_id",
        "jpath": lambda row: FDIR / "world" / f"{row['forecast_id']}_forecast.json",
        "payload_list": "questions", "payload_key": "q", "row_key": "question",
        "fields": [("p_market", "p_market"), ("p_model", "p_model"), ("p_gate", "p_gate"), ("verdict", "verdict")],
        "strip_key": None,
    },
    "races": {
        "path": FDIR / "world" / "usmid_races_ledger.csv", "sha_col": "forecast_sha256",
        "group_by": "forecast_id",
        "jpath": lambda row: FDIR / "world" / f"{row['forecast_id']}_forecast.json",
        "payload_list": "races", "payload_key": "race_id", "row_key": "race_id",
        "fields": [("p_market", "p_market"), ("p_model", "p_model"), ("p_gate", "p_gate"), ("verdict", "verdict")],
        "strip_key": None,
    },
    "matches": {
        "path": FDIR / "matches_ledger.csv", "sha_col": "forecast_sha256",
        "group_by": "matchweek",
        "jpath": lambda row: FDIR / "world" / f"EPL_MW{int(row['matchweek']):02d}_forecast.json",
        "payload_list": "matches", "payload_key": "match_id", "row_key": "match_id",
        "fields": [("p_home", "p_home"), ("p_draw", "p_draw"), ("p_away", "p_away")],
        "strip_key": None,
    },
    "research": {
        "path": FDIR / "research_ledger.csv", "sha_col": "dossier_sha256",
        "group_by": "forecast_id",
        "jpath": lambda row: FDIR / "research" / f"{row['forecast_id']}_research.json",
        "payload_list": "questions", "payload_key": "q", "row_key": "question",
        "fields": [("p_raw", "p_raw"), ("p_research", "p_research")],
        "strip_key": "dossier_sha256",
    },
}


def canonical_hash(path, strip_key=None):
    """Return (loaded_obj, hash) where hash reproduces the bytes the engine
    hashed: json.dumps(payload, indent=1, sort_keys=True), minus strip_key."""
    obj = json.loads(path.read_text(encoding="utf-8"))
    payload_obj = {k: v for k, v in obj.items() if k != strip_key} if strip_key else obj
    payload = json.dumps(payload_obj, indent=1, sort_keys=True)
    return obj, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _num(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() in ("nan", "none", "na", "null"):
        return None
    return float(s)


def _nums_equal(a, b):
    a, b = _num(a), _num(b)
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= TOL


def read_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def anchored_hashes():
    """Union of every forecast hash present in any anchored manifest."""
    seen = set()
    if not ADIR.exists():
        return seen
    for mp in sorted(ADIR.glob("manifest_*.json")):
        if mp.name.endswith(".ots"):
            continue
        try:
            man = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for info in man.get("ledgers", {}).values():
            seen.update(info.get("forecast_hashes", []))
    return seen


def audit_ledger(name, spec, anchored, quiet):
    path = spec["path"]
    if not path.exists():
        print(f"[{name}] no ledger file yet -- skipped")
        return 0, 0, 0, 0
    rows = read_rows(path)
    if not rows:
        print(f"[{name}] empty ledger -- skipped")
        return 0, 0, 0, 0
    sha_col = spec["sha_col"]
    for col in (spec["group_by"], sha_col, "run_at_utc", spec["row_key"]):
        if col not in rows[0]:
            print(f"[{name}] FAIL: ledger is missing expected column '{col}' "
                  f"(schema drift) -- aborting this ledger")
            return 0, 0, 0, 1

    groups = {}
    for r in rows:
        groups.setdefault(r[spec["group_by"]], []).append(r)

    n_verified = n_superseded = n_pending = n_fail = 0
    for gid, grp in sorted(groups.items()):
        latest_run = max(r["run_at_utc"] for r in grp)
        latest = [r for r in grp if r["run_at_utc"] == latest_run]
        superseded = len(grp) - len(latest)
        n_superseded += superseded
        latest_shas = {r[sha_col] for r in latest}

        jpath = spec["jpath"](latest[0])
        if not jpath.exists():
            print(f"[{name}] FAIL {gid}: latest forecast payload {jpath.name} is "
                  f"MISSING -- cannot verify {len(latest)} published row(s)")
            n_fail += len(latest)
            continue
        try:
            obj, cur_hash = canonical_hash(jpath, spec["strip_key"])
        except Exception as e:
            print(f"[{name}] FAIL {gid}: cannot read/parse {jpath.name}: {e}")
            n_fail += len(latest)
            continue

        if latest_shas != {cur_hash}:
            stored = sorted(latest_shas)[0]
            print(f"[{name}] FAIL {gid}: on-disk {jpath.name} re-hashes to "
                  f"{cur_hash[:12]} but the newest ledger rows (run {latest_run}) "
                  f"carry {stored[:12]} -- file and ledger DISAGREE "
                  f"(payload edited, or ledger rows altered)")
            n_fail += len(latest)
            continue

        index = {str(e[spec["payload_key"]]): e for e in obj.get(spec["payload_list"], [])}
        for r in latest:
            entry = index.get(str(r[spec["row_key"]]))
            if entry is None:
                print(f"[{name}] FAIL {gid}: ledger row key "
                      f"'{r[spec['row_key']]}' has no match in the hashed payload")
                n_fail += 1
                continue
            bad = []
            for rc, pf in spec["fields"]:
                rv, pv = r.get(rc), entry.get(pf)
                if pf == "verdict":
                    if str(rv or "") != str(pv or ""):
                        bad.append(f"{rc}: ledger={rv!r} payload={pv!r}")
                elif not _nums_equal(rv, pv):
                    bad.append(f"{rc}: ledger={rv!r} payload={pv!r}")
            if bad:
                print(f"[{name}] FAIL {gid} / '{r[spec['row_key']]}': "
                      f"row does not match hashed payload -> " + "; ".join(bad))
                n_fail += 1
                continue
            n_verified += 1
            if anchored and r[sha_col] not in anchored:
                n_pending += 1

    status = "FAIL" if n_fail else "ok"
    print(f"[{name}] {status}: {n_verified} published row(s) reconciled to their "
          f"hashed payload, {n_superseded} superseded (hash-presence only), "
          f"{n_pending} pending anchor, {n_fail} FAILED")
    return n_verified, n_superseded, n_pending, n_fail


def main(argv):
    quiet = "--quiet" in argv
    anchored = anchored_hashes()
    if not anchored:
        print("note: no anchored manifests found -- 'pending anchor' counts omitted\n")
    tot_v = tot_s = tot_p = tot_f = 0
    for name, spec in LEDGERS.items():
        v, s, p, f = audit_ledger(name, spec, anchored, quiet)
        tot_v += v; tot_s += s; tot_p += p; tot_f += f
    print("\n" + "=" * 60)
    print(f"VERIFY-LEDGER: {'OK' if tot_f == 0 else 'FAILED'} -- "
          f"{tot_v} published rows match their hashed payloads, "
          f"{tot_s} superseded, {tot_p} pending anchor, {tot_f} failures")
    if tot_p and not tot_f:
        print(f"  ({tot_p} published rows are not yet in an anchored manifest -- "
              f"run anchor.py stamp; this is not a failure)")
    return 1 if tot_f else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
