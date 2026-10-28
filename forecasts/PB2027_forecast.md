# Forecast: Punjab Assembly 2027

**Freeze:** 2026-10-23 · **Run:** 2026-10-23T09:18:27+00:00 · **SHA256:** `b88aebe522fcb3f7…` (full hash in ledger.csv)

Params: α=0.467 σ_c=12.31 τ=0.5 σ_state M2=6.3 M3=6.0 (UNRATED agencies)

## Predicted state vote shares (pts)

| bloc | baseline (reblocked) | GE | M2 | M3 (corrected polls) |
|---|---|---|---|---|
| AAP | 42.3 | 26.2 | 34.8 | 34.0 |
| INC | 23.1 | 26.4 | 24.7 | 28.8 |
| SAD | 18.5 | 13.5 | 16.2 | 12.4 |
| BJP | 6.7 | 18.6 | 12.3 | 12.5 |

## Seat simulations (10k runs)

| bloc | M2 5–95% (med) | P_maj | P_largest | M3 5–95% (med) | P_maj | P_largest |
|---|---|---|---|---|---|---|
| AAP | 36–85 (62) | 0.59 | 0.88 | 33–81 (58) | 0.48 | 0.75 |
| INC | 11–54 (28) | 0.03 | 0.11 | 18–65 (39) | 0.11 | 0.25 |
| SAD | 3–32 (13) | 0.00 | 0.01 | 2–23 (9) | 0.00 | 0.00 |
| BJP | 2–23 (9) | 0.00 | 0.00 | 2–22 (9) | 0.00 | 0.00 |

## Gate verdicts (dual, min(M2,M3) ≥ 0.95)

| question | P M2 | P M3 | gate | verdict |
|---|---|---|---|---|
| AAP wins majority | 0.591 | 0.483 | 0.483 | **WATCH** |
| AAP is largest | 0.876 | 0.750 | 0.750 | **WATCH** |
| INC wins majority | 0.029 | 0.105 | 0.029 | **WATCH** |
| INC is largest | 0.109 | 0.247 | 0.109 | **WATCH** |
| SAD wins majority | 0.000 | 0.000 | 0.000 | **WATCH-FLAG** |
| SAD is largest | 0.012 | 0.002 | 0.002 | **WATCH-FLAG** |
| BJP wins majority | 0.000 | 0.000 | 0.000 | **WATCH-FLAG** |
| BJP is largest | 0.002 | 0.001 | 0.001 | **WATCH-FLAG** |
| BJP under 15 seats | 0.780 | 0.807 | 0.780 | **WATCH** |
| SAD under 20 seats | 0.731 | 0.906 | 0.731 | **WATCH** |
| Winner (largest) in {AAP, INC} | 0.986 | 0.997 | 0.986 | **WATCH-FLAG** |

## Quality flags

- NEW-ENTRANT FLAG ACTIVE: Waris Punjab De (Amritpal Singh) polls 8.5-14% with no electoral baseline - the exact TVK/TN2026 pattern. All would-be CALLs are suppressed to WATCH-FLAG per the validated N=46 rule.
- All final-window polls are unrated agencies; two partisan-affiliated polls (Desh Ka Verdict/INC, Aapka Opinion/AAP) excluded - seat-only projections, no vote shares.
- Poll spread is extreme: AAP 27-38, SAD 6-19 across agencies in the same window.
- WPD is not a simulatable bloc (zero baseline): its 8-14% will come asymmetrically from AAP's and SAD's Panthic vote, which the uniform-swing Monte Carlo cannot represent.

## Tripwires (re-run on trigger)

- **WPD trajectory in later polls (toward 20%+ = TN2026 fracture pattern; fade below 5% = flag review)** → fracture would invalidate all two-way simulations; fade would lift the flag and make the gate decidable
- **Any SAD-BSP or SAD-WPD alliance formation** → re-bloc and re-run with tau transfers
- **A rated agency (CVoter/CSDS/Axis) publishes a vote-share poll** → M3 upgrades to rated sigma
- **Ticket-season defection flows, net direction** → insider-flow signal; sustained one-way flow triggers re-run