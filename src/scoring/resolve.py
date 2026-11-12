"""Guarded resolution: the ONLY sanctioned way to fill resolved/outcome/correct
on a pre-registration ledger by hand or by the autopilot.

Why this exists (finding #2 of the 2026-11-12 architecture audit):
  Resolution of the world, US-races, research and live-India ledgers was an LLM
  (or human) opening the CSV, editing cells and re-saving -- with "touch only
  the three resolution columns" enforced by prose, not code. A pandas round-trip
  or a stray keystroke could silently alter a pre-registered probability, and
  nothing would catch it. This tool makes that impossible:

  * It edits ONE line of the CSV in place, re-serializing only that row; every
    other line is written back byte-for-byte unchanged (no pandas, no round-trip
    of untouched rows).
  * It writes ONLY resolved / outcome / correct. A diff guard re-reads the file
    and ABORTS (restoring the original) if any other column of any row changed.
  * It resolves the LATEST run's row only (same rule as score.py and the app).
  * It REFUSES to overwrite a row already resolved to a different outcome --
    resolutions are final; a genuine correction is a deliberate, logged act, not
    a silent re-run.
  * --outcome must be in the ledger's allowed set; correct is computed, never
    typed. --source (the evidence URL) is required and appended to an
    append-only forecasts/resolution_log.csv with a UTC timestamp.

This does NOT fetch anything: the caller supplies the outcome from an
authoritative dated source (AP calls, ECI, official result) -- never from memory.
For EPL matches prefer epl_resolve.py (it auto-fetches the fixture feed); this
tool can resolve a match row manually if ever needed.

Usage:
  python resolve.py list  <ledger> [--id FORECAST_ID]
  python resolve.py set    <ledger> <selector> --outcome X --source URL [--date YYYY-MM-DD] [--dry-run]

  <ledger>   india | world | races | research | matches
  <selector> india/world/research : --id FORECAST_ID --question "EXACT TEXT"
             races                 : --race-id RACE_ID
             matches               : --match-id MATCH_ID
  --outcome  YES | NO | VOID        (matches: H | D | A | VOID)
  VOID marks a question that cannot resolve (e.g. an abandoned event); it is
  logged and excluded from scoring.
"""
import argparse
import csv
import io
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FDIR = ROOT / "forecasts"
RES_LOG = FDIR / "resolution_log.csv"

LEDGERS = {
    "india": {"path": FDIR / "ledger.csv", "identity": ["forecast_id", "question"],
              "verdict": "verdict", "outcomes": ["YES", "NO", "VOID"], "fav": False},
    "world": {"path": FDIR / "world_ledger.csv", "identity": ["forecast_id", "question"],
              "verdict": "verdict", "outcomes": ["YES", "NO", "VOID"], "fav": False},
    "races": {"path": FDIR / "world" / "usmid_races_ledger.csv", "identity": ["race_id"],
              "verdict": "verdict", "outcomes": ["YES", "NO", "VOID"], "fav": False},
    "research": {"path": FDIR / "research_ledger.csv", "identity": ["forecast_id", "question"],
                 "verdict": None, "outcomes": ["YES", "NO", "VOID"], "fav": False},
    "matches": {"path": FDIR / "matches_ledger.csv", "identity": ["match_id"],
                "verdict": None, "outcomes": ["H", "D", "A", "VOID"], "fav": True},
}
RES_COLS = ["resolved", "outcome", "correct"]


def _disp(p):
    """Repo-relative path for display, or the full path if it lives elsewhere."""
    try:
        return p.relative_to(ROOT)
    except ValueError:
        return p


