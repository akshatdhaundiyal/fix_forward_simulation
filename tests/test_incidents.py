import unittest

import helpers
import engine

# team number -> variant letter: 3 -> A, 1 -> B, 2 -> C
TEAM_FOR = {"A": 3, "B": 1, "C": 2}


def fresh(variant, **kw):
    cfg = helpers.make_cfg(**kw)
    return cfg, engine.new_state(cfg, TEAM_FOR[variant], 1)


def open_incident(cfg, state, n):
    if n == 2:
        helpers.ship(cfg, state, "A2")
    assert engine.apply(cfg, state, dict(type="trigger_incident", incident=n))["ok"]
    assert state["incidents"][n - 1]["status"] == "open"


class VariantTests(unittest.TestCase):
    def test_right_cause_resolves_wrong_cause_does_not(self):
        for n in (1, 2, 3):
            for v in "ABC":
                if n == 3 and v == "B":
                    pre = "A2"
                else:
                    pre = None
                with self.subTest(incident=n, variant=v):
                    cfg, state = fresh(v)
                    if pre:
                        helpers.ship(cfg, state, pre)
                    open_incident(cfg, state, n)
                    truth = state["incidents"][n - 1]["cause"]
                    wrong = [c for c in cfg["INCIDENTS"][n]["causes"] if c != truth][0]
                    uod0 = state["uod"]
                    engine.apply(cfg, state, dict(type="targeted_fix", incident=n, cause=wrong))
                    while state["queue"]:
                        engine.step(cfg, state)
                    self.assertEqual(state["incidents"][n - 1]["status"], "open")
                    self.assertEqual(state["uod"], uod0)
                    engine.apply(cfg, state, dict(type="targeted_fix", incident=n, cause=truth))
                    while state["queue"]:
                        engine.step(cfg, state)
                    self.assertEqual(state["incidents"][n - 1]["status"], "resolved")
                    self.assertEqual(state["defects"], [])
                    self.assertEqual(state["uod"], max(0.0, uod0 - 10))


