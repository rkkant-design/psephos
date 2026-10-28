# Forecast: Uttar Pradesh Assembly 2027

**Freeze:** 2026-10-16 · **Run:** 2026-10-23T09:18:24+00:00 · **SHA256:** `469c5e1394d7fc4c…` (full hash in ledger.csv)

Params: α=0.461 σ_c=10.64 τ=0.5 σ_state M2=6.3 M3=6.0 (UNRATED agencies)

## Predicted state vote shares (pts)

| bloc | baseline (reblocked) | GE | M2 | M3 (corrected polls) |
|---|---|---|---|---|
| NDA | 46.2 | 44.0 | 45.2 | 44.4 |
| INDIA | 33.5 | 43.4 | 38.0 | 38.5 |
| BSP | 13.0 | 9.5 | 11.4 | 5.7 |

## Seat simulations (10k runs)

| bloc | M2 5–95% (med) | P_maj | P_largest | M3 5–95% (med) | P_maj | P_largest |
|---|---|---|---|---|---|---|
| NDA | 126–314 (219) | 0.61 | 0.64 | 127–306 (212) | 0.57 | 0.59 |
| INDIA | 83–270 (176) | 0.34 | 0.36 | 94–273 (187) | 0.40 | 0.41 |
| BSP | 0–23 (5) | 0.00 | 0.00 | 0–12 (2) | 0.00 | 0.00 |

## Gate verdicts (dual, min(M2,M3) ≥ 0.95)

| question | P M2 | P M3 | gate | verdict |
|---|---|---|---|---|
| NDA wins majority | 0.612 | 0.575 | 0.575 | **WATCH** |
| NDA is largest | 0.637 | 0.589 | 0.589 | **WATCH** |
| INDIA wins majority | 0.340 | 0.400 | 0.340 | **WATCH** |
| INDIA is largest | 0.363 | 0.411 | 0.363 | **WATCH** |
| BSP wins majority | 0.000 | 0.000 | 0.000 | **CALL-NO** |
| BSP is largest | 0.000 | 0.000 | 0.000 | **CALL-NO** |
| BSP under 25 seats | 0.956 | 0.993 | 0.956 | **CALL-YES** |
| NDA at least 150 seats | 0.882 | 0.872 | 0.872 | **WATCH** |
| INDIA at least 150 seats | 0.667 | 0.735 | 0.667 | **WATCH** |
| Winner (largest) in {NDA, INDIA} | 1.000 | 1.000 | 1.000 | **CALL-YES** |

## Quality flags

- ALL four polls are from unrated agencies; none discloses methodology/sample/fieldwork dates (aitimeline.in audit, Sep 2026). M3 runs with inflated sigma and this forecast cannot upgrade to CALL on these polls alone.
- BSP polled range 0.8-11.0 pct across agencies - a 10-point spread on one party is a pollster-quality symptom, not information.
- INDIA bloc composition not final: SP-INC seat-sharing unresolved at freeze (INC demands ~150 seats, SP signals ~50).

## Tripwires (re-run on trigger)

- **SP-INC seat-sharing collapses (INC exits or fights separately)** → INDIA loses tau x INC transfer (~1.2 pts) and opposition fragments further; NDA majority probability rises materially
- **A rated agency (CVoter/CSDS-Lokniti/Axis) publishes a vote-share poll** → M3 upgrades to rated sigma; gate becomes meaningfully decidable
- **Ticket-season defection flow (late 2026/early 2027), net direction weighted by defector quality** → insider-flow signal; sustained one-way flow is grounds to re-run forecast
- **BSP-ASP(KR) dynamics: ASP contesting ~87 seats; any BSP-ASP tie-up or BSP revival sign** → changes Dalit-vote split assumptions; re-run with ASP as modeled entrant
- **EC announces schedule / phase dates** → freeze window formally ends; issue updated pre-registered forecast