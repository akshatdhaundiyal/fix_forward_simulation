# Fix Forward: build handoff

You are building the server and browser consoles for **Fix Forward**, a live product-management simulation for a student PM club event on **Friday 4 December 2026**. 15+ teams, one laptop each, 2.5 hours. The build must be finished by **Monday 23 November**.

## Source of truth

* `fix_forward_build_spec_v3.md` is the game design. Read all of it before writing code.
* `DECISIONS.md` records why the design is the way it is: every accepted decision, every rejected idea, and the reasons. Read Part 1 before proposing any change to a mechanic. Append your own build decisions to Part 2.
* This file covers how to build it, what the spec leaves open, and the rules for changing anything.
* `reference/v2_balance_sim.py` is the balance script from the earlier round-based design. The engine in it is obsolete. Reuse only the pattern: scripted strategies run headless, results printed as a table.

If this file and the spec disagree on a game rule, the spec wins. If the spec is silent, use the defaults below and record the choice in `DECISIONS.md`.

## Hard constraints

1. **Python 3.10+, standard library only.** No pip installs, no Node, no build step. It must start with `python3 server.py` on a laptop with no internet.
2. **Front end is plain HTML, CSS and JavaScript**, one file per screen, no CDN links, no frameworks. Charts are drawn with inline SVG or canvas.
3. **Hidden values never reach a team's browser.** True lifts, target gains, risk points, UOD, NEV, incident causes and other teams' private state are server-only. Write a test that fetches every team endpoint and fails if any hidden field name appears.
4. **The engine is deterministic.** State is a pure function of (config, seed, action log). Display noise is seeded per team and never feeds back into state. Write a test that replays an action log and gets identical state.
5. **Every game number lives in one config module.** No magic numbers in engine or server code.
6. **Time lives only on the server.** Consoles display the server's clock and never keep their own.
7. **Hosting is undecided** (own router on a local network, or a cloud VM). Bind to `0.0.0.0`, make the port configurable, and use relative URLs only.

## Suggested layout

```
config.py        all numbers, cards, incidents, script cards
engine.py        pure simulation: step(state, day) and apply(state, action)
bots.py          scripted strategies + headless runner + results table
calibrate.py     solves feature lifts to hit target gains
server.py        HTTP server, clock loop, auth, snapshots, action log
static/team.html
static/projector.html
static/stakeholder.html
static/admin.html
tests/
DECISIONS.md     design history (Part 1, provided) and your build decisions (Part 2)
```

## Build order

Follow Section 12 of the spec. Do not start a day's work until the previous day's "done when" is met. Report against it at the end of each stage.

1. **Engine and headless mode.** A do-nothing team stays at ₹25 Cr for 52 weeks.
2. **Calibration and balance.** Run the scripted strategies and print the table. See "Balance" below.
3. **Server, clock, checkpoints, action log, snapshots, admin pause.** Killing and restarting the process loses no state.
4. **Team console:** overview, roadmap queue, quality mode, funnel explorer.
5. **Incidents, slices, targeted fix, rollback, patch, operations telemetry.**
6. **Peak season, projector, stakeholder screen, whale contracts, reports.**
7. **Load test** with 20 simulated clients polling every 3 seconds for a full game, and a **failure drill**.

If time runs short, cut in the order given in Section 12 of the spec. Never cut snapshots, the action log, or the admin pause.

## Defaults for what the spec leaves open

Use these as starting values, put them in `config.py`, and log them in `DECISIONS.md`.

| Topic | Default |
| :--- | :--- |
| Calendar | 7 days per week, 364 days total. One step per simulated day |
| Feature lifts | For each card, bisect the lift so that a team which queues only that card at its unlock week, in Medium quality, gains the spec's target ARR by week 52 |
| Utility score shown in a segment report | round(100 × target gain ÷ pitch ARR). Example: AI Copilot shows 15 |
| Trust effects of a card | Applied on the day it ships; removed on rollback |
| Targeted fix and patch | Inserted at the front of the queue. The item in progress is paused and keeps its progress |
| Incident 1 damage | Weekly churn ×2 in the affected slice |
| Incident 2 damage | Activation −40% in the affected slice (from the spec) |
| Incident 3 damage | Paid conversion −50% in the affected slice |
| p99 latency | 300 ms + 6 ms × UOD, +200 ms while a platform-slowing incident is open, ×1.5 during weeks 28–30, plus noise |
| Support tickets per segment per week | baseline × (1 + 0.03 × (60 − trust)), plus a bump while an incident affects the segment, plus noise |
| Noise | Sized so one quarter is ambiguous and two quarters show a trend. Tune in calibration |
| Whale metrics on charts | Shown as ARR, not account counts |
| Platform hardening and customer success program | Each at most once per quarter |
| Auth | Six-character random team code; admin and stakeholder screens behind separate passwords set at startup |
| Polling | Team console every 3 seconds; projector every 2 seconds |
| Snapshot | Full state to disk every 5 seconds, written atomically; action log appended on every action |

## Balance

The spec's numbers are **untested starting values**. The engine changed from the version that was tested.

* Write at least these scripted strategies: measured-risk, maximum-caution, corner-cutter (Low quality, always patches), no-reports, whale-chaser, late sprinter (drops quality in Q4), fixed plan (queues everything in week 1 and never acts again), and do-nothing.
* Pass criteria are in Section 13 of the spec. The key ones: a measured-risk strategy wins; the corner-cutter leads on ARR at week 26 and loses by week 52; the fixed plan finishes in the bottom half; no single-tactic strategy is within 5% of the winner.
* Known concern: a weekly funnel rewards early shipping heavily, so Q4 cards may be too weak to be worth building. Check it and report it.
* **If you change any game number, re-run the strategies and show the before and after table.** Never tune a number silently.
* When the criteria cannot all be met, stop and report the trade-off; do not redesign mechanics on your own.

## Do not

The reasons for each of these are in `DECISIONS.md`, Section 1.3. If you think one should be revisited, say so and wait for the organiser; do not act on it.

* Add mechanics that are not in the spec (overtime, hiring, cash, a shared market between teams, a crowding discount, a "deflect" response). These were considered and rejected.
* Add randomness to state or scoring.
* Let any team affect the clock.
* Build a paper or spreadsheet fallback. Resilience comes from snapshots, the action log, and a spare machine.
* Use external services, analytics, fonts or scripts.

## Admin screen must have

Pause, resume, speed control, countdown override, trigger or cancel an incident for one team or all, edit a team's state with a logged reason, restore from snapshot, and a final reveal that unlocks UOD and NEV on the projector.

## Open items owned by the organiser, not by you

* Hosting choice, decided after a Wi-Fi test at the venue.
* Who operates the server on the day.
* Wording of the stakeholder script cards and incident alerts (the spec's text is a first draft).
* Rehearsal dates: live quarter with three teams on 24–26 November, dress rehearsal on 28–29 November, number freeze on 1 December.
