# Fix Forward: Build Spec v3

*52 weeks, one live product, 80 minutes. Formerly "The Executive Product Crucible".*

**Event:** Friday 4 December 2026. **Build complete:** Monday 23 November. **Rehearsals:** 24 November – 3 December.
**Format:** 15+ teams of 4–5, 2.5 hours, one laptop console per team, three live stakeholders, one server on a local network.
**Status:** design agreed in discussion. All numbers are starting values. Nothing here is balance-tested yet; the v2 test does not carry over, because the engine is different.

---

## 1. What changed from v2

| v2 | v3 |
| :--- | :--- |
| Four rounds, decisions submitted on Google Forms | Continuous clock with three centrally controlled checkpoints |
| Google Sheet scores the game | A server runs the simulation; the sheet is retired |
| ARR = Pitch × hidden utility, applied once per round | ARR emerges week by week from a funnel per segment |
| 100 BU per quarter, spent up front | 8 BU of build capacity per week, spent through a roadmap queue |
| Crisis card with three paths (deep fix, patch, deflect) | Seeded incidents diagnosed from live data; responses are targeted fix, rollback or patch |
| Hidden debt checked at the start of Q3 | Hidden debt drags the funnel continuously and is tested by peak season in week 28 |
| Whale contract open to all | Five contracts, awarded by Whale trust |
| Quality buffer bought with 0 / 10 / 20 BU per quarter | Quality mode keeps 100% / 90% / 80% of weekly capacity for features |
| A segment below 40 trust loses 15% of its ARR each quarter | Trust scales weekly churn continuously (Section 3.3) |
| Correct diagnosis made the deep fix cheaper | A targeted fix aimed at the wrong cause is wasted (Section 6.1) |
| Paper-and-forms fallback | Server redundancy plus one printed exercise (Section 11) |

Carried over unchanged: the three segments and starting ARR, trust per segment, the valuation formula, bespoke contract rules, segment reports, the three stakeholder roles and their script cards, the scored decline conversation, and the debrief.

Dropped: the "deflect" crisis path. In a live funnel an unresolved defect keeps hurting, so deflecting was never a real option.

---

## 2. Time model

| Item | Value |
| :--- | :--- |
| Game length | 52 simulated weeks (four quarters of 13) |
| Clock speed | 1 simulated day = 13 seconds, so 1 week ≈ 91 seconds and 1 quarter ≈ 20 minutes |
| Checkpoints | Automatic pause at the end of weeks 13, 26 and 39, 7 minutes each |
| Live play | ≈ 79 minutes of clock plus 21 minutes of pauses |

**Run-of-show (150 minutes)**

| Block | Minutes |
| :--- | :--- |
| Briefing with a 3-minute live demo of the console | 15 |
| Q1, then checkpoint 1 | 20 + 7 |
| Q2, then checkpoint 2 | 20 + 7 |
| Q3, then checkpoint 3 | 20 + 7 |
| Q4 | 20 |
| Reveal and debrief | 15 |
| Buffer | 19 |

**Clock rules**

* Simulated time exists only on the server. Consoles display it.
* The operator can pause early, extend a pause, resume, or change speed for everyone. No team can affect the clock.
* Consoles show a countdown to the next checkpoint and a 30-second warning before resume.
* During a pause teams can reorder the queue, book stakeholders and respond to incidents. Nothing ships and no data moves until resume.

---

## 3. The simulated product

Each team runs its own copy of the same product. State is per segment; every team starts identical.

### 3.1 Funnel

Each week, per segment: leads → sign-up → activation → paid → retained.

| Segment | Paying accounts | ARR per account | Starting ARR | Leads / week | Sign-up | Activation | Paid | Weekly churn |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Whales (W) | 20 | ₹50 L | ₹10 Cr | 2 | 50% | 50% | 10% | 0.25% |
| Mid-Market (M) | 150 | ₹6 L | ₹9 Cr | 60 | 30% | 50% | 10% | 0.6% |
| Self-Serve (S) | 2,000 | ₹0.3 L | ₹6 Cr | 4,000 | 10% | 50% | 10% | 1.0% |

* New accounts per week = leads × sign-up × activation × paid. Lost accounts = accounts × churn.
* At these values new accounts equal lost accounts, so a team that does nothing stays at ₹25 Cr.
* Accounts are tracked as expected values (fractions allowed). The state has no randomness.
* Displayed daily metrics carry small seeded noise so charts look live. Noise never affects state or score.

