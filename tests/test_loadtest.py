import unittest

import helpers  # noqa: F401  (puts the project root on sys.path)
import loadtest


def ok_rows(n=100, seconds=0.01):
    return [("view", seconds, 200)] * n


class EvaluateTests(unittest.TestCase):
    def test_a_clean_run_meets_every_bar(self):
        self.assertEqual(loadtest.evaluate(ok_rows(), [], 1.0), [])

    def test_a_server_error_and_a_timeout_fail_the_run_and_name_the_statuses(self):
        rows = ok_rows() + [("view", 0.01, 500), ("clock", 10.0, 0)]
        problems = loadtest.evaluate(rows, [], 1.0)
        self.assertTrue(any("2 requests failed" in p and "500" in p and "0" in p for p in problems), problems)

    def test_a_304_is_not_an_error(self):
        self.assertEqual(loadtest.evaluate(ok_rows() + [("view", 0.01, 304)] * 50, [], 1.0), [])

    def test_a_slow_tail_fails_on_p99(self):
        rows = ok_rows(95) + [("view", 2.0, 200)] * 5
        problems = loadtest.evaluate(rows, [], 1.0)
        self.assertTrue(any("p99" in p for p in problems), problems)

    def test_ticks_that_run_late_are_flagged_only_at_a_pace_the_sampling_can_judge(self):
        ticks = [(d, d * 1.6, True) for d in range(1, 40)]            # 1.6 s a day on a 1.0 s clock
        self.assertTrue(any("late" in p for p in loadtest.evaluate(ok_rows(), ticks, 1.0)))
        self.assertEqual(loadtest.evaluate(ok_rows(), ticks, 0.1), [])
        on_time = [(d, d * 1.05, True) for d in range(1, 40)]
        self.assertEqual(loadtest.evaluate(ok_rows(), on_time, 1.0), [])

    def test_the_gap_around_a_checkpoint_break_is_not_a_late_tick(self):
        ticks = [(90, 90.0, True), (91, 91.0, False), (92, 400.0, True), (93, 401.0, True)]
        self.assertEqual(sorted(loadtest.tick_gaps(ticks)), [1.0, 1.0])

    def test_percentile_of_nothing_is_zero(self):
        self.assertEqual(loadtest.percentile([], 0.99), 0.0)
        self.assertEqual(loadtest.percentile([1, 2, 3, 4], 0.5), 3)


class ShortRunTests(unittest.TestCase):
    def test_a_short_full_game_with_polling_consoles_completes_and_replays(self):
        rows, ticks, problems, summary = loadtest.run(
            teams=3, clients=6, seconds_per_day=0.02, poll=0.2, checkpoint_pause=1)
        self.assertEqual(problems, [])
        kinds = {r[0] for r in rows}
        self.assertTrue({"clock", "view", "funnel", "operations", "team view", "action"} <= kinds, kinds)
        self.assertGreater(len(ticks), 300)
        self.assertIn("3 teams, 6 consoles", summary)


if __name__ == "__main__":
    unittest.main()
