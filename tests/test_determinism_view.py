import unittest

import helpers
import config
import engine

LOG = [
    (0, dict(type="set_quality", mode="low")),
    (0, dict(type="queue_add", card="A2")),
    (0, dict(type="queue_add", report="W")),
    (3, dict(type="queue_add", card="A4")),
    (20, dict(type="set_quality", mode="high")),
    (40, dict(type="queue_add", card="A3")),
    (60, dict(type="queue_reorder", item=3, position=0)),
    (95, dict(type="apply_b1")),
    (120, dict(type="award_bespoke")),
    (130, dict(type="queue_add", card="P1")),
    (200, dict(type="rollback", card="A2")),
]

NO_NOISE = {"error_rate": 0, "p99": 0, "tickets": 0, "funnel": 0}


def play(cfg, log):
    state = engine.new_state(cfg, 2, 5)
    by_day = {}
    for d, a in log:
        by_day.setdefault(d, []).append(a)
    for day in range(cfg["TOTAL_DAYS"]):
        for a in by_day.get(day, []):
            engine.apply(cfg, state, a)
        engine.step(cfg, state)
    return state


class ReplayTests(unittest.TestCase):
    def test_replay_matches_original_state(self):
        cfg = config.load()
        self.assertEqual(helpers.dump(engine.replay(cfg, 5, 2, LOG)), helpers.dump(play(cfg, LOG)))

    def test_same_log_twice_gives_identical_state(self):
        cfg = config.load()
        self.assertEqual(helpers.dump(play(cfg, LOG)), helpers.dump(play(cfg, LOG)))

    def test_log_changes_state(self):
        cfg = config.load()
        self.assertNotEqual(helpers.dump(play(cfg, LOG)), helpers.dump(play(cfg, [])))

    def test_partial_replay_stops_at_requested_day(self):
        cfg = config.load()
        self.assertEqual(engine.replay(cfg, 5, 2, LOG, until_day=150)["day"], 150)

    def test_reading_the_view_never_changes_state(self):
        cfg = config.load()
        state = engine.new_state(cfg, 2, 5)
        clean = engine.new_state(cfg, 2, 5)
        for _ in range(100):
            engine.step(cfg, state)
            engine.team_view(cfg, state, include_slices=True)
            engine.step(cfg, clean)
        self.assertEqual(helpers.dump(state), helpers.dump(clean))


class NoiseTests(unittest.TestCase):
    def test_noise_is_repeatable_and_differs_by_team(self):
        a = engine.noise(5, 1, "error", 10)
        self.assertEqual(a, engine.noise(5, 1, "error", 10))
        self.assertNotEqual(a, engine.noise(5, 2, "error", 10))
        self.assertTrue(-1.0 <= a <= 1.0)

    def test_error_rate_and_latency_follow_uod_without_noise(self):
        cfg = helpers.make_cfg(NOISE=NO_NOISE)
        for uod in (0, 15, 50):
            state = engine.new_state(cfg, 1, 1)
            state["uod"] = float(uod)
            engine.step(cfg, state)
            point = engine.team_view(cfg, state, series_days=1)["telemetry"][-1]
            self.assertAlmostEqual(point["error_rate"], 0.005 + 0.0004 * uod)
            self.assertAlmostEqual(point["p99_ms"], 300 + 6 * uod)

    def test_p99_incident_bump_and_peak_surge(self):
        cfg = helpers.make_cfg(NOISE=NO_NOISE)
        state = engine.new_state(cfg, 3, 1)  # variant A slows the platform
        engine.apply(cfg, state, dict(type="trigger_incident", incident=1))
        engine.step(cfg, state)
        self.assertAlmostEqual(
            engine.team_view(cfg, state, series_days=1)["telemetry"][-1]["p99_ms"], 500.0)
        state = engine.new_state(cfg, 1, 1)
        state["day"] = 28 * 7
        engine.step(cfg, state)
        self.assertAlmostEqual(
            engine.team_view(cfg, state, series_days=1)["telemetry"][-1]["p99_ms"], 450.0)

    def test_tickets_rise_as_trust_falls(self):
        cfg = helpers.make_cfg(NOISE=NO_NOISE)
        state = engine.new_state(cfg, 1, 1)
        state["seg"]["M"]["trust"] = 40.0
        engine.step(cfg, state)
        t = engine.team_view(cfg, state, series_days=1)["telemetry"][-1]["tickets"]["M"]
        self.assertAlmostEqual(t, 40 / 7 * (1 + 0.03 * 20), places=3)


class VisibilityTests(unittest.TestCase):
    def _midgame_state(self):
        cfg = config.load()
        state = engine.new_state(cfg, 2, 5)
        engine.apply(cfg, state, dict(type="queue_add", card="A2"))
        engine.apply(cfg, state, dict(type="queue_add", report="S"))
        helpers.run_days(cfg, state, 50)
        return cfg, state

    def test_view_contains_no_hidden_names(self):
        cfg, state = self._midgame_state()
        self.assertEqual(state["incidents"][0]["status"], "open")
        self.assertTrue(state["reports"])
        keys = helpers.all_keys(engine.team_view(cfg, state, include_slices=True))
        self.assertFalse(keys & set(cfg["HIDDEN_FIELD_NAMES"]))

    def test_scan_is_not_vacuous_on_raw_state(self):
        cfg, state = self._midgame_state()
        self.assertTrue(helpers.all_keys(state) & set(cfg["HIDDEN_FIELD_NAMES"]))

    def test_report_utility_is_visible_but_target_gain_is_not(self):
        cfg, state = self._midgame_state()
        keys = helpers.all_keys(engine.team_view(cfg, state))
        self.assertIn("utility", keys)
        self.assertNotIn("target_gain", keys)
        self.assertNotIn("gain", keys)

    def test_view_has_only_four_overview_tiles(self):
        cfg, state = self._midgame_state()
        self.assertEqual(set(engine.team_view(cfg, state)["tiles"]),
                         {"arr", "trust", "capacity_bu_week", "open_incidents"})


if __name__ == "__main__":
    unittest.main()
