"""Scripted teams, headless league and balance criteria.

A strategy is a callable (view, day) -> list of actions. It only ever sees the
team view, so a scripted team cannot read hidden state. The six single-tactic
strategies are the measured-risk plan with one tactic changed; their rules are
fixed here and are not tuned to make the balance criteria pass.

Run `python bots.py` for the league table and the pass/fail lines.
"""
import statistics

import config
import engine

# --- strategy parameters (bot behaviour, not game numbers) ----------------
UTILITY_MIN = 50          # value-order bots skip cards with a lower known utility
QUEUE_TARGET = 2          # items a bot keeps queued
ALERT_CARD = {"W": "B2", "M": "B3"}   # card that answers a churn alert, by report segment
DIAG_DAYS = 3             # days averaged on each side of an alert
DIAG_MIN_CHANGE = 0.10    # smallest relative move that counts as a hit
DIAG_SHARE_OF_MAX = 0.60  # a slice is hit if it moved at least this share of the largest move
DIAG_GAP = 0.15           # gap between sibling slices that marks one of them as broken
DETAIL_DAYS = 14         # history a diagnosing bot asks for
FIX_ATTEMPTS = 2
COPIES = 3                # copies of each strategy, one per incident variant


# --- diagnosis from slice data --------------------------------------------
def diagnose(view, incident):
    """Name an incident's cause from funnel slices in the view, or None if unclear."""
    metric = incident["metric"]
    key = "churn" if metric == "retention" else metric
    since = incident["since_day"]
    # A release that lifts the alerted stage hides the drop in before/after data,
    # so first look for a gap between sibling slices that exists only in the
    # segment of a card shipped on the day the alert opened.
    seg_of = {c["id"]: c["seg"] for c in view["cards"]}
    shipped_segs = {seg_of.get(r["card"]) for r in view["releases"] if r["day"] == since}
    gaps = {}
    for seg, series in view["funnel"].items():
        after = [p for p in series if p["day"] >= since][-DIAG_DAYS:]
        if not after or "slices" not in after[0]:
            return None
        by_dim = {}
        for sk in after[0]["slices"]:
            by_dim.setdefault(sk.split(":")[0], []).append(
                statistics.mean(p["slices"][sk][key] for p in after))
        gaps[seg] = max((max(v) / min(v) - 1.0) if min(v) else 0.0 for v in by_dim.values())
    gapped = {seg for seg, g in gaps.items() if g >= DIAG_GAP}
    if len(gapped) == 1 and gapped <= shipped_segs:
        return "own_release"
    moves = {}
    for seg, series in view["funnel"].items():
        before = [p for p in series if since - DIAG_DAYS <= p["day"] < since]
        after = [p for p in series if p["day"] >= since][-DIAG_DAYS:]
        if not before or not after or "slices" not in after[0]:
            return None
        seg_moves = {}
        for sk in after[0]["slices"]:
            b = statistics.mean(p["slices"][sk][key] for p in before)
            a = statistics.mean(p["slices"][sk][key] for p in after)
            change = (a / b - 1.0) if b else 0.0
            seg_moves[sk] = change if key == "churn" else -change
        moves[seg] = seg_moves
    biggest = max(m for sm in moves.values() for m in sm.values())
    if biggest < DIAG_MIN_CHANGE:
        return None
    floor = max(DIAG_MIN_CHANGE, DIAG_SHARE_OF_MAX * biggest)
    hit = {seg: {sk for sk, m in sm.items() if m >= floor} for seg, sm in moves.items()}
    full = [seg for seg, sm in moves.items() if len(hit[seg]) == len(sm)]
    common = set.intersection(*hit.values())
    if metric == "activation":
        return "own_release"
    if metric == "retention":
        if len(full) == 1:
            return "external_load" if full[0] == "W" else "organic_growth"
        if "plan:annual" in common:
            return "vendor"
    if metric == "paid":
        if len(full) == 1:
            return "own_release"
        if "cohort:new" in common:
            return "pricing_change"
        if "plan:annual" in common:
            return "vendor"
    return None


