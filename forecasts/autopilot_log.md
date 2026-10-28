# Psephos Autopilot Log

Append-only run reports from the `psephos-autopilot` scheduled task (protocol: AUTOPILOT.md).

---

## 2026-10-23 — no signals moved

**Polls admitted:** none. Wikipedia vote-share tables match configs exactly — UP (4 polls, newest Matrize 29-Sep), PB (4, newest SCORE 15-Oct), UK (3, newest Times Now Navbharat 13-Sep).

**Tripwires fired:** none. Watched:
- UP / SP-INC seat-sharing: friction continues (INC demands 150+, SP MP floats 50, Akhilesh sets "winnability" test; formal talks expected late Oct/Nov) — no collapse, no deal.
- UP / rated poll: none. Note: News18-Pvalue mega survey (30,925 respondents, fieldwork 17-Sep–2-Oct) published ~16-Oct with retention figures but no headline vote shares; Pvalue is unrated — not admissible.
- UP / defections: 3 rebel SP MLAs (Rakesh Pratap Singh, Abhay Singh, Vinod Chaturvedi — all expelled 2025) formally joined BJP 14-Oct in Amethi. Single event of already-detached rebels, not a sustained flow — watched, not fired.
- UP / BSP-ASP: both still solo (Mayawati reiterated no alliance; ASP named 45 seat in-charges).
- UP / EC schedule: not notified; EC state reviews run to ~15-Dec, dates expected after; board exams (5–24 Feb 2027) may push polls to Mar–Apr.
- PB / WPD trajectory: no poll newer than SCORE 8.5% (15-Oct); neither 20%+ fracture nor <5% fade. Note: ECI registration dispute ongoing (party may run candidates as Independents); Amritpal pitched as CM face.
- PB / SAD alliances: no SAD-BSP or SAD-WPD formation. SAD-BJP reunion talk (Badal-Modi meeting 7-Aug, "advanced stage" per ANI sources) is single-source speculation, partly denied — watched, not fired. Would require re-bloc if confirmed.
- PB + UK / rated polls, defections, INC alliances, CM change: nothing concrete.

**Flags:** PB2027 new-entrant flag (WPD/Amritpal Singh) unchanged — active; latest datum 8.5% (SCORE, 15-Oct), no fade.

**Re-runs:** none (no admission, no fire, no flag change). **Republish:** no.

**Flagged for user, not acted on:** (1) SAD-BJP alliance talks — if confirmed, PB2027 needs a re-bloc (tau transfer) and re-run; watch closely. (2) WPD's ECI registration denial could force its candidates to run as Independents — the flag logic should still apply to the movement, not the ballot label; protocol doesn't address this, no action taken.

## 2026-10-23 — engine upgrade (user-directed session, not an autopilot run)

**Scoring layer added** (`scripts/score.py`): Brier + log for EVERY resolved pre-registered probability (WATCH rows included), calibration table, model-vs-market skill table (locked in at n=0; first datum when USMID2026 resolves 2026-11-03). First real numbers over the 2026 holdout: 61 instrument-probabilities, overall Brier 0.272, M2 0.235 / M3 0.321 — the TN upset priced in, nothing hidden. Outputs: `data/processed/scores.csv` + `scores_summary.json`.

**Fixture-level EPL model** (`scripts/epl_matches.py` + `epl_resolve.py`): shrunk-PPG (k=12) Poisson with stated priors (C=1.5 goals/PPG pt, home +0.35, μ=2.75). Feed: fixturedownload.com epl-2026 (recomputed table cross-checked vs config MD7 table: identical). **MW8 pre-registered before kickoff**: 10 matches, sha `30f52b28…`, new `forecasts/matches_ledger.csv` (same append-only law). Script hard-refuses post-kickoff pre-registration.

