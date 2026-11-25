import os
import shutil
import tempfile
import unittest

import config
import engine
import game as gamemod
import gamehelpers as gh
import helpers
from test_server import ServerCase

SEGS = config.SEGMENT_ORDER


def rec(week, uod, arr):
    """A daily record for the last day of a week, the shape engine._record_day writes."""
    return dict(day=week * 7 - 1, uod=uod, slow=False, inc_segs=[],
                trust={s: 60.0 for s in SEGS},
                seg={s: dict(arr=arr / len(SEGS), accounts=1.0, new=0.0, lost=0.0, rates={}) for s in SEGS})


def curve(weeks, uod, arr):
    return [rec(w, uod(w), arr(w)) for w in range(1, weeks + 1)]


def rig(game, histories, penalties):
    """Give each team a made-up weekly history and a valuation penalty, then reveal."""
    for n, history in histories.items():
        game.states[n]["history"] = history
        game.states[n]["penalty"] = penalties.get(n, 100.0)
    game.reveal()


class DebriefTests(unittest.TestCase):
    def game(self, teams=4):
        g, ft, d = gh.open_game(self, teams=teams)
        return g

    def test_it_refuses_until_the_final_reveal(self):
        g = self.game()
        self.assertIsNone(g.debrief())
        g.reveal()
        self.assertIsNotNone(g.debrief())

    def test_the_three_teams_are_chosen_by_rule(self):
        g = self.game()
        rig(g, {
            1: curve(52, lambda w: 5, lambda w: 30 if w <= 26 else 20),     # leads at week 26, falls after
            2: curve(52, lambda w: 5, lambda w: 10 + w * 0.3),               # steady climber
            3: curve(52, lambda w: 5, lambda w: 25 if w <= 20 else 5),       # peaks 25, ends 5: falls 20
            4: curve(52, lambda w: 5, lambda w: 20),
        }, penalties={2: 0.0})                                              # team 2 has the best valuation
        out = g.debrief()
        roles = {t["team"]: t["roles"] for t in out["teams"]}
        self.assertEqual(roles[1], ["week26_leader"])
        self.assertEqual(roles[2], ["winner"])
        self.assertEqual(roles[3], ["biggest_collapse"])
        self.assertNotIn(4, roles)

    def test_one_team_filling_two_roles_appears_once_with_both_roles(self):
        g = self.game(teams=3)
        rig(g, {
            1: curve(52, lambda w: 5, lambda w: 40 if w <= 30 else 10),     # leader at 26 and biggest fall
            2: curve(52, lambda w: 5, lambda w: 20),
            3: curve(52, lambda w: 5, lambda w: 15),
        }, penalties={2: 0.0})
        out = g.debrief()
        by_team = {t["team"]: t for t in out["teams"]}
        self.assertEqual(sorted(by_team[1]["roles"]), ["biggest_collapse", "week26_leader"])
        self.assertEqual(len([t for t in out["teams"] if t["team"] == 1]), 1)

    def test_ties_go_to_the_lower_team_number(self):
        g = self.game(teams=3)
        same = lambda: curve(52, lambda w: 5, lambda w: 20)
        rig(g, {1: same(), 2: same(), 3: same()}, penalties={1: 50.0, 2: 50.0, 3: 50.0})
        roles = {t["team"]: t["roles"] for t in g.debrief()["teams"]}
        self.assertEqual(roles, {1: ["week26_leader", "winner", "biggest_collapse"]})

    def test_the_band_series_follows_the_cto_thresholds_week_by_week(self):
        g = self.game(teams=2)
        uods = {10: 15.0, 11: 16.0, 12: 30.0, 13: 31.0}
        history = curve(52, lambda w: uods.get(w, 0.0), lambda w: 20)
        rig(g, {1: history, 2: curve(52, lambda w: 0, lambda w: 1)}, penalties={1: 0.0})
        series = {p["week"]: p for t in g.debrief()["teams"] if t["team"] == 1 for p in t["series"]}
        self.assertEqual([series[w]["band"] for w in (10, 11, 12, 13)], ["green", "amber", "amber", "red"])
        self.assertEqual(series[13]["debt"], 31.0)
        self.assertEqual(g.stakeholder_board()["teams"][0]["band"], engine.cto_band(g.cfg, g.states[1]["uod"]))

    def test_the_error_rate_is_the_figure_the_team_saw_on_its_dashboard(self):
        g = self.game(teams=2)
        history = curve(52, lambda w: 12.0, lambda w: 20)
        rig(g, {1: history, 2: history}, penalties={1: 0.0})
        point = next(p for t in g.debrief()["teams"] if t["team"] == 1 for p in t["series"] if p["week"] == 7)
        seen = engine._telemetry_point(g.cfg, g.states[1]["seed"], 1, history[6])["error_rate"]
        self.assertEqual(point["error_rate"], seen)

    def test_the_hidden_gains_come_from_the_calibrated_config(self):
        g = self.game()
        g.reveal()
        gains = {x["card"]: x for x in g.debrief()["gains"]}
        self.assertEqual(list(gains), ["A1", "B4", "C3"])
        for cid, x in gains.items():
            self.assertEqual(x["target_gain"], g.cfg["CALIBRATED_GAIN"].get(cid, g.cfg["CARD_BY_ID"][cid]["gain"]))
        self.assertEqual(gains["A1"]["name"], "AI Copilot")

    def test_a_real_game_to_the_end_gives_a_series_of_52_weeks_per_chosen_team(self):
        g, ft, d = gh.open_game(self, teams=3)
        g.clock_op("resume")
        gh.advance_days(g, ft, 364)
        g.reveal()
        out = g.debrief()
        self.assertTrue(out["teams"])
        for t in out["teams"]:
            self.assertEqual([p["week"] for p in t["series"]], list(range(1, 53)))

    def test_after_a_start_from_a_snapshot_it_answers_with_the_history_it_has(self):
        g, ft, d = gh.open_game(self, teams=3)
        g.clock_op("resume")
        gh.advance_days(g, ft, 40)
        snap = g.snapshot_now()
        path = os.path.join(d, "state", "snapshots", snap + ".json")
        out_dir = os.path.join(tempfile.mkdtemp(), "state")
        self.addCleanup(shutil.rmtree, os.path.dirname(out_dir), True)
        gamemod.start_from_snapshot(g.cfg, path, out_dir)
        again = gamemod.Game(g.cfg, out_dir, now=gh.FakeTime())
        self.addCleanup(again.close)
        again.reveal()
        out = again.debrief()
        self.assertTrue(out["gains"])
        for t in out["teams"]:
            self.assertEqual(t["series"], [])           # no history before the baseline day
        self.assertNotIn("week26_leader", [r for t in out["teams"] for r in t["roles"]])


