import unittest

import helpers
import bots
import config
import engine


class ConfigTests(unittest.TestCase):
    def test_starting_arr_sums_to_25(self):
        cfg = config.load()
        total = sum(s["accounts"] * s["arr_per_account"] for s in cfg["SEGMENTS"].values())
        self.assertAlmostEqual(total, 25.0, places=9)

    def test_load_returns_independent_copy(self):
        a = config.load()
        a["LIFTS"]["A1"] = 0.9
        self.assertEqual(config.load(calibrated=False)["LIFTS"]["A1"], config.PLACEHOLDER_LIFT)

    def test_card_table_matches_spec(self):
        cfg = config.load()
        by = cfg["CARD_BY_ID"]
        self.assertEqual(len(cfg["CARDS"]), 24)
        self.assertEqual((by["A1"]["cost"], by["A1"]["risk"], by["A1"]["gain"]), (35, 8, 0.9))
        self.assertEqual((by["B4"]["cost"], by["B4"]["risk"]), (35, 10))
        self.assertEqual((by["C3"]["cost"], by["C3"]["gain"]), (25, 1.0))
        self.assertEqual(by["D4"]["uod_delta"], -20)
        self.assertEqual(by["P1"]["uod_delta"], -12)

    def test_slice_shares_sum_to_one(self):
        for shares in config.SLICES.values():
            self.assertAlmostEqual(sum(shares.values()), 1.0)


class FunnelTests(unittest.TestCase):
    def test_do_nothing_holds_25_every_day(self):
        cfg = helpers.make_cfg()
        state = engine.new_state(cfg, 1, 1)
        for _ in range(cfg["TOTAL_DAYS"]):
            engine.step(cfg, state)
            self.assertAlmostEqual(engine.score(cfg, state)["arr"], 25.0, places=9)
        for s in cfg["SEGMENT_ORDER"]:
            self.assertEqual(state["seg"][s]["trust"], 60.0)
        self.assertEqual(state["uod"], 0.0)
        self.assertEqual(state["day"], 364)

    def test_do_nothing_with_scripted_events_falls_below_25(self):
        cfg = config.load()
        state = engine.new_state(cfg, 1, 1)
        for _ in range(cfg["TOTAL_DAYS"]):
            engine.step(cfg, state)
        self.assertLess(engine.score(cfg, state)["arr"], 25.0)

    def test_trust_scales_churn(self):
        cfg = helpers.make_cfg()
        state = engine.new_state(cfg, 1, 1)
        base = engine.stage_rates(cfg, state, "M")["churn"]
        state["seg"]["M"]["trust"] = 40.0
        self.assertAlmostEqual(engine.stage_rates(cfg, state, "M")["churn"], base * 1.4)
        state["seg"]["M"]["trust"] = 80.0
        self.assertAlmostEqual(engine.stage_rates(cfg, state, "M")["churn"], base * 0.6)

    def test_uod_cuts_activation(self):
        cfg = helpers.make_cfg()
        state = engine.new_state(cfg, 1, 1)
        state["uod"] = 50.0
        self.assertAlmostEqual(engine.stage_rates(cfg, state, "S")["activation"], 0.5 * 0.9)

    def _defect(self, segs, slice_, stage, mult):
        return dict(incident=9, segs=segs, stage=stage, slice=slice_, mult=mult, factor=1.0)

    def test_single_slice_defect_weights_segment_rate(self):
        cfg = helpers.make_cfg()
        state = engine.new_state(cfg, 1, 1)
        state["defects"].append(self._defect(["S"], {"platform": "mobile"}, "activation", 0.6))
        self.assertAlmostEqual(engine.stage_rates(cfg, state, "S")["activation"], 0.5 * (1 - 0.4 * 0.4))
        mobile = engine.stage_rates(cfg, state, "S", {"platform": "mobile"})["activation"]
        web = engine.stage_rates(cfg, state, "S", {"platform": "web"})["activation"]
        self.assertAlmostEqual(mobile, 0.5 * 0.6)
        self.assertAlmostEqual(web, 0.5)

    def test_two_dimension_defect_uses_product_of_shares(self):
        cfg = helpers.make_cfg()
        state = engine.new_state(cfg, 1, 1)
        state["defects"].append(self._defect(["M"], {"platform": "web", "cohort": "new"}, "paid", 0.5))
        frac = 0.6 * 0.15
        self.assertAlmostEqual(engine.stage_rates(cfg, state, "M")["paid"], 0.1 * (1 - frac * 0.5))

    def test_defect_stays_in_its_segment(self):
        cfg = helpers.make_cfg()
        state = engine.new_state(cfg, 1, 1)
        clean = {s: engine.stage_rates(cfg, state, s) for s in cfg["SEGMENT_ORDER"]}
        state["defects"].append(self._defect(["W"], {}, "retention", 2.0))
        self.assertEqual(engine.stage_rates(cfg, state, "M"), clean["M"])
        self.assertEqual(engine.stage_rates(cfg, state, "S"), clean["S"])
        self.assertAlmostEqual(engine.stage_rates(cfg, state, "W")["churn"], clean["W"]["churn"] * 2)

    def test_nev_matches_spec_formula(self):
        cfg = helpers.make_cfg()
        state = engine.new_state(cfg, 1, 1)
        for s in cfg["SEGMENT_ORDER"]:
            state["seg"][s]["trust"] = 70.0
        state["bespoke_arr"] = 5.0
        state["uod"] = 10.0
        state["penalty"] = 3.0
        self.assertAlmostEqual(engine.score(cfg, state)["nev"], 25 * 4.1 + 5 * 2.0 - 2.5 - 3.0)


class HeadlessTests(unittest.TestCase):
    def test_do_nothing_table_row(self):
        cfg = helpers.make_cfg()
        res = bots.run_game(cfg, [(1, "do-nothing", bots.do_nothing)])[1]
        self.assertAlmostEqual(res["weekly"][25], 25.0, places=9)
        self.assertAlmostEqual(res["weekly"][51], 25.0, places=9)
        self.assertAlmostEqual(res["score"]["nev"], 25 * (2.0 + 0.03 * 60), places=9)

    def test_smoke_builder_completes_and_replays_to_same_nev(self):
        cfg = config.load()
        res = bots.run_game(cfg, [(2, "smoke", bots.smoke_builder)], seed=7)[2]
        self.assertGreater(len(res["state"]["shipped"]), 0)
        again = engine.replay(cfg, 7, 2, res["log"])
        self.assertAlmostEqual(engine.score(cfg, again)["nev"], res["score"]["nev"])

    def test_strategies_see_no_hidden_names(self):
        cfg = config.load()
        seen = []

        def spy(view, day):
            if day in (0, 100, 300):
                seen.append(helpers.all_keys(view))
            return bots.smoke_builder(view, day)

        bots.run_game(cfg, [(1, "spy", spy)])
        hidden = set(cfg["HIDDEN_FIELD_NAMES"])
        for keys in seen:
            self.assertFalse(keys & hidden)


if __name__ == "__main__":
    unittest.main()