**Resolution criteria** added to all 6 live configs (`resolution` object: source, edge-case rules, resolve_by — EPL points-deduction rule, US Senate caucusing rule, CWC shared-trophy rule, India freeze-time-bloc rule). predict.py/world_predict.py now hash it into payloads and stamp `resolution_source` on ledger rows. **Schema extension:** `resolution_source` column appended (trailing) to ledger.csv and world_ledger.csv; existing rows got only a trailing comma — no cell edited. All 6 live forecasts re-registered with criteria in-hash (probabilities identical to prior runs): UP `469c5e13…`, PB `b88aebe5…`, UK `0dff80fc…`, USMID `c1ff9858…`, EPL `63303833…`, CWC `159d2d38…`.

**App**: Brier tile + collapsible calibration panel + Matches chip/section + resolution-criteria blocks; republished (artifact v4). **AUTOPILOT.md** extended: EPL resolve → pre-register → re-score steps in the Monday run; resolution-criteria hard rule (never adjusted after the fact).

## 2026-10-24 — EPL match model v1 -> v2 (user-directed session, not an autopilot run)

**Why:** the MW8 miss review (Villa 2-1 City after a 53% away pick; Ipswich 1-1 after a 53% home pick) surfaced three STRUCTURAL blind spots in v1 — it did not re-tune on those two results (single results never move parameters; calibration verdicts need ~50+ matches). The upgrades fix the structure prospectively; **MW1-8 rows stay v1 forever and are scored as made.**

**v2 changes** (`scripts/epl_matches.py`, prospective from MW9; `model_version` ledger column says which model made each row):
1. **Team-specific priors** — shrinkage target is now each club's OWN prior (2025-26 final PPG from the Wikipedia final table, fetched 2026-10-24; promoted Hull/Ipswich/Coventry get the 1.05 historical promoted-side average), not the league mean 1.37 that dragged strong-but-slow-starting teams (Man City) to mid-table strength. Blend: strength = lam*ppg + (1-lam)*prior, lam = p/(p+12) — k unchanged.
2. **Market instrument per fixture** — dated 1X2 odds fetched before pre-registration (this week: oddschecker PL coupon best price, 2026-10-24), de-vigged, stored as market_ph/pd/pa + overround + source + date ledger columns and in the hashed payload. Benchmark instrument #2: `score.py` now reports per-matchweek model-vs-market 3-way Brier (the weekly skill score). **The published pick stays the model's**; if the market wins most matchweeks over >=5 weeks the report prints a recommendation to consider blending — a user decision, never automatic.
3. **Congestion flag** — congestion_home/away (yes/no) + note per fixture: did the team play a listed cup/European midweek match within 4 calendar days before kickoff (basis in EPL_MWxx_context.json). Recorded for MEASUREMENT only; v2 deliberately does not price it — measure first, model later.

**Schema extension (append-only law kept):** 10 trailing columns added to matches_ledger.csv (model_version, market_*, congestion_*); the 10 existing MW8 rows got trailing commas only — no cell edited, MW8 sha 30f52b28... intact, anchor hashes unaffected.

**MW9 pre-registered with v2** (10 matches, freeze 2026-10-24, sha `c7640d3c...`): all kickoffs future at run time; market columns filled for 10/10 (overround 2.4-5.5%); congestion flags from the EFL Cup R4 midweek Oct 27-29 (UEFA calendar check: UCL MD3 Oct 20-21, MD4 Nov 3-4 — no European fixtures in the window): 12 of 20 team-slots flagged, incl. Man City-Brighton and Newcastle-Everton who each replay their own cup opponent. Notable model-vs-market gaps: Brentford 60% vs mkt 47% home; Spurs 41% vs mkt 59% home; Man City 69% vs mkt 56% home — v2's calls, scored honestly either way.

**MW8 untouched** — resolves in Monday's autopilot run as pre-registered, scored under v1.

**AUTOPILOT.md** matchweek steps rewritten for v2 (context file -> pre-register -> re-score with skill table).

