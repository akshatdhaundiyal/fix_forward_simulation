import json
import os
import shutil
import tempfile
import unittest

import engine
import game as gamemod
import gamehelpers as gh
import helpers
import store


class BaselineStartTests(unittest.TestCase):
    def source(self, days=40):
        g, ft, d = gh.open_game(self, teams=3)
        g.clock_op("resume")
        g.submit(1, dict(type="queue_add", card="A2"))
        g.submit(2, dict(type="queue_add", card="A3"))
        g.book(1, "cto")
        g.stakeholder_decline(3, 3)
        gh.advance_days(g, ft, days)
        snap_id = g.snapshot_now()
        path = os.path.join(d, "state", "snapshots", snap_id + ".json")
        return g, ft, d, path

    def target(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        return os.path.join(d, "state")

    def test_a_snapshot_starts_a_new_directory_at_its_day_and_replays_forward_in_step(self):
        g, ft, d, path = self.source(40)
        at_snapshot = gh.digests(g)
        out = self.target()
        day = gamemod.start_from_snapshot(g.cfg, path, out)
        self.assertEqual(day, g.clock.day)
        ft2 = gh.FakeTime()
        again = gamemod.Game(g.cfg, out, now=ft2)
        self.addCleanup(again.close)
        self.assertEqual(gh.digests(again), at_snapshot)
        st = again.clock.status(ft2.t)
        self.assertEqual((st["day"], st["running"]), (g.clock.day, False))
        again.clock_op("resume")
        gh.advance_days(again, ft2, 28)
        gh.advance_days(g, ft, 28)
        self.assertEqual(gh.digests(again), gh.digests(g))

    def test_the_booking_board_and_a_decline_survive_the_start_and_a_second_restart(self):
        g, ft, d, path = self.source(10)
        out = self.target()
        gamemod.start_from_snapshot(g.cfg, path, out)
        again = gamemod.Game(g.cfg, out, now=gh.FakeTime())
        self.addCleanup(again.close)
        board = again.stakeholder_board()
        self.assertEqual([(b["team"], b["role"]) for b in board["bookings"]], [(1, "cto")])
        self.assertEqual([t["team"] for t in board["teams"] if t["declined"]], [3])
        self.assertFalse(again.stakeholder_decline(3, 0)["ok"])
        third = gamemod.Game(g.cfg, out, now=gh.FakeTime())
        self.addCleanup(third.close)
        self.assertEqual(third.stakeholder_board()["bookings"], board["bookings"])
        self.assertEqual(gh.digests(third), gh.digests(g))

    def test_a_restore_after_a_baseline_start_works(self):
        g, ft, d, path = self.source(10)
        out = self.target()
        gamemod.start_from_snapshot(g.cfg, path, out)
        ft2 = gh.FakeTime()
        again = gamemod.Game(g.cfg, out, now=ft2)
        self.addCleanup(again.close)
        again.clock_op("resume")
        sid = again.snapshot_now()
        before = gh.digests(again)
        gh.advance_days(again, ft2, 5)
        self.assertTrue(again.restore(sid)["ok"])
        self.assertEqual(gh.digests(again), before)

    def test_history_starts_empty_at_the_baseline_day_and_grows_from_there(self):
        g, ft, d, path = self.source(40)
        out = self.target()
        gamemod.start_from_snapshot(g.cfg, path, out)
        ft2 = gh.FakeTime()
        again = gamemod.Game(g.cfg, out, now=ft2)
        self.addCleanup(again.close)
        self.assertEqual(again.states[1]["history"], [])
        engine.team_view(again.cfg, again.states[1])          # builds with no history
        again.clock_op("resume")
        gh.advance_days(again, ft2, 3)
        self.assertEqual([r["day"] for r in again.states[1]["history"]],
                         [g.clock.day + i for i in range(3)])

    def test_refusals_write_nothing(self):
        g, ft, d, path = self.source(10)
        out = self.target()
        with open(path, encoding="utf-8") as f:
            snap = json.load(f)
        cases = {}
        bad_digest = os.path.join(d, "bad-digest.json")
        with open(bad_digest, "w", encoding="utf-8") as f:
            json.dump(dict(snap, digest="0" * 64), f)
        cases["digest"] = (bad_digest, None)
        one_team = os.path.join(d, "one-team.json")
        with open(one_team, "w", encoding="utf-8") as f:
            json.dump(dict(snap, teams={"1": snap["teams"]["1"]}), f)
        cases["teams"] = (one_team, None)
        cases["registry"] = (path, os.path.join(d, "no-such-teams.json"))
        cases["unreadable"] = (os.path.join(d, "nothing.json"), None)
        for name, (snap_path, registry) in cases.items():
            with self.assertRaises(gamemod.StartupRefused, msg=name):
                gamemod.start_from_snapshot(g.cfg, snap_path, out, registry)
            self.assertFalse(os.path.exists(os.path.join(out, g.cfg["LOG_FILE"])), name)

    def test_a_directory_that_already_holds_a_log_is_refused(self):
        g, ft, d, path = self.source(10)
        out = self.target()
        gamemod.start_from_snapshot(g.cfg, path, out)
        with self.assertRaises(gamemod.StartupRefused):
            gamemod.start_from_snapshot(g.cfg, path, out)

    def test_a_baseline_anywhere_but_second_stops_startup(self):
        g, ft, d, path = self.source(10)
        out = self.target()
        gamemod.start_from_snapshot(g.cfg, path, out)
        log = os.path.join(out, g.cfg["LOG_FILE"])
        events, _ = store.read_events(log)
        stray = dict(events[1], seq=len(events) + 1)
        with open(log, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(stray) + "\n")
        with self.assertRaises(gamemod.StartupRefused):
            gamemod.Game(g.cfg, out, now=gh.FakeTime())


if __name__ == "__main__":
    unittest.main()