class DebriefEdgeTests(unittest.TestCase):
    def test_a_team_with_only_late_history_is_never_the_week_26_leader_but_can_have_a_fall(self):
        g, ft, d = gh.open_game(self, teams=3)
        rig(g, {
            1: curve(52, lambda w: 5, lambda w: 10),
            2: [r for r in curve(52, lambda w: 5, lambda w: 50 if w <= 40 else 5) if r["day"] > 26 * 7],  # starts after week 26
            3: curve(52, lambda w: 5, lambda w: 12),
        }, penalties={1: 0.0})
        roles = {t["team"]: t["roles"] for t in g.debrief()["teams"]}
        self.assertEqual(roles[3], ["week26_leader"])
        self.assertIn("biggest_collapse", roles[2])

    def test_every_team_starting_after_week_26_leaves_no_leader_and_does_not_fail(self):
        g, ft, d = gh.open_game(self, teams=2)
        late = lambda: [r for r in curve(52, lambda w: 5, lambda w: 20) if r["day"] > 26 * 7]
        rig(g, {1: late(), 2: late()}, penalties={1: 0.0})
        roles = [r for t in g.debrief()["teams"] for r in t["roles"]]
        self.assertNotIn("week26_leader", roles)
        self.assertIn("winner", roles)

    def test_the_result_is_cached_until_the_log_moves(self):
        g, ft, d = gh.open_game(self, teams=2)
        g.reveal()
        first = g.debrief()
        self.assertIs(g.debrief(), first)
        g.submit(1, dict(type="set_quality", mode="high"))
        self.assertIsNot(g.debrief(), first)


class DebriefRouteTests(ServerCase):
    def test_the_route_is_403_before_the_reveal_and_json_after(self):
        status, data = self.call("GET", "/api/debrief")
        self.assertEqual(status, 403)
        self.assertNotIn("teams", data)
        self.g.reveal()
        status, data = self.call("GET", "/api/debrief")
        self.assertEqual(status, 200)
        self.assertEqual(set(data), {"weeks", "band_limits", "teams", "gains"})
        self.assertEqual(data["band_limits"], list(self.g.cfg["CTO_BAND_LIMITS"]))

    def test_hidden_debt_stays_off_every_other_route_before_the_reveal(self):
        hidden = set(self.g.cfg["HIDDEN_FIELD_NAMES"])
        self.g.states[1]["uod"] = 12.345
        for path in ("/api/team/%s/view" % self.codes[1], "/api/calendar", "/api/clock"):
            _, body = self.call("GET", path)
            self.assertFalse(helpers.all_keys(body) & hidden, path)
            self.assertNotIn("12.345", str(body))
        _, projector = self.call("GET", "/api/projector")
        self.assertFalse(helpers.all_keys(projector) & {"uod", "nev", "penalty", "debt"})
        self.assertNotIn("12.345", str(projector))


if __name__ == "__main__":
    unittest.main()