### 3.2 Slices

Every funnel metric can be cut by:

* segment (W, M, S)
* platform (web 60%, mobile 40%)
* plan (monthly 70%, annual 30%)
* cohort (new: under 8 weeks; existing)
* time (daily series with a marker on each release)

Slices are fixed shares of each segment. A defect applies a multiplier to one slice of one stage; the segment's rate is the weighted average. This is what makes root cause analysis possible.

### 3.3 Trust

* One index per segment, 0–100, starting at 60.
* Weekly churn is multiplied by 1 + 0.02 × (60 − trust). Trust 40 raises churn 40%; trust 80 lowers it 40%.
* Trust moves through features, incidents, stakeholder conversations and peak season.

### 3.4 Hidden debt (UOD)

* Starts at 0. Never shown to teams as a number.
* Added when a feature ships: its risk points × the quality multiplier in force while it was built.
* Visible only through its effects:
  * error rate = 0.5% + 0.04% × UOD, plus noise;
  * activation and retention are reduced by 0.2% per UOD point (UOD 50 means −10%).
* The CTO's stakeholder screen shows each team's band: green 0–15, amber 16–30, red above 30.

### 3.5 Operations telemetry

The console's operations view shows three live series. All are derived from hidden state plus seeded noise.

| Series | Driven by |
| :--- | :--- |
| Error rate | UOD (formula in 3.4) |
| p99 latency | UOD, plus any open incident that slows the platform, plus the peak-season surge |
| Support tickets, per segment | Falling trust in that segment, plus any open incident affecting it |

* **Noise rule:** noise is sized so that one quarter of data is ambiguous and two quarters show a clear trend. A team must not be able to read its exact debt in Q1. The noise level is set during calibration (build day 2) and checked in the live trial.
* **Overview is capped at four tiles** (ARR, trust, build capacity, open incidents). Everything else sits one click down, so the dashboard does not compete with the team's discussion.

---

## 4. What teams can do

### 4.1 Roadmap queue

* Build capacity is **8 BU per week**, minus 0.8 per bespoke contract.
* Capacity flows to the first item in the queue. An item ships the day its cost is fully built.
* The queue can be reordered at any time. Removing a partly built item loses the BU already spent.
* New initiative cards unlock at the start of each quarter. Earlier cards stay available.

### 4.2 Quality mode

One setting, changeable at any time, applied to work as it is built.

| Mode | Capacity kept for features | Debt multiplier |
| :--- | :--- | :--- |
| Low | 100% | 1.6 |
| Medium | 90% | 1.0 |
| High | 80% | 0.35 |

A feature built half in Low and half in High gets the average of the two multipliers, so switching just before a ship date gains nothing.

### 4.3 Segment reports

* A queue item costing 4 BU, one per segment.
* On completion it shows, for that segment: a utility score (0–100) for every card currently available, and any churn alert.
* It covers the cards available when it was ordered. New cards need a new report.

### 4.4 Rollback

* Any shipped feature except a bespoke contract can be rolled back.
* Takes effect after 1 week and uses no build capacity.
* Removes the feature's funnel effects, any regression it carries, and the debt it added.
* Costs: the original BU are not returned; the target segment loses 3 trust; re-shipping costs 50% of the original BU.

### 4.5 Stakeholder meetings

* Each stakeholder takes 5 bookings per quarter, first come, made on the console.
* Meetings are 3 minutes, in person, any time in the quarter or its checkpoint.
* Script cards are as in v2 Section 8.2, keyed to the quarter.

---

## 5. Initiative cards

Teams see name, cost, target segment, the funnel stage sales claims it moves, pitch ARR and trust effect. **True effect and risk are hidden.**

"Target gain" is the ARR the feature should add by week 52 if queued first when it unlocks. The engine's lift values are calibrated to hit these targets (build day 2).

