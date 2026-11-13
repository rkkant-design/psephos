# Methodology Audit — Psephos

**Date:** 2026-11-13
**Scope:** the forecasting *method* and the statistical honesty of its accuracy claims — not the record's integrity (that is covered separately; every integrity finding is now closed in code).
**Data:** `data/processed/scores.csv` (202 resolved binary probabilities + 30 football matches), scored as of cutoff 2026-11-10.
**Method of this audit:** base-rate baselines, Murphy decomposition of the Brier score (reliability / resolution / uncertainty), and model-vs-market comparison paired by question with a 2,000-sample bootstrap 95% CI.

---

## Verdict in one line

Psephos is an **honest, well-calibrated, disciplined abstention engine — not a demonstrated alpha generator.** It is much better at *knowing what it knows* than at being *more right than the alternatives*.

Two grades, because they genuinely differ:

| Dimension | Grade | Why |
|---|---|---|
| Epistemics, calibration, abstention, integrity | **A−** | Rare honesty; the gate reliably abstains on weak signals; calibration is in the right range; the record is tamper-evident. |
| Demonstrated predictive edge | **C+** | Loses to the market wherever one exists; on the home turf (India) the one real out-of-sample test shows ≈ zero skill. |

The gap between the two is the story of this audit.

---

## Evidence

### 1. Skill over a base rate, and the Murphy decomposition

`BSS` = Brier Skill Score vs always predicting the group's base rate (0 = no better than climatology; <0 = worse). `RESOL` = resolution/discrimination (higher is better). `RELY` = reliability/miscalibration (lower is better).

| Cohort / instrument | n | Brier | Base-rate Brier | **BSS** | RESOL | RELY | mean p | mean outcome |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| India **M2** (structural), blind 2026 | 35 | 0.2353 | 0.2400 | **+0.020** | 0.1035 | 0.0962 | 0.456 | 0.400 |
| India **M3** (corrected polls), blind 2026 | 26 | 0.3209 | 0.2441 | **−0.315** | 0.0922 | 0.1690 | 0.518 | 0.423 |
| US races — model | 67 | 0.0902 | 0.2339 | +0.615 | 0.1656 | 0.0224 | 0.588 | 0.627 |
| US races — **market** | 65 | 0.0331 | 0.2367 | **+0.860** | 0.2187 | 0.0164 | 0.563 | 0.615 |
| World — model | 3 | 0.0786 | 0.2222 | +0.646 | — | — | — | — |
| World — market | 3 | 0.0272 | 0.2222 | +0.877 | — | — | — | — |
| Research (M_research) | 3 | 0.0835 | 0.2222 | +0.624 | — | — | — | — |

Reading it:
- **India M2 adds essentially nothing** over predicting the average rate (BSS +0.02 is noise at n=35).
- **India M3 is *worse than the base rate*** (BSS −0.32) — the corrected-polls instrument actively hurt on the one real Indian out-of-sample test. This is the TVK new-entrant failure, quantified.
- **The US race model has genuine skill** (BSS 0.62) — it is a legitimate forecaster — but the **market is materially better** (0.86), with higher discrimination (0.219 vs 0.166) and near-perfect calibration (RELY 0.016).
- World and research cohorts (n=3 each) are too small to carry any weight.

### 2. Model vs market, paired by question (bootstrap 95% CI)

Negative edge = market better. `mean(B_model − B_market)` over identical resolved questions:

| Set | n | mean(B_model − B_market) | 95% CI | market better on |
|---|---:|---:|---:|---:|
| World | 3 | +0.0514 | [−0.0016, +0.1573] | 1/3 |
| **US races** | 65 | **+0.0598** | **[+0.0274, +0.1002]** | 37/65 |
| Football (3-way) | 19 | +0.0357 | — | 2/2 matchweeks |

On US races — the only matched set large enough to test — **the market beats the model and the CI excludes zero (significant).** On every other matched set the market also wins; the samples are just too small to be conclusive. **Net: no demonstrated edge over a market anywhere.**

