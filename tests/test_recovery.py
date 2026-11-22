import json
import os
import time
import unittest
from unittest import mock

import gamehelpers as gh
import config
import engine
import game as gamemod
import helpers
import store


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def play(g, ft, days):
    """A busy stretch: actions, quality changes, a speed change and a reveal."""
    g.clock_op("resume")
    for d in range(days):
        gh.advance_days(g, ft, 1)
        if d == 3:
            g.submit(1, dict(type="set_quality", mode="low"))
            g.submit(1, dict(type="queue_add", card="A2"))
            g.submit(2, dict(type="queue_add", report="W"))
        if d == 8:
            g.submit(2, dict(type="queue_add", card="A4"))
            g.submit(2, dict(type="queue_reorder", item=1, position=0))
            g.clock_op("speed", 2)
            g.clock_op("speed", 1)
        if d == 12:
            g.admin_incident(3, 1, "trigger")
            g.submit(3, dict(type="patch", incident=1))
        if d == 15:
            g.reveal()
            g.admin_edit(1, "seg.S.trust", 66, "rehearsal fix")


class RecoveryTests(unittest.TestCase):
    def reopen(self, g, ft, directory, cfg=None, **kw):
        again, _, _ = gh.open_game(self, cfg=cfg or g.cfg, directory=directory, ft=ft, **kw)
        return again

    def test_restart_rebuilds_every_team_exactly_and_comes_back_paused(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 30)
        live = gh.digests(g)
        codes = g.registry
        again = self.reopen(g, ft, d)          # the first process is simply abandoned
        self.assertEqual(gh.digests(again), live)
        self.assertEqual(again.registry, codes)
        st = again.clock.status(ft.t)
        self.assertEqual((st["day"], st["running"], st["reason"]), (30, False, "restart"))
        self.assertTrue(again.revealed)
        self.assertEqual(again.clock.speed, 1)

    def test_restored_speed_is_the_last_one_logged(self):
        g, ft, d = gh.open_game(self)
        g.clock_op("speed", 4)
        again = self.reopen(g, ft, d)
        self.assertEqual(again.clock.speed, 4)

    def test_resuming_after_a_restart_continues_from_the_restored_day(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 20)
        again = self.reopen(g, ft, d)
        again.clock_op("resume")
        gh.advance_days(again, ft, 5)
        self.assertEqual(again.clock.day, 25)
        third = self.reopen(again, ft, d)
        self.assertEqual(gh.digests(third), gh.digests(again))

    def test_a_torn_final_line_recovers_and_later_appends_stay_clean(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 10)
        live = gh.digests(g)
        with open(g.log_path, "ab") as f:
            f.write(b'{"kind":"action","day":10,"team":1,"source":"team","act')
        again = self.reopen(g, ft, d)
        self.assertEqual(gh.digests(again), live)
        self.assertTrue(again.submit(1, dict(type="queue_add", card="A3"))["ok"])
        events, _ = store.read_events(again.log_path)
        self.assertEqual([e["seq"] for e in events], list(range(1, len(events) + 1)))

    def test_a_changed_digest_stops_recovery_and_names_the_day_and_team(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 5)
        g.close()
        lines = read_text(g.log_path).split("\n")
        for i, line in enumerate(lines):
            if '"kind":"tick"' in line and '"day":2,' in line:
                e = json.loads(line)
                e["digests"]["2"] = "0" * 16
                lines[i] = json.dumps(e, separators=(",", ":"))
        with open(g.log_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
        with self.assertRaises(gamemod.StartupRefused) as ctx:
            self.reopen(g, ft, d)
        self.assertIn("day 2", str(ctx.exception))
        self.assertIn("2", str(ctx.exception))

    def test_a_different_game_setting_is_refused_with_a_pointer_to_new_game(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 3)
        g.close()
        changed = gh.make_game_cfg(LIFTS=dict(config.LIFTS, A2=0.77))
        with self.assertRaises(gamemod.StartupRefused) as ctx:
            self.reopen(g, ft, d, cfg=changed)
        self.assertIn("--new-game", str(ctx.exception))

    def test_a_server_only_setting_may_change_between_runs(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 3)
        g.close()
        faster = gh.make_game_cfg(SECONDS_PER_DAY=0.1, SNAPSHOT_INTERVAL_SECONDS=1)
        again = self.reopen(g, ft, d, cfg=faster)
        self.assertEqual(again.clock.day, 3)

    def test_new_game_archives_the_old_state_and_starts_clean(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 3)
        g.close()
        fresh = self.reopen(g, ft, d, new_game=True)
        self.assertEqual(fresh.clock.day, 0)
        self.assertNotEqual(fresh.registry, g.registry)
        archived = [n for n in os.listdir(d) if n.startswith("state.")]
        self.assertEqual(len(archived), 1)

    def test_a_corrupt_line_in_the_middle_refuses_to_start(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 3)
        g.close()
        text = read_text(g.log_path).split("\n")
        text[2] = "{{{ not json"
        with open(g.log_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(text))
        with self.assertRaises(store.CorruptLog):
            self.reopen(g, ft, d)

    def test_full_game_recovery_for_sixteen_teams_fits_the_budget(self):
        cfg = gh.make_game_cfg(teams=16, RECORD_SLICES=True, CHECKPOINT_PAUSE_SECONDS=1)
        g, ft, d = gh.open_game(self, cfg=cfg)
        g.clock_op("resume")
        for team in range(1, 17):
            g.submit(team, dict(type="queue_add", card="A2"))
        gh.advance_days(g, ft, 364)
        self.assertTrue(g.clock.finished)
        live = gh.digests(g)
        start = time.perf_counter()
        again = self.reopen(g, ft, d, cfg=cfg)
        took = time.perf_counter() - start
        self.assertEqual(gh.digests(again), live)
        self.assertEqual(again.clock.status(ft.t)["reason"], "finished")
        self.assertLess(took, cfg["RECOVERY_BUDGET_SECONDS"])


class SnapshotTests(unittest.TestCase):
    def test_snapshot_holds_every_team_without_history_and_skips_when_nothing_changed(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 10)
        sid = g.snapshot_now()
        self.assertIsNotNone(sid)
        snap = g.snapshots.read(sid)
        self.assertEqual(sorted(snap["teams"]), ["1", "2", "3"])
        self.assertTrue(all("history" not in t for t in snap["teams"].values()))
        self.assertIsNone(g.snapshot_now())
        g.submit(1, dict(type="queue_add", card="A3"))
        self.assertIsNotNone(g.snapshot_now())

    def test_a_blocked_snapshot_swap_never_stops_the_game(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 5)
        with mock.patch("store.os.replace", side_effect=PermissionError("in use")):
            self.assertIsNone(g.snapshot_now())
        self.assertIn("snapshot swap blocked", g.status()["snapshot_warning"])
        gh.advance_days(g, ft, 3)
        self.assertEqual(g.clock.day, 8)
        self.assertIsNotNone(g.snapshot_now())
        self.assertIsNone(g.status()["snapshot_warning"])

    def test_restore_rewinds_to_the_snapshot_and_a_restart_agrees(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 10)
        sid = g.snapshot_now()
        at_snapshot = gh.digests(g)
        play_more = g.clock_op("resume")
        gh.advance_days(g, ft, 10)
        g.submit(1, dict(type="queue_add", card="A3"))
        self.assertNotEqual(gh.digests(g), at_snapshot)
        res = g.restore(sid)
        self.assertTrue(res["ok"], res)
        self.assertEqual(gh.digests(g), at_snapshot)
        st = g.clock.status(ft.t)
        self.assertEqual((st["day"], st["running"], st["reason"]), (10, False, "restore"))
        again, _, _ = gh.open_game(self, cfg=g.cfg, directory=d, ft=ft)
        self.assertEqual(gh.digests(again), at_snapshot)
        again.clock_op("resume")
        gh.advance_days(again, ft, 3)
        fourth, _, _ = gh.open_game(self, cfg=g.cfg, directory=d, ft=ft)
        self.assertEqual(gh.digests(fourth), gh.digests(again))

    def test_restore_keeps_the_old_lines_in_the_log(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 6)
        sid = g.snapshot_now()
        gh.advance_days(g, ft, 4)
        seq_before = g.log.seq
        g.restore(sid)
        events, _ = store.read_events(g.log_path)
        self.assertEqual(len(events), seq_before + 1)
        self.assertEqual(events[-1]["op"], "rewind")

    def test_unknown_or_hostile_snapshot_ids_are_refused(self):
        g, ft, d = gh.open_game(self)
        for sid in ("snap-9-d9", "../teams", "", None, 5):
            self.assertFalse(g.restore(sid)["ok"])

    def test_a_snapshot_whose_digest_no_longer_matches_refuses_the_restore(self):
        g, ft, d = gh.open_game(self)
        play(g, ft, 6)
        sid = g.snapshot_now()
        path = os.path.join(g.snapshots.dir, sid + ".json")
        snap = json.loads(read_text(path))
        snap["digest"] = "0" * 64
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snap, f)
        before = gh.digests(g)
        gh.advance_days(g, ft, 2)
        now = gh.digests(g)
        self.assertFalse(g.restore(sid)["ok"])
        self.assertEqual(gh.digests(g), now)
        self.assertNotEqual(before, now)


if __name__ == "__main__":
    unittest.main()
