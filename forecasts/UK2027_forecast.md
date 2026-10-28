# Forecast: Uttarakhand Assembly 2027

**Freeze:** 2026-10-23 · **Run:** 2026-10-23T10:09:03+00:00 · **SHA256:** `65a214e65e05aec5…` (full hash in ledger.csv)

Params: α=0.386 σ_c=10.27 τ=0.5 σ_state M2=6.3 M3=6.0 (UNRATED agencies)

## Predicted state vote shares (pts)

| bloc | baseline (reblocked) | GE | M2 | M3 (corrected polls) |
|---|---|---|---|---|
| BJP | 44.7 | 57.5 | 49.7 | 43.0 |
| INC | 38.2 | 33.1 | 36.2 | 36.1 |
| BSP | 4.9 | 1.8 | 3.7 | nan |

## Seat simulations (10k runs)

| bloc | M2 5–95% (med) | P_maj | P_largest | M3 5–95% (med) | P_maj | P_largest |
|---|---|---|---|---|---|---|
| BJP | 33–65 (53) | 0.93 | 0.94 | 26–61 (46) | 0.81 | 0.83 |
| INC | 4–35 (15) | 0.05 | 0.06 | 9–44 (24) | 0.17 | 0.17 |
| BSP | — |

## Gate verdicts (dual, min(M2,M3) ≥ 0.95)

| question | P M2 | P M3 | gate | verdict |
|---|---|---|---|---|
| BJP wins majority | 0.927 | 0.809 | 0.809 | **WATCH** |
| BJP is largest | 0.944 | 0.826 | 0.826 | **WATCH** |
| INC wins majority | 0.046 | 0.174 | 0.046 | **WATCH** |
| INC is largest | 0.056 | 0.174 | 0.056 | **WATCH** |
| BSP wins majority | 0.000 | — | — | **WATCH-NOPOLL** |
| BSP is largest | 0.000 | — | — | **WATCH-NOPOLL** |
| BSP under 5 seats | 0.965 | — | — | **WATCH-NOPOLL** |
| Winner (largest) in {BJP, INC} | 1.000 | 1.000 | 1.000 | **CALL-YES** |

## Quality flags

- All three vote-share polls are unrated agencies and they disagree on the leader (Poll Mitra has INC ahead; TNN/Vote Vibe have BJP). Seat polls disagree even more (BJP 29-54 of 70).
- No AAP/UKD vote-share lines in any poll; both are treated as background others.
- M3 BSP line missing from all polls - BSP questions run effectively on M2 plus baseline.

## Tripwires (re-run on trigger)

- **A rated agency publishes a vote-share poll** → M3 upgrades to rated sigma
- **Any INC-led opposition alliance (SP/ASP/AAP tie-ups)** → re-bloc and re-run
- **CM-change or major defection news** → insider-flow signal; re-run