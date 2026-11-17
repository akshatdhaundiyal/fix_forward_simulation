---
title: Fix Forward Calibration and Balance - Plan
type: feat
date: 2026-11-17
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# Fix Forward Calibration and Balance - Plan

## Goal Capsule

- **Objective:** The organiser can see, from one command, whether the game rewards measured risk over shortcuts, with every card's hidden effect matched to the spec's target gain or flagged as unreachable.
- **Means:** A bisection calibrator that writes lifts as data, eight pre-registered scripted strategies, and a league report against the spec's pass criteria (KTD1, KTD3, KTD4).
- **Authority:** `fix_forward_build_spec_v3.md` section 13 defines the pass criteria. `CLAUDE.md` "Balance" defines how numbers may change. This plan defines the tools and the strategy rules.
- **Stop conditions:** Stop and report if a pass criterion fails after calibration. Do not change any game number other than lifts and telemetry noise, and do not change a mechanic. Propose other number changes through the what-if table only.
- **Execution profile:** One change on a feature branch, one PR. No external dependencies.
- **Out of this stage:** server, clock, screens, stakeholder flows, and any committed change to costs, targets, capacity or scoring numbers.

---

## Product Contract

### Summary

Add `calibrate.py`, extend `bots.py` with eight strategies and a league report, cap lifts so the engine stays physical, tune telemetry noise against a stated rule, and write a balance report with a what-if table the organiser can decide from.

### Problem Frame

Stage 1's lifts are one placeholder, so no result with cards built means anything. Research before this plan showed three problems that would cascade into every later stage if left unseen. Three retention cards cannot reach their target gains even with churn cut to zero. A rough league put a measured-risk strategy fourth, because cards differ only about 2 to 3 times in value per BU while reports cost 48 BU a year and debt is cheap below the week-28 cliff. The corner-cutter did not lead at week 26, because Low quality buys only 11% more capacity. Stage 2 has to make these visible, precise and decidable.

### Requirements

**Calibration**

- R1. For each funnel card, the calibrator finds the lift at which a team that queues only that card at its unlock week, in Medium quality with scripted events off, gains the spec's target ARR by week 52.
- R2. A lift never exceeds its stage's cap from config. When the target cannot be reached inside the cap, the card keeps the cap value and is reported as unreachable with the gain it does achieve.
- R3. Calibrated lifts are saved as a committed data file that `config.load` reads, with the placeholder as fallback.
- R4. The calibration table states, for every card, target, solved lift, achieved gain, gain per BU and status, and says whether each Q4 card is worth building.

**Strategies and league**

- R5. Eight scripted strategies exist: measured-risk, maximum-caution, corner-cutter, no-reports, whale-chaser, late sprinter, fixed plan and do-nothing. Each sees only the team view.
- R6. Each strategy other than do-nothing and fixed plan is the measured-risk plan with one stated tactic changed, and its rules are fixed in this plan before the first run.
- R7. Strategies that diagnose incidents do so from the funnel slice data in the view, not from hidden state.
- R8. A league runs every strategy in three copies, one per incident variant, and reports mean, minimum and maximum of ARR at weeks 26 and 52, trust, and NEV.
- R9. The report prints pass or fail for each of the four balance criteria in spec section 13 and `CLAUDE.md`.

**Noise and reporting**

- R10. Telemetry noise levels are set by a measurable rule for "one quarter ambiguous, two quarters a trend", and the report shows before and after values.
- R11. A what-if table shows how the pass criteria move under named number changes, without committing any of them.
- R12. Every number this stage changes is logged in `DECISIONS.md` Part 2 with before and after values.

### Success Criteria

- `python calibrate.py` and `python bots.py` each finish in under two minutes on a laptop and give the same output on every run.
- The balance report lets the organiser decide the retention-target question and the measured-risk question without reading code.

### Scope Boundaries

**Deferred to Follow-Up Work**

- Committing any change to target gains, costs, capacity, report cost or the valuation rate. Those are the organiser's decision from the what-if table, then a re-run.
- A crowded B1 contest. With three whale-chaser copies there are fewer applicants than slots, so scarcity is not exercised here.

**Considered and not built**

