# 2026 Holdout Test — WB / TN / KL / AS (first true out-of-sample run)

**Date:** 2026-10-16 · **Scope:** Run the frozen N=46 engine, unchanged, on the four 2026 state elections that were deliberately excluded from every fit and ledger. These elections (polled 9–29 Apr 2026, counted 4 May 2026) post-date the model's training-data horizon and every parameter fit, so nothing about their outcomes could have leaked into the engine. Forecasts were pre-registered (SHA256, `forecasts/ledger.csv`) **before** any result was looked up; results were fetched only after all 35 ledger rows were hashed.

## Verdict

**The gate made its first wrong calls: 9 CALLs, 6 correct — 66.7% precision, far below the ≥95% design target. All three failures have a single root cause, and it is the one the pre-registered config itself flagged: TVK, a new entrant with zero electoral base.** In Tamil Nadu, actor Vijay's Tamilaga Vettri Kazhagam — polling 10–15% pre-freeze, invisible to M2 by construction — won 35.0% of the vote and became the largest bloc with 108/234 seats. The engine CALL-NO'd "TVK is largest", CALL-YES'd "Winner in {SPA, NDA}", and CALL-YES'd "TVK under 40 seats" (gate 0.992). All three wrong; they are two independent events (TVK-largest counted twice via the complementary top-2 question).

**Everywhere else the architecture did exactly what the retrodiction promised.** West Bengal produced a polling catastrophe — every pre-election poll, to election eve, had AITC ahead 41–45 vs 35–42; the actual result was a BJP landslide (45.9%, 208/294 vs AITC 41.0%, 80). The engine's sub-threshold lean was wrong (AITC majority p≈0.76) but the dual gate **abstained on every WB single-bloc question** and its one WB CALL (winner in {AITC, BJP}) was correct. Kerala (UDF 102/140 — LDF's lone pre-freeze poll had the wrong leader) and Assam (NDA sweep 102/126) resolved 4-for-4 on CALLs with correct abstentions elsewhere.

| Election | CALLs | correct | wrong | note |
|---|---|---|---|---|
| WB2026 | 1 | 1 | 0 | abstained through a 10-pt dual polling+structure miss |
| TN2026 | 4 | 1 | 3 | all wrong calls trace to the TVK blind spot |
| KL2026 | 3 | 3 | 0 | incl. two correct CALL-NOs on NDA |
| AS2026 | 1 | 1 | 0 | |
| **2026 total** | **9** | **6** | **3** | **66.7%** |

Lifetime ledger: N=46 retrodiction 28/28 + 2026 forward 6/9 = **34/37 = 91.9%**, now below the 95% target. First positive CALLs ever issued: 5, of which 3 correct.

## The governance failure that matters more than the forecast failure

The N=46 pipeline (`05_loo_retrodict.py`) forces **WATCH-FLAG on every question of a new-entrant election** — the stated rule: *a serious contender invisible to both baseline AE and prior GE* — and excludes those elections from precision claims (AAP×3, KJP, JCC, JJP, Jan Suraaj…). TVK satisfies that definition exactly, and the TN2026 config said so in prose at freeze ("This election is a stress test of the engine's new-entrant blind spot"). But **`predict.py` never implemented the flag mechanism**, so the engine issued CALLs the validated protocol would have suppressed. Under the engine's own already-written rule, TN2026 would have been entirely WATCH-FLAG and the 2026 record would be 6/6. That is *not* the pre-registered record — 6/9 stands in the ledger — but the fix is not a new idea, it is porting an existing safeguard to the forward tool. Related structural artifact: "Winner in {SPA, NDA}" carried gate = 1.000 partly because M2 assigns a baseline-less bloc exactly zero — a certainty manufactured by model closure, not evidence.

## Pre-registered forecasts vs actuals

Vote shares (pts; M3 = corrected final-window polls):