| ID | Unlocks | Initiative | BU | Seg | Stage moved | Pitch ARR | Target gain (hidden) | Risk (hidden) | Trust |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| A1 | Q1 | AI Copilot | 35 | M | Paid | ₹6.0 Cr | ₹0.9 Cr | 8 | |
| A2 | Q1 | Self-serve onboarding revamp | 20 | S | Activation | ₹2.0 Cr | ₹1.6 Cr | 3 | S +5 |
| A3 | Q1 | Bulk import & integrations | 25 | M | Activation | ₹2.5 Cr | ₹1.9 Cr | 5 | |
| A4 | Q1 | Enterprise SSO & audit logs | 30 | W | Paid | ₹3.0 Cr | ₹2.1 Cr | 6 | W +5 |
| A5 | Q1 | Mobile app refresh | 20 | S | Sign-up | ₹2.5 Cr | ₹0.9 Cr | 4 | |
| A6 | Q1 | Usage-based pricing tier | 15 | S | ARR per account | ₹1.5 Cr | ₹0.9 Cr | 4 | |
| B1 | Q2 | Bespoke compliance dashboard, Whale Alpha (**bespoke**, 5 available) | 30 | W | Contract | ₹5.0 Cr signed | ₹5.0 Cr | 9 | W +10 |
| B2 | Q2 | Enterprise data isolation | 30 | W | Retention | ₹2.0 Cr | ₹1.2 Cr | 5 | |
| B3 | Q2 | Mid-market reporting suite | 25 | M | Retention | ₹3.0 Cr | ₹2.4 Cr | 5 | |
| B4 | Q2 | Partner marketplace API | 35 | M | Leads | ₹5.0 Cr | ₹1.5 Cr | 10 | |
| B5 | Q2 | SMB referral loops | 15 | S | Leads | ₹1.5 Cr | ₹1.05 Cr | 3 | |
| B6 | Q2 | Workflow automation | 25 | S | Retention | ₹3.0 Cr | ₹1.65 Cr | 6 | |
| C1 | Q3 | Bespoke integration, Whale Beta (**bespoke**) | 25 | W | Contract | ₹4.0 Cr signed | ₹4.0 Cr | 8 | W +5 |
| C2 | Q3 | Advanced analytics add-on | 30 | W | ARR per account | ₹4.0 Cr | ₹3.0 Cr | 6 | |
| C3 | Q3 | AI meeting summaries | 25 | M | Paid | ₹4.0 Cr | ₹1.0 Cr | 7 | |
| C4 | Q3 | Annual-plan pricing | 15 | S | Retention | ₹2.0 Cr | ₹1.7 Cr | 2 | |
| C5 | Q3 | Localization pack | 25 | M | Leads | ₹3.0 Cr | ₹1.95 Cr | 5 | |
| D1 | Q4 | Enterprise expansion pack | 30 | W | ARR per account | ₹4.0 Cr | ₹2.8 Cr | 7 | |
| D2 | Q4 | Quick-win promo campaign | 20 | S | Sign-up | ₹3.0 Cr | ₹1.2 Cr | 6 | |
| D3 | Q4 | Mid-market upsell bundle | 25 | M | ARR per account | ₹3.0 Cr | ₹2.25 Cr | 5 | |
| D4 | Q4 | Audit readiness sprint | 20 | | | | UOD −20 | 0 | |
| D5 | Q4 | Executive customer summit | 20 | | | | | 0 | All +5 |
| P1 | Always | Platform hardening (once per quarter) | 15 | | | | UOD −12 | 0 | |
| P2 | Always | Customer success program (once per quarter) | 15 | | | | | 0 | All +3 |

**Bespoke contracts**

* B1 has five slots. Teams apply during weeks 14–17; at the end of week 17 the five applicants with the highest Whale trust win, and it enters their queue. Losing applicants lose nothing.
* Each contract takes 0.8 BU per week of capacity for the rest of the game.
* Bespoke ARR shows in public ARR but is valued at 2.0× at the end.

**Churn alerts (in the matching segment report, and obtainable from the whale lead by asking)**

* Whale Alpha (₹3 Cr) leaves at the end of week 39 unless B2 has shipped. If not: Whale ARR −₹3 Cr, Whale trust −10.
* Mid-market accounts are evaluating a competitor over reporting. If B3 has not shipped by the end of week 39: Mid-Market trust −15.

---

## 6. Incidents and root cause analysis

Three seeded incidents per team. Each damages one slice of one funnel stage until resolved. While an incident is open, the affected segment loses 2 trust per week.

### 6.1 Responses

