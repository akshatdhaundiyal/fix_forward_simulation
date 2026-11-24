import unittest

import helpers
import config
import engine


def config_loaded(**overrides):
    """Config with the calibration file applied (helpers.make_cfg pins placeholder lifts)."""
    return config.load(overrides)


def add(cfg, state, card):
    r = engine.apply(cfg, state, dict(type="queue_add", card=card))
    return r


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.cfg = helpers.make_cfg()
        self.state = engine.new_state(self.cfg, 1, 1)

    def test_medium_quality_ship_timing(self):
        add(self.cfg, self.state, "A2")  # 20 BU at 0.9 * 8 / 7 per day
        helpers.run_days(self.cfg, self.state, 19)
        self.assertNotIn("A2", self.state["shipped"])
        helpers.run_days(self.cfg, self.state, 1)
        self.assertIn("A2", self.state["shipped"])

    def test_reorder_pauses_item_and_keeps_progress(self):
        add(self.cfg, self.state, "A2")
        add(self.cfg, self.state, "A3")
        helpers.run_days(self.cfg, self.state, 5)
        first, second = self.state["queue"]
        kept = first["progress"]
        self.assertGreater(kept, 0)
        engine.apply(self.cfg, self.state, dict(type="queue_reorder", item=second["id"], position=0))
        helpers.run_days(self.cfg, self.state, 1)
        self.assertEqual(first["progress"], kept)
        self.assertGreater(second["progress"], 0)

    def test_removing_part_built_item_loses_progress(self):
        add(self.cfg, self.state, "A2")
        helpers.run_days(self.cfg, self.state, 8)
        item = self.state["queue"][0]
        engine.apply(self.cfg, self.state, dict(type="queue_remove", item=item["id"]))
        self.assertEqual(self.state["queue"], [])
        add(self.cfg, self.state, "A2")
        self.assertEqual(self.state["queue"][0]["progress"], 0.0)

    def test_debt_is_bu_weighted_average_across_modes(self):
        add(self.cfg, self.state, "A2")  # risk 3, 20 BU
        engine.apply(self.cfg, self.state, dict(type="set_quality", mode="low"))
        helpers.run_days(self.cfg, self.state, 9)
        built_low = self.state["queue"][0]["progress"]
        engine.apply(self.cfg, self.state, dict(type="set_quality", mode="high"))
        while "A2" not in self.state["shipped"]:
            engine.step(self.cfg, self.state)
        expected = 3 * (built_low * 1.6 + (20 - built_low) * 0.35) / 20
        self.assertAlmostEqual(self.state["uod"], expected)
        self.assertGreater(self.state["uod"], 3 * 0.35)

    def test_leftover_capacity_flows_to_next_item_same_day(self):
        cfg = helpers.make_cfg(CAPACITY_BU_PER_WEEK=70.0)
        state = engine.new_state(cfg, 1, 1)
        add(cfg, state, "A6")  # 15 BU, 9 BU per day available
        add(cfg, state, "A2")
        helpers.run_days(cfg, state, 2)
        self.assertIn("A6", state["shipped"])
        self.assertAlmostEqual(state["queue"][0]["progress"], 18 - 15, places=6)

    def test_bespoke_contract_cuts_capacity_and_adds_arr(self):
        engine.apply(self.cfg, self.state, dict(type="award_bespoke"))
        while "B1" not in self.state["shipped"]:
            engine.step(self.cfg, self.state)
        self.assertEqual(self.state["bespoke_n"], 1)
        self.assertEqual(self.state["bespoke_arr"], 5.0)
        view = engine.team_view(self.cfg, self.state, series_days=1)
        self.assertAlmostEqual(view["tiles"]["capacity_bu_week"], 7.2)
        self.assertAlmostEqual(self.state["seg"]["W"]["trust"], 70.0)

    def test_report_shows_utility_for_unlocked_cards_only(self):
        engine.apply(self.cfg, self.state, dict(type="queue_add", report="M"))
        helpers.run_days(self.cfg, self.state, 5)
        rep = self.state["reports"][0]
        self.assertEqual(rep["utility"]["A1"], 15)
        self.assertEqual(rep["utility"]["A3"], round(100 * 1.9 / 2.5))
        self.assertNotIn("B3", rep["utility"])
        self.assertTrue(rep["alerts"])

    def _report_utility(self, cfg, seg, until_quarter_card):
        state = engine.new_state(cfg, 1, 1)
        state["day"] = cfg["DAYS_PER_WEEK"] * cfg["WEEKS_PER_QUARTER"] * (until_quarter_card - 1)
        engine.apply(cfg, state, dict(type="queue_add", report=seg))
        helpers.run_days(cfg, state, 6)
        return state["reports"][0]["utility"]

    def test_report_utility_uses_calibrated_gain_for_unreachable_cards(self):
        cfg = config_loaded(RECORD_SLICES=False, EVENTS_ENABLED=dict(
            incidents=False, peak_season=False, churn_alerts=False))
        util = self._report_utility(cfg, "M", 2)
        calibrated = cfg["CALIBRATED_GAIN"]["B3"]
        self.assertLess(calibrated, cfg["CARD_BY_ID"]["B3"]["gain"])
        self.assertEqual(util["B3"], round(100 * calibrated / cfg["CARD_BY_ID"]["B3"]["pitch"]))
        self.assertLess(util["B3"], round(100 * 2.4 / 3.0))

    def test_report_utility_matches_target_for_solved_cards(self):
        cfg = config_loaded(RECORD_SLICES=False, EVENTS_ENABLED=dict(
            incidents=False, peak_season=False, churn_alerts=False))
        util = self._report_utility(cfg, "M", 2)
        self.assertEqual(util["A3"], round(100 * 1.9 / 2.5))

    def test_report_utility_falls_back_to_target_without_calibration(self):
        cfg = config.load(dict(RECORD_SLICES=False, EVENTS_ENABLED=dict(
            incidents=False, peak_season=False, churn_alerts=False)), calibrated=False)
        util = self._report_utility(cfg, "M", 2)
        self.assertEqual(util["B3"], round(100 * 2.4 / 3.0))

    def test_standing_card_once_per_quarter(self):
        self.assertTrue(add(self.cfg, self.state, "P1")["ok"])
        self.assertFalse(add(self.cfg, self.state, "P1")["ok"])
        while self.state["queue"]:
            engine.step(self.cfg, self.state)
        self.assertFalse(add(self.cfg, self.state, "P1")["ok"])
        helpers.run_days(self.cfg, self.state, 91 - self.state["day"])
        self.assertTrue(add(self.cfg, self.state, "P1")["ok"])

    def test_locked_card_is_refused(self):
        self.assertFalse(add(self.cfg, self.state, "B3")["ok"])

    def test_rollback_restores_effects_and_halves_reship_cost(self):
        helpers.ship(self.cfg, self.state, "A2")
        self.assertAlmostEqual(self.state["seg"]["S"]["trust"], 65.0)
        lifted = engine.stage_rates(self.cfg, self.state, "S")["activation"]
        self.assertGreater(lifted, 0.5)
        self.assertTrue(engine.apply(self.cfg, self.state, dict(type="rollback", card="A2"))["ok"])
        helpers.run_days(self.cfg, self.state, 7)  # a full week of days still carries it
        self.assertIn("A2", self.state["shipped"])
        helpers.run_days(self.cfg, self.state, 1)  # gone from the first day of the next week
        self.assertNotIn("A2", self.state["shipped"])
        self.assertAlmostEqual(self.state["seg"]["S"]["trust"], 60 - 3.0)
        self.assertAlmostEqual(self.state["uod"], 0.0)
        self.assertAlmostEqual(engine.stage_rates(self.cfg, self.state, "S")["activation"], 0.5)
        add(self.cfg, self.state, "A2")
        self.assertEqual(self.state["queue"][0]["cost"], 10.0)

    def test_bespoke_cannot_be_rolled_back(self):
        engine.apply(self.cfg, self.state, dict(type="award_bespoke"))
        while "B1" not in self.state["shipped"]:
            engine.step(self.cfg, self.state)
        self.assertFalse(engine.apply(self.cfg, self.state, dict(type="rollback", card="B1"))["ok"])

    def test_three_queued_cards_ship_in_order_with_expected_debt(self):
        for c in ("A2", "A3", "A4"):
            add(self.cfg, self.state, c)
        order = []
        for _ in range(120):
            engine.step(self.cfg, self.state)
            for c in ("A2", "A3", "A4"):
                if c in self.state["shipped"] and c not in order:
                    order.append(c)
        self.assertEqual(order, ["A2", "A3", "A4"])
        self.assertAlmostEqual(self.state["uod"], 3 + 5 + 6)


if __name__ == "__main__":
    unittest.main()
