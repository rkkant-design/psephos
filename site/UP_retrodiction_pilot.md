# UP Retrodiction Pilot — Report

**Date:** 2026-10-09 · **Scope:** Retrodict UP Assembly 2017 and 2022 using only pre-election data, to test the confidence-gate architecture before committing to the full engine build.

## Verdict

**The confidence gate went 2-for-2.** It correctly **CALLED** BJP+ majority for 2022 (and was right: actual 273/403), and correctly **ABSTAINED** on 2017 — the election where every model input was broken and a naive forecaster would have called it wrong. No false CALL was issued. That is exactly the behavior the architecture promises: *be right when you speak; stay silent when the evidence diverges.*

| | 2017 (freeze Feb 2017) | 2022 (freeze Jan 2022) |
|---|---|---|
| M1 Fundamentals (rotation prior) | SP out, BJP strongest challenger ✓ | BJP out ✗ (pattern-validity flag raised) |
| M2 LS-blend | SP+INC 251 seats — **wrong** | BJP+ 282–345 (med 317) — right call, interval too high |
| M3 Polls | SP+INC lean, P=0.57 — uncertain | BJP+ 217–299 (med 260) — **actual 273 inside, near median** |
| **Gate (min of M2,M3 ≥ 0.95)** | **WATCH** — correct abstention | **CALL BJP+ majority (0.988)** — correct |
| Actual | BJP+ 325 | BJP+ 273, SP+ 125 |

Sub-question gate (2022): "Winner in {BJP+, SP+}" → CALL (P=1.00), correct. "BSP under 20 seats" (P=0.72), "SP+ gains 40+" (P=0.89) stayed WATCH — both in fact happened, so abstentions were safe but not maximally aggressive.

## The two headline findings

### 1. 2022 validates the machinery

The bias-corrected polls model (M3) was the star: raw polls said BJP+ 40.9%; applying half of the 2017 poll-error ledger (+7.8 BJP underestimate) corrected to 44.8% vs actual 43.8%. Its seat median of 260 vs actual 273 and a contained 90% interval is genuinely good forecasting 6+ weeks out. The pollster-error ledger — a core design bet — earned its place on its first use.

### 2. 2017 is the case for the full engine — the abstention was correct, but a better engine could have called it

Both M2 and M3 pointed wrong (SP+INC) because *both inputs were broken*: polls underestimated BJP by ~8 points, and M2's GE→AE blend weight α, fitted on the pre-Modi 2009→2012 cycle, came out 0.30 — when the 2014→2017 cycle later showed the true weight had jumped to 0.90. **The GE→AE relationship itself regime-shifted in 2014** (state elections nationalized). This is the "pattern validity" problem from the design, observed live in the data: α is not a constant, it's a regime indicator.

What would have called 2017 correctly? Exactly the modules this pilot doesn't have: insider-flow (the 2016–17 defection wave toward BJP, BJP's ticket-demand surge), segment matrices (non-Yadav OBC consolidation was visible in CSDS data), and vernacular ground signal. The 2017 miss is not an argument against the engine — it is the strongest possible argument *for* building its remaining layers, because the gate already protects you from the miss while the missing modules would convert it into an early CALL.

## Honest accounting (read before trusting anything above)

- **n=2.** This proves the plumbing and the gate logic, not a 95% precision claim. That needs ~60+ resolved calls (the decomposed sub-question machinery exists for exactly this).
- **Designer leakage risk.** I knew the outcomes while writing the code. Defenses used: all parameters fixed by stated rules before the single run (α fitted only on prior cycles; σ from prior-cycle dispersion or declared assumption; τ=0.75 declared prior; seed fixed; no tuning loop after seeing results — the engine ran once and this report describes that run). Residual risk remains; the only clean test is 2027, pre-registered.
- **M2's 2022 interval missed** (282–345 vs actual 273): fitting α on the single 2014→2017 cycle overweights GE2019. Fix: hierarchical α across many states/cycles, which the full multi-state dataset enables.
- **Known data simplifications:** uniform swing with Gaussian noise (no regional correlation blocks yet); τ (alliance transfer) assumed not measured; INC 2022 share hand-set to 5.0 from polls; 2012 DataMeet file resolves 401/403 ACs; GE data is PC-level (80 seats), not AC-segment-level.

## Data assets now in hand (`data/`)

| Asset | Source | Coverage |
|---|---|---|
| TCPD/Lok Dhaba AE dump for UP | via Kaggle mirror (Lok Dhaba itself is down) | 2017, candidate-level, incl. turncoat/incumbent/terms fields |
| DataMeet assembly.csv | GitHub | UP AE 1951–2012, candidate-level |
| ECI 2022 results | via Kaggle mirror | UP 2022 candidate-level, 403 ACs |
| TCPD GE All-States | GitHub mirror | UP LS 1962–2019 incl. 2014/2019 |
| Poll ledger (hand-built) | Wikipedia compilations | 2017: 11 polls, 2022: 7 polls, + 2017 exit polls |

Validation: processed data reproduces official seat counts (2017 BJP 312 exact; 2022 BJP 255, SP 111 exact) and vote shares within 0.3 pts.

## What the pilot says to build next (priority order)

1. **Multi-state expansion** of the same pipeline (~30 elections 2012–2025) → hierarchical α, measured τ per alliance, real σ structure, and enough resolved sub-questions to start the real precision ledger.
2. **Insider-flow module** (defections, ticket demand) — the single module that flips 2017 from WATCH to early CALL.
3. **Regime-break detector** formalizing the α-shift finding.
4. **Pre-registration ledger** before any live 2027 forecast.

*Citation: election results data derived from TCPD "Indian Elections Data v2.0" (Lok Dhaba, Ashoka University), DataMeet india-election-data, and ECI results via public Kaggle mirrors.*