| Response | Cost | Works when | Result |
| :--- | :--- | :--- | :--- |
| Targeted fix (team picks 1 of 4 causes) | 15 BU, queued at the front | The cause picked is correct | Resolved, UOD −10 |
| | | The cause is wrong | BU spent, nothing changes; team can try again |
| Rollback (team picks a shipped feature) | See 4.4 | That feature caused the incident | Resolved |
| | | It did not | Feature lost, nothing else changes |
| Patch | 6 BU, queued at the front | Always | Damage halved for the rest of the game, trust loss stops, UOD +15 |

### 6.2 The three incidents

| # | Starts | Symptom | Variant by team number | True cause | Best response |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Week 6 | Retention falls in one segment | A | One whale's nightly bulk jobs slow the platform: Whale accounts only, same hours each night | Targeted fix |
| | | | B | Organic traffic growth: Self-Serve only, at daily peak hours | Targeted fix |
| | | | C | Vendor degradation: all segments, annual-plan renewals only | Targeted fix |
| 2 | Ship day of the team's first feature shipped in weeks 15–24 | Activation drops 40% in one slice of that feature's segment | A: mobile; B: new cohort; C: annual plan | The team's own release | Rollback (fast, lose the feature) or targeted fix (keep it) |
| 3 | Week 33 | Paid conversion falls | A | Payment provider failing on annual plans | Targeted fix |
| | | | B | The team's most recent release | Rollback or targeted fix |
| | | | C | Pricing page change by marketing: web only, new cohort | Targeted fix |

* The four candidate causes shown to every team are the same list per incident: external load, organic growth, own release, vendor (incident 3 swaps organic growth for "pricing or marketing change").
* Variants are assigned by team number modulo 3, so the answer at the next table is usually wrong for you.
* Incident 2 is tied to a team's own ship, so teams that ship nothing in weeks 15–24 never get it.

### 6.3 What teams see

* An alert on the console: the symptom only, never the cause.
* The funnel explorer, where the pattern is visible in the right slice and on the timeline.
* Release markers on every chart.

---

## 7. Peak season

* Announced in the briefing and shown on every console's calendar: a load surge in **weeks 28–30**.
* At the start of week 28 the server checks each team's UOD.

| UOD | Result |
| :--- | :--- |
| 40 or below | Platform holds. Trust +5 in every segment |
| Above 40 | Outage. Build capacity is seized for rework until (UOD − 30) BU are paid, capped at 50 BU. ₹3 Cr SLA penalty. Whale trust −35. UOD falls by the BU paid |

Week 27 runs normally after checkpoint 2, so teams see one ordinary week before the surge.

---

## 8. Scoring

NEV = (non-bespoke ARR × trust multiple) + (bespoke ARR × 2.0) − (₹0.25 Cr × final UOD) − penalties

Trust multiple = 2.0 + 0.03 × average trust across segments

* Measured at the end of week 52.
* The projected leaderboard shows live ARR and trust for every team. UOD and NEV stay hidden until the debrief.

---

## 9. Live stakeholders

Three people play fixed roles for the whole event: the VP Sales, Whale Alpha's account lead, and the CTO. They are a free but biased source of information; segment reports stay the only source of utility scores.

### 9.1 Rules

* Stakeholders say only what is on their card for the quarter: what they say unprompted, and what they say only if asked.
* Nobody ever states utility scores, risk points or the UOD number.
* One actor per role for every team, except the decline conversation.
* **Bookings** are made on the console (4.5).
* **CTO traffic light** is live on the CTO's screen. No printing.
* **Decline conversation:** teams that do not apply for B1 decline in person during checkpoint 1. Three actors, 90 seconds each, three-item checklist entered on the stakeholder screen: 3 ticks Whale trust +5, 2 ticks 0, fewer or no-show −5.
* **Staff:** MC, server operator, two floor runners, three stakeholders.
* **Cut-back rule:** after the dress rehearsal, drop the scored decline conversation and keep stakeholders as information only if the decline scores change the order of the top three, or any stakeholder queue cannot be cleared within its quarter.

### 9.2 Script cards

**Q1: The Growth Trap**

