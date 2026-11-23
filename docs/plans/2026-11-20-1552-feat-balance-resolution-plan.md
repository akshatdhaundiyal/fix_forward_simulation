---
title: Fix Forward Balance Resolution - Plan
type: feat
date: 2026-11-20
topic: balance-resolution
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Fix Forward Balance Resolution - Plan

## Goal Capsule

- **Objective:** On 4 December the strategy the spec calls wise wins, the corner-cutter leads early and loses late, and a team that buys a report can trust what it says.
- **Product authority:** `fix_forward_build_spec_v3.md` section 13 defines the balance criteria. `CLAUDE.md` "Balance" defines how numbers may change. This plan decides which numbers and which one structural fix are in play.
- **Open blockers:** none for planning. The unreachable retention targets and the capacity split are open choices inside the sweep (see Outstanding Questions).
- **Not active scope:** new mechanics, changes to the debt formulas, the server and screens (stages 3 to 7), and any redesign of the retention cards.

---

## Product Contract

### Summary

A bounded balance pass in two parts. One structural fix makes report utility honest. A number sweep from 24 November to 1 December, checked against the scripted league and the rehearsal, picks values for the few numbers that decide the four criteria, then freezes them.

### Problem Frame

After stage 2 calibration, only the fixed-plan criterion passes. A bot that drops to Low quality in the last quarter beats the measured-risk bot (NEV 169 against 148), and a bot that skips reports ties it. The corner-cutter trails at week 26 by 0.2 ARR. The cause is cost structure: debt is priced at ₹0.25 Cr per point at the end and does little before the week-28 check, reports roughly break even against their 4 BU cost, and Low quality buys only 11% more capacity than Medium.

A second problem is about trust. A report quotes a card's utility from its target gain. Three retention cards (B2, B3, C4) cannot deliver their targets, so a team paying for a report is told B2 is worth 60 when it delivers about 37. The game's premise is that reports are the honest signal.

A sweep run now showed that the ongoing debt drag is the wrong lever (even four times stronger it barely moves the late sprinter) and that the end-of-game debt cost is the right one: at about ₹1.00 Cr per point the late sprinter falls behind measured-risk and the corner-cutter collapses, though the no-reports bot then edges ahead by 0.4 NEV.

### Key Decisions

- **Report utility comes from the calibrated gain, not the target.** Reports then stay honest under any later number change, and the debrief reveal stays consistent. Governs R1, R2. (session-settled: user-approved — chosen over lowering the three targets so they match: it holds for every future change, not just this one.)
- **Debt formulas stay as the spec has them.** The sweep showed the ongoing drag barely moves the result. Governs R5. (session-settled: user-approved — chosen over strengthening the drag: it did not change which strategy wins.)
- **Build the server and screens first and sweep numbers during the rehearsal window.** The 24 to 26 November trial shows real play, which bots only approximate. Governs R4, R8. (session-settled: user-approved — chosen over balancing before building: stages 3 to 7 are the event's critical path and balance is config only.)
- **Criteria A to C stay as gates and D follows A.** D fails today only because a single-tactic bot wins. Governs R6.
- **The measured-risk bot is redefined once to harden only when it holds debt, then bot definitions freeze.** It currently queues the hardening card every quarter at zero debt, which wastes about 15 BU a quarter. Governs R3.
- **Anything unselected in the walk-through takes the default.** Report cost, trap-card values, the capacity split and the retention targets go to the sweep, not to an up-front decision.

### Requirements

**Honest reports**

- R1. A report's utility score for a card is round(100 × the card's calibrated gain ÷ its pitch ARR), where calibrated gain is the gain the card delivers at its solved lift, capped lift included.
- R2. For a card whose target is unreachable, the report shows the lower, deliverable score, and the calibration record carries the achieved gain alongside the target.

**Scripted strategies**

- R3. The measured-risk bot queues the hardening card only when its team holds debt, and no bot definition changes after that one redefinition.

**Sweep**

- R4. A sweep runner varies named numbers in memory, re-runs calibration where card values change and re-runs the 24-team league, and prints the four criteria per row with before and after values.
- R5. The sweep covers the end-of-game debt cost, report cost, the three pitch-trap card values (A1, B4, C3), the Low, Medium and High capacity split, and the three unreachable retention targets. It changes no formula.
- R6. A configuration passes when measured-risk has the highest mean NEV, the corner-cutter has the highest mean ARR at week 26 and a lower NEV than measured-risk, the fixed plan finishes in the bottom half, and no single-tactic bot is within 5% of the winner.
- R7. Every committed number change appears in `DECISIONS.md` Part 2 with its before and after league table.

**Freeze and fallback**

- R8. Numbers freeze on 1 December. Any change after the rehearsal goes through the sweep runner and the same logging.
- R9. If no configuration passes all four criteria by the freeze, the best-scoring configuration ships and the failing criteria and the trade-off go to the organiser as a decision, not as a tuned number.
- R10. When rehearsal behaviour disagrees with the league, the rehearsal evidence decides between configurations that pass or fail equally.

### Success Criteria

- A report's utility for B2, B3 and C4 matches what each card delivers.
- One command prints the league, the four criteria, and the before and after values for any proposed change.
- The configuration at the freeze either passes all four criteria or comes with a short written trade-off for the organiser.

### Scope Boundaries

**Deferred for later**

- Redesigning the retention cards so their targets are reachable. That is a new mechanic and `DECISIONS.md` section 1.3 rules those out.
- A larger, human-played test than the three-team trial and dress rehearsal.

**Not in this work**

- Changes to the debt drag formulas or the week-28 rule.
- A second redefinition of any scripted strategy after R3.
- The server, clock, screens and snapshots.

### Dependencies / Assumptions

- The stage 2 league, calibration and report tools exist and run in under a minute.
- A5. Printed briefing materials listing the quality capacity split are updated before the freeze if the split changes.
- A6. The debrief's hidden-gain reveal for Copilot, Partner API and AI Summaries uses whatever values the freeze fixes.
- A7. Rehearsal teams give a rough picture of human play, not a statistically useful one.

### Outstanding Questions

**Deferred to Planning**

- Which values the sweep tries for each named number, and how many rows are worth running in the available time.
- Whether the capacity split needs to move, or whether raising the end-of-game debt cost is enough for criterion B.
- Whether lowering the three retention targets is needed at all once R1 makes reports honest.

### Sources / Research

- `docs/balance/stage2-report.md` for the league, calibration table and what-if rows.
- `DECISIONS.md` Part 2 for the stage 2 number changes and the debt-cost sweep (end cost 0.60 and 1.00, drag ×2 and ×4).
- `fix_forward_build_spec_v3.md` section 13 for the pass criteria and section 5 for the card values.
