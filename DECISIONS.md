# Fix Forward: decision log

Why the design is the way it is. Read this before proposing a change to any mechanic. If an idea appears under "Rejected", do not reintroduce it without new evidence and the organiser's agreement.

Part 1 records the design decisions made before the build. Part 2 is for decisions made during the build; append to it.

---

## Part 1: Design decisions (to 16 November 2026)

### 1.1 History in brief

| Version | What it was | Why it was replaced |
| :--- | :--- | :--- |
| v1 "The Executive Product Crucible" | Four rounds, five decision levers, mechanics borrowed from four academic simulations, scored in a Google Sheet | Formulas rewarded the opposite of the intended lessons; too many levers; schedule did not fit 150 minutes |
| v2 | Four rounds, three decisions plus a crisis call, Google Forms into a Sheet, full initiative menu, balance-tested with scripted strategies | Organiser wanted laptops, live data, root cause analysis and visible consequences |
| v3 "Fix Forward" | Continuous clock with checkpoints, a simulated funnel per team, incidents diagnosed from live data, one server | Current design |

### 1.2 Accepted decisions and their reasons

| # | Decision | Reason |
| :--- | :--- | :--- |
| 1 | Revenue is deterministic: a feature's value depends on a hidden true effect, revealed by a paid report | In v1, blind builds paid about 0.90 × base regardless of utility while surveyed builds paid base × U/100 × 1.25. A phantom-demand feature (U = 15) paid 0.90 blind and 0.19 surveyed, so the survey punished its buyers. Random draws also let luck decide a short game |
| 2 | Reports are sold per segment at 4 BU | With 15 teams in one room a single report leaks to everyone. Partial reports leak partially |
| 3 | Trust multiple is linear: 2.0 + 0.03 × average trust | v1 used steps (1.8× / 3.5× / 5.0×). One trust point at the 79/80 boundary was worth about ₹45 Cr and decided the winner alone |
| 4 | Bespoke contracts take capacity for the rest of the game and their ARR is valued at a flat 2.0× | In a short game a "permanent" 10 BU tax was only 20 BU. The valuation discount makes the cost outlast the game |
| 5 | One hidden debt counter (UOD), never shown as a number | v1 had a visible fragility index and a hidden debt pool doing the same job |
| 6 | The debt threshold of 40 is a deliberate cliff; the rework owed is measured from 30 | A team just over the line loses at least 11 BU, ₹3 Cr and 35 Whale trust. The cliff is the event's shared climax |
| 7 | Over-caution should lose to measured risk | In the v2 test, maximum quality plus a deep fix every time finished fourth at 84%. The intended lesson is judgment, not "always be careful" |
| 8 | Three live stakeholders (VP Sales, Whale Alpha's account lead, CTO) as free but biased information | Stakeholder pressure was the one PM skill the game did not test. Information-only keeps scoring free of judgment |
| 9 | One meeting per team per stakeholder slot; 5 slots per stakeholder per quarter | 3-minute meetings in a quarter give about 15 in total. Choosing whom to meet becomes a decision |
| 10 | Exactly one scored conversation: declining the whale, marked on a three-item checklist | A checklist keeps 15 teams comparable. Maximum swing is about ₹3 Cr on roughly ₹160 Cr, enough to matter without deciding the winner |
| 11 | For the decline conversation only, all three actors play the whale lead | One actor cannot hold 15 conversations in the window |
| 12 | The CTO shows each team a green / amber / red debt band, never a number | Gives a fair, free warning and the debrief line "your CTO told you" |
| 13 | The whale lead reveals the data-isolation churn risk if asked the right question | Rewards good stakeholder questioning. Accepted even though it undercuts the paid Whale report |
| 14 | Five whale contracts, awarded by Whale trust | Adds interdependence between teams cheaply. Scarcity makes the deal more tempting while it remains a trap, and gives early trust a competitive use |
| 15 | Each team has a simulated product (a funnel per segment), not a real build | Real builds mean 15 deployments, seeded bugs and participants changing software. The event must need no coding |
| 16 | Continuous clock with three centrally controlled checkpoints | Continuous time lets teams see consequences. Checkpoints keep the shared reveal, team discussion, stakeholder bookings and a place to regroup |
| 17 | Only the operator controls the clock | A team must not be able to stop time for itself |
| 18 | Bandwidth is weekly build capacity through a reorderable queue | Build time is the natural delay between a decision and its effect, which prevents instant trial and error |
| 19 | Rollback exists and only works if the team's own release caused the problem | Makes root cause analysis matter: rolling back the wrong feature loses it and fixes nothing |
| 20 | "Ship, watch the data, roll back" is allowed as a way to test demand | It is a legitimate discovery tactic and the sunk BU keeps it from being free |
| 21 | Incidents come in three variants assigned by team number | Otherwise the answer crosses the room in minutes |
| 22 | A targeted fix aimed at the wrong cause is wasted | Replaced the v2-era idea that a correct diagnosis merely made the fix cheaper. In a live funnel a wrong fix visibly changes nothing |
| 23 | Peak season starts in week 28, not 27 | Week 27 is the first week after a checkpoint. One normal week makes the collapse read as a consequence, not a glitch |
| 24 | Trust scales weekly churn continuously | The v2 rule (below 40 trust, lose 15% of segment ARR per quarter) was a round-based threshold |
| 25 | Quality mode is a share of weekly capacity, averaged over a feature's build | The v2 purchase of 0 / 10 / 20 BU per quarter has no meaning on a continuous clock. Averaging stops teams switching mode just before a ship date |
| 26 | Operations telemetry is noisy: one quarter ambiguous, two quarters a trend | If error rate tracked debt exactly, the reveal would be spoiled in Q1 |
| 27 | Console overview is capped at four tiles | Teams already have reports, stakeholders and a queue to manage. The dashboard must not replace discussion |
| 28 | One zero-dependency Python process; hidden values stay on the server | Runs on a laptop with no internet. Anything sent to a browser can be read in developer tools |
| 29 | Resilience through action log, snapshots, spare laptop and spare router | See rejected item R15 |
| 30 | If the server is down for more than 10 minutes, run one printed root-cause exercise | Costs one page per team and no rehearsal |
| 31 | Hosting is left open between an own-router local network and a cloud server | Decided after a Wi-Fi test at the venue. The code is the same either way |
| 32 | The name is "Fix Forward" | A real industry phrase for the game's central incident decision, and it does not hint at hidden debt |

### 1.3 Rejected ideas and why

| # | Idea | Why it was rejected |
| :--- | :--- | :--- |
| R1 | Overtime, emergency contractors, burnout and a fatigue multiplier (from v1) | Contractors were dominant: hired in Q1 they netted +65 BU for ₹4.5 Cr, teaching the opposite of Brooks's Law. Five levers per round could not be scored live for 15 teams, and the extra mechanics diluted the hidden-debt reveal |
| R2 | Cash reserves | Existed only to pay contractors. Penalties now subtract directly from valuation |
| R3 | Random revenue outcomes | Luck could decide a four-quarter game, and "same decisions, same result" is easier to defend to 75 students |
| R4 | A single 10 BU survey covering everything | Leaks across the room; see decision 2 |
| R5 | "Deflect" (blame a vendor) as a crisis response | In a live funnel an unresolved defect keeps hurting, so deflecting was never a real option |
| R6 | A fully shared market in which teams compete for the same customers | Teams could not tell whether they lost to their own choices or to the market, which breaks the debrief. With 15 players each moves the market by about 1/15, so the interaction is noise. Balance cannot be tested with fixed scripts. One late team would corrupt everyone's score |
| R7 | Splitting 15 teams into three markets of five | Triples the scoring work and leaves three winners who cannot be compared |
| R8 | A crowding discount (payoff falls as more teams build the same feature) | A low result could mean low utility or crowding, which muddies the lesson about buying reports |
| R9 | Stakeholders awarding points by impression, or scoring every conversation | Fifteen teams would dispute it, and it turns the event into a role-play contest |
| R10 | Splitting one stakeholder role across several actors | Teams would hear different facts. The decline conversation is the only exception |
| R11 | A real product build per team | See decision 15 |
| R12 | Pure continuous play with no pauses | Loses the shared reveal, rewards click speed over judgment, leaves no time for discussion, and gives the MC and stakeholders nothing to anchor to |
| R13 | Running the simulation in the browser | Hidden parameters would be readable in developer tools |
| R14 | Interventions that take effect instantly at no cost | Teams would try everything and learn nothing |
| R15 | A rehearsed paper-and-forms version of the full game as a fallback | It means preparing and rehearsing two different events. Redundancy on the server path covers the same risks for less |
| R16 | A phone hotspot instead of a router | Hotspots commonly cap connected devices below what 15 teams need |
| R17 | Google Forms into a Google Sheet as the engine (v2) | Could not provide live data, investigation or visible consequences. Superseded, not flawed |
| R18 | A separate streaming dashboard sitting on top of the Sheet | Superseded once the server became the engine |
| R19 | Names containing "debt", "meltdown" or "reckoning"; "War Room"; "Ship or Sink"; "Peak Season" | The first group gives away the twist. "War Room" undersells discovery and stakeholders. "Ship or Sink" implies shipping fast is the goal, which is the trap. "Peak Season" points at the reveal |
| R20 | Citing "*Business Odyssey*" and an INSEAD "*Innovator's Method / Stakeholder LiveCase*", and describing the Harvard simulation as having a hidden defect pool | A search found no simulation called Business Odyssey; the INSEAD one was not verified; the Harvard simulation's public description does not mention a hidden defect pool. The specific percentages v1 attributed to MIT were design choices, not published parameters |
| R21 | v1's 40-minute rounds | They summed to 160 minutes before the briefing, in a 150-minute event |
| R22 | Printing the CTO's traffic-light list each quarter | The CTO's screen now shows it live |

### 1.4 What the v2 balance test showed

Eight scripted strategies were run through the v2 engine. The numbers do **not** apply to v3, but the shape is the target v3 should reproduce.

| Strategy | Public ARR after Q2 | Final valuation | vs winner |
| :--- | :--- | :--- | :--- |
| Balanced (reports, medium quality, patches only the last crisis) | ₹29.9 Cr | ₹161 Cr | 100% |
| Late sprinter (drops quality in Q4) | ₹30.1 Cr | ₹149 Cr | 93% |
| Whale-chaser (takes both bespoke deals) | ₹33.7 Cr | ₹143 Cr | 89% |
| Disciplined (maximum quality, deep fix every time) | ₹30.1 Cr | ₹136 Cr | 84% |
| Blind careful (same, no reports) | ₹29.0 Cr | ₹125 Cr | 78% |
| Corner-cutter (no quality spend, always patches) | ₹34.2 Cr | ₹124 Cr | 77% |
| Deflector (always deflects) | ₹32.3 Cr | ₹115 Cr | 72% |
| Blind reckless | ₹32.3 Cr | ₹114 Cr | 70% |

* The corner-cutter led the public scoreboard at the halfway point and finished sixth. This is the reveal the game is built around.
* Reports were worth about six points of final valuation.
* The late sprinter was the closest exploit. The planned remedy was to raise the audit rate from ₹0.25 Cr to ₹0.40 Cr per debt point.

### 1.5 Known open questions

| Question | Owner | Settled by |
| :--- | :--- | :--- |
| Local router or cloud hosting | Organiser | Wi-Fi test at the venue during the three-team trial |
| Who operates the server on the day | Organiser | Before the dress rehearsal |
| Are the Q4 cards worth building in a weekly funnel | Build | Calibration (stage 2) |
| How much telemetry noise | Build | Calibration, then the live trial |
| Every team's second incident is its own release, so "roll it back" will spread | Build and organiser | Live trial. The rollback or targeted-fix decision still stands |
| Does the late-sprinter exploit survive in v3 | Build | Balance run |
| Does the decline score reorder the top three | Organiser | Dress rehearsal; cut-back rule in spec Section 9 |

---

## Part 2: Build decisions

Append one row per decision made during the build that the spec did not make.

| Date | Decision | Reason | Numbers changed (before → after) | Balance re-run? |
| :--- | :--- | :--- | :--- | :--- |
| 2026-11-16 | The "do-nothing holds ₹25 Cr" check runs with scripted events off (`EVENTS_ENABLED` in config). With them on, a team that does nothing falls to about ₹18 Cr by week 52 | The spec's seeded incidents, the week-28 +5 trust bonus and the week-39 alerts all move a team that acts on nothing, so the funnel invariant and the full game cannot both hold at 25 | none (new switch) | Not applicable, stage 1. Organiser should confirm this reading |
| 2026-11-16 | New cohort is 15% of each segment | Spec gives "under 8 weeks" but no share | new: 0.15 | Not applicable, stage 1 |
| 2026-11-16 | UOD lowers retention as weekly churn × (1 + 0.002 × UOD) | Literal "retention −0.2% per point" would be a large weekly loss | new: 0.002 | Not applicable. Calibration should revisit |
| 2026-11-16 | The 0.8 BU bespoke capacity tax starts when the contract ships, not when it is awarded | Spec says "per bespoke contract"; a queued contract is not yet delivered | none | Not applicable, stage 1 |
| 2026-11-16 | C1 (Whale Beta) has no slot limit | Spec limits only B1 | none | Not applicable, stage 1 |
| 2026-11-16 | Incident 2 counts the first shipped non-bespoke card with a target segment in weeks 15–24. Incident 3 variant B damages the whole segment of the most recent such release, and is skipped if there is none | Keeps rollback possible; spec gives no slice for 3B | none | Not applicable, stage 1 |
| 2026-11-16 | Variant letter is team number mod 3, with 0 mapped to A | Spec says "modulo 3" without the mapping | none | Not applicable, stage 1 |
| 2026-11-16 | Incident 1: A damages Whale retention, B Self-Serve, C all segments on annual plans. Incident 3 variant C hits all segments on web and new cohort. Incident 1 A and B slow the platform (p99 +200 ms) | Spec names the pattern, not always the segment | none | Not applicable, stage 1 |
| 2026-11-16 | The quality capacity share applies to all queue work (reports, fixes, patches too). Debt accrues only from cards | Simplest reading of "applied to work as it is built" | none | Not applicable, stage 1 |
| 2026-11-16 | Rework after a peak-season outage uses full weekly capacity, not the quality-adjusted share | Rework is not feature work | none | Not applicable, stage 1 |
| 2026-11-16 | Feature lifts are one placeholder (0.05) for every card until calibration | Calibration is stage 2 | new: PLACEHOLDER_LIFT = 0.05 | Not applicable. Feature results before calibration mean nothing |
| 2026-11-16 | Telemetry noise half-widths: error rate 15%, p99 8%, tickets 12%, funnel 3% | Starting values, no data yet | new: NOISE | Not applicable. Tune in calibration |
| 2026-11-16 | Rules are data in `config.py`, not code in the engine. Incident triggers (week start or ship in a window), segment scope ("release" or a list), variant order, peak-season trust changes by segment, alert weeks, ranking and decline segments, utility scale and float tolerance are all config entries | Organiser wants to tune and reshape rules without touching engine code | Replaced `VARIANT_BY_MOD`, `PEAK_WHALE_TRUST`, `ALERT_WEEK` and per-incident week keys with the entries above | Not applicable: behaviour unchanged, 66 tests pass |
| 2026-11-17 | Lifts are capped per stage: 0.95 for retention, 3.0 for other stages. The engine floors the retention multiplier at zero | A retention lift of 1 or more made churn negative | new: `LIFT_CAPS` | Yes, see `docs/balance/stage2-report.md` |
| 2026-11-17 | Feature lifts are solved by `calibrate.py` and stored in `calibration/lifts.json`, which `config.load` reads. Gain is measured with scripted events off | Placeholder lifts meant nothing; events on would mix incident effects into each card | every funnel lift 0.05 → solved value (0.167 to 2.128; table in the report) | Yes: league before and after in the report |
| 2026-11-17 | B2, B3 and C4 keep the retention cap and are flagged unreachable (max gains ₹0.75, ₹1.74 and ₹1.34 Cr against targets ₹1.2, ₹2.4 and ₹1.7 Cr) | With the spec's churn rates a retention card cannot save that much ARR in the weeks left. Lowering the targets is the organiser's call | none committed | What-if row in the report |
| 2026-11-17 | Telemetry noise stays at 15% (error rate) and 8% (latency). The "one quarter ambiguous" rule cannot be met | A Low-quality team's debt moves error rate and latency so fast that hiding one quarter would need noise of about 300% and 130%. The lever is the per-UOD slopes, which are spec numbers | none | Not applicable |
| 2026-11-17 | The noise rule is measured on the corner-cutter's series for both windows, not on measured-risk for the first | Measured-risk ends most quarters with no debt, so it has no trend to hide and would pass at any level | none | Not applicable |
| 2026-11-17 | Eight scripted strategies are fixed in `bots.py` as one-change variants of measured-risk and are not tuned after a run | Otherwise the pass criteria could be met by editing the bots | none | Yes |
| 2026-11-17 | The team view's open incidents now carry the alerted metric and the four candidate causes | Both are already public: the symptom names the metric and every team sees the same cause list | none | Not applicable |
| 2026-11-17 | Scripted teams diagnose from slice data. An alert that opens on a team's own ship day, with a gap between sibling slices only in that card's segment, reads as own release | Incident 2's release can lift the same stage it breaks, so activation rises overall and no before/after drop exists. Organiser should check the "activation has dropped" wording | none | Yes |
| 2026-11-23 | The event log is the source of truth. Every day tick, accepted action, admin action, clock operation and reveal is a log line, and each tick line carries a per-team state digest. Recovery replays the log alone and stops on the first digest mismatch | Replaying a full game takes about 0.07 s per team, so no snapshot is needed for speed, and digests catch divergence at restart instead of mid-game | none | Not applicable |
| 2026-11-23 | Snapshots hold every team's state without per-day history and are written atomically every 5 seconds. Restoring one appends a rewind marker to the log, never deletes lines, and is verified by digest | History is about 1 MB per team by the end of the game, so full snapshots would be tens of MB every 5 seconds | none | Not applicable |
| 2026-11-23 | The server comes back paused after any restart and the operator resumes | An unattended clock on a restored state is the worse failure | none | Not applicable |
| 2026-11-23 | The first log line records a digest of every game setting, and a restart with different settings is refused (`--new-game` archives the old state). Server-only settings (port, seconds per day, snapshot interval and so on) may change | A number tuned during rehearsal must not silently change a live game | new: `SERVER_ONLY_KEYS` | Not applicable. Operators must use `--new-game` between rehearsals and after the 1 December freeze changes |
| 2026-11-23 | An action is validated against a table in config, applied, logged and then acknowledged, under one lock. Only actions the engine accepts are logged. If the log cannot be written the game pauses and rejects actions until the operator reloads | Acknowledged means durable. The engine raises on malformed fields and accepts admin action types, so the server must filter first | new: `ACTION_SPECS`, `CALLER_ACTIONS` | Not applicable |
| 2026-11-23 | Team views are cached per team and version, and an ETag includes a per-boot token. The ETag applies to the view route only; the clock is a separate cheap route and is also embedded in a 200 response | A stale ETag from before a restart must not produce a false 304, and a countdown must never be served from cache | new: `VIEW_DEFAULT_SERIES_DAYS` 28 | Not applicable |
| 2026-11-23 | Default of 16 teams numbered 1 to N, six-character codes from an alphabet without 0, O, 1 and I, saved in `teams.json`. Admin and stakeholder passwords come from flags or environment variables and are generated and printed once if absent | A restart must not lock teams out, and codes must be easy to read aloud | new: `NUM_TEAMS`, `TEAM_CODE_ALPHABET` | Not applicable |
| 2026-11-23 | The stakeholder password is accepted at startup but opens no routes yet | Stakeholder endpoints are stage 6 | none | Not applicable |
