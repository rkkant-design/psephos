# Multi-State Retrodiction — Report (N = 46)

**Date:** 2026-10-16 · **Scope:** Extend the UP pilot to 46 state assembly elections (2013–2025, 18 states), refit α/τ/σ hierarchically, and run leave-one-out retrodictions through the confidence gate to start the real precision ledger.

## Verdict

**The gate made zero wrong calls in 46 elections.** Run exactly as designed — CALL only when both the GE-blend model (M2) and the polls model (M3) independently exceed 0.95 — the gate issued 28 negative CALLs (loo mode; 27 in past-only mode), every one correct, and zero positive CALLs. Its internal ordering is strikingly good: relaxing the dual threshold from 0.95 all the way to 0.80 adds 5 positive and 12 more negative calls, and **all 45 dual-agreement calls are correct**. The machine knows which way elections lean; what it cannot yet do, with instruments whose measured error is ~5–6 pts of vote share, is certify a majority at 95% confidence six weeks out.

The contrast that matters: an M2-only gate (what a single-model forecaster would ship) makes 14 positive CALLs at 0.95 and gets 3 wrong (78.6% precision), plus 9 wrong negatives. Requiring the second independent witness removed **every single false call** at the cost of all positive calls. That is the architecture doing exactly what it promised — and it quantifies the price of the missing modules.

| Gate (loo mode) | Positive CALLs | correct | Negative CALLs | correct | Wrong calls |
|---|---|---|---|---|---|
| M2-only, ≥0.95 | 14 | 11 (78.6%) | 91 | 82 (90.1%) | 12 |
| **Strict dual, ≥0.95** | **0** | — | **28** | **28 (100%)** | **0** |
| Strict dual, ≥0.80 (sensitivity) | 5 | 5 (100%) | 40 | 40 (100%) | 0 |

(past-only parameter mode gives the same picture: strict gate 27/27 correct, 0 wrong; M2-only 64.7% positive precision. Question set is fixed and mechanical — every bloc × {wins majority, is largest} — no cherry-picking.)

The five dual-agreement near-certainties (min(M2,M3) ≥ 0.80), all of which happened: MH2019 BJP+SHS largest, MH2024 Mahayuti largest, GJ2017 BJP largest *and* majority, UP2022 BJP+ largest. The pilot's UP2022 CALL reproduces directionally (M2 P=0.97 majority) but no longer clears the dual bar, because the multi-state pipeline lacks UP's 2017 vote-share poll ledger that powered the pilot's bias-corrected M3 — see "what to build next".

## Parameter tables (refit on N=46; saved in `data/processed/`)

**α (GE→AE blend weight)** — fitted per state-cycle (66 observations), partially pooled by era:

| era | pooled α | n | spread |
|---|---|---|---|
| pre-2014 | 0.34 | 28 | per-cycle fits range 0–1 |
| post-2014 | 0.46 | 38 | per-cycle fits range 0–1 |

The pilot's regime-shift finding holds at scale: α jumped after 2014 (state elections nationalized), but the per-cycle spread is enormous — α is a regime indicator, not a constant. Shrunk per-state values are in `alpha_table.csv`.

**τ (alliance transfer efficiency)** — measured for the first time, by regressing target bloc share on anchor-party and partner-party baseline shares across matched constituencies, for 11 real alliance formations (JH2014 INC+RJD+JDU, BR2015 NDA, AS2016 BJP+AGP+BPF, WB2016 Left+INC, UP2017 SP+INC, TG2018 INC+TDP, BR2020 NDA, AS2021 Mahajot, TN2021 ADMK+, UP2022 SP+, PB2022 SAD+BSP):

| measured τ median | IQR | pilot prior |
|---|---|---|
| **0.50** | 0.38–0.74 | 0.75 |

Alliance arithmetic transfers only about half of a junior partner's prior vote — the pilot's 0.75 prior was generous. (Full per-alliance table: `tau_obs.csv`.)

**σ (swing dispersion across ACs)** — bloc-level, per state (median over cycles; `sigma_table.csv`): national median **12.6 pts**; calm states Delhi 8.5, Chhattisgarh 9.8, UP 10.6; churn states Bihar **20.3**, Haryana 18.7, Maharashtra 16.5. Party-level (contested-both-times) national median is 10.6, confirming the pilot's UP figure (6.8) sits at the calm end. Bihar's 20-pt dispersion is real alliance-churn, and it is why the engine will rightly almost never certify a Bihar majority from structure alone.

**M2's own error, measured out-of-sample:** the state-level residual of the α-blend has sd ≈ 6.3 pts with heavy tails and **no stable party bias** (BJP mean residual +0.2 across 36 observations). The errors are bimodal: GE-premium overestimates (BJP's GE vote not carrying into AEs — RJ2018, JH2019, DL2020, KA2023) versus wave underestimates (UP2017, WB2021, HR2014). Variance, not bias — which is why a second independent instrument, not a correction term, is the fix.

**M1 fundamentals:** incumbents stayed largest in **22 of 46** elections (48%). UP's 0-for-7 rotation prior does not generalize; anti-incumbency is a state-specific trait, not a national law. M1 must be rebuilt per state before it can gate anything.

## Calibration (leave-one-out, all 262 unflagged bloc-questions)