| Role | Says unprompted | Says only if asked |
| :--- | :--- | :--- |
| VP Sales | "Every prospect asks about AI Copilot. That is ₹6 Cr of pipeline. The mobile app loses us demos." | *Has anyone committed budget for Copilot?* "No. It is demo interest so far." |
| Whale lead | "We need SSO and audit logs for our security review." | *Would you pay for AI Copilot?* "Nice to have. We would not pay extra." *Anything else coming?* "Our security team has started asking about data isolation." |
| CTO | "Latency is creeping up. If you ship a lot this quarter, fund the quality buffer." | *Which features are risky?* "Copilot is the riskiest by far. SSO is moderate. Onboarding is safe." |

**Q2: The Enterprise Temptation**

| Role | Says unprompted | Says only if asked |
| :--- | :--- | :--- |
| VP Sales | "Whale Alpha will sign ₹5 Cr for the compliance dashboard. Biggest deal of the year. Partners are also lining up for the marketplace API, ₹5 Cr." | *Have partners signed?* "Letters of interest, no contracts." *What does the dashboard cost to maintain?* "They will want changes every quarter." |
| Whale lead | "We want the compliance dashboard built for us." | *What if we say no?* "We would be disappointed. It is not why we would leave." *What would make you leave?* "Data isolation. Our security review closes at the end of Q3." |
| CTO | Traffic-light line (3.4) | *What is the dashboard like to build?* "Custom code we maintain forever. It is one of the riskiest items on the menu." |

**Q3: The Reckoning**

| Role | Says unprompted | Says only if asked |
| :--- | :--- | :--- |
| VP Sales | "Whale Beta will sign ₹4 Cr for a custom integration. Competitors just launched AI meeting summaries; that is ₹4 Cr of pipeline." | *Is there budget behind AI summaries?* "Nobody has attached budget." |
| Whale lead | If B2 not shipped: "Our security review closes this quarter. Is data isolation shipping?" If the team melted down: "Your outage hit our operations. Leadership is asking about alternatives." | *Would you buy the analytics add-on?* "Yes, we would pay for that." |
| CTO | Traffic-light line (3.4) | *What about mid-market?* "Support tickets say they are unhappy with reporting." |

**Q4: The Valuation Sprint**

| Role | Says unprompted | Says only if asked |
| :--- | :--- | :--- |
| VP Sales | "A promo campaign gets us a quick ₹3 Cr before the round closes." | *Will promo customers stay?* "Mostly discount-seekers. Expect fewer than half to stick." |
| Whale lead | "Investors will call us for a reference. We would expand if the expansion pack ships." | *What will you tell investors?* "Depends on how this year went for us." |
| CTO | Traffic-light line (3.4), then: "Auditors arrive at quarter end. Every unresolved shortcut gets priced." | *What clears the most?* "The audit readiness sprint." |

---

## 10. Software

### 10.1 Architecture

* **One Python 3 process, standard library only.** Runs with `python3 server.py` on a laptop. No installs, no internet.
* **Own router.** Teams join a local network and open the server's address in a browser.
* **Engine is a pure function** of the configuration and the list of team actions, each stamped with the simulated day. Same inputs, same result.
* **Consoles poll** the server every 3 seconds. At 20 clients that is under 10 requests per second.
* **All hidden values stay on the server.** The browser receives only what the team is allowed to see.

### 10.2 Screens

| Screen | Who | Contents |
| :--- | :--- | :--- |
| Team console | Each team, by team code | Overview tiles; funnel explorer with slice filters and release markers; operations (error rate, latency, tickets); roadmap queue and quality mode; incidents; stakeholder booking; clock and countdown |
| Projector | Room | Leaderboard (ARR, trust), clock, checkpoint countdown |
| Stakeholder | Three actors | Booking list; CTO traffic lights; decline checklist |
| Admin | Operator, by password | Pause, resume, speed; trigger or cancel incidents; edit a team's state; restore a snapshot; final reveal |

### 10.3 Resilience (required, not optional)

* Action log appended to disk on every team action; full state snapshot every 5 seconds.
* Restart rebuilds state from the snapshot and log in under 1 minute.
* Spare laptop receives the snapshot every 30 seconds and can take over the same address.
* Spare router preconfigured with the same network name; router runs from a power bank.
* Team codes are random, six characters.

### 10.4 Headless mode

The engine runs without the server at full speed, driven by scripted teams. This is how balance is tested and how every number in this spec gets tuned.

---

## 11. If the server is down for more than 10 minutes

The MC hands out one printed incident packet per team and runs it as a root-cause exercise while the operator recovers. One page per team, no rehearsal needed. There is no paper version of the full game.