# --- the shared policy ----------------------------------------------------
class Policy:
    """Measured-risk plan with switches. Each named strategy flips one tactic."""

    def __init__(self, name, quality="medium", reports=True, order="value", p1_from=2,
                 p2_from=None, d4=True, incident="fix", bespoke=False, whale_first=False,
                 sprint_week=None, act_once=False, idle=False):
        self.name = name
        self.quality, self.reports, self.order = quality, reports, order
        self.p1_from, self.p2_from, self.d4 = p1_from, p2_from, d4
        self.incident, self.bespoke, self.whale_first = incident, bespoke, whale_first
        self.sprint_week, self.act_once, self.idle = sprint_week, act_once, idle
        self.mem = {"attempts": {}}

    # the runner asks this before building the costly slice view
    def wants_detail(self, view):
        if self.idle or self.act_once or self.incident != "fix":
            return False
        return any(self._needs_fix(view, inc) for inc in view["incidents"])

    def _needs_fix(self, view, inc):
        queued = any(it["kind"] == "fix" and it["incident"] == inc["id"] for it in view["queue"])
        return not queued and self.mem["attempts"].get(inc["id"], 0) < FIX_ATTEMPTS

    def _utility(self, view):
        known = {}
        for r in view["reports"]:
            known.update(r["utility"])
        return known

    def _alert_cards(self, view):
        return {ALERT_CARD[r["seg"]] for r in view["reports"] if r["alerts"] and r["seg"] in ALERT_CARD}

    def _candidates(self, view):
        known = self._utility(view)
        urgent = self._alert_cards(view)
        out = []
        for c in view["cards"]:
            if c["status"] != "available" or c["bespoke"] or c["stage"] is None:
                continue
            if self.order == "pitch":
                value = c["pitch_arr"] / c["cost"]
            else:
                if c["id"] not in known or known[c["id"]] < UTILITY_MIN:
                    continue
                value = known[c["id"]] * c["pitch_arr"] / c["cost"]
            rank = (0 if c["id"] in urgent else 1,
                    0 if (self.whale_first and c["seg"] == "W") else 1, -value, c["id"])
            out.append((rank, c["id"]))
        return [cid for _, cid in sorted(out)]

    def _all_q1_by_pitch(self, view):
        cards = [c for c in view["cards"]
                 if c["status"] == "available" and not c["bespoke"] and c["stage"] is not None]
        cards.sort(key=lambda c: (-c["pitch_arr"] / c["cost"], c["id"]))
        return [c["id"] for c in cards]

    def __call__(self, view, day):
        if self.idle:
            return []
        acts = []
        mem = self.mem
        week, quarter = view["week"], view["quarter"]
        if day == 0:
            acts.append(dict(type="set_quality", mode=self.quality))
        if self.act_once:
            if day == 0:
                acts += [dict(type="queue_add", report=s) for s in "WMS"]
                acts += [dict(type="queue_add", card=c) for c in self._all_q1_by_pitch(view)]
            return acts
        sprinting = self.sprint_week is not None and week >= self.sprint_week
        if sprinting and not mem.get("sprinted"):
            mem["sprinted"] = True
            acts.append(dict(type="set_quality", mode="low"))
        new_quarter = mem.get("quarter") != quarter
        mem["quarter"] = quarter
        if self.reports and new_quarter:
            acts += [dict(type="queue_add", report=s) for s in "WMS"]
        # reports jump ahead of cards so the next build choice is informed
        reps = [it for it in view["queue"] if it["kind"] == "report"]
        ahead = [it for it in view["queue"] if it["kind"] in ("fix", "patch")]
        for i, it in enumerate(reps):
            want = len(ahead) + i
            if view["queue"].index(it) != want:
                acts.append(dict(type="queue_reorder", item=it["id"], position=want))
        if self.bespoke:
            if view["b1"]["window_open"] and not view["b1"]["applied"]:
                acts.append(dict(type="apply_b1"))
            for c in view["cards"]:
                if c["id"] == "C1" and c["status"] == "available":
                    acts.append(dict(type="queue_add", card="C1"))
        for inc in view["incidents"]:
            if self.incident == "patch":
                queued = any(it["kind"] == "patch" and it["incident"] == inc["id"]
                             for it in view["queue"])
                if not inc["patched"] and not queued:
                    acts.append(dict(type="patch", incident=inc["id"]))
            elif self.incident == "fix" and self._needs_fix(view, inc):
                cause = diagnose(view, inc)
                if cause:
                    mem["attempts"][inc["id"]] = mem["attempts"].get(inc["id"], 0) + 1
                    acts.append(dict(type="targeted_fix", incident=inc["id"], cause=cause))
        if new_quarter and not sprinting:
            if self.p1_from is not None and quarter >= self.p1_from:
                acts.append(dict(type="queue_add", card="P1"))
            if self.p2_from is not None and quarter >= self.p2_from:
                acts.append(dict(type="queue_add", card="P2"))
            if self.d4 and quarter == 4:
                acts.append(dict(type="queue_add", card="D4"))
        queued = len(view["queue"]) + sum(1 for a in acts if a["type"] == "queue_add")
        for cid in self._candidates(view):
            if queued >= QUEUE_TARGET:
                break
            acts.append(dict(type="queue_add", card=cid))
            queued += 1
        return acts


