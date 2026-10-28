# Forecast: Kerala Legislative Assembly 2026 (holdout)

**Freeze:** 2026-03-16 · **Run:** 2026-10-16T14:45:38+00:00 · **SHA256:** `90764ecf26e7ebc4…` (full hash in ledger.csv)

Params: α=0.311 σ_c=13.76 τ=0.5 σ_state M2=6.3 M3=6.0 (UNRATED agencies)

## Predicted state vote shares (pts)

| bloc | baseline (reblocked) | GE | M2 | M3 (corrected polls) |
|---|---|---|---|---|
| LDF | 38.9 | 33.6 | 37.3 | 42.5 |
| UDF | 38.0 | 45.5 | 40.4 | 41.5 |
| NDA | 12.9 | 19.7 | 15.0 | 12.5 |

## Seat simulations (10k runs)

| bloc | M2 5–95% (med) | P_maj | P_largest | M3 5–95% (med) | P_maj | P_largest |
|---|---|---|---|---|---|---|
| LDF | 35–91 (64) | 0.36 | 0.48 | 45–98 (74) | 0.57 | 0.66 |
| UDF | 40–96 (66) | 0.41 | 0.52 | 36–88 (60) | 0.27 | 0.34 |
| NDA | 2–22 (8) | 0.00 | 0.00 | 1–15 (5) | 0.00 | 0.00 |

## Gate verdicts (dual, min(M2,M3) ≥ 0.95)

| question | P M2 | P M3 | gate | verdict |
|---|---|---|---|---|
| LDF wins majority | 0.358 | 0.568 | 0.358 | **WATCH** |
| LDF is largest | 0.480 | 0.658 | 0.480 | **WATCH** |
| UDF wins majority | 0.407 | 0.270 | 0.270 | **WATCH** |
| UDF is largest | 0.520 | 0.342 | 0.342 | **WATCH** |
| NDA wins majority | 0.000 | 0.000 | 0.000 | **CALL-NO** |
| NDA is largest | 0.000 | 0.000 | 0.000 | **CALL-NO** |
| Winner (largest) in {LDF, UDF} | 1.000 | 1.000 | 1.000 | **CALL-YES** |
| NDA under 10 seats | 0.574 | 0.809 | 0.574 | **WATCH** |

## Quality flags

- ONE pre-freeze poll only (IANS-Matrize 15 Mar, unrated, n=12,015; midpoints of 42-43/41-42/12-13 ranges). M3 rests on a single unrated poll at sigma 6.0.
- Freeze set to 2026-03-16 (T-24d, just after the EC schedule announcement of 15 Mar) instead of strict T-28d (2026-03-12): the 12 Mar frozen revision has EMPTY poll tables and the only published pre-campaign poll is dated 15 Mar. Decision made before seeing any result. At strict T-28 this forecast would be poll-less.
- Poll record read from the last pre-election frozen revision (2026-04-08) because the 16 Mar revision's tables were still empty; only the poll PUBLISHED on/before freeze was admitted. Post-freeze polls (incl. rated CVoter 31 Mar) were visible in that revision but excluded.
- History note: Kerala has alternated LDF/UDF every election since 1982 except 2021; LDF seeks a third consecutive term.

## Tripwires (re-run on trigger)

- **Rated CVoter/Axis pre-election poll** → M3 upgrades to rated sigma (CVoter did publish 31 Mar - post-freeze, excluded)