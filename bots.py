"""Scripted teams, headless runner and results table.

A strategy is a function (view, day) -> list of actions. It only ever sees the
team view, so a scripted team cannot read hidden state. Run `python bots.py`
for the stage 1 table.
"""
import config
import engine


# --- strategies -----------------------------------------------------------
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


STRATEGIES = {"do-nothing": do_nothing, "smoke-builder": smoke_builder}


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
            for action in strategy(view, day):
                engine.apply(cfg, state, action)
                logs[n].append((day, action))
            engine.step(cfg, state)
            if (day + 1) % cfg["DAYS_PER_WEEK"] == 0:
                weekly[n].append(engine.score(cfg, state)["arr"])
    return {n: dict(name=name, log=logs[n], state=states[n], score=engine.score(cfg, states[n]),
                    weekly=weekly[n]) for n, name, _ in teams}


def results_table(cfg, results):
    mid = cfg["WEEKS"] // 2
    lines = ["%-16s %10s %10s %7s %9s" % ("strategy", "ARR wk26", "ARR wk52", "trust", "NEV")]
    for r in results.values():
        lines.append("%-16s %10.3f %10.3f %7.1f %9.2f" % (
            r["name"], r["weekly"][mid - 1], r["weekly"][-1], r["score"]["trust_avg"],
            r["score"]["nev"]))
    return "\n".join(lines)


def main():
    cfg = config.load()
    teams = [(i + 1, name, fn) for i, (name, fn) in enumerate(STRATEGIES.items())]
    print("With scripted events (incidents, peak season, churn alerts):")
    print(results_table(cfg, run_game(cfg, teams)))
    quiet = config.load(dict(EVENTS_ENABLED={k: False for k in cfg["EVENTS_ENABLED"]}))
    print("\nWith scripted events off (pure funnel check):")
    print(results_table(quiet, run_game(quiet, teams)))


if __name__ == "__main__":
    main()