## 2026-10-25 — US midterms race-level board (user-directed session, not an autopilot run)

**Why:** USMID2026 covered chamber control only, and the Senate question ran market-only. Election day 2026-11-03 is the engine's biggest single scoring event; this build pre-registers every race before it.

**Rosters, verified not assumed** (Wikipedia, fetched 2026-10-24): **36 state governor races** (user brief said 34; the official count is 36 — 18 D-held, 18 R-held) and **35 Senate seats** (33 Class 2 + FL/OH specials; 22 R-held, 13 D-held up; 34 D-aligned + 31 R seats not up; Dems need 51, VP is R). Post-cutoff surprises verified per-race: Lindsey Graham died 2026-07-11 (sister Darline Graham appointed, running); OK interim appointee barred from running; **no Democratic nominee on the ballot in ID/SD/NE Senate** (p_model = 0.01 by rule, flagged).

**New dual-instrument race model** (`scripts/usmid_races.py`, all parameters stated priors in the docstring): M_market = de-vigged Polymarket per-race party-winner prices (`scripts/usmid_fetch_markets.py`, gamma-api anonymous, raw responses kept; 68/71 races liquid; AK gov+sen and CA gov have only candidate-level markets — not admitted under the party-pair rule, so market=null). M_model = candidate-blind structural probit: 0.9 (Sen) / 0.6 (Gov) x relative 2024 lean + generic ballot (Silver Bulletin **D+9.1**, 2026-10-23) + incumbency (Sen +/-3 elected, +/-1 appointed; Gov +/-5, +/-1.5); sigma 7.07 (Sen) / 10.6 (Gov) with a SHARED national error (sd 5) for the Monte Carlo.

**Pre-registered:** 71 races in new append-only ledger `forecasts/world/usmid_races_ledger.csv`, sha `ffe4c93d...`, freeze 2026-10-25 (markets fetched 2026-10-24): **16 CALL-YES, 11 CALL-NO, 41 WATCH, 3 WATCH-1INST**. The gate called the safe states and left every genuine contest open; 8 races carry splits > 25 pts (VT gov 74 pts — the candidate-blind model cannot see Phil Scott; that miss will be scored, not hidden).

**Senate question now dual-instrument:** correlated MC roll-up (100k sims) gives **P(Dem control) = 0.5465** (median 51 seats, 90% range 47-56) vs market 0.675 — pasted into USMID2026.json `model.senate_model`, chamber re-run (sha `81b3307f...`): all three chamber questions WATCH (House: market .915 / model .970 / research .90; Senate: .675 / .5465 / .40). House added a seat-total distribution (median 247 D seats, 90% range 218-276, seats-votes curve spp=4.5) + 5 Polymarket state seat-band markets recorded as context; **no district models built, by design**.

**Plumbing:** anchor.py LEDGERS + score.py now cover the races ledger (us_races block + its own model-vs-market skill table — first big skill sample at resolution); `anchor.py stamp` run (manifest_20261025T050113, verify OK). **App:** USMID2026 detail gained the sortable race board (Governors / Senate / House, verdict chips, TOO CLOSE at 45-55 combined, splits printed); artifact republished (v14), capabilities carried forward. **AUTOPILOT.md:** race-board refresh steps + full election-night/Nov-9 resolution procedure (AP calls only; uncalled races wait for certification).

## 2026-10-26 — MW8 scored (partially), USMID + EPL2027 re-run

**Polls admitted:** none. UP (newest Matrize 29-Sep), PB (SCORE 15-Oct), UK (TNN 13-Sep) — Wikipedia tables match configs exactly.