# Strategy rules, fixed before the first balance run. One change each from measured-risk.
STRATEGY_SPECS = [
    ("measured-risk", dict()),
    ("maximum-caution", dict(quality="high", p1_from=1, p2_from=1)),
    ("corner-cutter", dict(quality="low", incident="patch", p1_from=None, d4=False)),
    ("no-reports", dict(reports=False, order="pitch")),
    ("whale-chaser", dict(bespoke=True, whale_first=True)),
    ("late-sprinter", dict(sprint_week=40)),
    ("fixed-plan", dict(act_once=True)),
    ("do-nothing", dict(idle=True)),
]
SINGLE_TACTIC = ["maximum-caution", "corner-cutter", "no-reports", "whale-chaser",
                 "late-sprinter", "fixed-plan"]


def make_strategy(name):
    for n, kw in STRATEGY_SPECS:
        if n == name:
            return Policy(n, **kw)
    raise KeyError(name)


def do_nothing(view, day):
    return []


def smoke_builder(view, day):
    """Queue three Q1 cards on day 0 in Medium quality, then do nothing."""
    if day != 0:
        return []
    return [dict(type="set_quality", mode="medium"),
            dict(type="queue_add", card="A2"),
            dict(type="queue_add", card="A3"),
            dict(type="queue_add", card="A4")]


# --- runner ---------------------------------------------------------------
def run_game(cfg, teams, seed=1):
    """Run scripted teams for a full game.

    teams is a list of (team_no, name, strategy). Returns a result per team with
    its action log, final state, final score and weekly ARR.
    """
    states = {n: engine.new_state(cfg, n, seed) for n, _, _ in teams}
    logs = {n: [] for n, _, _ in teams}
    weekly = {n: [] for n, _, _ in teams}
    award_day = cfg["B1_APPLY_LAST_WEEK"] * cfg["DAYS_PER_WEEK"]
    for day in range(cfg["TOTAL_DAYS"]):
        if day == award_day:
            for n in engine.resolve_b1_awards(cfg, list(states.values())):
                action = dict(type="award_bespoke")
                engine.apply(cfg, states[n], action)
                logs[n].append((day, action))
        for n, _, strategy in teams:
            state = states[n]
            view = engine.team_view(cfg, state, series_days=1)
            wants = getattr(strategy, "wants_detail", None)
            if wants is not None and wants(view):
                view = engine.team_view(cfg, state, series_days=DETAIL_DAYS, include_slices=True)
            for action in strategy(view, day):
                engine.apply(cfg, state, action)
                logs[n].append((day, action))
            engine.step(cfg, state)
            if (day + 1) % cfg["DAYS_PER_WEEK"] == 0:
                weekly[n].append(engine.score(cfg, state)["arr"])
    return {n: dict(name=name, log=logs[n], state=states[n], score=engine.score(cfg, states[n]),
                    weekly=weekly[n]) for n, name, _ in teams}


def league_teams():
    """Every strategy in COPIES copies; team numbers cover each incident variant."""
    teams = []
    for i, (name, _) in enumerate(STRATEGY_SPECS):
        for v in range(COPIES):
            teams.append((COPIES * (i + 1) + v, name, make_strategy(name)))
    return teams


