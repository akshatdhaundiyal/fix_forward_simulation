import unittest

import helpers
import engine


class PeakSeasonTests(unittest.TestCase):
    def _at_week_27(self, uod):
        cfg = helpers.make_cfg(events={"peak_season": True})
        state = engine.new_state(cfg, 1, 1)
        state["day"] = 27 * 7
        state["uod"] = float(uod)
        return cfg, state

    def test_uod_40_holds_and_adds_trust(self):
        cfg, state = self._at_week_27(40)
        engine.step(cfg, state)
        for s in cfg["SEGMENT_ORDER"]:
            self.assertAlmostEqual(state["seg"][s]["trust"], 65.0)
        self.assertEqual(state["penalty"], 0.0)

    def test_uod_41_owes_eleven_bu_penalty_and_whale_trust(self):
        cfg, state = self._at_week_27(41)
        engine.step(cfg, state)
        self.assertAlmostEqual(state["penalty"], 3.0)
        self.assertAlmostEqual(state["seg"]["W"]["trust"], 25.0)
        self.assertAlmostEqual(state["seg"]["M"]["trust"], 60.0)
        helpers.run_days(cfg, state, 14)
        self.assertEqual(state["rework_owed"], 0.0)
        self.assertAlmostEqual(state["uod"], 30.0)

    def test_rework_is_capped_at_fifty(self):
        cfg, state = self._at_week_27(90)
        engine.step(cfg, state)
        self.assertAlmostEqual(state["rework_owed"] + (90 - state["uod"]), 50.0)

    def test_outage_seizes_capacity_before_the_queue(self):
        cfg, state = self._at_week_27(41)
        engine.apply(cfg, state, dict(type="queue_add", card="A6"))
        engine.step(cfg, state)
        self.assertEqual(state["queue"][0]["progress"], 0.0)


class AlertTests(unittest.TestCase):
    def _run_week_39(self, shipped=()):
        cfg = helpers.make_cfg(events={"churn_alerts": True})
        state = engine.new_state(cfg, 1, 1)
        state["day"] = 38 * 7
        for c in shipped:
            state["shipped"][c] = dict(card=c, day=0, seg=None, stage=None, lift=0.0,
                                       debt=0.0, trust={}, bespoke=False)
        before = state["seg"]["W"]["accounts"]
        helpers.run_days(cfg, state, 7)
        return cfg, state, before

    def test_without_b2_whale_loses_arr_and_trust(self):
        cfg, state, before = self._run_week_39()
        self.assertAlmostEqual(before - state["seg"]["W"]["accounts"], 3.0 / 0.5)
        self.assertAlmostEqual(state["seg"]["W"]["trust"], 50.0)

    def test_without_b3_mid_market_trust_falls(self):
        cfg, state, _ = self._run_week_39()
        self.assertAlmostEqual(state["seg"]["M"]["trust"], 45.0)

    def test_with_b2_and_b3_nothing_happens(self):
        cfg, state, before = self._run_week_39(("B2", "B3"))
        self.assertAlmostEqual(state["seg"]["W"]["accounts"], before)
        self.assertEqual(state["seg"]["W"]["trust"], 60.0)
        self.assertEqual(state["seg"]["M"]["trust"], 60.0)


class LeagueTests(unittest.TestCase):
    def _states(self, trusts):
        cfg = helpers.make_cfg()
        out = []
        for team, trust in trusts:
            s = engine.new_state(cfg, team, 1)
            s["seg"]["W"]["trust"] = trust
            s["b1_applied"] = True
            out.append(s)
        return cfg, out

    def test_top_five_by_whale_trust_win(self):
        trusts = [(1, 61), (2, 80), (3, 70), (4, 90), (5, 65), (6, 75), (7, 50)]
        cfg, states = self._states(trusts)
        self.assertEqual(sorted(engine.resolve_b1_awards(cfg, states)), [2, 3, 4, 5, 6])
        self.assertEqual(sorted(engine.resolve_b1_awards(cfg, list(reversed(states)))),
                         [2, 3, 4, 5, 6])

    def test_tie_goes_to_lower_team_number(self):
        trusts = [(1, 90), (2, 90), (3, 90), (4, 90), (9, 60), (5, 60)]
        cfg, states = self._states(trusts)
        self.assertEqual(sorted(engine.resolve_b1_awards(cfg, states)), [1, 2, 3, 4, 5])

    def test_non_applicants_never_win(self):
        cfg, states = self._states([(1, 90), (2, 80)])
        states[0]["b1_applied"] = False
        self.assertEqual(engine.resolve_b1_awards(cfg, states), [2])

    def test_application_window(self):
        cfg = helpers.make_cfg()
        state = engine.new_state(cfg, 1, 1)
        state["day"] = 130
        self.assertFalse(engine.apply(cfg, state, dict(type="apply_b1"))["ok"])
        state["day"] = 100
        self.assertTrue(engine.apply(cfg, state, dict(type="apply_b1"))["ok"])

    def test_decline_result_moves_whale_trust(self):
        cfg = helpers.make_cfg()
        for ticks, delta in ((3, 5), (2, 0), (1, -5), (0, -5)):
            state = engine.new_state(cfg, 1, 1)
            engine.apply(cfg, state, dict(type="decline_result", ticks=ticks))
            self.assertEqual(state["seg"]["W"]["trust"], 60 + delta)


if __name__ == "__main__":
    unittest.main()