class IncidentTests(unittest.TestCase):
    def test_incident_one_variant_b_hits_self_serve_only(self):
        cfg, state = fresh("B")
        clean = {s: engine.stage_rates(cfg, state, s) for s in cfg["SEGMENT_ORDER"]}
        open_incident(cfg, state, 1)
        self.assertEqual(engine.stage_rates(cfg, state, "W"), clean["W"])
        self.assertEqual(engine.stage_rates(cfg, state, "M"), clean["M"])
        self.assertAlmostEqual(engine.stage_rates(cfg, state, "S")["churn"], clean["S"]["churn"] * 2)

    def test_incident_one_starts_in_week_six_when_enabled(self):
        cfg, state = fresh("B", events={"incidents": True})
        helpers.run_days(cfg, state, 5 * 7)
        self.assertEqual(state["incidents"][0]["status"], "pending")
        helpers.run_days(cfg, state, 1)
        self.assertEqual(state["incidents"][0]["status"], "open")

    def test_no_incident_two_without_a_ship(self):
        cfg, state = fresh("A", events={"incidents": True})
        helpers.run_days(cfg, state, cfg["TOTAL_DAYS"])
        self.assertEqual(state["incidents"][1]["status"], "pending")

    def test_incident_two_opens_on_first_qualifying_ship_day(self):
        cfg, state = fresh("A", events={"incidents": True})
        state["day"] = 15 * 7
        engine.apply(cfg, state, dict(type="queue_add", card="A6"))
        engine.apply(cfg, state, dict(type="queue_add", card="A2"))
        while "A6" not in state["shipped"]:
            engine.step(cfg, state)
        inc = state["incidents"][1]
        self.assertEqual(inc["status"], "open")
        self.assertEqual(inc["opened_day"], state["shipped"]["A6"]["day"])
        self.assertEqual(inc["caused_by"], "A6")
        while "A2" not in state["shipped"]:
            engine.step(cfg, state)
        self.assertEqual(state["incidents"][1]["caused_by"], "A6")

    def test_ship_outside_window_does_not_trigger_incident_two(self):
        cfg, state = fresh("A", events={"incidents": True})
        helpers.ship(cfg, state, "A6")
        self.assertEqual(state["incidents"][1]["status"], "pending")

    def test_patch_halves_damage_stops_trust_loss_and_adds_debt(self):
        cfg, state = fresh("B")
        open_incident(cfg, state, 1)
        engine.apply(cfg, state, dict(type="patch", incident=1))
        while state["queue"]:
            engine.step(cfg, state)
        self.assertTrue(state["incidents"][0]["patched"])
        self.assertAlmostEqual(state["uod"], 15.0)
        trust = state["seg"]["S"]["trust"]
        saved = state["defects"]
        state["defects"] = []
        clean = engine.stage_rates(cfg, state, "S")["churn"]
        state["defects"] = saved
        self.assertAlmostEqual(engine.stage_rates(cfg, state, "S")["churn"], clean * 1.5)
        helpers.run_days(cfg, state, 7)
        self.assertEqual(state["seg"]["S"]["trust"], trust)

    def test_open_incident_costs_two_trust_a_week(self):
        cfg, state = fresh("A")
        open_incident(cfg, state, 1)
        helpers.run_days(cfg, state, 7)
        self.assertAlmostEqual(state["seg"]["W"]["trust"], 58.0)
        self.assertEqual(state["seg"]["S"]["trust"], 60.0)

    def test_rollback_of_the_caused_by_card_resolves_incident_two(self):
        cfg, state = fresh("C")
        open_incident(cfg, state, 2)
        engine.apply(cfg, state, dict(type="rollback", card="A2"))
        helpers.run_days(cfg, state, 8)
        self.assertEqual(state["incidents"][1]["status"], "resolved")
        self.assertNotIn("A2", state["shipped"])

    def test_rollback_of_another_card_loses_it_and_leaves_incident_open(self):
        cfg, state = fresh("C")
        helpers.ship(cfg, state, "A3")
        open_incident(cfg, state, 2)  # opens on A2, the latest release
        self.assertEqual(state["incidents"][1]["caused_by"], "A2")
        engine.apply(cfg, state, dict(type="rollback", card="A3"))
        helpers.run_days(cfg, state, 8)
        self.assertNotIn("A3", state["shipped"])
        self.assertEqual(state["incidents"][1]["status"], "open")

    def test_no_incident_three_variant_b_without_a_release(self):
        cfg, state = fresh("B", events={"incidents": True})
        helpers.run_days(cfg, state, 33 * 7)
        self.assertEqual(state["incidents"][2]["status"], "skipped")


class ConfigDrivenTests(unittest.TestCase):
    def test_changing_trigger_week_in_config_moves_the_incident(self):
        import copy
        import config
        inc = copy.deepcopy(config.INCIDENTS)
        inc[1]["trigger"]["week"] = 3
        cfg = helpers.make_cfg(events={"incidents": True}, INCIDENTS=inc)
        state = engine.new_state(cfg, 1, 1)
        helpers.run_days(cfg, state, 2 * 7)
        self.assertEqual(state["incidents"][0]["status"], "pending")
        helpers.run_days(cfg, state, 1)
        self.assertEqual(state["incidents"][0]["status"], "open")

    def test_variant_order_in_config_decides_team_variant(self):
        cfg = helpers.make_cfg(VARIANT_ORDER=["C", "B"])
        self.assertEqual(engine.new_state(cfg, 2, 1)["incidents"][0]["variant"], "C")
        self.assertEqual(engine.new_state(cfg, 3, 1)["incidents"][0]["variant"], "B")

    def test_peak_outage_trust_is_read_from_config(self):
        cfg = helpers.make_cfg(events={"peak_season": True},
                               PEAK_OUTAGE_TRUST={"M": -10.0, "S": -20.0})
        state = engine.new_state(cfg, 1, 1)
        state["day"], state["uod"] = 27 * 7, 60.0
        engine.step(cfg, state)
        self.assertEqual(state["seg"]["W"]["trust"], 60.0)
        self.assertEqual(state["seg"]["M"]["trust"], 50.0)
        self.assertEqual(state["seg"]["S"]["trust"], 40.0)


if __name__ == "__main__":
    unittest.main()