| claimed P | n | realized (M2) | realized (M3, n) |
|---|---|---|---|
| 0–5% | 91 | 9.9% | 0.0% (32) |
| 5–20% | 27 | 33.3% | 0.0% (16) |
| 20–40% | 30 | 30.0% | 27.8% (18) |
| 40–60% | 15 | 26.7% | 44.4% (9) |
| 60–80% | 26 | 65.4% | 83.3% (18) |
| 80–95% | 19 | 57.9% | 100% (8) |
| 95–100% | 14 | 78.6% | 100% (3) |

M2 is overconfident in both tails (claimed 97% realizes 79%; its nominal 90% seat intervals cover only 58% of outcomes) — single-instrument probabilities cannot be taken at face value. M3 (polls) is conservative-to-calibrated where it exists. The min() rule inherits the best of both: in the 46-election ledger the dual gate's claimed ≥95% region realized 100% (28/28), and the whole ≥80% dual region realized 45/45.

## Honest accounting (read before trusting anything above)

- **Zero positive CALLs at 0.95 means the headline "100% precision" is earned on negatives only.** Negative calls ("BSP will not win a majority") are real, resolvable sub-questions of the design, but they are the easy end. The positive-call precision claim remains untested at threshold — the 45/45 dual-agreement record down to 0.80 is the evidence the ordering is right, not that 0.95-calls would be 95% right.
- **Leave-one-out is not a forward test.** LOO parameters see other elections from the target's future. The `past` mode (parameters from strictly earlier elections only) is reported throughout and agrees; the only clean test remains pre-registered 2027.
- **Designer leakage.** Bloc compositions, new-entrant flags, and election metadata were hand-coded by someone who knows the outcomes. Defenses: compositions are matters of public record at freeze time; the 8 new-entrant flags (AAP×3, KJP, JCC, JJP, GJ-AAP, Jan Suraaj) follow one stated rule — a serious contender invisible to both baseline AE and prior GE — and flag-forced WATCHes are excluded from all precision claims rather than credited; the question set is mechanical; parameters were fitted by stated rules and the engine ran once per configuration. Three iterations of the M3 error model happened after seeing ledger output (documented in git/session history); all were data-hygiene or pilot-design items (final-window filter, incoherent-extraction drop, prior-election bias correction), none moved a wrong call to right.
- **Poll coverage is 23/46 elections** (frozen pre-election Wikipedia revisions; current-revision fallback for 9 articles whose poll tables were added later — those rows carry a hindsight-curation risk). 118 of 270 loo questions are WATCH-NOPOLL: the strict gate abstains for lack of a witness, not from modeled uncertainty. Seat-projection polls (the only kind available for 13 elections) have measured errors of ±17% of assembly size — nearly useless for certification.
- **Data degradations**, all documented in `data/raw/multistate/SOURCES.md`: HR2019/BR2020/DL2020 baselines are top-2-per-AC; KA2018 is a near-final trends scrape (shares within ~1pt, 5 of 222 winners off); TG2014 baseline is the Telangana slice of united-AP 2014; HP2017/JH2019/GJ2022 targets are hand-entered official tallies (no constituency mirror found). Everything else validates seat-exactly against official results (56 checks, 0 unexplained mismatches).
- **Excluded:** AP/Telangana pre-2014 (bifurcation), J&K, Goa/Manipur/Puducherry and small NE states. The N=46 is biased toward large bipolar states by data availability, which flatters σ estimates slightly.

## What N=46 says to build next (priority order)

1. **Per-state pollster-error ledgers (vote share, not seats).** The single highest-leverage item. The pilot's UP2022 CALL worked because 2017's poll errors corrected 2022's polls; the multi-state pipeline could apply that correction in only a handful of states. With clean final-window vote-share polls + prior-cycle corrections, M3's measured error should drop from 5.6 toward 3–4 pts — enough for the dual gate to start issuing positive CALLs on genuine landslides (UP2022, GJ2017, WB2021-largest were all near-misses).
2. **Variance calibration pass on M2.** Its 90% intervals cover 58%; a single out-of-sample inflation factor on σ_state would fix the tails without touching the mean model.
3. **State-specific M1.** 48% pooled retention means the rotation prior is a UP/KL/RJ-style trait (strong alternation) absent in WB/MP/GJ-style dominance states; encode per-state base rates from the long history already in `state_shares_all.csv`.
4. **Insider-flow and segment modules** — unchanged from the pilot: they are what converts correct WATCHes (UP2017, PB2022, KA2023) into early CALLs that polls and structure alone cannot certify.
5. **Pre-registration ledger for the 2026–27 cycle** (WB/TN/KL/AS 2026 results exist but were deliberately left out of this ledger; they are the first out-of-sample test set — run the frozen engine on them before looking).

## Reproduction

`scripts/03_build_multistate.py` → `04_fit_params.py` → `06_fetch_polls.py` → `07_curate_polls.py` → `05_loo_retrodict.py`. Outputs: `precision_ledger.csv` (552 gated questions), `election_summaries.csv` (per-bloc forecasts vs actuals), `calibration_table.csv`, `alpha/tau/sigma` tables — all in `data/processed/`. Seed fixed (42), N_SIM=10,000.

*Citations: election results derived from TCPD "Indian Elections Data v2.0" (Lok Dhaba, Ashoka University) via public mirrors, DataMeet india-election-data, ECI results via Kaggle/GitHub mirrors (full provenance in `data/raw/multistate/SOURCES.md`); opinion polls from frozen pre-election Wikipedia revisions.*