- Letting retention cards add ARR directly. It is a new mechanic and `CLAUDE.md` forbids those.
- Changing starting churn or leads so retention targets fit. It breaks the do-nothing equilibrium.
- Tuning strategy rules after the first run. It would let the criteria pass by editing the test instead of the game.
- A random or accuracy-limited diagnosis for bots. It would add randomness to a deterministic balance run.

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Target gain is ARR at week 52 minus the same run with no card, scripted events off.** Events on would mix incident and alert effects into each card's solve. Bespoke cards are not solved, because their gain is the signed contract. (session-settled: user-approved — chosen over solving with events on: the solve must isolate one card's effect.)
- KTD2. **Lift caps live in config, per stage.** Retention is capped below 1 so churn cannot go negative, and rate stages get a generous cap. The engine also floors the retention multiplier at zero as a guard. The calibrator reports any card that hits its cap. (session-settled: user-approved — chosen over inflating effects or changing cards: unreachable targets are the organiser's call.)
- KTD3. **Strategies are one-change ablations of the measured-risk plan, fixed before the first run.** This makes "no single-tactic strategy within 5%" a clean comparison and removes the option of tuning strategies to pass. (session-settled: user-approved — chosen over free-form strategies: criteria 2 and 4 otherwise depend on how each bot is written.)
- KTD4. **The league runs 24 teams in one game: 8 strategies in 3 copies, with team numbers chosen to cover variants A, B and C.** Results are reported per strategy as mean with spread. (session-settled: user-approved — chosen over one team per strategy: one variant's luck must not decide the ranking.)
- KTD5. **Calibrated lifts are stored in `calibration/lifts.json`.** `config.load` reads it when present, and a load flag turns it off. Unit tests pin lifts explicitly so they do not depend on the file. (session-settled: user-approved — chosen over writing lifts into `config.py` by hand: the solver's output should be reproducible data.)
- KTD6. **Diagnosis is a deterministic rule over slice data.** A bot compares each slice's recent rates with the weeks before the alert. A hit in one segment across all slices, in all segments on one slice, or right after its own release maps to one of the four causes. This also gives early evidence for stage 5's "all nine variants resolvable from the data".
- KTD7. **Stage 2 commits changes only to lifts and noise.** Every other number change is explored in memory through config overrides and shown in the what-if table.
- KTD8. **The noise rule is a signal-to-noise ratio on weekly means.** Signal is the change in the noise-free series across the window. Noise is the standard deviation of a weekly mean. A level passes when the ratio is at most 2 over weeks 1 to 13 on the measured-risk path and at least 3 over weeks 1 to 26 on the corner-cutter path. If no level meets both, the report says so and keeps the closest.

### Strategy definitions

All strategies keep two items queued. "Value order" means utility × pitch ARR ÷ cost, highest first, using only cards with a known utility of 50 or more.

| Strategy | Rule |
| :--- | :--- |
| measured-risk | Medium quality. Buys all three segment reports at the start of each quarter. Builds in value order. Moves B2 and B3 to the front once a report shows their churn alert. Queues P1 once a quarter from Q2 and D4 in Q4. Diagnoses each incident from slice data and queues a targeted fix. Does not apply for B1 or queue C1. |
| maximum-caution | measured-risk, but High quality, and P1 and P2 every quarter from Q1. |
| corner-cutter | measured-risk, but Low quality, a patch for every incident, and never P1 or D4. |
| no-reports | measured-risk, but buys no reports and builds by pitch ARR ÷ cost. |
| whale-chaser | measured-risk, but applies for B1, queues C1 when it unlocks, and builds Whale cards before the rest. |
| late sprinter | measured-risk until week 40, then Low quality and no P1 or D4. |
| fixed plan | On day 0 sets Medium quality and queues the three reports and every Q1 card by pitch ARR ÷ cost. Never acts again. |
| do-nothing | No actions. |

### Assumptions

- A1. Rate-stage lifts above +100% are acceptable as hidden values. Research showed A4, D2, C5, B4 and C3 need roughly +96% to +213%.
- A2. A strategy that does not apply for B1 sends no decline result, so the scored decline conversation has no effect in headless runs.
- A3. "Wins" means highest mean NEV across the three copies. "Leads at week 26" means highest mean ARR at the end of week 26.
- A4. Single-tactic strategies are the five ablations plus fixed plan.

### Open Questions

- **Retention targets (deferred, organiser).** B2, B3 and C4 cannot reach ₹1.2, ₹2.4 and ₹1.7 Cr. The calibrator caps and reports them. Lowering the targets is a spec number change the organiser decides from the report.
- **Measured-risk may not win (deferred, organiser).** If criterion 1 fails, the what-if table shows which number changes would make it pass. Choosing one is the organiser's decision.

---

## Implementation Units

### U1. Lift caps and calibrated-lift loading

- **Goal:** The engine stays physical at any lift, and config can load solved lifts from data.
- **Requirements:** R2, R3.
- **Dependencies:** none.
- **Files:** modify `config.py`, `engine.py`, `tests/helpers.py`, `tests/test_funnel.py`; create `tests/test_calibrate.py`.
- **Approach:**
  1. Add per-stage lift caps and the calibration file path to `config.py`.
  2. `config.load` reads `calibration/lifts.json` when present and takes a flag to skip it.
  3. The engine floors the retention multiplier at zero.
  4. `tests/helpers.py` pins lifts to the placeholder so stage 1 tests do not move when the file appears.
- **Test scenarios:**
  - A retention lift of 1.5 gives churn of exactly zero, not a negative value.
  - With a lifts file present, `config.load` returns its values. With the flag off, it returns placeholders.
  - A lifts file naming an unknown card is rejected with a clear error.
  - All 66 stage 1 tests pass with and without the lifts file.
- **Verification:** stage 1 tests are unaffected by the presence of calibrated lifts.

### U2. Calibrator

- **Goal:** Solve every funnel card's lift and report reachability and value per BU.
- **Requirements:** R1, R2, R3, R4.
- **Dependencies:** U1.
- **Files:** create `calibrate.py`, `calibration/lifts.json` (generated); test `tests/test_calibrate.py`.
- **Approach:**
  1. A gain function runs one card queued at its unlock week, Medium quality, events and history off, and subtracts the no-card run (KTD1).
  2. Bisection between zero and the stage cap stops within a tolerance held in config. A card whose gain at the cap is below target is marked unreachable and keeps the cap.
  3. The output file holds, per card, lift, target, achieved gain, status and ship day, plus the config values the solve depended on.
  4. The printed table adds gain per BU and a Q4 verdict: a Q4 card is "worth building" when its gain per BU is at least the median of the Q1 to Q3 cards.
- **Execution note:** Check monotonicity first. If gain does not rise with lift for some card, stop and report it, because bisection would be invalid.
- **Test scenarios:**
  - For a card known to be reachable (A6), the solved lift reproduces the target within tolerance when replayed.
  - For B2, the result is marked unreachable, the lift equals the retention cap, and the achieved gain is below ₹1.2 Cr.
  - Bespoke cards and cards with no stage are skipped.
  - Running the calibrator twice gives byte-identical output.
  - Gain at lift zero for a card with no trust effect equals the debt drag alone and is not positive.
- **Verification:** the table lists every funnel card with a status, and replaying each solved lift reproduces its reported gain.

### U3. Slice-based diagnosis

- **Goal:** A bot can name an incident's cause from the view alone.
- **Requirements:** R7.
- **Dependencies:** U1.
- **Files:** modify `bots.py`; create `tests/test_strategies.py`.
- **Approach:**
  1. Compare each segment's and each slice's recent rate for the alerted stage with the two weeks before the alert, with a threshold above funnel noise.
  2. Map the pattern to a cause per KTD6. An alert that opens on the day of the team's own release, or one segment hit across all slices right after a release, reads as own release.
  3. Return no diagnosis when the pattern is unclear, so the caller can wait a day.
- **Test scenarios:**
  - For each of the nine incident variants, the rule returns the true cause within seven days of the alert, using a view with default noise.
  - With no incident open, the rule returns nothing.
  - The function receives only a team view. Passing it raw state is not required for any variant.
- **Verification:** nine of nine variants are diagnosed from view data.

### U4. Eight strategies

- **Goal:** Implement the strategy table exactly as written in this plan.
- **Requirements:** R5, R6.
- **Dependencies:** U3.
- **Files:** modify `bots.py`; test `tests/test_strategies.py`.
- **Approach:**
  1. One base policy takes a small set of switches (quality, reports, order, standing cards, incident response, bespoke, sprint week, act once).
  2. Each named strategy is the base with the switches from the strategy table. The registry maps names to configured policies.
  3. Per-team memory lives inside the policy object, not in engine state.
- **Test scenarios:**
  - measured-risk queues three reports on day 0 and never builds a card whose known utility is below 50.
  - corner-cutter sets Low quality on day 0 and answers every incident with a patch.
  - no-reports never queues a report.
  - whale-chaser applies for B1 inside weeks 14 to 17 and queues C1 in Q3.
  - late sprinter switches to Low quality in week 40 and not before.
  - fixed plan issues no action after day 0.
  - Each strategy's action log replays to the same final NEV.
- **Verification:** every strategy completes a 52-week game and its first-quarter actions match its row in the strategy table.

### U5. League and criteria report

- **Goal:** One command prints the league table and pass or fail for each criterion.
- **Requirements:** R8, R9.
- **Dependencies:** U2, U4.
- **Files:** modify `bots.py`; test `tests/test_strategies.py`.
- **Approach:**
  1. Build 24 teams per KTD4 and run them with `run_game`.
  2. Aggregate per strategy: mean, minimum and maximum of ARR at weeks 26 and 52, trust, UOD, penalty and NEV.
  3. Evaluate the four criteria per A3 and A4 and print each with the numbers behind it.
- **Test scenarios:**
  - Every strategy appears with exactly three copies covering variants A, B and C.
  - A hand-built result set where measured-risk has the top mean NEV passes criterion 1, and one where another strategy is within 5% fails criterion 4.
  - Two runs of the league give identical tables.
- **Verification:** `python bots.py` prints the table and four pass or fail lines.

### U6. Noise rule

- **Goal:** Set telemetry noise by the rule in KTD8 and show the change.
- **Requirements:** R10, R12.
- **Dependencies:** U5.
- **Files:** modify `calibrate.py`, `config.py`; test `tests/test_calibrate.py`.
- **Approach:**
  1. Take the noise-free error-rate and latency series from the measured-risk and corner-cutter reference runs.
  2. For each candidate level, compute the two ratios in KTD8 and pick the smallest level that meets both.
  3. Write the chosen levels to config and print before and after values with the ratios.
- **Test scenarios:**
  - At the chosen level, the 13-week ratio on the measured-risk path is at most 2 and the 26-week ratio on the corner-cutter path is at least 3.
  - When no level meets both, the function returns the closest level and a flag saying the rule was not met.
- **Verification:** the report shows old and new noise levels and both ratios.

### U7. Balance report and decision log

- **Goal:** Give the organiser everything needed to decide, in one document.
- **Requirements:** R4, R9, R11, R12.
- **Dependencies:** U5, U6.
- **Files:** create `docs/balance/stage2-report.md`; modify `DECISIONS.md`, `calibrate.py` or `bots.py` for the what-if runner.
- **Approach:**
  1. A what-if runner re-runs calibration and the league under named overrides and prints criteria results per row. Rows: report cost 4 → 2, valuation rate 0.25 → 0.40 and 0.60, retention targets lowered to their reachable maximum, phantom-card targets halved.
  2. The report holds the calibration table, the Q4 verdict, the league table before calibration (placeholder lifts) and after, the criteria results, the noise change, and the what-if table.
  3. `DECISIONS.md` Part 2 gets rows for lift caps, calibrated lifts, noise levels and the strategy definitions.
- **Test scenarios:**
  - Test expectation: none for the document itself. The what-if runner is covered by one test that an override row changes the league result and leaves `config.py` values untouched.
- **Verification:** the report states each criterion's result and names, for each failing one, which what-if rows make it pass.

---

## Verification Contract

| Check | Command | Passes when |
| :--- | :--- | :--- |
| All tests | `uv run python -m unittest discover -s tests` | stage 1 and stage 2 tests pass |
| Calibration | `uv run python calibrate.py` | prints the card table, writes `calibration/lifts.json`, identical on re-run |
| League | `uv run python bots.py` | prints the 8-strategy table and four criteria lines |
| Standard library only | `uv run python -c "import config, engine, bots, calibrate"` | imports succeed with no dependencies in `pyproject.toml` |

## Definition of Done

- Every funnel card has a solved lift or an explicit unreachable status in `calibration/lifts.json`.
- The league table and the four criteria results are printed and recorded in `docs/balance/stage2-report.md`.
- The report answers whether the Q4 cards are worth building.
- No game number other than lifts and noise differs from the committed stage 1 values.
- `DECISIONS.md` Part 2 has before and after values for lifts and noise.
- No scratch or abandoned code remains.
- If any criterion fails, the run ends with the trade-off stated and the what-if table attached, not with a tuned number.

---

## Risks

- **Criterion 1 is likely to fail on the first run.** Research put measured-risk fourth. The plan's answer is a clear report, not a fix.
- **Diagnosis thresholds versus noise.** If U6 raises funnel noise, U3's rule may need a longer window. The funnel noise level is not part of the KTD8 rule, so it stays unless a variant stops being diagnosable.
- **Calibration depends on every number it reads.** Any later change to capacity, quality shares or funnel rates invalidates the lifts. The output file records the inputs it used so a stale file can be detected.

## Sources

- `fix_forward_build_spec_v3.md` sections 5, 6, 13 and 16.
- `CLAUDE.md` "Balance" and "Defaults".
- `DECISIONS.md` section 1.4 (v2 balance shape) and Part 2.
- `engine.py` `stage_rates`, `team_view` and `bots.py` `run_game`.
- Pre-plan research on 16 to 17 November 2026: solved lifts per card and a rough 24-team league.
