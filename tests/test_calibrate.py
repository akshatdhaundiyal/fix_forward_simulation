import json
import os
import tempfile
import unittest

import helpers
import calibrate
import config
import engine


class LiftCapTests(unittest.TestCase):
    def test_retention_lift_above_one_gives_zero_churn_not_negative(self):
        lifts = dict(config.LIFTS, B3=1.5)
        cfg = helpers.make_cfg(LIFTS=lifts)
        state = engine.new_state(cfg, 1, 1)
        state["day"] = 91
        helpers.ship(cfg, state, "B3")
        self.assertEqual(engine.stage_rates(cfg, state, "M")["churn"], 0.0)


class CalibrationFileTests(unittest.TestCase):
    def _file(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        self.addCleanup(os.remove, path)
        return path

    def test_load_reads_lifts_and_noise_from_the_file(self):
        path = self._file(dict(lifts={"A1": 0.7}, noise={"p99": 0.2}))
        cfg = config.load(dict(CALIBRATION_FILE=path))
        self.assertEqual(cfg["LIFTS"]["A1"], 0.7)
        self.assertEqual(cfg["LIFTS"]["A2"], config.PLACEHOLDER_LIFT)
        self.assertEqual(cfg["NOISE"]["p99"], 0.2)

    def test_flag_and_explicit_override_both_beat_the_file(self):
        path = self._file(dict(lifts={"A1": 0.7}))
        off = config.load(dict(CALIBRATION_FILE=path), calibrated=False)
        self.assertEqual(off["LIFTS"]["A1"], config.PLACEHOLDER_LIFT)
        pinned = config.load(dict(CALIBRATION_FILE=path, LIFTS=dict(config.LIFTS, A1=0.1)))
        self.assertEqual(pinned["LIFTS"]["A1"], 0.1)

    def test_unknown_card_in_the_file_is_rejected(self):
        path = self._file(dict(lifts={"Z9": 0.7}))
        with self.assertRaises(ValueError):
            config.load(dict(CALIBRATION_FILE=path))

    def test_missing_file_falls_back_to_placeholders(self):
        cfg = config.load(dict(CALIBRATION_FILE="calibration/does-not-exist.json"))
        self.assertEqual(cfg["LIFTS"]["A1"], config.PLACEHOLDER_LIFT)


class SolverTests(unittest.TestCase):
    def test_reachable_card_solves_to_its_target(self):
        card = config.load(calibrated=False)["CARD_BY_ID"]["A6"]
        solved = calibrate.solve_card(None, card)
        self.assertEqual(solved["status"], "solved")
        gain, _ = calibrate.card_gain(None, "A6", solved["lift"])
        self.assertAlmostEqual(gain, 0.9, delta=config.CALIBRATION_TOLERANCE)

    def test_unreachable_card_keeps_the_cap_and_says_so(self):
        card = config.load(calibrated=False)["CARD_BY_ID"]["B2"]
        solved = calibrate.solve_card(None, card)
        self.assertEqual(solved["status"], "unreachable")
        self.assertEqual(solved["lift"], config.LIFT_CAPS["retention"])
        self.assertLess(solved["achieved"], 1.2)

    def test_solving_twice_gives_the_same_answer(self):
        card = config.load(calibrated=False)["CARD_BY_ID"]["A5"]
        self.assertEqual(calibrate.solve_card(None, card), calibrate.solve_card(None, card))

    def test_gain_at_zero_lift_is_only_debt_drag(self):
        gain, _ = calibrate.card_gain(None, "A6", 0.0)
        self.assertLessEqual(gain, 0.0)

    def test_gain_rises_with_lift(self):
        low, _ = calibrate.card_gain(None, "A3", 0.2)
        high, _ = calibrate.card_gain(None, "A3", 0.6)
        self.assertLess(low, high)

    def test_unlock_day_follows_the_quarter(self):
        cfg = config.load(calibrated=False)
        by = cfg["CARD_BY_ID"]
        self.assertEqual([calibrate.unlock_day(cfg, by[c]) for c in ("A1", "B2", "C2", "D1")],
                         [0, 91, 182, 273])


class NoiseRuleTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config.load(calibrated=False)

    def test_flat_then_rising_series_meets_the_rule(self):
        series = [1.0] * 84 + [1.0 + 0.02 * i for i in range(98)]
        pick = calibrate.pick_noise_level(series, self.cfg)
        self.assertTrue(pick["rule_met"])
        self.assertLessEqual(pick["one_quarter"], calibrate.NOISE_MAX_RATIO_ONE_QUARTER)
        self.assertGreaterEqual(pick["two_quarters"], calibrate.NOISE_MIN_RATIO_TWO_QUARTERS)

    def test_steep_early_rise_cannot_meet_the_rule(self):
        series = [1.0 + 0.1 * i for i in range(182)]
        self.assertFalse(calibrate.pick_noise_level(series, self.cfg)["rule_met"])


class WhatIfTests(unittest.TestCase):
    def test_rows_override_in_memory_and_leave_config_untouched(self):
        cards = [dict(id="B2", status="unreachable", max_gain=0.75),
                 dict(id="A6", status="solved", max_gain=17.8)]
        rows = calibrate.what_if_rows(dict(cards=cards))
        label, overrides, resolve = rows[0]
        self.assertEqual(config.load(overrides, calibrated=False)["REPORT_COST"], 2)
        self.assertEqual(config.REPORT_COST, 4)
        retarget = [r for r in rows if "unreachable targets" in r[0]][0]
        self.assertTrue(retarget[2])
        new_gain = {c["id"]: c["gain"] for c in retarget[1]["CARDS"]}["B2"]
        self.assertAlmostEqual(new_gain, 0.6)
        self.assertEqual({c["id"]: c["gain"] for c in config.CARDS}["B2"], 1.2)


if __name__ == "__main__":
    unittest.main()
