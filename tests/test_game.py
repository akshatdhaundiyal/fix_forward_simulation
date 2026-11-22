import unittest
from unittest import mock

import gamehelpers as gh
import config
import engine
import game as gamemod
import store


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.g, self.ft, _ = gh.open_game(self)
        self.g.clock_op("resume")

    def logged(self):
        return self.g.log.seq

    def test_a_team_cannot_submit_admin_or_system_actions(self):
        for action in (dict(type="award_bespoke"), dict(type="admin_edit", path="uod", value=0, reason="x"),
                       dict(type="trigger_incident", incident=1), dict(type="decline_result", ticks=3),
                       dict(type="cancel_incident", incident=1)):
            before = self.logged()
            res = self.g.submit(1, action)
            self.assertFalse(res["ok"], action)
            self.assertEqual(self.logged(), before)

    def test_malformed_fields_are_refused_without_an_exception_or_a_log_line(self):
        bad = [
            dict(type="queue_add", card=["A1"]), dict(type="queue_add", card=123),
            dict(type="queue_add", card="A1", report="W"), dict(type="queue_add"),
            dict(type="queue_remove", item="3"), dict(type="queue_remove", item=True),
            dict(type="queue_reorder", item=1, position="front"), dict(type="queue_reorder", item=1),
            dict(type="set_quality", mode=5), dict(type="queue_add", card="A" * 10000),
            dict(type="queue_add", card="A1", extra=1), dict(type="targeted_fix", incident=1.5, cause="x"),
            dict(type="nonsense"), dict(), "not a dict", None, dict(type=["queue_add"]),
            dict(type="queue_remove", item=10 ** 12),
        ]
        before = self.logged()
        for action in bad:
            res = self.g.submit(1, action)
            self.assertFalse(res["ok"], action)
        self.assertEqual(self.logged(), before)

    def test_an_engine_refusal_is_returned_and_not_logged(self):
        before = self.logged()
        res = self.g.submit(1, dict(type="queue_add", card="B3"))   # locked in quarter 1
        self.assertFalse(res["ok"])
        self.assertEqual(self.logged(), before)

    def test_an_unknown_team_is_refused(self):
        self.assertFalse(self.g.submit(99, dict(type="set_quality", mode="low"))["ok"])

    def test_every_accepted_action_adds_exactly_one_log_line(self):
        before = self.logged()
        self.assertTrue(self.g.submit(1, dict(type="queue_add", card="A2"))["ok"])
        self.assertEqual(self.logged(), before + 1)
        self.assertTrue(self.g.submit(1, dict(type="set_quality", mode="low"))["ok"])
        self.assertEqual(self.logged(), before + 2)


class LogFailureTests(unittest.TestCase):
    def test_a_log_failure_degrades_the_game_and_rejects_further_actions(self):
        g, ft, _ = gh.open_game(self)
        g.clock_op("resume")
        with mock.patch.object(g.log, "append", side_effect=store.LogWriteError("disk full")):
            with self.assertRaises(gamemod.Degraded):
                g.submit(1, dict(type="queue_add", card="A2"))
        self.assertEqual(g.clock.status(ft.t)["reason"], "degraded")
        self.assertFalse(g.clock.running)
        with self.assertRaises(gamemod.Degraded):
            g.submit(1, dict(type="queue_add", card="A3"))
        with self.assertRaises(gamemod.Degraded):
            g.clock_op("resume")
        ft.t += 100
        self.assertIsNone(g.pump())

    def test_reload_clears_the_degraded_state_and_drops_the_unacknowledged_change(self):
        g, ft, _ = gh.open_game(self)
        g.clock_op("resume")
        with mock.patch.object(g.log, "append", side_effect=store.LogWriteError("disk full")):
            with self.assertRaises(gamemod.Degraded):
                g.submit(1, dict(type="queue_add", card="A2"))
        self.assertTrue(g.states[1]["queue"])        # in memory only, never acknowledged
        g.reload()
        self.assertIsNone(g.degraded)
        self.assertEqual(g.states[1]["queue"], [])
        self.assertTrue(g.submit(1, dict(type="queue_add", card="A3"))["ok"])


class ClockIntegrationTests(unittest.TestCase):
    def test_game_starts_paused_and_ticks_only_after_resume(self):
        g, ft, _ = gh.open_game(self)
        ft.t += 100
        self.assertIsNone(g.pump())
        self.assertEqual(g.clock.day, 0)
        self.assertTrue(g.clock_op("resume")["ok"])
        gh.advance_days(g, ft, 5)
        self.assertEqual({st["day"] for st in g.states.values()}, {5})

    def test_pause_stops_every_team_and_actions_are_still_accepted(self):
        g, ft, _ = gh.open_game(self)
        g.clock_op("resume")
        gh.advance_days(g, ft, 3)
        g.clock_op("pause")
        ft.t += 50
        self.assertIsNone(g.pump())
        self.assertEqual(g.clock.day, 3)
        self.assertTrue(g.submit(2, dict(type="queue_add", card="A2"))["ok"])
        self.assertEqual(g.states[2]["queue"][0]["progress"], 0.0)

    def test_checkpoint_pauses_logs_it_and_resumes_by_itself(self):
        g, ft, _ = gh.open_game(self)
        g.clock_op("resume")
        gh.advance_days(g, ft, 91)
        self.assertEqual(g.clock.status(ft.t)["reason"], "checkpoint")
        events, _ = store.read_events(g.log_path)
        self.assertEqual([e["op"] for e in events if e["kind"] == "clock"][-1], "checkpoint_pause")
        ft.t += 3
        self.assertEqual(g.pump(), "auto_resume")
        self.assertTrue(g.clock.running)

    def test_clock_operations_are_logged_and_bad_values_refused(self):
        g, ft, _ = gh.open_game(self)
        before = g.log.seq
        self.assertTrue(g.clock_op("speed", 2)["ok"])
        self.assertFalse(g.clock_op("speed", 3)["ok"])
        self.assertFalse(g.clock_op("speed", "fast")["ok"])
        self.assertFalse(g.clock_op("extend", None)["ok"])
        self.assertFalse(g.clock_op("bogus")["ok"])
        self.assertEqual(g.log.seq, before + 1)


