# Forecast: Tamil Nadu Legislative Assembly 2026 (holdout)

**Freeze:** 2026-03-26 · **Run:** 2026-10-16T14:45:36+00:00 · **SHA256:** `f89b359c4d744747…` (full hash in ledger.csv)

Params: α=0.492 σ_c=14.97 τ=0.5 σ_state M2=6.3 M3=6.0 (UNRATED agencies)

## Predicted state vote shares (pts)

| bloc | baseline (reblocked) | GE | M2 | M3 (corrected polls) |
|---|---|---|---|---|
| SPA | 46.3 | 48.7 | 47.5 | 40.1 |
| NDA | 41.5 | 38.2 | 39.9 | 40.7 |
| TVK | 0.0 | 0.0 | 0.0 | 13.1 |

## Seat simulations (10k runs)

| bloc | M2 5–95% (med) | P_maj | P_largest | M3 5–95% (med) | P_maj | P_largest |
|---|---|---|---|---|---|---|
| SPA | 90–191 (144) | 0.79 | 0.81 | 62–162 (112) | 0.42 | 0.49 |
| NDA | 42–142 (89) | 0.19 | 0.19 | 64–164 (114) | 0.45 | 0.51 |
| TVK | 0–5 (1) | 0.00 | 0.00 | 1–24 (6) | 0.00 | 0.00 |

## Gate verdicts (dual, min(M2,M3) ≥ 0.95)

| question | P M2 | P M3 | gate | verdict |
|---|---|---|---|---|
| SPA wins majority | 0.793 | 0.423 | 0.423 | **WATCH** |
| SPA is largest | 0.806 | 0.490 | 0.490 | **WATCH** |
| NDA wins majority | 0.188 | 0.450 | 0.188 | **WATCH** |
| NDA is largest | 0.194 | 0.510 | 0.194 | **WATCH** |
| TVK wins majority | 0.000 | 0.000 | 0.000 | **CALL-NO** |
| TVK is largest | 0.000 | 0.000 | 0.000 | **CALL-NO** |
| Winner (largest) in {SPA, NDA} | 1.000 | 1.000 | 1.000 | **CALL-YES** |
| TVK under 40 seats | 1.000 | 0.992 | 0.992 | **CALL-YES** |

## Quality flags

- ALL three pre-freeze polls are unrated agencies; Agni News Agency is an outlier/quality symptom (SPA 44.9 pct + '180+ seats' projection on a claimed n=101,643) but is kept mechanically - no cherry-picking at freeze.
- TVK (polling 10-15 pct) has zero AE/GE base: M2 cannot see it, and the vote it draws will shift both main blocs in ways the baseline-shift sim does not model. This election is a stress test of the engine's new-entrant blind spot.
- NTK (6.7 pct AE2021, 8.2 pct GE2024) contests all 234 alone but has no poll column (lumped in Others); not modeled as a bloc.
- Spellings: TMC(M) carries 0.95 at GE2024; AMMK below reporting threshold at GE2024 (contributes ~0).

## Tripwires (re-run on trigger)

- **TVK alliance reversal (joins NDA or SPA)** → bloc structure changes; re-run
- **A rated agency publishes vote shares before 23 Apr** → M3 upgrades to rated sigma