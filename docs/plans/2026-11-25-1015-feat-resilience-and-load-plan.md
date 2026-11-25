---
title: Fix Forward Resilience and Load - Plan
type: feat
date: 2026-11-25
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# Fix Forward Resilience and Load - Plan

## Goal Capsule

- **Objective:** On 4 December the game survives its server dying, its network dropping, or a full room of laptops polling it, and the operator can get it back within five minutes with no team's state lost.
- **Means:** A real-process load test and failure drill that prove the bar, plus the two recovery paths the spec requires and nothing yet builds: a spare laptop that follows the primary's log, and a start from a bare snapshot (KTD1, KTD2, KTD3, KTD4).
- **Authority:** `fix_forward_build_spec_v3.md` sections 10.3, 11, 12 (day 7), 13 and 14 win on rules. `CLAUDE.md` hard constraints win on how: Python standard library only at runtime, no state lost, every number in config, relative URLs, and the committed `static/` build. This plan wins on how the work is built.
- **Stop conditions:** Stop and report if any drill loses or resurrects an acknowledged action, if a recovery takes more than five minutes, if 20 polling clients push the p99 latency past the bar or make the clock tick late, or if the load test needs a mechanic change to pass. Do not redesign mechanics on your own.
- **Execution profile:** Two PRs (see Implementation Units). Python standard library only at runtime.
- **Out of this stage:** the balance sweep (rehearsal-week tuning for the organiser using the existing `bots.py` table, with no number changed silently), printed incident packets, router configuration, and the choice of hosting.

---

## Product Contract

### Summary

Prove and, where missing, build the resilience the spec makes mandatory. A load test runs 20 simulated clients against a real server process for a full game. A failure drill kills the real server at three points and times each recovery against the five-minute bar. A spare laptop follows the primary's log so it can take over, and a server can start from a bare snapshot when nothing else survives. The full-game test also drives bookings and decline entries, and a reveal-gated debrief feed lets the projector show the spec's hidden-debt curves.

### Problem Frame

Recovery from a kill is tested in-process and with one killed subprocess, but nothing times it against a full-length game log or runs many clients at once. The spec requires a spare laptop that "receives the snapshot every 30 seconds and can take over the same address", yet no code copies anything off the primary. The state directory is the only source a restart reads, so a dead primary laptop is currently the end of the game. A snapshot alone cannot start the server, because a start rebuilds from the log. The full-game test predates the stakeholder system, so bookings and decline entries have never run over HTTP. The debrief's central moment, "it was on your dashboard, and your CTO told you", has no data behind it after the reveal.

### Key Decisions

