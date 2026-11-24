# Forecast: Punjab Assembly 2027

**Freeze:** 2026-11-24 · **Run:** 2026-11-24T09:32:11+00:00 · **SHA256:** `64663e85a49272cd…` (full hash in ledger.csv)

Params: α=0.467 σ_c=12.31 τ=0.5 σ_state M2=6.3 M3=6.0 (UNRATED agencies)

## Predicted state vote shares (pts)

| bloc | baseline (reblocked) | GE | M2 | M3 (corrected polls) |
|---|---|---|---|---|
| AAP | 42.3 | 26.2 | 34.8 | 33.5 |
| INC | 23.1 | 26.4 | 24.7 | 27.0 |
| NDA | 21.8 | 22.8 | 22.3 | 21.2 |

## Seat simulations (10k runs)

| bloc | M2 5–95% (med) | P_maj | P_largest | M3 5–95% (med) | P_maj | P_largest |
|---|---|---|---|---|---|---|
| AAP | 36–87 (62) | 0.59 | 0.83 | 33–82 (58) | 0.48 | 0.75 |
| INC | 11–56 (30) | 0.03 | 0.11 | 17–62 (37) | 0.07 | 0.20 |
| NDA | 7–48 (22) | 0.01 | 0.06 | 6–43 (20) | 0.00 | 0.04 |

## Gate verdicts (dual, min(M2,M3) ≥ 0.95)

| question | P M2 | P M3 | gate | verdict |
|---|---|---|---|---|
| AAP wins majority | 0.591 | 0.483 | 0.483 | **WATCH** |
| AAP is largest | 0.832 | 0.754 | 0.754 | **WATCH** |
| INC wins majority | 0.035 | 0.074 | 0.035 | **WATCH** |
| INC is largest | 0.113 | 0.205 | 0.113 | **WATCH** |
| NDA wins majority | 0.010 | 0.005 | 0.005 | **WATCH-FLAG** |
| NDA is largest | 0.055 | 0.041 | 0.041 | **WATCH** |
| NDA (SAD+BJP) under 30 seats | 0.712 | 0.766 | 0.712 | **WATCH** |
| Winner (largest) in {AAP, INC} | 0.945 | 0.959 | 0.945 | **WATCH** |

## Quality flags

- NEW-ENTRANT FLAG ACTIVE: Waris Punjab De (Amritpal Singh) polls 8.5-14% with no electoral baseline - the exact TVK/TN2026 pattern. All would-be CALLs are suppressed to WATCH-FLAG per the validated N=46 rule.
- All final-window polls are unrated agencies; two partisan-affiliated polls (Desh Ka Verdict/INC, Aapka Opinion/AAP) excluded - seat-only projections, no vote shares.
- Poll spread is extreme: AAP 27-38, SAD 6-19 across agencies in the same window.
- WPD is not a simulatable bloc (zero baseline): its 8-14% will come asymmetrically from AAP's and SAD's Panthic vote, which the uniform-swing Monte Carlo cannot represent.
- SAD-BJP ALLIANCE (announced 24-Nov-2026): modeled as one NDA bloc (SAD anchor + BJP at tau transfer). Pre-alliance polls are party-wise, so the NDA poll share is composed SAD + tau*BJP; the real post-alliance transfer is uncertain (bitter 2020 split, rural-Sikh vs urban-Hindu bases, WPD draining the Panthic vote). FPTP also makes a ~25-28% combined vote seat-inefficient (2022: SAD 18%=3 seats, BJP 6.6%=2 seats).

## Tripwires (re-run on trigger)

- **WPD trajectory in later polls (toward 20%+ = TN2026 fracture pattern; fade below 5% = flag review)** → fracture would invalidate all two-way simulations; fade would lift the flag and make the gate decidable
- **SAD-BJP seat-sharing finalized, or any SAD-BSP / SAD-WPD tie-up** → SAD-BJP FIRED 24-Nov-2026 -> re-blocked to one NDA bloc (SAD + tau*BJP), freeze 2026-11-24; re-run again on finalized seat-sharing or any further alliance move
- **A rated agency (CVoter/CSDS/Axis) publishes a vote-share poll** → M3 upgrades to rated sigma
- **Ticket-season defection flows, net direction** → insider-flow signal; sustained one-way flow triggers re-run