**Tripwires fired:** none. Watched: UP SP-INC seat-sharing friction continues (INC 150 vs SP ~50, formal talks expected Nov); no UP defections since the 14-Oct trio (already in insider ledger); PB SAD-BJP talks remain sourced speculation, partly denied; WPD no new datum (8.5%, 15-Oct); UK quiet. **Flags:** PB WPD flag unchanged. **Insider flow:** no new qualifying events; day's signal pre-registered — UP NDA strong (1.0), PB WPD moderate (0.714), labels unchanged. **Moments:** no EC 2027 schedule, no new by-poll schedule, no dated slate changes; calendar untouched. **India re-runs:** none.

**EPL:** MW8 resolved 5/10 (Ipswich-Forest D, Villa 2-1 City H, Arsenal 2-0 Everton H, Coventry 0-1 Fulham A, Chelsea 0-2 Spurs A) — favourites 1/5, matchweek 3-way Brier 0.789 (uniform ref 0.667); an upset-heavy week, scored as made. Other 5 MW8 games played per Wikipedia but fixturedownload feed lacks finals — left pending per protocol (never resolve from memory); resolve next run. MW9 already pre-registered 24-Oct (v2, sha c7640d3c…) — no new pre-registration. score.py: binary n=61 Brier 0.2718; match-skill table starts at MW9.

**World:** USMID2026 re-run (Senate Polymarket 0.675→0.645, a 3.0-pt move; House 0.915 and generic ballot D+9.1 (23-Oct) unchanged): all three chamber questions stay WATCH, sha a7ef9acc…. Race board: all 65 liquid race markets refetched; largest move 5.1 pts (OK gov 0.080→0.131) < 10-pt threshold and generic ballot unmoved → board NOT re-registered. EPL2027 re-run (fresh dated outrights, TNT best-price 20-Oct; MD8 table complete 25-Oct): model City 0.740→0.480, Arsenal 0.180→0.463 (title race now level on points); market Arsenal 0.610; verdicts unchanged — Liverpool CALL-NO, top-5 CALL-YES, rest WATCH; sha 74326640…. CWC2027: ICC ratings drifted (England 93→91, Pakistan 103→104) — under the 5-pt tripwire, no re-run.

**Asks:** 1 open row (gold, resolve_by 30-Oct) — none due. **Republish:** yes (artifact v16). **Anchors:** 3 earlier manifests upgraded to complete Bitcoin attestations; VERIFY OK (all hashes present); new manifest 20261026T053623 stamped (pending).

**Flagged for user, not acted on:** (1) fixturedownload feed lags finished MW8 finals by 1+ day — if it persists, consider adding a secondary official results source to epl_resolve.py (user decision). (2) EPL market odds (20-Oct) predate MW8, so part of the model-market gap is timing; fresher dated outrights next run.

## 2026-10-26 — ForecastBench round 2026-10-25: MISSED leaderboard, record sealed
- The 06:00 IST scheduled task never fired (app closed overnight); recovery was done
  manually but the session paused and resumed past the 23:59 UTC 2026-10-25 upload
  deadline (checked: passed by ~5.7h). Oct-25 LEADERBOARD ENTRY MISSED.
- Work completed and NOT wasted: question set fetched (500 Q -> 1496 forecast pairs),
  all 1496 forecasts authored (146 researched: Metaculus + election/macro/markets
  Kalshi clusters; 104 rule-based Kalshi priors; 1246 dataset family base-rates from
  each question's own freeze value), committed to research_ledger.csv (60 dossiers,
  all hashed), submission file built at 100% coverage (data/benchmarks/
  2026-10-25.Anonymous 58.1.json), ledger anchored (manifest_20261026T054114, OTS
  pending). These 1496 pre-registered forecasts stand as a self-scored benchmark run:
  score.py will Brier-score them as ForecastBench questions resolve, even without the
  leaderboard.
- NEXT ROUND ~2026-11-08. FIX REQUIRED: the scheduled-task approach failed because the
  desktop app must be open at fire time. For Nov 8, either (a) keep the app open that
  morning, or (b) run the build manually on the due date. The harness + fill scripts
  (fb_fill_oct25.py pattern) are reusable; only the dated question set changes.
