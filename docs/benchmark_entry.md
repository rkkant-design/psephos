# Entering independent benchmarks with M_research

Goal: a refereed, third-party scored record for Psephos' research instrument —
the arena where Mantic-class forecasters are measured. Two venues, researched
2026-10-23. Everything below that needs an account or key is marked **USER**.

## 1. ForecastBench (Forecasting Research Institute)

The benchmark from the ForecastBench paper (arXiv 2409.19839), now open to
public submissions. Two leaderboards: **Baseline** (out-of-the-box models) and
**Tournament** (any scaffolding allowed — that's us: M_research is scaffolding
by design).

- **Cadence:** submission rounds every two weeks (bi-weekly since 2025-03-02).
  Observed in the datasets repo on 2026-10-23: question sets through
  `2026-10-11-llm.json`, so the next rounds are ~**2026-10-25** and
  ~2026-11-08 — verify at forecastbench.org before committing to a round.
  (A copy of the 2026-10-11 set is kept at `data/benchmarks/` as a pipeline
  test fixture; the harness was verified against it.)
- **USER — register once:** form at https://register.forecastbench.org
  (team name, optional anonymity). Within ~24h you get an email with a
  **GCP Cloud Storage upload folder**, the next due date, and your org name.
  Test-upload a file when it arrives. Contact:
  forecastbench@forecastingresearch.org. Limit: 3 submissions/round per person
  across all teams.
- **Question feed (no account needed):** at 00:00 UTC on the due date,
  `datasets/question_sets/<due_date>-llm.json` appears in
  https://github.com/forecastingresearch/forecastbench-datasets.
  500 questions: 250 "market" (kalshi/manifold/metaculus/polymarket — you
  predict how the market's question resolves; you must still never look at its
  price) and 250 "dataset" (acled/dbnomics/fred/wikipedia/yfinance), the
  latter forecast at up to 8 horizons (due date +7/+30/+90/+180/+365/+1095/
  +1825/+3650 days). Drop combination questions (array-valued `id`).
- **Submission file:** `<due_date>.<org>.<N>.json` with keys
  `organization`, `model`, `model_organization`, `question_set`, `forecasts`;
  each forecast = `{id, source, forecast (0-1), resolution_date (null for
  market questions), reasoning (optional)}`. The `model` name is permanent
  once results post — pick it carefully (suggest: `Psephos M_research v1`).
- **Deadline:** upload to the GCP folder by **23:59:59 UTC on the due date**
  (same day the questions drop — a one-day turnaround for ~2,000 (question,
  horizon) pairs; plan the run).
- **Ranking rule:** >= 95% coverage of market questions AND of dataset
  questions, or you don't appear; missing forecasts impute 0.5. Unresolved
  market questions wait for resolution before scoring.
- **Harness:** `python scripts/benchmark_harness.py normalize <question_set.json>`
  → dossier skeletons → LLM fills them per the m_research protocol →
  `python scripts/m_research.py batch forecasts/research/dossiers/benchmarks`
  (ledger rows, hashed) →
  `python scripts/benchmark_harness.py submission forecastbench <question_set.json> --org <ORG> --model "Psephos M_research v1"`
  → upload the produced `data/benchmarks/<due_date>.<org>.1.json`.

## 2. Metaculus AI Benchmarking tournaments

Bot-only tournaments (quarterly series, $120k prize pools in past cycles;
the current cycle's tournament id in Metaculus' own bot template is **33121**,
"Fall 2026 AI Benchmarking"). Only **bot accounts** can enter; forecasts must
go through the API (manual-triggered runs are allowed, hand-entered forecasts
are not).

- **USER — create a bot account:** log out of any personal Metaculus session,
  register via the bot sign-up (https://www.metaculus.com/aib/ — a demo page
  exists at /aib/demo; a gmail `+suffix` address works for a separate
  account), activate from the email, then copy the **API token** shown at
  /aib/ (or Settings → API access). Keep it as the `METACULUS_TOKEN`
  environment variable. From a human account, Settings → "My Forecasting
  Bots" → "Switch to bot account" manages it.
- **Rules:** recent series require a reasoning comment posted with each
  forecast (the harness posts the dossier's `reasoning_summary` as a private
  comment with `included_forecast: true`) and willingness to describe how the
  bot works. Per-series rules change — read the current tournament page when
  the account exists.
- **API (verified against Metaculus' own bot template):**
  - List open questions: `GET https://www.metaculus.com/api/posts/` with
    `tournaments=<id>&statuses=open&forecast_type=binary&include_description=true`,
    header `Authorization: Token <METACULUS_TOKEN>` (listing works
    anonymously; submitting does not).
  - Submit: `POST /api/questions/forecast/` with body
    `[{"question": <question_id>, "source": "api", "probability_yes": p,
    "probability_yes_per_category": null, "continuous_cdf": null}]`.
  - Comment: `POST /api/comments/create/` with
    `{"text", "parent": null, "included_forecast": true, "is_private": true,
    "on_post": <post_id>}`.
  - Multiple-choice / numeric questions need `probability_yes_per_category` /
    a 201-point `continuous_cdf` — **the harness currently handles binary
    questions only** and filters to those.
- **Harness:** `python scripts/benchmark_harness.py fetch-metaculus
  [--tournament 33121]` → skeletons → fill → `m_research.py batch` →
  `python scripts/benchmark_harness.py submission metaculus` (dry run writes
  `data/benchmarks/metaculus_payload.json`; add `--post` with
  `METACULUS_TOKEN` set to actually submit).

## What the user must do before any entry is live

1. **ForecastBench:** register the team at register.forecastbench.org, confirm
   the GCP upload folder works, and tell the autopilot/operator the org name
   and the next due date. No API key — upload access IS the credential.
2. **Metaculus:** create the bot account, retrieve the API token, and set
   `METACULUS_TOKEN` in the environment the harness runs in. Confirm the
   current tournament id (33121 per the bot template as of Oct 2026).
3. Decide identity policy: ForecastBench offers irreversible anonymity;
   entering as Trueinfo Labs / Psephos is the visibility play.

Until then the harness stops at building files — it never fabricates a
submission, and every benchmark forecast it does produce is already
pre-registered in `forecasts/research_ledger.csv` with a SHA-256 hash at
commit time, scoreable by `scripts/score.py` regardless of whether the
external entry happens.

## Known constraints (honest accounting)

- The ForecastBench one-day turnaround (question drop 00:00 UTC, upload by
  23:59:59 UTC) is the binding operational constraint: ~250 market + up to
  ~2,000 dataset (question, horizon) forecasts in under 24h of LLM research.
  First entry should target covering 100% of market questions and the minimum
  95% of dataset questions, with dataset-question research batched by source
  (FRED series, Wikipedia tables) rather than per-question.
- Metaculus binary-only coverage: multiple-choice/numeric/discrete questions
  are skipped by the harness today; tournaments score only what you forecast,
  but prize eligibility may require broader coverage — check the series rules.
- Mantic comparison: Mantic self-reports vs Polymarket; ForecastBench and
  Metaculus AIB are the venues where any comparison is third-party refereed.
  Mantic won the Summer 2026 Metaculus Cup — the Metaculus bot tournament is
  the most direct head-to-head available.