| | bloc | M2 | M3 | **actual** | M2 err | M3 err |
|---|---|---|---|---|---|---|
| WB | AITC | 47.1 | 46.3 | **41.0** | +6.1 | +5.3 |
| WB | BJP | 39.0 | 38.9 | **45.9** | −6.9 | −7.0 |
| TN | SPA | 47.5 | 40.1 | **31.4** | +16.1 | +8.7 |
| TN | NDA (ADMK+) | 39.9 | 40.7 | **27.2** | +12.7 | +13.5 |
| TN | TVK | 0.0 | 13.1 | **35.0** | −35.0 | −22.0 |
| KL | LDF | 37.3 | 42.5 | **37.6** | −0.4 | +4.9 |
| KL | UDF | 40.4 | 41.5 | **46.6** | −6.2 | −5.0 |
| KL | NDA | 15.0 | 12.5 | **14.2** | +0.8 | −1.7 |
| AS | NDA | 45.3 | 43.7 | **48.0** | −2.7 | −4.3 |
| AS | ASOM | 36.5 | 38.6 | **36.0** | +0.6 | +2.6 |
| AS | AIUDF | 6.2 | — | **5.5** | +0.7 | — |

Mean |error|: M2 7.0 pts (vs 6.3 retrodiction sd), M3 7.5 pts (vs ~5.6) — but bimodal: excluding TN, M2's mean |error| is 2.9 pts (KL/AS near-exact); WB and TN are regime breaks (a 10-pt two-party polling miss; a three-way fracture with 35% going to a party that did not exist in any baseline).

Seats (median, 5–95% interval vs actual): **M2 intervals covered 5/13, M3 2/10** — the retrodiction's warning that M2's nominal 90% intervals cover 58% got worse out of sample, in a cycle of three landslides and one fracture. Majorities: WB 148 → BJP 208 (M2 median 106); TN 118 → none (TVK largest 108); KL 71 → UDF 102 (M2 median 66); AS 64 → NDA 102 (M2 median 69).

## Resolved gate ledger (full rows in `forecasts/ledger.csv`, SHA-hashed pre-registration)

| question | gate | verdict | outcome | correct |
|---|---|---|---|---|
| WB: Winner (largest) in {AITC, BJP} | 1.000 | CALL-YES | YES (BJP) | ✓ |
| TN: TVK wins majority | 0.000 | CALL-NO | NO (108 < 118) | ✓ |
| TN: TVK is largest | 0.000 | CALL-NO | **YES** | ✗ |
| TN: Winner (largest) in {SPA, NDA} | 1.000 | CALL-YES | **NO (TVK)** | ✗ |
| TN: TVK under 40 seats | 0.992 | CALL-YES | **NO (108)** | ✗ |
| KL: NDA wins majority | 0.000 | CALL-NO | NO (3) | ✓ |
| KL: NDA is largest | 0.000 | CALL-NO | NO | ✓ |
| KL: Winner (largest) in {LDF, UDF} | 1.000 | CALL-YES | YES (UDF) | ✓ |
| AS: Winner (largest) in {NDA, ASOM} | 1.000 | CALL-YES | YES (NDA) | ✓ |

Remaining 26 rows: WATCH / WATCH-NOPOLL, all resolved for calibration. Notable correct abstentions: WB AITC majority (gate 0.761 → NO), WB BJP majority (0.163 → **YES**), AS NDA majority (0.647 → YES), KL LDF vs UDF largest (0.48/0.34 — polls had the wrong leader).

**Threshold sensitivity, forward-tested:** the retrodiction's "all 45 dual-agreement calls down to 0.80 correct" does **not** survive 2026. At a 0.80 dual gate, WB "BJP wins majority" fires as CALL-NO (1−max(p2,p3) = 0.81) and is wrong. The 0.95 threshold is what kept West Bengal clean; 0.80 would have added a fourth wrong call.

Calibration on the 26 rows with both instruments: mean claimed p_gate 0.458 vs realized 0.423; Brier 0.298 (M2 0.235 on all 35). Sub-threshold probabilities remain directional at best.

## Honest accounting (read before trusting anything above)

