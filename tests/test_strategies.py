import unittest

import helpers
import bots
import config
import engine

TEAM_FOR = {"A": 3, "B": 1, "C": 2}


def detailed(cfg, state):
    return engine.team_view(cfg, state, series_days=bots.DETAIL_DAYS, include_slices=True)


class DiagnosisTests(unittest.TestCase):
    def _open(self, n, variant, settle_days):
        cfg = helpers.make_cfg(RECORD_SLICES=True)
        state = engine.new_state(cfg, TEAM_FOR[variant], 1)
        helpers.run_days(cfg, state, 10)
        if n == 2 or (n == 3 and variant == "B"):
            helpers.ship(cfg, state, "A2")
            helpers.run_days(cfg, state, 5)
        self.assertTrue(engine.apply(cfg, state, dict(type="trigger_incident", incident=n))["ok"])
        helpers.run_days(cfg, state, settle_days)
        return cfg, state

    def test_all_nine_variants_are_diagnosed_from_the_view(self):
        for n in (1, 2, 3):
            for variant in "ABC":
                for settle in (1, 3, 7):
                    with self.subTest(incident=n, variant=variant, days=settle):
                        cfg, state = self._open(n, variant, settle)
                        view = detailed(cfg, state)
                        inc = [i for i in view["incidents"] if i["id"] == n][0]
                        truth = engine._inc(state, n)["cause"]
                        self.assertEqual(bots.diagnose(view, inc), truth)

    def test_diagnosis_is_one_of_the_offered_options(self):
        cfg, state = self._open(3, "C", 3)
        view = detailed(cfg, state)
        inc = view["incidents"][0]
        self.assertIn(bots.diagnose(view, inc), inc["options"])

    def test_without_slice_data_there_is_no_diagnosis(self):
        cfg, state = self._open(1, "A", 3)
        view = engine.team_view(cfg, state, series_days=bots.DETAIL_DAYS)
        self.assertIsNone(bots.diagnose(view, view["incidents"][0]))


class MaskedDiagnosisTests(unittest.TestCase):
    def test_release_that_lifts_the_stage_is_still_read_as_own_release(self):
        cfg = helpers.make_cfg(events={"incidents": True}, RECORD_SLICES=True,
                               LIFTS=dict(config.LIFTS, A3=0.9))
        state = engine.new_state(cfg, 3, 1)
        state["day"] = 15 * 7
        helpers.ship(cfg, state, "A3")
        helpers.run_days(cfg, state, 2)
        view = detailed(cfg, state)
        inc = [i for i in view["incidents"] if i["id"] == 2][0]
        self.assertGreater(view["funnel"]["M"][-1]["rates"]["activation"], 0.5)
        self.assertEqual(bots.diagnose(view, inc), "own_release")

    def test_unrelated_release_on_the_alert_day_is_not_blamed(self):
        cfg = helpers.make_cfg(RECORD_SLICES=True)
        state = engine.new_state(cfg, 3, 1)
        helpers.run_days(cfg, state, 5)
        helpers.ship(cfg, state, "A6")
        state["releases"][-1]["day"] = state["day"]
        engine.apply(cfg, state, dict(type="trigger_incident", incident=1))
        helpers.run_days(cfg, state, 3)
        view = detailed(cfg, state)
        self.assertEqual(bots.diagnose(view, view["incidents"][0]), "external_load")


class StrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config.load(dict(LIFTS=dict(config.LIFTS)), calibrated=False)
        teams = [(10 + i, name, bots.make_strategy(name))
                 for i, (name, _) in enumerate(bots.STRATEGY_SPECS)]
        cls.res = {r["name"]: r for r in bots.run_game(cls.cfg, teams).values()}

    def actions(self, name, kind=None):
        return [(d, a) for d, a in self.res[name]["log"] if kind is None or a["type"] == kind]

    def test_measured_risk_buys_three_reports_on_day_zero(self):
        reps = [a for d, a in self.actions("measured-risk", "queue_add") if d == 0 and "report" in a]
        self.assertEqual(sorted(a["report"] for a in reps), ["M", "S", "W"])

    def test_measured_risk_never_builds_low_utility_cards(self):
        built = {a["card"] for d, a in self.actions("measured-risk", "queue_add") if "card" in a}
        self.assertFalse(built & {"A1", "B4", "C3", "A5"})
        self.assertTrue(built & {"A2", "A3", "A4"})

    def test_measured_risk_fixes_every_incident(self):
        state = self.res["measured-risk"]["state"]
        self.assertEqual([i["status"] for i in state["incidents"] if i["status"] == "open"], [])

    def test_corner_cutter_goes_low_and_patches(self):
        self.assertEqual(self.actions("corner-cutter", "set_quality")[0][1]["mode"], "low")
        self.assertTrue(self.actions("corner-cutter", "patch"))
        self.assertFalse(self.actions("corner-cutter", "targeted_fix"))
        cards = {a.get("card") for d, a in self.actions("corner-cutter", "queue_add")}
        self.assertFalse(cards & {"P1", "D4"})

    def test_no_reports_never_buys_a_report(self):
        self.assertFalse([a for d, a in self.actions("no-reports", "queue_add") if "report" in a])

    def test_whale_chaser_applies_in_window_and_queues_c1(self):
        days = [d for d, a in self.actions("whale-chaser", "apply_b1")]
        self.assertEqual(len(days), 1)
        self.assertTrue(13 * 7 <= days[0] < 17 * 7)
        self.assertTrue([a for d, a in self.actions("whale-chaser", "queue_add")
                         if a.get("card") == "C1"])
        self.assertIn("B1", self.res["whale-chaser"]["state"]["shipped"])

    def test_late_sprinter_switches_to_low_in_week_40(self):
        switches = self.actions("late-sprinter", "set_quality")
        self.assertEqual([(d, a["mode"]) for d, a in switches], [(0, "medium"), (39 * 7, "low")])

    def test_maximum_caution_uses_high_quality_and_both_standing_cards(self):
        self.assertEqual(self.actions("maximum-caution", "set_quality")[0][1]["mode"], "high")
        cards = [a.get("card") for d, a in self.actions("maximum-caution", "queue_add") if d == 0]
        self.assertIn("P1", cards)
        self.assertIn("P2", cards)

    def test_fixed_plan_never_acts_after_day_zero(self):
        self.assertEqual({d for d, a in self.actions("fixed-plan")}, {0})

    def test_do_nothing_takes_no_action(self):
        self.assertEqual(self.actions("do-nothing"), [])

    def test_every_strategy_replays_to_the_same_nev(self):
        for i, (name, _) in enumerate(bots.STRATEGY_SPECS):
            with self.subTest(strategy=name):
                again = engine.replay(self.cfg, 1, 10 + i, self.res[name]["log"])
                self.assertAlmostEqual(engine.score(self.cfg, again)["nev"],
                                       self.res[name]["score"]["nev"])


class LeagueTests(unittest.TestCase):
    def test_three_copies_cover_every_variant(self):
        cfg = config.load(calibrated=False)
        seen = {}
        for team_no, name, _ in bots.league_teams():
            seen.setdefault(name, []).append(engine.variant_for(cfg, team_no))
        self.assertEqual(len(seen), 8)
        for variants in seen.values():
            self.assertEqual(sorted(variants), ["A", "B", "C"])

    def _rows(self, nev):
        return sorted([dict(name=n, nev=v, arr26=nev_arr[0], arr52=0, trust=0, uod=0, penalty=0,
                            nev_min=v, nev_max=v, copies=3)
                       for n, (v, *nev_arr) in nev.items()], key=lambda r: -r["nev"])

    def test_criteria_pass_on_the_target_shape(self):
        rows = self._rows({
            "measured-risk": (160, 30), "late-sprinter": (149, 30), "whale-chaser": (143, 33),
            "maximum-caution": (136, 30), "no-reports": (125, 29), "corner-cutter": (124, 34),
            "fixed-plan": (60, 27), "do-nothing": (40, 23)})
        self.assertEqual([ok for _, ok, _ in bots.criteria(rows)], [True, True, True, True])

    def test_criteria_fail_when_a_single_tactic_is_within_five_percent(self):
        rows = self._rows({
            "measured-risk": (160, 30), "late-sprinter": (155, 30), "whale-chaser": (143, 33),
            "maximum-caution": (136, 30), "no-reports": (125, 29), "corner-cutter": (124, 34),
            "fixed-plan": (60, 27), "do-nothing": (40, 23)})
        self.assertEqual([ok for _, ok, _ in bots.criteria(rows)], [True, True, True, False])

    def test_criteria_fail_when_measured_risk_does_not_win(self):
        rows = self._rows({
            "measured-risk": (140, 30), "late-sprinter": (160, 30), "whale-chaser": (120, 33),
            "maximum-caution": (110, 30), "no-reports": (100, 29), "corner-cutter": (90, 28),
            "fixed-plan": (60, 27), "do-nothing": (40, 23)})
        ok = [p for _, p, _ in bots.criteria(rows)]
        self.assertEqual(ok, [False, False, True, False])


if __name__ == "__main__":
    unittest.main()
