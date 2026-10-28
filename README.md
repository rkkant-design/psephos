# Psephos

A calibrated prediction engine for elections, sport, and world events. It answers
each question with several **independent** methods, certifies a **CALL** only when
they agree beyond 95%, and seals every forecast into the Bitcoin blockchain
**before** the event — so the track record can be verified by anyone and edited by
no one, misses included.

By **Trueinfo Labs**.

---

## What it does

- **Forecasts** Indian state elections (constituency-level Monte Carlo), US
  elections, football (per-fixture and title), and cricket.
- **Gates** every forecast: `CALL` (certified), `WATCH` (genuinely open, with the
  tripwires that would settle it), or `WATCH-FLAG` (a safety rule — e.g. a new party
  with no electoral history — suppresses calls).
- **Scores** every resolved probability with Brier/log scores and calibration,
  including the open `WATCH` ones (hit-rate alone is gameable).
- **Pre-registers** each forecast with a SHA-256 hash in append-only ledgers,
  anchored to Bitcoin via OpenTimestamps.
- **Serves** a searchable web app (`site/`) with live forecasts, a moments
  calendar, free-form *Ask*, and the full track record.

Lifetime record at time of writing: **34/37 certified calls correct**; measured
cross-instrument error correlation **r = 0.745** (the published reason a CALL
requires agreement between methods).

## The instruments

| Instrument | Reads | Blind to |
|---|---|---|
| **Structural model** (M2) | 60+ years of results, seat maps, alliance history | all news |
| **Corrected polls** (M3) | surveys, adjusted by each pollster's measured past error | — |
| **Market** | de-vigged betting / prediction-market odds | — |
| **Research** | evidence under a base-rate-first protocol | market prices (by rule) |

A forecast is a `CALL` only when the instruments that apply independently clear 95%.

## Repository layout

```
src/
  engine/        the forecasting models
    predict.py          India state elections (M2 structure + M3 polls, MC seats)
    world_predict.py    world events (market x model x research, dual/2-of-3 gate)
    m_research.py       the research instrument (base-rate-first protocol)
    usmid_races.py      US midterm race-level correlated Monte Carlo
    epl_matches.py      football fixture model (v2: own-priors, market, congestion)
    insider_flow.py     defection / ticket-demand signal (reported, pre-registered)
  pipeline/      data acquisition & feature building (numbered stages 01..15)
  scoring/       score.py (Brier/calibration), anchor.py (Bitcoin anchoring)
  benchmark/     ForecastBench / Metaculus entry harness
  webbuild/      app-data and static-site builders
  lib/           shared helpers (ms_lib) + answer data

data/
  raw/           source downloads (gitignored; see **/SOURCES.md to rebuild)
  processed/     engine-ready tables (alpha/tau/sigma, state shares, ...)
  benchmarks/    ForecastBench question sets + submission files

forecasts/       THE RECORD — configs + pre-registration ledgers + anchors
  *.json              India election configs (UP/PB/UK 2027, ...)
  world/              world-event configs + forecasts (USMID, EPL, CWC)
  *_ledger.csv        append-only, SHA-256 hashed forecast ledgers
  anchors/            OpenTimestamps manifests + .ots proofs

reports/         written analyses (retrodiction, holdout, parameter fits)
docs/            how-it-works, benchmark entry, pitch
site/            the published Psephos web app
AUTOPILOT.md     weekly maintenance protocol (signals, re-runs, resolution, anchoring)
```

## Running it

Python 3.12.

```bash
pip install -r requirements.txt
```

Forecast an election (config-driven), score, rebuild the app:

```bash
python src/engine/predict.py UP2027            # -> appends hashed ledger rows
python src/engine/world_predict.py USMID2026
python src/scoring/score.py                    # Brier / calibration over all resolved rows
python src/scoring/anchor.py stamp             # anchor ledgers to OpenTimestamps
python src/webbuild/13_build_app_data.py       # regenerate site/app_data.json
```

## The laws (non-negotiable)

- **Ledgers are append-only.** Only the three resolution columns
  (`resolved`/`outcome`/`correct`) may ever be filled later, on the latest rows.
- **Parameter changes are prospective.** A model is only ever changed going forward;
  past forecasts stay scored under the model that made them.
- **No tuning on single results.** Calibration verdicts need volume (~60+ resolved
  CALLs); one bad week is recorded exactly as-is.
- **Instruments stay independent.** The research pass never consults market prices.

---

*Probabilistic analysis for research, not advice. Not a betting product; no
financial advice. Data: TCPD/Lok Dhaba, DataMeet, ECI via public mirrors; polls from
pre-election frozen Wikipedia revisions; markets via public APIs.*