def read_lines(path):
    """Raw physical lines (endings preserved) + the parsed header."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    lines = raw.splitlines(keepends=True)
    if not lines:
        sys.exit(f"ABORT: {path} is empty")
    header = next(csv.reader([lines[0]]))
    return lines, header


def parse_line(line):
    return next(csv.reader([line.rstrip("\r\n")]))


def serialize_fields(fields):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(fields)
    return buf.getvalue()


def compute_correct(spec, fields, header, outcome):
    if outcome == "VOID":
        return ""
    if spec["fav"]:  # matches: descriptive 'favourite hit?'
        p = {k: float(fields[header.index(c)]) for k, c in (("H", "p_home"), ("D", "p_draw"), ("A", "p_away"))}
        fav = max(p, key=p.get)
        return str(fav == outcome)
    if spec["verdict"] is None:  # research: single instrument, scored by Brier, no CALL
        return ""
    verdict = fields[header.index(spec["verdict"])]
    if verdict == "CALL-YES":
        return str(outcome == "YES")
    if verdict == "CALL-NO":
        return str(outcome == "NO")
    return ""  # WATCH / WATCH-FLAG / WATCH-1INST: no call was made, correct stays blank


def select_target(lines, header, spec, selectors):
    """Return (index_in_lines, parsed_fields) for the LATEST-run row matching
    the selectors, or exit with a clear message."""
    idx = {c: header.index(c) for c in spec["identity"] + ["run_at_utc"] + RES_COLS}
    candidates = []
    for i, line in enumerate(lines[1:], start=1):
        if not line.strip():
            continue
        fields = parse_line(line)
        if all(fields[idx[c]] == selectors[c] for c in spec["identity"]):
            candidates.append((i, fields))
    if not candidates:
        sys.exit("ABORT: no ledger row matches "
                 + ", ".join(f"{c}={selectors[c]!r}" for c in spec["identity"])
                 + " (use `list` to see exact identity values)")
    # latest run wins (ISO-8601 UTC strings sort correctly)
    i, fields = max(candidates, key=lambda t: t[1][idx["run_at_utc"]])
    return i, fields, idx


def cmd_set(ledger, spec, selectors, outcome, source, when, dry):
    if outcome not in spec["outcomes"]:
        sys.exit(f"ABORT: outcome {outcome!r} not allowed for '{ledger}' "
                 f"(allowed: {', '.join(spec['outcomes'])})")
    if not source:
        sys.exit("ABORT: --source (the authoritative evidence URL) is required")
    lines, header = read_lines(spec["path"])
    for c in RES_COLS:
        if c not in header:
            sys.exit(f"ABORT: {spec['path'].name} has no '{c}' column")
    i, fields, idx = select_target(lines, header, spec, selectors)

    existing_out = fields[idx["outcome"]].strip()
    existing_res = fields[idx["resolved"]].strip()
    if existing_res or existing_out:
        if existing_out == outcome:
            print(f"no-op: row already resolved as {outcome!r} on "
                  f"{existing_res or '?'} -- nothing to change.")
            return 0
        sys.exit(f"ABORT: row is already resolved as {existing_out!r} on "
                 f"{existing_res or '?'}. Resolutions are final; refusing to "
                 f"overwrite with {outcome!r}. (A real correction is a deliberate, "
                 f"separately logged act -- not this tool.)")

    correct = compute_correct(spec, fields, header, outcome)
    new_fields = list(fields)
    new_fields[idx["resolved"]] = when
    new_fields[idx["outcome"]] = outcome
    new_fields[idx["correct"]] = correct

    ident = ", ".join(f"{c}={selectors[c]}" for c in spec["identity"])
    print(f"ledger : {ledger}  ({_disp(spec['path'])})")
    print(f"row    : {ident}  [run {fields[idx['run_at_utc']]}]")
    print(f"set    : resolved={when}  outcome={outcome}  correct={correct or '(blank)'}")
    print(f"source : {source}")
    if dry:
        print("DRY RUN -- nothing written.")
        return 0

    # write only this one line back; every other physical line is unchanged
    ending = lines[i][len(lines[i].rstrip("\r\n")):]
    new_lines = list(lines)
    new_lines[i] = serialize_fields(new_fields) + ending
    out = "".join(new_lines)

    # diff guard: re-parse and confirm ONLY the three resolution cells of ONLY
    # this row changed -- abort without writing if anything else moved
    check = out.splitlines(keepends=True)
    if len(check) != len(lines):
        sys.exit("ABORT: line count changed -- refusing to write (bug guard)")
    for j, (old_l, new_l) in enumerate(zip(lines, check)):
        if j == i:
            o, n = parse_line(old_l), parse_line(new_l)
            changed = {header[k] for k in range(len(header)) if o[k] != n[k]}
            if changed - set(RES_COLS):
                sys.exit(f"ABORT: target row changed non-resolution column(s) "
                         f"{changed - set(RES_COLS)} -- refusing to write")
        elif old_l != new_l:
            sys.exit(f"ABORT: a non-target row (line {j}) changed -- refusing to write")

    with open(spec["path"], "w", encoding="utf-8", newline="") as f:
        f.write(out)

    log_new = not RES_LOG.exists()
    with open(RES_LOG, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if log_new:
            w.writerow(["logged_utc", "ledger", "identity", "outcome", "correct",
                        "resolved_date", "source"])
        w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    ledger, ident, outcome, correct, when, source])
    print(f"written. logged to {_disp(RES_LOG)}. "
          f"Now run: python src/scoring/score.py  &&  python src/scoring/verify_ledger.py")
    return 0


def cmd_list(ledger, spec, fid):
    lines, header = read_lines(spec["path"])
    idx = {c: header.index(c) for c in spec["identity"] + ["run_at_utc", "resolved"]}
    # latest run per identity; show the still-open ones
    latest = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        f = parse_line(line)
        key = tuple(f[idx[c]] for c in spec["identity"])
        if key not in latest or f[idx["run_at_utc"]] > latest[key][idx["run_at_utc"]]:
            latest[key] = f
    show = [f for f in latest.values()
            if not f[idx["resolved"]].strip()
            and (fid is None or f[idx[spec["identity"][0]]] == fid)]
    if not show:
        print(f"[{ledger}] no open (unresolved latest) rows"
              + (f" for {fid}" if fid else ""))
        return 0
    pcols = [c for c in ("p_m2", "p_m3", "p_model", "p_market", "p_research",
                         "p_home", "p_draw", "p_away", "verdict") if c in header]
    print(f"[{ledger}] {len(show)} open row(s) -- copy the identity exactly into `set`:")
    for f in sorted(show, key=lambda r: tuple(r[idx[c]] for c in spec["identity"])):
        ident = "  ".join(f"{c}={f[header.index(c)]!r}" for c in spec["identity"])
        probs = " ".join(f"{c}={f[header.index(c)]}" for c in pcols)
        print(f"  {ident}\n      {probs}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Guarded ledger resolution.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("list"); pl.add_argument("ledger"); pl.add_argument("--id", default=None)
    ps = sub.add_parser("set"); ps.add_argument("ledger")
    ps.add_argument("--id"); ps.add_argument("--question")
    ps.add_argument("--race-id"); ps.add_argument("--match-id")
    ps.add_argument("--outcome", required=True)
    ps.add_argument("--source", required=True)
    ps.add_argument("--date", default=date.today().isoformat())
    ps.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    if a.ledger not in LEDGERS:
        sys.exit(f"unknown ledger {a.ledger!r}; choose from {', '.join(LEDGERS)}")
    spec = LEDGERS[a.ledger]
    if not spec["path"].exists():
        sys.exit(f"ABORT: {spec['path']} does not exist yet")

    if a.cmd == "list":
        return cmd_list(a.ledger, spec, a.id)

    # build selectors for the ledger's identity columns
    sel = {}
    for c in spec["identity"]:
        val = {"forecast_id": a.id, "question": a.question,
               "race_id": a.race_id, "match_id": a.match_id}.get(c)
        if not val:
            sys.exit(f"ABORT: '{a.ledger}' needs --{c.replace('_', '-')} "
                     f"(identity columns: {', '.join(spec['identity'])})")
        sel[c] = val
    return cmd_set(a.ledger, spec, sel, a.outcome.strip(), a.source,
                   a.date, a.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
