import unittest

import helpers
import clock as clockmod


def make(**over):
    cfg = helpers.make_cfg(SECONDS_PER_DAY=13.0, **over)
    return cfg, clockmod.Clock(cfg)


def run_ticks(clock, start, n):
    """Run n ticks as the runner would, one poll per second. Returns (time, outcomes)."""
    now, out = start, []
    while len(out) < n:
        now += 1.0
        if clock.due(now) == "tick":
            out.append(clock.ticked(now))
    return now, out


class ClockTests(unittest.TestCase):
    def test_new_clock_is_paused_at_day_zero(self):
        cfg, c = make()
        st = c.status(0.0)
        self.assertEqual((st["day"], st["running"], st["reason"]), (0, False, "start"))
        self.assertIsNone(c.due(1000.0))

    def test_one_tick_per_interval(self):
        cfg, c = make()
        c.resume(0.0)
        self.assertIsNone(c.due(12.9))
        self.assertEqual(c.due(13.0), "tick")
        c.ticked(13.0)
        self.assertIsNone(c.due(25.9))
        self.assertEqual(c.due(26.0), "tick")

    def test_a_stall_never_fast_forwards(self):
        cfg, c = make()
        c.resume(0.0)
        self.assertEqual(c.due(600.0), "tick")
        c.ticked(600.0)
        self.assertEqual(c.day, 1)
        self.assertIsNone(c.due(601.0))

    def test_checkpoint_pause_warning_and_automatic_resume(self):
        cfg, c = make()
        c.resume(0.0)
        now, outcomes = run_ticks(c, 0.0, 91)
        self.assertEqual(outcomes[-1], "checkpoint")
        self.assertEqual(c.day, 91)
        st = c.status(now)
        self.assertEqual((st["running"], st["reason"], st["warning"]), (False, "checkpoint", False))
        self.assertAlmostEqual(st["countdown_remaining"], 420.0)
        self.assertTrue(c.status(now + 391)["warning"])
        self.assertFalse(c.status(now + 389)["warning"])
        self.assertIsNone(c.due(now + 419))
        self.assertEqual(c.due(now + 420), "auto_resume")
        c.resume(now + 420)
        self.assertTrue(c.running)

    def test_no_checkpoint_after_other_weeks(self):
        cfg, c = make()
        c.resume(0.0)
        _, outcomes = run_ticks(c, 0.0, 90)
        self.assertNotIn("checkpoint", outcomes)

    def test_hold_removes_the_automatic_resume_and_extend_adds_time(self):
        cfg, c = make()
        c.resume(0.0)
        now, _ = run_ticks(c, 0.0, 91)
        self.assertTrue(c.extend(now, 60))
        self.assertAlmostEqual(c.status(now)["countdown_remaining"], 480.0)
        self.assertTrue(c.hold_pause(now))
        self.assertIsNone(c.due(now + 10000))
        self.assertIsNone(c.status(now)["countdown_remaining"])
        self.assertTrue(c.set_countdown(now, 5))
        self.assertEqual(c.due(now + 5), "auto_resume")

    def test_operator_pause_and_resume(self):
        cfg, c = make()
        c.resume(0.0)
        self.assertTrue(c.pause(5.0))
        self.assertIsNone(c.due(100.0))
        self.assertEqual(c.status(5.0)["reason"], "operator")
        self.assertTrue(c.resume(100.0))
        self.assertEqual(c.due(113.0), "tick")

    def test_speed_changes_the_interval_and_unknown_speed_is_refused(self):
        cfg, c = make()
        c.resume(0.0)
        self.assertTrue(c.set_speed(0.0, 2))
        self.assertEqual(c.due(6.5), "tick")
        self.assertFalse(c.set_speed(0.0, 3))
        self.assertEqual(c.speed, 2)

    def test_game_stops_after_the_last_day(self):
        cfg, c = make()
        c.day = cfg["TOTAL_DAYS"] - 1
        c.resume(0.0)
        self.assertEqual(c.ticked(13.0), "finished")
        st = c.status(13.0)
        self.assertEqual((st["finished"], st["running"], st["reason"]), (True, False, "finished"))
        self.assertIsNone(c.due(1e6))
        self.assertFalse(c.resume(14.0))

    def test_restored_clock_is_paused_with_the_logged_speed(self):
        cfg, c = make()
        c.restored(120, 4)
        st = c.status(0.0)
        self.assertEqual((st["day"], st["speed"], st["running"], st["reason"]), (120, 4, False, "restart"))

    def test_status_reports_week_and_next_checkpoint(self):
        cfg, c = make()
        c.day = 100
        st = c.status(0.0)
        self.assertEqual((st["week"], st["next_checkpoint_week"]), (15, 26))
        c.day = 300
        self.assertIsNone(c.status(0.0)["next_checkpoint_week"])


if __name__ == "__main__":
    unittest.main()
