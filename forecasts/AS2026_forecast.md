# Forecast: Assam Legislative Assembly 2026 (holdout)

**Freeze:** 2026-03-16 · **Run:** 2026-10-16T14:45:40+00:00 · **SHA256:** `fcc2a4cccb7d879c…` (full hash in ledger.csv)

Params: α=0.529 σ_c=13.23 τ=0.5 σ_state M2=6.3 M3=6.0 (UNRATED agencies)

## Predicted state vote shares (pts)

| bloc | baseline (reblocked) | GE | M2 | M3 (corrected polls) |
|---|---|---|---|---|
| NDA | 44.0 | 46.4 | 45.3 | 43.7 |
| ASOM | 33.2 | 39.4 | 36.5 | 38.6 |
| AIUDF | 9.6 | 3.2 | 6.2 | nan |

## Seat simulations (10k runs)

| bloc | M2 5–95% (med) | P_maj | P_largest | M3 5–95% (med) | P_maj | P_largest |
|---|---|---|---|---|---|---|
| NDA | 44–91 (69) | 0.65 | 0.82 | 49–96 (74) | 0.76 | 0.78 |
| ASOM | 22–66 (43) | 0.07 | 0.18 | 30–77 (52) | 0.22 | 0.22 |
| AIUDF | — |

## Gate verdicts (dual, min(M2,M3) ≥ 0.95)

| question | P M2 | P M3 | gate | verdict |
|---|---|---|---|---|
| NDA wins majority | 0.647 | 0.758 | 0.647 | **WATCH** |
| NDA is largest | 0.822 | 0.777 | 0.777 | **WATCH** |
| ASOM wins majority | 0.074 | 0.223 | 0.074 | **WATCH** |
| ASOM is largest | 0.178 | 0.223 | 0.178 | **WATCH** |
| AIUDF wins majority | 0.000 | — | — | **WATCH-NOPOLL** |
| AIUDF is largest | 0.000 | — | — | **WATCH-NOPOLL** |
| Winner (largest) in {NDA, ASOM} | 1.000 | 1.000 | 1.000 | **CALL-YES** |
| AIUDF under 25 seats | 0.999 | — | — | **WATCH-NOPOLL** |

## Quality flags

- Both pre-freeze polls are unrated agencies, published the day of the EC schedule announcement; M3 sigma 6.0.
- AIUDF has no poll column (lumped in Others) -> its questions are M3-blind (WATCH-NOPOLL) and the M3 seat sim excludes it, inflating NDA/ASOM M3 seat counts in AIUDF strongholds; min() gate partially protects.
- Freeze set to 2026-03-16 (T-24d, just after EC announcement) instead of strict T-28d (2026-03-12), same rationale as KL2026: the T-28 revision has empty poll tables. Decision made before seeing any result.
- Poll record read from the last pre-election frozen revision (2026-04-08); a 'Chanakya' row with no publication date was excluded (cannot verify pre-freeze).
- Opposition fragmentation (Raijor Dal and AIUDF outside ASOM, UPPL alone) is severe; baseline reblocking cannot capture local BTR seat deals

## Tripwires (re-run on trigger)

- **ASOM-AIUDF or ASOM-Raijor Dal rapprochement before 9 Apr** → bloc structure changes; re-run