- **The spare follows the primary's event log, byte for byte, over HTTP.** Governs R3. (session-settled: user-approved — chosen over copying snapshots every 30 seconds: a snapshot lacks history and the log is the exact record every restart already trusts.)
- **The balance sweep is not in this plan.** Governs R9. (session-settled: user-approved — chosen over a scripted sweep unit: tuning during rehearsal week is the organiser's call and the existing bots table already supports it.)
- **Debrief charts are in scope but last, and may be cut.** Governs R8. (session-settled: user-approved — chosen over leaving them out: spec section 14 cannot run without the curves, and a cut costs only the debrief.)

### Requirements

**Proving the bar**

- R1. A load test runs 20 simulated clients polling every 3 seconds against a real server process for a full game, with scripted teams acting, and reports request errors, p50 and p99 latency, and how late the clock's ticks ran.
- R2. A failure drill kills the real server process at three points, restarts it, and shows every team's state and every acknowledged action intact, with the restart time recorded against the five-minute bar and the spec's one-minute rebuild.
- R3. A drill kills the primary while a spare follows it, starts the game on the spare from the spare's own copy, and shows no acknowledged action lost beyond the replication interval.

**Recovery paths**

- R4. A spare laptop can follow a running primary: it copies the log, the team registry and the newest snapshot every few seconds, and the operator promotes it by stopping the follower and starting the server on the copied directory.
- R5. A server can start from a bare snapshot and the team registry when the log is gone, resume paused at the snapshot's day with every team's state and the booking board intact, and replay forward with digests checked.
- R6. A written runbook tells the operator what to run for a server kill, a spare takeover, a bare-snapshot start and a router pull, and records the address-takeover step as the organiser's.

**Verification and debrief**

- R7. The full-game test drives bookings and decline entries over HTTP, and its restart from the log reproduces the booking board and decline entries as well as every team's state.
- R8. After the reveal, the projector can show the spec's debrief: hidden-debt curves for the week-26 ARR leader, the final winner and the biggest collapse, each with its error rate and CTO band over time, and the hidden target gains for AI Copilot, Partner marketplace API and AI meeting summaries. Before the reveal the feed refuses.
- R9. No game number or mechanic changes in this stage.

### Success Criteria

- The load test and the drill pass on a 16-team full game on the laptop the event will use, and their printed tables go in the runbook as the measured baseline.
- A spare started from replicated files matches the primary's digests at the replicated point.
- A bare-snapshot start continues a game for 28 more days with digests checked and no refusal.

### Scope Boundaries

**Deferred to Follow-Up Work**

- Taking over the primary's network address. It depends on the router, which the organiser sets up after the Wi-Fi test.
- The balance sweep and any retuning during 24 November to 1 December.

**Considered and not built**

- Automatic failover or a standby that serves traffic. The operator promotes the spare by hand, because a wrong automatic switch during a live game costs more than a two-minute manual one.
- Encrypting or authenticating anything beyond the admin password header the existing routes use.
- A paper version of the full game (`CLAUDE.md` forbids it).

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Replication is a pull of complete log lines by byte offset.** A new admin route returns the log from an offset up to the last full line, so a torn tail is never copied and the copy is byte-identical to what `store.read_events` trusts. The follower is a standalone script (`replicate.py`) that never opens a `Game`. It writes the same file names into its own state directory, and promotion is the ordinary `server.py --state-dir` start, which already comes back paused. The follower also copies `teams.json` and the newest snapshot. (session-settled: user-approved — chosen over snapshot copies: see Key Decisions.) Cited by U2.
- KTD2. **A bare-snapshot start writes a new log whose second line carries the snapshot.** `server.py --from-snapshot PATH` creates a state directory holding `init` and one `baseline` line (day, speed, revealed, board, every team's state without history), and `_replay` replaces the fresh states with the baseline when it meets that line. The `baseline` line keeps the log the single recovery source and rewinds and later restarts keep working. History before the baseline day is gone, which the engine allows because the state digest excludes history, so team charts start at the baseline day. `teams.json` must sit beside the snapshot, since a snapshot holds no team codes. Cited by U1.
- KTD3. **The load test runs a real server process on an accelerated clock and measures what the server does, not what the client sees alone.** Clients are threads using the stdlib client in `httpgame.py` and poll the clock and the team view with the ETag exactly as the console does, plus a window view at the console's slower rate. An accelerated clock makes every poll more likely to return a changed view than the event's 13 seconds per day does, so it is the harder case. The thresholds are constants at the top of the test module, not game numbers. A full-length run at 13 seconds per day is available by flag for an overnight check. Cited by U4.
- KTD4. **The failure drill is a script around real subprocesses, run from the same code the tests use.** `drill.py` starts the server, plays bots over HTTP, kills it hard at three points (mid-quarter, inside a checkpoint pause, right after an action burst), restarts it, and compares each team's view JSON, the booking board and the log's last acknowledged sequence before and after. The spare scenario adds `replicate.py` between the kill and the restart. Router pull is a network event with no server-side effect, so it is a runbook check on the console's connection banner, not code. Cited by U3.
- KTD5. **The replication interval defaults to 5 seconds, tighter than the spec's 30.** The route is cheap (a byte range read), and a shorter interval shrinks the actions at risk on a takeover from up to 30 seconds to up to 5. The value is a config key marked server-only. Cited by U2.
- KTD6. **The debrief feed is built on the server from history and refuses until the reveal.** `GET /api/debrief` returns 403 before the reveal. After it, the route picks the three teams by rule (week-26 ARR leader, final winner by valuation, largest peak-to-final ARR drop), and returns for each a weekly series of debt, error rate and CTO band, plus the three cards' target gains from the calibrated config. Choosing teams on the server keeps hidden series off the wire for every other team. Cited by U6.

### Assumptions

- The replay cost of a full game's log is a few seconds, not minutes. This is unmeasured and U3's drill records it.
- The window view and the slice view dominate request cost. If the load test fails, a targeted fix to a view cache is allowed but no mechanic change.
- Windows is the event laptop's likely OS, so the drill kills with the process object's `kill()` as `tests/test_kill_restart.py` does.

### Risks & Dependencies

| Risk | Mitigation |
| :--- | :--- |
| The single global game lock makes 20 polling clients delay the clock tick | The load test measures tick lateness directly. A failure is reported with the numbers before any fix. |
| A bare-snapshot start loses history, so the debrief curves and team charts have a hole | Documented in the runbook as the last resort. The log-following spare keeps full history, which is why it is the primary recovery. |
| A torn or partial log copy corrupts the spare | KTD1 copies only complete lines, and `store.EventLog.open` already truncates a torn tail on start. |
| The follower sees a rewind marker or a `--new-game` rename on the primary | The follower tracks the primary's boot id and log size. If the log shrinks, it stops with a message instead of overwriting. |

---

## Implementation Units

### PR1: Recovery paths, drill and load test

Waits on: none. The recovery paths are not needed by the load test, but the drill uses them.

#### U1. Start from a bare snapshot

- **Goal:** A server can start from one snapshot file and a team registry and carry on the game.
- **Requirements:** R5. Governed by KTD2.
- **Dependencies:** none.
- **Files:** `game.py`, `server.py`, `store.py`, `tests/test_recovery.py`, `tests/test_baseline_start.py`.
- **Approach:**
  1. Add `Game.baseline_from(snapshot, state_dir)` style creation used by `server.py --from-snapshot PATH`: refuse when the directory already holds a log, when `teams.json` is absent beside the snapshot, or when the snapshot's team list does not match the registry.
  2. Write `init` then `baseline`; teach `_replay` to accept a `baseline` as the second line, set states, speed, revealed and board from it, and reject a `baseline` anywhere else.
  3. Verify the snapshot's own digest before writing anything. Come back paused with reason `restart`, as every start does.
- **Patterns to follow:** `Game._replay` and `Game.restore`'s digest check, `store.SnapshotStore.read`.
- **Test scenarios:**
  - A snapshot taken at day 40 starts a new directory, resumes paused at day 40, and 28 further days replay with digests matching a game that never stopped.
  - A snapshot with a changed digest, a missing `teams.json`, or a mismatched team list is refused and nothing is written.
  - The booking board and a decline entry in the snapshot survive the start and a second restart from the new log.
  - A restore (rewind) after a baseline start works, and a `baseline` line anywhere but second stops startup with a clear message.
  - Team views after the start carry a history window that begins at the baseline day with no error.
- **Verification:** the new tests pass with the existing recovery and kill tests.

#### U2. Spare laptop follows the primary

- **Goal:** A second laptop holds a current copy of the game that can be started in place of the primary.
- **Requirements:** R4. Governed by KTD1, KTD5.
- **Dependencies:** none.
- **Files:** `config.py`, `game.py`, `server.py`, `replicate.py`, `tests/test_replicate.py`.
- **Approach:**
  1. Add admin routes `GET /api/admin/log?offset=N` (bytes from the offset to the last full line, with the log size and boot id in headers), `GET /api/admin/registry`, and `GET /api/admin/snapshot/latest`. All sit behind the admin password header.
  2. Add `replicate.py`: `--primary URL --admin-password PW --state-dir DIR`, polling at `REPLICATE_INTERVAL_SECONDS`, appending bytes to its own log with fsync, writing `teams.json` once, and refreshing the latest snapshot. It stops with a message if the primary's log shrinks or its boot id changes with a smaller log.
  3. Add the interval to config as a server-only key. Print one status line per pull so the operator sees it working.
- **Patterns to follow:** `store.read_events`, the admin routes in `Handler._admin`, `httpgame.Client`.
- **Test scenarios:**
  - After a pull the spare's log equals the primary's byte for byte, including after more actions arrive between pulls.
  - A log with a torn final line is copied only up to the last newline, and the next pull completes it once the primary finishes the write.
  - The spare started with `server.py --state-dir` on the copied directory reproduces every team's digest and the board.
  - A wrong admin password gets the same 401 on all three routes, and the team code or stakeholder password does not open them.
  - A shrunken primary log stops the follower without touching the spare's files.
- **Verification:** the new tests pass and no response from the new routes is reachable without the admin password.

#### U3. Failure drill and runbook

- **Goal:** The recovery bar is measured with real processes, and the operator has a runbook that matches what was measured.
- **Requirements:** R2, R3, R6. Governed by KTD4.
- **Dependencies:** U1, U2.
- **Files:** `drill.py`, `tests/test_drill.py`, `README.md`.
- **Approach:**
  1. Write `drill.py` with scenarios `kill`, `spare` and `snapshot`. Each starts a real server on a free port with a short seconds-per-day, plays several scripted teams over HTTP (reusing `httpgame.play`), then injects the failure.
  2. Record wall time from the kill to the first successful `/api/clock`, and compare every team's view, the booking board and the last acknowledged log sequence before and after. Print a results table.
  3. The `kill` scenario runs at mid-quarter, inside a checkpoint pause and just after an action burst. The `spare` scenario kills the primary, then starts the server on the follower's directory. The `snapshot` scenario deletes the log, then starts from the newest snapshot.
  4. Write a short operator runbook in `README.md`: the commands for each recovery, the router-pull check, the address-takeover step marked as the organiser's, and the measured table.
- **Patterns to follow:** `tests/test_kill_restart.py` for the process helper, `httpgame.py` for play.
- **Test scenarios:**
  - A hard kill at each of the three points loses no acknowledged action and no game day, and each team's view matches before and after.
  - The restart time for a full-length log is recorded and is under the five-minute bar; if it is over one minute, the table says so.
  - A spare started from the follower's copy matches the primary up to the last replicated line, and the actions lost are at most those of one interval.
  - A bare-snapshot start continues for 28 days and refuses nothing.
- **Verification:** `drill.py` exits non-zero on any mismatch, and its table is pasted into the runbook.

#### U4. Load test with 20 clients

- **Goal:** Show the server holds 20 polling consoles for a full game without errors or a late clock.
- **Requirements:** R1. Governed by KTD3.
- **Dependencies:** none.
- **Files:** `loadtest.py`, `tests/test_loadtest.py`, `httpgame.py`.
- **Approach:**
  1. Write `loadtest.py` that starts or attaches to a server, creates 20 team clients in threads, and runs each as a console would: clock and view with ETag every 3 seconds with a small seeded offset, the funnel and operations window views every fifth poll, and scripted strategy actions through the same client.
  2. Sample the server's own tick times (from the clock block's day changes) to compute lateness against the configured seconds per day, and record per-request latency, status counts and 304 share.
  3. Print the table: requests, errors, p50, p99, 304 share, max tick lateness. Constants at the top of the module set the pass bars (no errors, p99 under one second, tick lateness under ten percent) and are recorded in `DECISIONS.md`.
  4. Add a `--full-length` flag for a 13-second-per-day run, and verify the final state replays to the same digests.
- **Patterns to follow:** `httpgame.play` and `httpgame.Client`.
- **Test scenarios:**
  - A short run (three clients, a few game days) completes with zero errors, and the table's counts are consistent with the number of polls.
  - A server that returns a 500 or stalls for longer than the request timeout makes the run fail and name the status.
  - Tick lateness is computed from the clock and flags a deliberately delayed tick.
  - The replay after the run matches the live digests.
- **Verification:** the unit test passes quickly, and a 16-team run on the event laptop meets the bars. If it fails, the numbers are reported before any fix.

### PR2: Test coverage and debrief

Waits on: PR1 merged, for the shared harness only. U5 and U6 do not depend on each other.

#### U5. Full-game test drives bookings and decline entries

- **Goal:** The full-game test exercises the stakeholder system and proves it survives a restart.
- **Requirements:** R7.
- **Dependencies:** none.
- **Files:** `httpgame.py`, `tests/test_full_game_http.py`.
- **Approach:**
  1. Extend the harness so each scripted team books a stakeholder in each quarter, and a stakeholder client marks meetings done and enters one decline result per team that did not apply for the bespoke contract.
  2. Compare the booking board and the declined set before and after the restart-from-log check.
- **Patterns to follow:** the existing full-game test and `tests/test_stakeholders.py`.
- **Test scenarios:**
  - After a full game the board holds bookings from all four quarters, none over five per stakeholder per quarter, and the restart reproduces it exactly.
  - Every decline entry is accepted once and a repeat is refused over HTTP.
  - No stakeholder or booking response in the run carries a hidden field name.
- **Verification:** the full-game test passes in about the same time it takes today.

#### U6. Debrief feed and projector view

- **Goal:** After the reveal the MC can show the spec's debrief curves and hidden gains.
- **Requirements:** R8. Governed by KTD6.
- **Dependencies:** none (cuttable).
- **Files:** `game.py`, `server.py`, `tests/test_debrief.py`, `web/src/lib/debrief.ts`, `web/src/lib/debrief.test.ts`, `web/src/components/projector/debrief.tsx`, `web/src/pages/projector.tsx`, `static/` (rebuilt).
- **Approach:**
  1. Add `Game.debrief()` and `GET /api/debrief`: 403 before the reveal; after it, pick the three teams by KTD6, and return weekly debt, error rate and CTO band for each, plus the three cards' target gains.
  2. Add a debrief mode to the projector, entered with a key press or a URL hash, with a debt-curve chart over the three teams, an error-rate and band overlay per team, and the hidden gains table. The ranking view stays the default.
  3. Rebuild `static/` and commit it.
- **Patterns to follow:** `Game.projector`, `web/src/components/projector/*`, the operations chart in `web/src/components/ops-chart.tsx`.
- **Test scenarios:**
  - The route refuses before the reveal and answers after it, and no field name from `HIDDEN_FIELD_NAMES` appears on any other route as a result.
  - The three teams are chosen by the rule, including a tie broken by team number, and the same team can fill two roles without duplicating a series.
  - The band series matches the band the CTO screen showed at each week's end for a scripted team.
  - After a bare-snapshot start the route still answers, with series starting at the baseline day.
  - The projector shows the ranking by default and the debrief only on the key or hash.
- **Verification:** the debrief renders from a finished scripted game in a browser, with the three curves and the gains table.

---

## Verification Contract

| Check | Command or procedure | Applies to |
| :--- | :--- | :--- |
| Python suite | `python -m unittest discover -s tests` | all units |
| Full-game test | `python -m unittest discover -s tests -p "test_full_game_http.py"` | U5 |
| Load test | `python loadtest.py --teams 16 --clients 20` on the event laptop | U4 |
| Failure drill | `python drill.py kill`, `python drill.py spare`, `python drill.py snapshot` | U1, U2, U3 |
| Console and screens | `npm --prefix web run typecheck`, `npm --prefix web run test`, `npm --prefix web run build` | U6 |
| No hidden fields | the existing endpoint tests plus the new route tests | R8 |

## Definition of Done

- U1 to U5 merged with their verification met, U6 merged or cut and the cut recorded in `DECISIONS.md`.
- The load test and the drill pass on the event laptop, and their tables are in the runbook.
- The runbook lists the commands for each recovery and marks the address takeover as the organiser's step.
- New config keys, the load test bars and the 5-second replication interval are recorded in `DECISIONS.md` Part 2.
- No game number or mechanic changed. Dead-end experiment code is removed.