---

## 12. Build plan

| Day | Date | Deliverable | Done when |
| :--- | :--- | :--- | :--- |
| 1 | Tue 17 Nov | Spec sign-off. Paper test of incident 1 with three volunteers | Volunteers find the cause in 2–10 minutes |
| 2 | Wed 18 Nov | Engine, headless mode, scripted teams, calibration of lifts to target gains | A do-nothing team stays at ₹25 Cr; scripted results reported |
| 3 | Thu 19 Nov | Server, global clock, checkpoints, action log, snapshots, admin pause | Kill and restart loses no state |
| 4 | Fri 20 Nov | Team console: overview, roadmap queue, quality mode, funnel explorer | A person can play Q1 end to end |
| 5 | Sat 21 Nov | Incidents, slices, targeted fix, rollback, patch, operations telemetry | All nine incident variants resolvable from the data |
| 6 | Sun 22 Nov | Peak season, projector leaderboard, stakeholder screen, whale contracts, reports | A full 52-week game runs with scripted teams over HTTP |
| 7 | Mon 23 Nov | Load test with 20 simulated clients; failure drill; feature freeze | Recovery under 5 minutes with no state lost |

**After the build**

| Date | Activity |
| :--- | :--- |
| 24–26 Nov | One live quarter with three volunteer teams. Tune clock speed and incident difficulty |
| 28–29 Nov | Full dress rehearsal with stakeholders and operator. Tune numbers only |
| 1 Dec | Number freeze. Print the fallback packets and rules sheet |
| 4 Dec | Event |

**If the week runs short, cut in this order:** stakeholder screen (use paper cards and a sign-up board), whale contract ranking (open B1 to all), incident 3, platform and plan slices (keep segment, cohort and time).

---

## 13. Pass tests

| Test | Passes when |
| :--- | :--- |
| Balance (headless, day 2) | A measured-risk strategy wins; a corner-cutting strategy leads on ARR at week 26 and loses by week 52; no single-tactic strategy finishes within 5% of the winner |
| Incident difficulty (paper, day 1; live, 24–26 Nov) | 50–70% of teams pick the correct cause first time |
| Pace (live quarter) | Teams act at least once every three minutes, and decisions are discussed before they are clicked |
| Fixed-plan exploit (headless) | A team that queues everything in week 1 and never touches the console finishes in the bottom half |
| Recovery (day 7 and dress rehearsal) | Server kill and router pull each recover in under 5 minutes with no state lost |
| Attribution (dress rehearsal) | Teams explain their result by their own decisions, not other teams' |

---

## 14. Debrief (15 minutes)

1. Reveal the final NEV ranking on the projector.
2. Show three hidden-debt curves: the week-26 leader, the final winner, and the biggest collapse.
3. Overlay each of those teams' error-rate chart and CTO traffic light: "It was on your dashboard, and your CTO told you."
4. Reveal the hidden target gains for AI Copilot, Partner marketplace API and AI meeting summaries, and ask who built them without a report.
5. Ask the team with the highest final ARR why it did not win.
6. Ask one team that rolled back the wrong feature what the data had shown.
7. Award the trophy to the highest NEV.

Questions to pose:

* Which decision looked best on the leaderboard and worst in the valuation?
* What did a report cost you, and what did not buying it cost you?
* When was a patch or a rollback the right call?

---

## 15. Sources

The mechanics are our own design and none of the numbers come from published sources. Inspirations: the rework cycle in system dynamics project models (Abdel-Hamid & Madnick; Sterman), Harvard Business Publishing's *Project Management Simulation: Scope, Resources, Schedule* (Robert D. Austin), and *Markstrat* (StratX) for paid market research. The v1 references to "*Business Odyssey*" and an INSEAD "*LiveCase*" remain removed as unverified.

---

## 16. Known risks

* **Balance is untested.** A weekly funnel rewards shipping early far more than the v2 round model did. Q4 cards may be too weak to be worth building; calibration on day 2 will show it.
* **Incident 2 leaks its type.** Every team's second incident is their own release, so "roll it back" will spread. The decision between rollback and targeted fix still stands.
* **Whale funnel numbers are small.** 0.05 new accounts a week will look odd on a chart. The console may need to show Whale metrics as ARR, not account counts.
* **One operator.** The person running the server must have done both rehearsals and the failure drill.
