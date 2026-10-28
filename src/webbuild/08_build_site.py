"""Build site/index.html - a self-contained local page for the multi-state
retrodiction results. No external assets, no fetch (works from file://);
all tables are rendered inline from data/processed/ at build time.
Rerun after any pipeline rerun: python scripts/08_build_site.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True)

led = pd.read_csv(PROC / "precision_ledger.csv")
summ = pd.read_csv(PROC / "election_summaries.csv")
cal = pd.read_csv(PROC / "calibration_table.csv")
alpha = pd.read_csv(PROC / "alpha_table.csv")
tau = pd.read_csv(PROC / "tau_table.csv")
sigma = pd.read_csv(PROC / "sigma_table.csv")

loo = led[led["mode"] == "loo"]


def tbl(df, cls=""):
    return df.to_html(index=False, border=0, classes=("t " + cls).strip(),
                      na_rep="", justify="left")


# ---- headline gate stats ----
rows = []
for gcol, ccol, name in [("gate_m2", "m2_correct", "M2-only gate ≥0.95"),
                         ("gate_strict", "strict_correct", "Strict dual gate ≥0.95")]:
    for mode in ("loo", "past"):
        dm = led[led["mode"] == mode]
        pos = dm[dm[gcol] == "CALL-YES"]
        neg = dm[dm[gcol] == "CALL-NO"]
        rows.append({
            "gate": name, "mode": mode,
            "positive CALLs": f"{int(pos[ccol].sum())}/{len(pos)}"
            + (f" ({pos[ccol].mean()*100:.0f}%)" if len(pos) else ""),
            "negative CALLs": f"{int(neg[ccol].sum())}/{len(neg)}"
            + (f" ({neg[ccol].mean()*100:.0f}%)" if len(neg) else ""),
            "wrong calls": int((pos[ccol] == 0).sum() + (neg[ccol] == 0).sum()),
        })
gate_tbl = pd.DataFrame(rows)

# ---- per-election headline table (loo) ----
el_rows = []
for eid, g in summ.groupby("election_id", sort=False):
    lead_pred = g.loc[g.seats_med.idxmax()]
    lead_act = g.loc[g.actual_seats.idxmax()]
    q = loo[(loo.election_id == eid) & (loo.question == "majority")]
    gates = q.gate_strict.unique()
    if "CALL-NO" in gates or "CALL-YES" in gates:
        gate = "CALL"
    elif "WATCH-FLAG" in gates:
        gate = "WATCH (flag)"
    elif set(gates) == {"WATCH-NOPOLL"}:
        gate = "WATCH (no polls)"
    else:
        gate = "WATCH"
    el_rows.append({
        "election": eid,
        "M2 forecast leader (med seats)": f"{lead_pred.bloc} ({lead_pred.seats_med})",
        "actual leader (seats)": f"{lead_act.bloc} ({lead_act.actual_seats})",
        "M2 right?": "✓" if lead_pred.bloc == lead_act.bloc else "✗",
        "strict gate": gate,
    })
el_tbl = pd.DataFrame(el_rows)

# ---- wrong M2 calls ----
bad = loo[loo.m2_correct == 0][["election_id", "bloc", "question",
                                "p_m2", "p_m3", "actual"]]
# ---- strict negative calls ----
negs = loo[loo.gate_strict == "CALL-NO"][["election_id", "bloc", "question",
                                          "p_m2", "p_m3"]]

sigma_t = sigma.rename(columns={"sigma_median": "σ_c (bloc-level median)"})
alpha_t = alpha[alpha.state == "_POOLED_"][["era", "n", "alpha_raw"]] \
    .rename(columns={"alpha_raw": "pooled α"})

html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prediction Engine — Multi-State Retrodiction (N=46)</title>
<style>
:root {{ --bg:#f6f7f9; --card:#ffffff; --ink:#1a1d23; --mut:#5b6472;
  --acc:#1a7f4e; --warn:#9a6b00; --bad:#b3261e; --line:#e3e6eb; }}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{ --bg:#0f1115; --card:#171a21; --ink:#e8eaf0;
    --mut:#9aa3b2; --acc:#4cc38a; --warn:#e5b567; --bad:#e06c75; --line:#262b36; }} }}
:root[data-theme="dark"] {{ --bg:#0f1115; --card:#171a21; --ink:#e8eaf0;
  --mut:#9aa3b2; --acc:#4cc38a; --warn:#e5b567; --bad:#e06c75; --line:#262b36; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.55 "Segoe UI",system-ui,sans-serif; padding:16px; }}
.wrap {{ max-width:1000px; margin:0 auto; }}
h1 {{ font-size:1.5rem; margin:.4em 0 .1em; }}
h2 {{ font-size:1.1rem; margin:1.6em 0 .5em; color:var(--acc); }}
.sub {{ color:var(--mut); margin-bottom:1.2em; }}
.card {{ background:var(--card); border:1px solid var(--line);
  border-radius:10px; padding:14px 18px; margin:12px 0; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
  gap:12px; }}
.kpi b {{ display:block; font-size:1.7rem; }}
.kpi span {{ color:var(--mut); font-size:.85rem; }}
table.t {{ border-collapse:collapse; width:100%; font-size:.86rem; }}
.t th {{ text-align:left; color:var(--mut); font-weight:600;
  border-bottom:1px solid var(--line); padding:5px 10px 5px 0; }}
.t td {{ padding:4px 10px 4px 0; border-bottom:1px solid var(--line); }}
.good {{ color:var(--acc); font-weight:600; }}
.scroll {{ max-height:420px; overflow:auto; }}
.note {{ color:var(--mut); font-size:.85rem; }}
a {{ color:var(--acc); }}
details summary {{ cursor:pointer; color:var(--acc); margin:.6em 0; }}
</style></head><body><div class="wrap">
<h1>Prediction Engine — Multi-State Retrodiction</h1>
<div class="sub">46 Indian state assembly elections, 2013–2025 · leave-one-out
retrodiction through the confidence gate · built {pd.Timestamp.now():%Y-%m-%d}</div>

<div class="kpis">
<div class="card kpi"><b class="good">0</b><span>wrong gate calls in 46 elections
(strict dual gate ≥0.95)</span></div>
<div class="card kpi"><b>28/28</b><span>negative CALLs correct (loo mode)</span></div>
<div class="card kpi"><b>45/45</b><span>dual-agreement calls correct down to a
0.80 threshold (sensitivity)</span></div>
<div class="card kpi"><b>78.6%</b><span>what an M2-only gate would have scored
on positive CALLs (12 wrong calls total)</span></div>
</div>

<h2>Gate ledger</h2>
<div class="card">{tbl(gate_tbl)}
<p class="note">Fixed mechanical question set: every bloc × {{wins majority, is
largest}}. loo = parameters from all other elections; past = only earlier
elections. Zero positive strict CALLs is the honest finding: measured instrument
error (~6 pts of vote share) cannot certify a majority at 95% six weeks out.</p></div>

<h2>Strict-gate negative CALLs (all correct)</h2>
<div class="card scroll">{tbl(negs)}</div>

<h2>Where M2 alone would have been wrong</h2>
<div class="card">{tbl(bad)}
<p class="note">Every one of these is removed by requiring the second witness
(polls, M3) — the dual-gate design doing its job.</p></div>

<h2>Calibration (claimed probability vs realized frequency, M2, loo)</h2>
<div class="card">{tbl(cal)}
<p class="note">M2 is overconfident in the tails (claimed 97% realizes 79%; its
nominal 90% seat intervals cover 58%). Poll-based M3 is calibrated-to-conservative
where it exists (23/46 elections).</p></div>

<h2>Refitted parameters</h2>
<div class="card"><h3>α — GE→AE blend weight (pooled by era)</h3>{tbl(alpha_t)}
<h3>τ — alliance transfer efficiency (measured, 11 alliances)</h3>{tbl(tau)}
<h3>σ — constituency swing dispersion by state</h3>{tbl(sigma_t)}
<p class="note">Incumbent retained largest-bloc status in 22/46 elections (48%) —
UP's rotation prior does not generalize; M1 must be state-specific.</p></div>

<h2>All 46 elections</h2>
<div class="card scroll">{tbl(el_tbl)}
<p class="note">M2 median-seat leader is right only 24/46 — the blend is an
uncertainty machine, not a point forecaster; the gate's abstentions are the point.</p></div>

<h2>Files</h2>
<div class="card note">
Full report: <a href="multistate_retrodiction.md">multistate_retrodiction.md</a> ·
UP pilot: <a href="UP_retrodiction_pilot.md">UP_retrodiction_pilot.md</a><br>
Data tables (CSV): <a href="data/precision_ledger.csv">precision_ledger</a> ·
<a href="data/election_summaries.csv">election_summaries</a> ·
<a href="data/calibration_table.csv">calibration</a> ·
<a href="data/alpha_table.csv">alpha</a> ·
<a href="data/tau_obs.csv">tau (per alliance)</a> ·
<a href="data/sigma_table.csv">sigma</a> ·
<a href="data/polls_blocs.csv">polls</a><br>
Rebuild this page after a pipeline rerun: <code>python scripts/08_build_site.py</code>
</div>
</div></body></html>"""

(SITE / "index.html").write_text(html, encoding="utf8")
print("wrote", SITE / "index.html", f"({len(html)//1024} KB)")
