import unittest

import helpers  # noqa: F401  (puts the project root on the path)
import httpgame


class ScriptedClient:
    """Answers /api/clock from a list of clock blocks, one per request."""

    def __init__(self, clocks):
        self.clocks = list(clocks)
        self.requests = 0

    def request(self, method, path, body=None, headers=None):
        self.requests += 1
        clock = self.clocks.pop(0) if len(self.clocks) > 1 else self.clocks[0]
        return 200, clock


class FakeTime:
    """Time that moves one second every time it is read."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 1.0
        return self.t


def clock(day, running=True, countdown=None, finished=False):
    return dict(day=day, running=running, countdown_remaining=countdown, finished=finished)


class WaitForNextDayTests(unittest.TestCase):
    def test_returns_when_the_day_changes(self):
        client = ScriptedClient([clock(5), clock(5), clock(6)])
        httpgame.wait_for_next_day(client, poll=0, timeout=5, now=FakeTime(), sleep=lambda s: None)()
        self.assertGreaterEqual(client.requests, 3)

    def test_returns_when_the_game_finishes(self):
        client = ScriptedClient([clock(363), clock(363, finished=True)])
        httpgame.wait_for_next_day(client, poll=0, timeout=5, now=FakeTime(), sleep=lambda s: None)()

    def test_a_long_checkpoint_pause_does_not_count_against_the_timeout(self):
        # Paused with a countdown for far more polls than the timeout allows.
        pause = [clock(91, running=False, countdown=400)] * 50
        client = ScriptedClient([clock(91)] + pause + [clock(92)])
        httpgame.wait_for_next_day(client, poll=0, timeout=5, now=FakeTime(), sleep=lambda s: None)()

    def test_a_running_clock_that_never_moves_times_out(self):
        client = ScriptedClient([clock(5)])
        with self.assertRaises(RuntimeError):
            httpgame.wait_for_next_day(client, poll=0, timeout=5, now=FakeTime(), sleep=lambda s: None)()

    def test_an_operator_pause_is_waited_out_too(self):
        stopped = [clock(5, running=False)] * 50
        client = ScriptedClient([clock(5)] + stopped + [clock(6)])
        httpgame.wait_for_next_day(client, poll=0, timeout=5, now=FakeTime(), sleep=lambda s: None)()


if __name__ == "__main__":
    unittest.main()