### 3. Calibration

Pooled over 292 binary events (202 forecasts + 90 football H/D/A):

| Claimed band | n | mean claimed | realized | note |
|---|---:|---:|---:|---|
| 0–5% | 45 | 1.1% | 4.4% | slightly underconfident |
| 5–20% | 31 | 14% | **25.8%** | underconfident — these happened ~2× as often as claimed |
| 20–40% | 68 | 27.7% | 33.8% | |
| 40–60% | 40 | 48.3% | 42.5% | |
| 60–80% | 25 | 71.6% | 68.0% | |
| 80–95% | 24 | 87.4% | 91.7% | |
| **95–100%** | 59 | 98.8% | **91.5%** | **overconfident — the most confident bucket realized below the 95% the gate promises** |

Calibration is in the right ballpark, but the **confident tail is overstated**, which matters directly for a product whose gate threshold *is* 95%.

### 4. Instrument independence

Cross-instrument residual correlation **r(M2, M3) = 0.745**; the two back the wrong winner together ~**1.9×** more often than independence would predict. The "independent witnesses" framing is overstated — the dual gate's theoretical 95%→99% precision lift assumes an independence the instruments do not have.

### 5. Sample size / what the hit rate really is

- **"26/26 live"** is **one event** — 71 correlated US races on a single night (effectively ~1 independent observation).
- **"28/28 backtest"** calls are **all CALL-NO** ("X will not win a majority") — usually true, and easy.
- The gate has **essentially never made and validated a hard *positive* majority call.** One cannot distinguish a true 95% gate from an 85% gate at this sample size.
- The pooled headline **Brier 0.1255** is **dominated by 132 mostly-safe US seats**; the hard problems (India) sit near 0.27 — barely better than guessing 50/50.

### 6. The football model is dead weight

Three-way Brier **0.595** vs **0.667** for always-guessing, and it loses to the market every matchweek. It inflates the *count* of scored predictions (~50×/week) without adding evidential value.

---

## What is genuinely good (not faint praise)

1. **The gate does its job.** Despite M3 being *worse than the base rate* on the blind test, **zero** of those bad readings became wrong CALLs — the gate fires only on agreement and abstains otherwise. Turning weak, correlated instruments into sparse-but-reliable calls via abstention is a sound design.
2. **Calibration is honest** — no wild overconfidence; the tails are close.
3. **Abstention-as-product + a tamper-evident, self-critical record** is rarer than any accuracy number. The track-record page already discloses that the market beats the model and that the live sample is tiny.

---

## Bottom line

For decisions where **markets are absent** and **"we don't know" is a valuable answer** — the intended Indian-elections wedge — the calibration and abstention discipline have real worth. But the marketing-grade claim, *"calibrated forecasts you can trust,"* is currently carried by **abstention plus small, easy samples**, not by demonstrated skill:
- it **loses to markets** wherever they exist (significantly, on US races); and
- on its **home turf**, the only genuine out-of-sample Indian test shows **no skill** (M2 ≈ base rate, M3 worse), and the fix for that failure is **untested**.

## What would move the grade from C+ to B+

1. **Beat a benchmark you don't control, out of sample, once.** Currently 0-for-everything vs the market.
2. **Validate the WATCH-FLAG / new-entrant fix on the 2027 Indian elections** — the single most important pending test; the home-turf thesis stands or falls on it.
3. **Earn the 95% gate with positive calls**, or publish the deferred threshold sweep on the backtest/blind cohorts and state the empirical precision with its CI.
4. **Stop claiming instrument independence** at r = 0.745, or add a genuinely independent instrument.
5. **Retire or rebuild the football model** — it adds volume, not skill.

---

*Computed from `data/processed/scores.csv`; reproduce with the base-rate/Murphy/bootstrap analysis described at the top. All figures as of cutoff 2026-11-10.*