def summarize(cfg, results):
    """Per-strategy mean, min and max across copies, sorted by mean NEV."""
    mid = cfg["WEEKS"] // 2 - 1
    groups = {}
    for r in results.values():
        groups.setdefault(r["name"], []).append(r)
    rows = []
    for name, rs in groups.items():
        nev = [r["score"]["nev"] for r in rs]
        rows.append(dict(
            name=name, copies=len(rs),
            arr26=statistics.mean(r["weekly"][mid] for r in rs),
            arr52=statistics.mean(r["weekly"][-1] for r in rs),
            trust=statistics.mean(r["score"]["trust_avg"] for r in rs),
            uod=statistics.mean(r["score"]["uod"] for r in rs),
            penalty=statistics.mean(r["score"]["penalty"] for r in rs),
            nev=statistics.mean(nev), nev_min=min(nev), nev_max=max(nev)))
    rows.sort(key=lambda r: -r["nev"])
    return rows


def run_league(cfg, seed=1):
    return summarize(cfg, run_game(cfg, league_teams(), seed))


def criteria(rows):
    """The four balance criteria as (label, passed, detail)."""
    by = {r["name"]: r for r in rows}
    winner = rows[0]
    m, c = by["measured-risk"], by["corner-cutter"]
    lead26 = max(rows, key=lambda r: r["arr26"])
    rank = [r["name"] for r in rows].index("fixed-plan") + 1
    closest = max((by[n] for n in SINGLE_TACTIC), key=lambda r: r["nev"])
    return [
        ("measured-risk wins", winner["name"] == "measured-risk",
         "winner %s at %.1f, measured-risk %.1f" % (winner["name"], winner["nev"], m["nev"])),
        ("corner-cutter leads ARR at week 26 and loses by week 52",
         lead26["name"] == "corner-cutter" and c["nev"] < winner["nev"]
         and winner["name"] != "corner-cutter",
         "week-26 leader %s at %.2f, corner-cutter %.2f; corner-cutter NEV %.1f vs winner %.1f"
         % (lead26["name"], lead26["arr26"], c["arr26"], c["nev"], winner["nev"])),
        ("fixed plan finishes in the bottom half", rank > len(rows) / 2,
         "fixed-plan rank %d of %d" % (rank, len(rows))),
        ("no single-tactic strategy within 5% of the winner",
         winner["name"] not in SINGLE_TACTIC and closest["nev"] <= 0.95 * winner["nev"],
         "closest single-tactic %s at %.1f, %.1f%% of winner"
         % (closest["name"], closest["nev"], 100 * closest["nev"] / winner["nev"])),
    ]


def results_table(rows):
    lines = ["%-16s %8s %8s %6s %6s %5s %8s %8s %8s" % (
        "strategy", "ARR wk26", "ARR wk52", "trust", "UOD", "pen", "NEV", "NEV min", "NEV max")]
    for r in rows:
        lines.append("%-16s %8.2f %8.2f %6.1f %6.1f %5.1f %8.1f %8.1f %8.1f" % (
            r["name"], r["arr26"], r["arr52"], r["trust"], r["uod"], r["penalty"],
            r["nev"], r["nev_min"], r["nev_max"]))
    return "\n".join(lines)


def criteria_lines(rows):
    return "\n".join("%s  %s (%s)" % ("PASS" if ok else "FAIL", label, detail)
                     for label, ok, detail in criteria(rows))


def main():
    cfg = config.load()
    rows = run_league(cfg)
    print(results_table(rows))
    print()
    print(criteria_lines(rows))
    quiet = config.load(dict(EVENTS_ENABLED={k: False for k in cfg["EVENTS_ENABLED"]}))
    base = run_game(quiet, [(1, "do-nothing", do_nothing)])[1]
    print("\nDo-nothing with scripted events off: ARR %.3f at week 26, %.3f at week 52"
          % (base["weekly"][cfg["WEEKS"] // 2 - 1], base["weekly"][-1]))


if __name__ == "__main__":
    main()