class B1AwardTests(unittest.TestCase):
    def test_top_applicants_by_whale_trust_win_and_awards_are_logged_as_system_actions(self):
        g, ft, _ = gh.open_game(self, teams=4, B1_SLOTS=2)
        g.clock_op("resume")
        gh.advance_days(g, ft, 100)
        for team, trust in ((1, 55), (2, 75), (3, 65), (4, 45)):
            self.assertTrue(g.admin_edit(team, "seg.W.trust", trust, "test setup")["ok"])
            self.assertTrue(g.submit(team, dict(type="apply_b1"))["ok"])
        gh.advance_days(g, ft, 21)
        events, _ = store.read_events(g.log_path)
        awards = [e for e in events if e["kind"] == "action" and e["source"] == "system"]
        self.assertEqual(sorted(e["team"] for e in awards), [2, 3])
        self.assertTrue(g.states[2]["b1_awarded"] and g.states[3]["b1_awarded"])
        self.assertFalse(g.states[1]["b1_awarded"])
        self.assertEqual({e["day"] for e in awards}, {119})


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.g, self.ft, _ = gh.open_game(self)

    def test_edit_needs_a_reason_and_logs_it(self):
        self.assertFalse(self.g.admin_edit(1, "uod", 5, "")["ok"])
        self.assertFalse(self.g.admin_edit(1, "uod", 5, "   ")["ok"])
        self.assertTrue(self.g.admin_edit(1, "uod", 5, "fix a mistake")["ok"])
        self.assertEqual(self.g.states[1]["uod"], 5)
        events, _ = store.read_events(self.g.log_path)
        self.assertEqual(events[-1]["action"]["reason"], "fix a mistake")
        self.assertEqual(events[-1]["source"], "admin")

    def test_edit_cannot_touch_fields_outside_the_allowed_roots(self):
        self.assertFalse(self.g.admin_edit(1, "queue", 5, "x")["ok"])
        self.assertFalse(self.g.admin_edit(1, "uod", float("nan"), "x")["ok"])

    def test_incident_trigger_and_cancel_for_all_teams(self):
        out = self.g.admin_incident("all", 1, "trigger")
        self.assertTrue(all(r["ok"] for r in out["results"].values()))
        self.assertTrue(all(st["incidents"][0]["status"] == "open" for st in self.g.states.values()))
        self.g.admin_incident("all", 1, "cancel")
        self.assertTrue(all(st["incidents"][0]["status"] == "cancelled" for st in self.g.states.values()))

    def test_incident_trigger_for_one_team_leaves_the_others_alone(self):
        self.g.admin_incident(2, 1, "trigger")
        status = {n: st["incidents"][0]["status"] for n, st in self.g.states.items()}
        self.assertEqual(status, {1: "pending", 2: "open", 3: "pending"})


class ProjectorTests(unittest.TestCase):
    def test_projector_hides_debt_and_valuation_until_the_reveal(self):
        g, ft, _ = gh.open_game(self)
        before = g.projector()
        keys = set().union(*[set(r) for r in before["rows"]])
        self.assertFalse(keys & {"uod", "nev", "penalty"})
        self.assertEqual([r["rank"] for r in before["rows"]], [1, 2, 3])
        g.reveal()
        after = g.projector()
        self.assertTrue(after["revealed"])
        self.assertTrue({"uod", "nev"} <= set(after["rows"][0]))

    def test_view_is_cached_per_version_and_changes_after_an_action(self):
        g, ft, _ = gh.open_game(self)
        etag1, body1 = g.view_response(1)
        etag2, body2 = g.view_response(1)
        self.assertEqual((etag1, body1), (etag2, body2))
        g.submit(1, dict(type="queue_add", card="A2"))
        etag3, _ = g.view_response(1)
        self.assertNotEqual(etag1, etag3)
        self.assertEqual(g.view_response(2)[0].split("-")[1], "2")

    def test_team_code_lookup(self):
        g, ft, _ = gh.open_game(self)
        code = g.registry["teams"][1]["code"]
        self.assertEqual(g.team_by_code(code), 2)
        self.assertIsNone(g.team_by_code("ZZZZZZ"))
        self.assertIsNone(g.team_by_code(""))


if __name__ == "__main__":
    unittest.main()
