"""Shared helpers for the multi-state pipeline (04/05/06)."""
import difflib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
META = ROOT / "data" / "raw" / "multistate" / "meta"


def load_all():
    ae = pd.read_csv(PROC / "ae_long.csv")
    ss = pd.read_csv(PROC / "state_shares_all.csv")
    el = pd.read_csv(META / "elections.csv")
    blocs = pd.read_csv(META / "blocs.csv")
    return ae, ss, el, blocs


def wide_shares(ae, eid):
    """ACs x parties share matrix for one election; index = ac key."""
    d = ae[ae.election_id == eid].copy()
    if d.empty:
        return None
    use_no = d.ac_no.notna().all()
    d["key"] = d.ac_no.astype(int) if use_no else d.ac_name
    w = d.pivot_table(index="key", columns="party", values="share", aggfunc="sum").fillna(0)
    w.attrs["keyed_by"] = "no" if use_no else "name"
    # name lookup for cross-matching
    w.attrs["names"] = d.groupby("key").ac_name.first().to_dict()
    return w


def match_acs(w_base, w_targ):
    """Return list of (base_key, targ_key) matched constituency pairs.

    Prefer AC numbers when both sides have them and counts agree; else
    normalized-name match with difflib fallback (>=0.8 cutoff).
    """
    if w_base.attrs["keyed_by"] == "no" and w_targ.attrs["keyed_by"] == "no":
        common = sorted(set(w_base.index) & set(w_targ.index))
        if len(common) >= 0.9 * min(len(w_base), len(w_targ)):
            return [(k, k) for k in common]
    bnames = {k: v for k, v in w_base.attrs["names"].items()}
    tnames = {k: v for k, v in w_targ.attrs["names"].items()}
    rev_t = {}
    for k, v in tnames.items():
        rev_t.setdefault(v, k)
    pairs, unmatched = [], []
    used_t = set()
    for bk, bn in bnames.items():
        tk = rev_t.get(bn)
        if tk is not None and tk not in used_t:
            pairs.append((bk, tk))
            used_t.add(tk)
        else:
            unmatched.append((bk, bn))
    tpool = {v: k for k, v in tnames.items() if k not in used_t}
    for bk, bn in unmatched:
        hit = difflib.get_close_matches(bn, list(tpool), n=1, cutoff=0.8)
        if hit:
            tk = tpool.pop(hit[0])
            pairs.append((bk, tk))
    return pairs


def state_share_map(ss, election):
    d = ss[ss.election == election]
    return dict(zip(d.party, d.share))


def bloc_weights(blocs, eid, scope, tau):
    """{bloc: {party: numeric weight}} for 'ae' or 'ge' scope."""
    d = blocs[(blocs.election_id == eid) & (blocs.scope.isin([scope, "both"]))]
    out = {}
    wmap = {"1": 1.0, "t": tau, "h": 0.5 * tau}
    for _, r in d.iterrows():
        out.setdefault(r.bloc, {})[r.party] = wmap[str(r.w)]
    return out
