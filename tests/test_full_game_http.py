"""Stage 6 done-when: a full 52-week game with scripted teams over HTTP, restartable from the log."""
import os
import shutil
import tempfile
import threading
import unittest

import bots
import config
import engine
import game as gamemod
import gamehelpers as gh
import httpgame
import server
import store

ADMIN = "full-game-admin"
STAKE = "full-game-stake"
TEAMS = len(bots.STRATEGY_SPECS)


class FullGameOverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = config.load(dict(NUM_TEAMS=TEAMS, LOG_FSYNC=False, SECONDS_PER_DAY=1.0,
                               CHECKPOINT_PAUSE_SECONDS=2))
        cls.cfg = cfg
        cls.dir = tempfile.mkdtemp()
        cls.ft = gh.FakeTime()
        cls.game = gamemod.Game(cfg, os.path.join(cls.dir, "state"), now=cls.ft)
        static = os.path.join(cls.dir, "static")
        os.makedirs(static)
        cls.httpd = server.make_server(cls.game, "127.0.0.1", 0, ADMIN, STAKE, static)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.client = httpgame.Client("127.0.0.1", cls.httpd.server_address[1])
        codes = {t["team"]: t["code"] for t in cls.game.registry["teams"]}
        cls.teams = {n: (codes[n], bots.make_strategy(name))
                     for n, (name, _) in zip(sorted(codes), bots.STRATEGY_SPECS)}
        cls.names = {n: name for n, (name, _) in zip(sorted(codes), bots.STRATEGY_SPECS)}
        status, _ = cls.client.admin("POST", "/api/admin/clock", ADMIN, {"op": "resume"})
        assert status == 200
        cls.report = httpgame.play(cls.client, cls.teams,
                                   lambda: gh.advance_days(cls.game, cls.ft, 1))
        cls.live_digests = gh.digests(cls.game)
        cls.reveal_status = cls.client.admin("POST", "/api/admin/reveal", ADMIN, {})[0]
        cls.projector = cls.client.request("GET", "/api/projector")[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.game.close()
        shutil.rmtree(cls.dir, True)

    def test_every_team_plays_to_the_last_day(self):
        self.assertEqual(self.report.days, self.cfg["TOTAL_DAYS"])
        self.assertTrue(self.game.clock.finished)
        self.assertEqual({st["day"] for st in self.game.states.values()}, {self.cfg["TOTAL_DAYS"]})

    def test_no_action_is_refused_by_the_action_table(self):
        self.assertGreater(self.report.accepted, 100)
        self.assertEqual(self.report.validation_rejections(), [])

    def test_actions_on_a_checkpoint_pause_day_are_accepted(self):
        pause_days = {d * self.cfg["DAYS_PER_WEEK"] for d in self.cfg["CHECKPOINT_WEEKS"]}
        events, _ = store.read_events(self.game.log_path)
        acted = [e for e in events if e["kind"] == "action" and e["source"] == "team"
                 and e["day"] in pause_days]
        self.assertTrue(acted, "no team acted on a checkpoint day")

    def test_the_reveal_shows_debt_and_valuation_ranked_by_valuation(self):
        self.assertEqual(self.reveal_status, 200)
        proj = self.projector
        self.assertTrue(proj["revealed"])
        self.assertEqual(len(proj["rows"]), TEAMS)
        self.assertEqual([r["rank"] for r in proj["rows"]], list(range(1, TEAMS + 1)))
        nevs = [r["nev"] for r in proj["rows"]]
        self.assertEqual(nevs, sorted(nevs, reverse=True))
        for row in proj["rows"]:
            self.assertAlmostEqual(row["nev"], engine.score(self.cfg, self.game.states[row["team"]])["nev"])

    def test_a_scripted_do_nothing_team_finishes_below_the_measured_risk_team(self):
        by_name = {self.names[r["team"]]: r for r in self.projector["rows"]}
        self.assertGreater(by_name["measured-risk"]["nev"], by_name["do-nothing"]["nev"])

    def test_restart_from_the_log_reproduces_every_team(self):
        again = gamemod.Game(self.cfg, os.path.join(self.dir, "state"), now=gh.FakeTime())
        try:
            self.assertEqual(gh.digests(again), self.live_digests)
            self.assertTrue(again.revealed)
        finally:
            again.close()


if __name__ == "__main__":
    unittest.main()
