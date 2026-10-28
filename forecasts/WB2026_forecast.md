# Forecast: West Bengal Legislative Assembly 2026 (holdout)

**Freeze:** 2026-03-26 · **Run:** 2026-10-16T14:45:35+00:00 · **SHA256:** `016df22dfcc0743b…` (full hash in ledger.csv)

Params: α=0.642 σ_c=12.62 τ=0.5 σ_state M2=6.3 M3=6.0 (UNRATED agencies)

## Predicted state vote shares (pts)

| bloc | baseline (reblocked) | GE | M2 | M3 (corrected polls) |
|---|---|---|---|---|
| AITC | 48.6 | 46.2 | 47.0 | 46.2 |
| BJP | 38.9 | 39.1 | 39.0 | 38.9 |
| LF | 5.4 | 5.7 | 5.6 | nan |
| INC | 3.0 | 4.7 | 4.1 | nan |

## Seat simulations (10k runs)

| bloc | M2 5–95% (med) | P_maj | P_largest | M3 5–95% (med) | P_maj | P_largest |
|---|---|---|---|---|---|---|
| AITC | 107–240 (178) | 0.76 | 0.80 | 110–238 (180) | 0.77 | 0.80 |
| BJP | 46–177 (106) | 0.16 | 0.20 | 52–180 (110) | 0.19 | 0.20 |
| LF | — |
| INC | — |

## Gate verdicts (dual, min(M2,M3) ≥ 0.95)

| question | P M2 | P M3 | gate | verdict |
|---|---|---|---|---|
| AITC wins majority | 0.761 | 0.772 | 0.761 | **WATCH** |
| AITC is largest | 0.803 | 0.795 | 0.795 | **WATCH** |
| BJP wins majority | 0.163 | 0.192 | 0.163 | **WATCH** |
| BJP is largest | 0.197 | 0.205 | 0.197 | **WATCH** |
| LF wins majority | 0.000 | — | — | **WATCH-NOPOLL** |
| LF is largest | 0.000 | — | — | **WATCH-NOPOLL** |
| INC wins majority | 0.000 | — | — | **WATCH-NOPOLL** |
| INC is largest | 0.000 | — | — | **WATCH-NOPOLL** |
| Winner (largest) in {AITC, BJP} | 1.000 | 1.000 | 1.000 | **CALL-YES** |
| LF under 30 seats | 0.999 | — | — | **WATCH-NOPOLL** |
| INC under 30 seats | 0.999 | — | — | **WATCH-NOPOLL** |

## Quality flags

- Both pre-freeze polls are unrated agencies (IANS-Matrize, VoteVibe CNN-News18); M3 runs at inflated sigma 6.0.
- LF+ and INC have NO separate poll numbers at freeze (Wikipedia table merges LF+/INC/Others into one 13-15% colspan cell) -> their questions are M3-blind (WATCH-NOPOLL) and the M3 seat sim excludes them, which mechanically inflates AITC/BJP M3 seat counts; the dual gate's min() partially protects.
- BJP-ISF seat sharing unresolved at freeze; ISF excluded from BJP bloc.
- Baseline AE (WB2021) covers 290 of 294 ACs in ae_long; seat sims run on 290.
- 2021 WB polls underestimated AITC by 6.6 pts; correction +3.3 applied per ledger rule.

## Tripwires (re-run on trigger)

- **BJP-ISF alliance finalized** → BJP bloc gains ~1.4pt transfer-weighted; re-run
- **A rated agency (CVoter/Axis/CSDS) publishes pre-election vote shares** → M3 upgrades to rated sigma