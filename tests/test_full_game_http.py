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
import helpers
import httpgame
import server
import store

ADMIN = "full-game-admin"
STAKE = "full-game-stake"
TEAMS = len(bots.STRATEGY_SPECS)
PER_QUARTER = config.BOOKINGS_PER_ROLE_PER_QUARTER
# Game days on which every team tries a booking, one set per quarter, and what it tries.
BOOK_DAYS = {5: "cto", 96: None, 187: "cto", 278: "vp_sales"}    # None: each team picks a role by number
ROLES = [r["id"] for r in config.STAKEHOLDER_ROLES]
MEET_DAY = 40
DECLINE_DAY = 20


class Desk:
    """Teams booking and stakeholders meeting and declining, driven from the game's day."""

    def __init__(self, client, codes):
        self.desk = httpgame.StakeholderDesk(client, STAKE)
        self.codes = codes
        self.booking_results = []     # (day, team, role, status, message)
        self.decline_results = []     # (team, status, message)
        self.boards = []

    def step(self, day):
        if day in BOOK_DAYS:
            for team, code in sorted(self.codes.items()):
                role = BOOK_DAYS[day] or ROLES[team % len(ROLES)]
                status, result = self.desk.book(code, role)
                self.booking_results.append((day, team, role, status, (result or {}).get("error", "")))
        if day == MEET_DAY:
            board = self.desk.board()
            self.boards.append(board)
            for booking in board["bookings"][:2]:
                assert self.desk.meet(booking["id"])[0] == 200
        if day == DECLINE_DAY:
            for team in sorted(self.codes):
                if team % 2 == 0:
                    for _ in range(2):               # the second entry for a team must be refused
                        status, result = self.desk.decline(team, team % 4)
                        self.decline_results.append((team, status, (result or {}).get("error", "")))


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
        cls.desk = Desk(cls.client, {n: code for n, (code, _) in cls.teams.items()})

        def advance():
            cls.desk.step(cls.game.clock.day)
            gh.advance_days(cls.game, cls.ft, 1)

        cls.report = httpgame.play(cls.client, cls.teams, advance)
        cls.live_board = cls.desk.desk.board()
        cls.live_trust = {n: st["seg"]["W"]["trust"] for n, st in cls.game.states.items()}
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

    def test_a_full_quarter_refuses_the_sixth_team_and_a_new_quarter_opens_fresh_places(self):
        by_day = {}
        for day, team, role, status, message in self.desk.booking_results:
            by_day.setdefault(day, []).append((team, role, status, message))
        first = by_day[5]
        self.assertEqual(sum(1 for r in first if r[2] == 200), PER_QUARTER)
        refused = [r for r in first if r[2] != 200]
        self.assertEqual(len(refused), TEAMS - PER_QUARTER)
        self.assertTrue(all("taken" in r[3] for r in refused))
        self.assertTrue(all(r[2] == 200 for r in by_day[96]), by_day[96])    # roles by team number, new quarter
        self.assertEqual(sum(1 for r in by_day[187] if r[2] == 200), PER_QUARTER)
        self.assertEqual(sum(1 for r in by_day[278] if r[2] == 200), PER_QUARTER)

    def test_no_stakeholder_quarter_holds_more_than_its_places_and_the_first_come_win(self):
        for role in ROLES:
            for quarter in (1, 2, 3, 4):
                held = [b for b in self.live_board["bookings"] if b["role"] == role and b["quarter"] == quarter]
                self.assertLessEqual(len(held), PER_QUARTER, (role, quarter))
        q1 = [b["team"] for b in self.live_board["bookings"] if b["role"] == "cto" and b["quarter"] == 1]
        self.assertEqual(q1, sorted(self.desk.codes)[:PER_QUARTER])

    def test_every_decline_is_accepted_once_and_a_repeat_is_refused(self):
        teams = [t for t in self.desk.codes if t % 2 == 0]
        results = [r for r in self.desk.decline_results]
        self.assertEqual(len(results), 2 * len(teams))
        for i, team in enumerate(teams):
            first, second = results[2 * i], results[2 * i + 1]
            self.assertEqual((first[0], first[1]), (team, 200))
            self.assertEqual((second[0], second[1]), (team, 400))
            self.assertIn("already entered", second[2])
        self.assertEqual({t["team"] for t in self.live_board["teams"] if t["declined"]}, set(teams))

    def test_meetings_marked_done_show_on_the_board(self):
        done = [b for b in self.live_board["bookings"] if b["done"]]
        self.assertEqual(len(done), 2)

    def test_no_board_or_booking_response_carries_a_hidden_field_or_the_debt(self):
        hidden = set(self.cfg["HIDDEN_FIELD_NAMES"])
        _, mine = self.client.request("GET", "/api/team/%s/bookings" % self.desk.codes[1])
        for body in (self.live_board, mine, *self.desk.boards):
            self.assertFalse(helpers.all_keys(body) & hidden)
        live_uod = [repr(round(st["uod"], 6)) for st in self.game.states.values() if st["uod"]]
        text = str(self.live_board)
        for number in live_uod:
            self.assertNotIn(number, text)

    def test_restart_from_the_log_reproduces_every_team_and_the_board(self):
        again = gamemod.Game(self.cfg, os.path.join(self.dir, "state"), now=gh.FakeTime())
        try:
            self.assertEqual(gh.digests(again), self.live_digests)
            self.assertTrue(again.revealed)
            board = again.stakeholder_board()
            self.assertEqual(board["bookings"], self.live_board["bookings"])
            self.assertEqual([t["declined"] for t in board["teams"]],
                             [t["declined"] for t in self.live_board["teams"]])
            self.assertEqual({n: st["seg"]["W"]["trust"] for n, st in again.states.items()}, self.live_trust)
        finally:
            again.close()


if __name__ == "__main__":
    unittest.main()
