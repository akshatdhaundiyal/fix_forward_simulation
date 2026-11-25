import unittest

import helpers
import engine


class OutageFlagTests(unittest.TestCase):
    def _at_week_27(self, uod):
        cfg = helpers.make_cfg(events={"peak_season": True})
        state = engine.new_state(cfg, 1, 1)
        state["day"] = 27 * 7
        state["uod"] = float(uod)
        return cfg, state

    def test_no_outage_flag_in_a_fresh_view(self):
        cfg = helpers.make_cfg()
        state = engine.new_state(cfg, 1, 1)
        self.assertIs(engine.team_view(cfg, state, series_days=1)["outage"], False)

    def test_outage_flag_is_true_while_rework_is_owed_and_false_once_paid(self):
        cfg, state = self._at_week_27(60)
        engine.step(cfg, state)
        self.assertIs(engine.team_view(cfg, state, series_days=1)["outage"], True)
        helpers.run_days(cfg, state, 28)
        self.assertEqual(state["rework_owed"], 0.0)
        self.assertIs(engine.team_view(cfg, state, series_days=1)["outage"], False)

    def test_a_team_at_the_threshold_never_has_an_outage(self):
        cfg, state = self._at_week_27(40)
        engine.step(cfg, state)
        self.assertIs(engine.team_view(cfg, state, series_days=1)["outage"], False)

    def test_the_view_never_carries_the_owed_amount(self):
        cfg, state = self._at_week_27(60)
        engine.step(cfg, state)
        view = engine.team_view(cfg, state, series_days=1)
        self.assertFalse(helpers.all_keys(view) & set(cfg["HIDDEN_FIELD_NAMES"]))
        self.assertNotIn("rework_owed", helpers.all_keys(view))


if __name__ == "__main__":
    unittest.main()