- **Step ordering was followed**: configs built and `predict.py` run from frozen pre-election Wikipedia revisions only; all 35 rows SHA-hashed into `ledger.csv` (run_at 2026-10-16T14:45Z) before any result page was fetched (`11_fetch_2026_results.py` asserts pre-registration before fetching). The assistant running the protocol has a January 2026 knowledge cutoff; these elections were scheduled (15 Mar 2026) and held (Apr 2026) after it, so prior knowledge of outcomes was impossible, not merely avoided.
- **Freeze deviations, both disclosed at freeze, decided before any result was seen:** (1) KL/AS freeze set to 2026-03-16 (T−24d, just after the EC schedule announcement) instead of strict T−28d, because the T−28 revisions contain empty poll tables and the only pre-campaign poll published 15 Mar. (2) The poll *record* for KL/AS was read from the last pre-election frozen revision (8 Apr; their freeze-date revisions' tables were still empty), admitting only polls published on/before each freeze. Post-freeze polls — including the only rated agency, CVoter (31 Mar KL, 8 Apr WB) — were visible in those revisions and excluded. Campaign-window polls would not have saved TN: the nine pre-election vote-share polls average TVK ≈ 17.5 (actual 35.0).
- **Alliance compositions are from the freeze-date frozen revisions** (not post-hoc): AIADMK+BJP+PMK+AMMK reunion, DMDK's move to SPA, TVK's refusal of the NDA (18 Mar), WB's Left–INC divorce (INC alone on all 294), BJP–ISF unresolved at freeze (ISF excluded from BJP bloc; it ultimately ran with LF+), Assam's BPF→NDA switch, UPPL exit, and the Congress-led Asom Sonmilito Morcha with AIUDF outside. One judgment call pre-registered in each config: τ-weights for switched partners per the N=46 convention.
- **All pre-freeze polls are unrated agencies** (IANS-Matrize, Vote Vibe, Agni; 1–3 polls per state). Kerala's M3 rests on a single n=12,015 unrated poll with the wrong leader. The unrated-σ (6.0) is clearly still too small for this poll class: measured 2026 errors ran to 7 pts on WB BJP, 13.5 on TN NDA, 22 on TVK.
- **Question-set correlation:** the three wrong calls are two independent events (the top-2 question is the logical complement of "TVK is largest"). Per independent event the 2026 record is 6 right, 2 wrong. The ledger counts questions, as pre-registered.
- **Actuals are from current Wikipedia results-by-alliance tables** (`data/raw/holdout2026/actuals_2026.csv`), not yet re-validated against ECI constituency files as the N=46 set was. Bloc totals as published by the alliance groupings; WB seat sims ran on 290 of 294 baseline ACs.
- **Agni News Agency was kept mechanically** despite visible quality symptoms (SPA "180+ seats" on a claimed n=101,643) — no cherry-picking at freeze; it pulled M3's SPA up ~2.4 pts, away from the actual.

## What 2026 teaches (updates the N=46 priority list)

1. **Port the new-entrant flag to `predict.py` (was not on the list; now #1).** The rule exists, is stated, and was validated on 8 retrodiction elections; the forward tool must force WATCH-FLAG on any election where a flagged entrant polls above noise, and must never emit a top-2 CALL whose certainty rests on a zero-baseline bloc. This single change converts 2026's record to 6/6 under the pre-existing rule — the cheapest 29-points-of-precision available anywhere in the system.
2. **M2 variance calibration (was #2, confirmed, worse than thought).** Interval coverage 5/13 out of sample in a wave cycle. The σ_state=6.3 is a *typical-cycle* error; 2026 was drawn from the tail (WB two-party swing of ~12 pts off baseline).
3. **Per-state pollster-error ledgers (was #1, still critical).** WB polls understated BJP by ~7 pts in 2026 after understating AITC by 6.6 in 2021 — errors this large and sign-unstable cannot be bias-corrected from one prior cycle; the 2021-based +3.3 AITC correction moved M3 the wrong way in 2026. The unrated-agency σ should be re-measured from the now-five resolved cycles (2021 ×4 + 2026 ×4) — first pass suggests ≥8, not 6.
4. **Fragmentation stress mode.** TN produced a 35/31/27 three-way fracture from a 46/41 two-way baseline; the uniform-shift Monte Carlo cannot represent a new party drawing asymmetrically from both blocs. A Dirichlet-style vote-transfer entrant module is the modeling (not governance) answer to TVK.

## Reproduction

`09_fetch_2026_frozen.py` (frozen revisions; rvstart ≤ freeze, never current) → configs `forecasts/{WB,TN,KL,AS}2026.json` → `predict.py` ×4 (seed 42, N_SIM 10,000; SHA256 per forecast in ledger) → `11_fetch_2026_results.py` (post-registration only) → `12_resolve_2026.py` (fills resolved/outcome/correct, prints scoring). Frozen snapshots in `data/raw/holdout2026/wiki_frozen/` (revision ids and timestamps embedded); actuals in `data/raw/holdout2026/actuals_2026.csv`.

*Opinion polls and alliance compositions from frozen pre-election Wikipedia revisions (ids in the cached JSONs); results from current Wikipedia results-by-alliance tables pending ECI constituency-file validation.*
