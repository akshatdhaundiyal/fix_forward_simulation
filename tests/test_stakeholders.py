import re
import unittest

import gamehelpers as gh
import helpers
import engine
import server
from test_server import ADMIN, STAKE, ServerCase

SH = {server.STAKEHOLDER_HEADER: STAKE}


def set_day(g, day):
    g.clock.day = day


class BookingRuleTests(unittest.TestCase):
    def test_the_sixth_team_in_a_quarter_is_refused_and_the_first_five_keep_their_order(self):
        g, ft, _ = gh.open_game(self, teams=6)
        for n in range(1, 6):
            self.assertTrue(g.book(n, "cto")["ok"])
        res = g.book(6, "cto")
        self.assertFalse(res["ok"])
        self.assertIn("taken", res["error"])
        self.assertEqual([b["team"] for b in g.board["bookings"]], [1, 2, 3, 4, 5])
        self.assertTrue(g.book(6, "vp_sales")["ok"])         # other stakeholders have their own places

    def test_a_team_cannot_book_twice_in_a_quarter_but_can_in_the_next(self):
        g, ft, _ = gh.open_game(self)
        self.assertTrue(g.book(1, "cto")["ok"])
        self.assertFalse(g.book(1, "cto")["ok"])
        set_day(g, 92)
        self.assertTrue(g.book(1, "cto")["ok"])

    def test_the_break_after_a_quarter_counts_toward_that_quarter(self):
        g, ft, _ = gh.open_game(self)
        set_day(g, 91)
        g.book(1, "cto")
        set_day(g, 92)
        g.book(2, "cto")
        self.assertEqual([b["quarter"] for b in g.board["bookings"]], [1, 2])

    def test_unknown_stakeholder_and_unknown_team_are_refused(self):
        g, ft, _ = gh.open_game(self)
        self.assertFalse(g.book(1, "janitor")["ok"])
        self.assertFalse(g.book(99, "cto")["ok"])
        self.assertEqual(g.board["bookings"], [])

    def test_a_team_sees_its_queue_position_and_places_left(self):
        g, ft, _ = gh.open_game(self)
        g.book(2, "cto")
        g.book(1, "cto")
        mine = next(r for r in g.team_bookings(1)["roles"] if r["role"] == "cto")
        self.assertEqual((mine["places_left"], mine["mine"]["position"]), (3, 2))
        g.mark_done(g.board["bookings"][0]["id"])
        mine = next(r for r in g.team_bookings(1)["roles"] if r["role"] == "cto")
        self.assertEqual(mine["mine"]["position"], 1)
        other = next(r for r in g.team_bookings(3)["roles"] if r["role"] == "cto")
        self.assertIsNone(other["mine"])

    def test_places_reset_when_the_quarter_changes(self):
        g, ft, _ = gh.open_game(self, teams=5)
        for n in range(1, 6):
            g.book(n, "vp_sales")
        full = next(r for r in g.team_bookings(1)["roles"] if r["role"] == "vp_sales")
        self.assertEqual(full["places_left"], 0)
        set_day(g, 92)
        fresh = next(r for r in g.team_bookings(1)["roles"] if r["role"] == "vp_sales")
        self.assertEqual(fresh["places_left"], 5)

    def test_marking_done_twice_or_an_unknown_booking_is_refused(self):
        g, ft, _ = gh.open_game(self)
        bid = g.book(1, "cto")["booking"]
        self.assertTrue(g.mark_done(bid)["ok"])
        self.assertFalse(g.mark_done(bid)["ok"])
        self.assertFalse(g.mark_done(9999)["ok"])
        self.assertFalse(g.mark_done(True)["ok"])


class DeclineTests(unittest.TestCase):
    def whale_trust(self, g, team=1):
        return g.states[team]["seg"]["W"]["trust"]

    def test_a_second_entry_is_refused_and_whale_trust_moves_once(self):
        for ticks, delta in ((3, 5), (2, 0), (1, -5), (0, -5)):
            g, ft, _ = gh.open_game(self)
            before = self.whale_trust(g)
            self.assertTrue(g.stakeholder_decline(1, ticks)["ok"])
            self.assertFalse(g.stakeholder_decline(1, ticks)["ok"])
            self.assertEqual(self.whale_trust(g), before + delta)

    def test_bad_ticks_and_teams_are_refused_without_a_trust_change(self):
        g, ft, _ = gh.open_game(self)
        before = self.whale_trust(g)
        for team, ticks in ((1, 4), (1, -1), (1, "3"), (1, True), (1, None), (99, 3), (None, 3)):
            self.assertFalse(g.stakeholder_decline(team, ticks)["ok"], (team, ticks))
        self.assertEqual(self.whale_trust(g), before)

    def test_the_decline_survives_a_restart_and_still_blocks_a_second_entry(self):
        g, ft, d = gh.open_game(self)
        g.stakeholder_decline(2, 3)
        again, _, _ = gh.open_game(self, cfg=g.cfg, directory=d, ft=ft)
        self.assertEqual(gh.digests(again), gh.digests(g))
        self.assertFalse(again.stakeholder_decline(2, 0)["ok"])
        self.assertTrue(again.stakeholder_board()["teams"][1]["declined"])


class AdminDeclineTests(unittest.TestCase):
    def test_the_admin_route_follows_the_same_once_per_team_rule_in_either_order(self):
        g, ft, d = gh.open_game(self)
        before = g.states[1]["seg"]["W"]["trust"]
        self.assertTrue(g.stakeholder_decline(1, 3)["ok"])
        res = g.decline_result(1, 0)
        self.assertFalse(res["ok"])
        self.assertIn("admin edit", res["error"])
        self.assertEqual(g.states[1]["seg"]["W"]["trust"], before + 5)
        self.assertTrue(g.decline_result(2, 1)["ok"])
        self.assertFalse(g.stakeholder_decline(2, 3)["ok"])
        again, _, _ = gh.open_game(self, cfg=g.cfg, directory=d, ft=ft)
        self.assertEqual(gh.digests(again), gh.digests(g))
        self.assertEqual({t["team"] for t in again.stakeholder_board()["teams"] if t["declined"]}, {1, 2})

    def test_a_restore_past_a_decline_and_a_meeting_done_clears_both(self):
        g, ft, d = gh.open_game(self)
        bid = g.book(1, "cto")["booking"]
        snap = g.snapshot_now()
        trust = g.states[2]["seg"]["W"]["trust"]
        g.mark_done(bid)
        g.stakeholder_decline(2, 3)
        self.assertTrue(g.restore(snap)["ok"])
        self.assertFalse(g.board["bookings"][0]["done"])
        self.assertEqual(g.board["declined"], {})
        self.assertEqual(g.states[2]["seg"]["W"]["trust"], trust)
        self.assertTrue(g.stakeholder_decline(2, 3)["ok"])

    def test_a_non_integer_team_is_a_refusal_not_an_error(self):
        g, ft, _ = gh.open_game(self)
        for team in ([1], {"a": 1}, "1", 1.0):
            self.assertFalse(g.stakeholder_decline(team, 3)["ok"], team)


class QuarterTests(unittest.TestCase):
    def test_booking_quarter_boundaries(self):
        cfg = helpers.make_cfg()
        got = [config_quarter(cfg, d) for d in (0, 1, 91, 92, 182, 183, 273, 274, 364, 400)]
        self.assertEqual(got, [1, 1, 1, 2, 2, 3, 3, 4, 4, 4])


def config_quarter(cfg, day):
    import config
    return config.booking_quarter(cfg, day)


class RecoveryTests(unittest.TestCase):
    def test_a_restart_rebuilds_the_same_board_including_a_meeting_marked_done(self):
        g, ft, d = gh.open_game(self)
        g.clock_op("resume")
        g.book(1, "cto")
        gh.advance_days(g, ft, 3)
        b2 = g.book(2, "cto")["booking"]
        g.book(2, "vp_sales")
        g.mark_done(b2)
        live = g.stakeholder_board()["bookings"]
        again, _, _ = gh.open_game(self, cfg=g.cfg, directory=d, ft=ft)
        self.assertEqual(again.stakeholder_board()["bookings"], live)
        self.assertTrue(next(b for b in live if b["id"] == b2)["done"])

    def test_a_restore_past_a_booking_drops_it_and_one_after_it_keeps_it(self):
        g, ft, d = gh.open_game(self)
        g.book(1, "cto")
        early = g.snapshot_now()
        g.book(2, "cto")
        late = g.snapshot_now()
        self.assertTrue(g.restore(early)["ok"])
        self.assertEqual([b["team"] for b in g.board["bookings"]], [1])
        again, _, _ = gh.open_game(self, cfg=g.cfg, directory=d, ft=ft)
        self.assertEqual([b["team"] for b in again.board["bookings"]], [1])
        g2, ft2, _ = gh.open_game(self)
        g2.book(1, "cto")
        snap = g2.snapshot_now()
        g2.book(2, "cto")
        self.assertTrue(g2.restore(snap)["ok"])
        self.assertEqual(len(g2.board["bookings"]), 1)
        g3, ft3, _ = gh.open_game(self)
        g3.book(1, "cto")
        g3.book(2, "cto")
        snap = g3.snapshot_now()
        self.assertTrue(g3.restore(snap)["ok"])
        self.assertEqual(len(g3.board["bookings"]), 2)

    def test_the_snapshot_carries_the_board(self):
        g, ft, _ = gh.open_game(self)
        g.book(1, "cto")
        snap = g.snapshots.read(g.snapshot_now())
        self.assertEqual(snap["board"]["bookings"][0]["team"], 1)


class BoardTests(unittest.TestCase):
    def test_the_cto_band_is_green_at_15_amber_at_16_and_red_at_31(self):
        g, ft, _ = gh.open_game(self)
        for uod, band in ((0, "green"), (15, "green"), (16, "amber"), (30, "amber"), (31, "red")):
            g.states[1]["uod"] = float(uod)
            self.assertEqual(g.stakeholder_board()["teams"][0]["band"], band, uod)

    def test_whale_facts_change_with_isolation_outage_and_application(self):
        g, ft, _ = gh.open_game(self)
        facts = lambda: g.stakeholder_board()["teams"][0]["whale"]["facts"]
        self.assertEqual(facts(), dict(data_isolation_shipped=False, outage_hit=False, applied=False))
        g.states[1]["shipped"][g.cfg["WHALE_LEAD_CARD"]] = dict(debt=0)
        self.assertTrue(facts()["data_isolation_shipped"])
        g.states[1]["events"].append(dict(kind="outage", day=1, owed=30.0))
        self.assertTrue(facts()["outage_hit"])
        g.states[1]["b1_applied"] = True
        self.assertTrue(facts()["applied"])

    def test_the_whale_quarter_3_lines_appear_only_when_their_fact_holds(self):
        g, ft, _ = gh.open_game(self)
        set_day(g, 2 * 91 + 5)
        lines = lambda: g.stakeholder_board()["teams"][0]["whale"]["lines"]
        self.assertEqual(len(lines()), 1)
        self.assertIn("data isolation", lines()[0])
        g.states[1]["shipped"][g.cfg["WHALE_LEAD_CARD"]] = dict(debt=0)
        self.assertEqual(lines(), [])
        g.states[1]["events"].append(dict(kind="outage", day=1, owed=30.0))
        self.assertIn("outage", lines()[0])

    def test_the_cto_line_matches_the_teams_band_and_quarter_1_has_none(self):
        g, ft, _ = gh.open_game(self)
        self.assertIsNone(g.stakeholder_board()["teams"][0]["cto_line"])
        set_day(g, 91 + 5)
        cards = g.cfg["SCRIPT_CARDS"][2]["cto"]["bands"]
        for uod, band in ((0, "green"), (20, "amber"), (40, "red")):
            g.states[1]["uod"] = float(uod)
            row = g.stakeholder_board()["teams"][0]
            self.assertEqual((row["band"], row["cto_line"]), (band, cards[band]))

    def test_the_board_lists_the_current_quarters_cards(self):
        g, ft, _ = gh.open_game(self)
        for q in (1, 2, 3, 4):
            set_day(g, (q - 1) * 91 + 3)
            board = g.stakeholder_board()
            self.assertEqual(board["quarter"], q)
            self.assertEqual([r["role"] for r in board["roles"]], ["vp_sales", "whale_lead", "cto"])
            self.assertEqual(board["roles"][0]["unprompted"], g.cfg["SCRIPT_CARDS"][q]["vp_sales"]["unprompted"])


class ScriptCardTests(unittest.TestCase):
    def setUp(self):
        self.cfg = helpers.make_cfg()

    def texts(self, card):
        out = [card.get("unprompted") or "", card.get("after") or ""]
        for q, a in card["asked"]:
            out += [q, a]
        out += list(card.get("bands", {}).values())
        out += [c["text"] for c in card.get("conditional", [])]
        return out

    def test_every_quarter_has_all_roles_with_unprompted_text_or_lines_and_a_question(self):
        roles = [r["id"] for r in self.cfg["STAKEHOLDER_ROLES"]]
        for q in (1, 2, 3, 4):
            for role in roles:
                card = self.cfg["SCRIPT_CARDS"][q][role]
                self.assertGreaterEqual(len(card["asked"]), 1, (q, role))
                has_text = (card.get("unprompted") or card.get("bands") or card.get("conditional"))
                self.assertTrue(has_text, (q, role))

    def test_no_card_text_names_a_hidden_number(self):
        banned = re.compile(r"\bUOD\b|\bNEV\b|risk points?|utility score|\bdebt\b", re.I)
        for q, roles in self.cfg["SCRIPT_CARDS"].items():
            for role, card in roles.items():
                for text in self.texts(card):
                    self.assertIsNone(banned.search(text), (q, role, text))

    def test_conditional_lines_read_known_facts(self):
        facts = {"data_isolation_shipped", "outage_hit", "applied"}
        for roles in self.cfg["SCRIPT_CARDS"].values():
            for c in roles["whale_lead"].get("conditional", []):
                self.assertIn(c["when"], facts)


class StakeholderRouteTests(ServerCase):
    def team_book(self, team, role):
        return self.call("POST", "/api/team/%s/bookings" % self.codes[team], dict(role=role))

    def test_the_same_401_on_every_route_without_the_stakeholder_password(self):
        routes = [("GET", "/api/stakeholder/board", None), ("POST", "/api/stakeholder/done", dict(booking=1)),
                  ("POST", "/api/stakeholder/decline", dict(team=1, ticks=3))]
        for headers in (None, {server.STAKEHOLDER_HEADER: "wrong"}, {server.ADMIN_HEADER: ADMIN},
                        {server.STAKEHOLDER_HEADER: ""}):
            seen = set()
            for method, path, body in routes:
                status, data = self.call(method, path, body, headers)
                seen.add((status, data["error"]))
            self.assertEqual(seen, {(401, "unauthorized")}, headers)

    def test_the_stakeholder_password_does_not_open_the_admin_routes(self):
        status, _ = self.call("GET", "/api/admin/status", None, SH)
        self.assertEqual(status, 401)

    def test_booking_over_http_then_marking_done_and_declining(self):
        status, data = self.team_book(1, "cto")
        self.assertEqual(status, 200, data)
        status, data = self.team_book(1, "cto")
        self.assertEqual(status, 400)
        self.assertIn("already booked", data["error"])
        status, board = self.call("GET", "/api/stakeholder/board", None, SH)
        self.assertEqual(status, 200)
        booking = board["bookings"][0]
        self.assertEqual((booking["team"], booking["role"], booking["done"]), (1, "cto", False))
        self.assertEqual(self.call("POST", "/api/stakeholder/done", dict(booking=booking["id"]), SH)[0], 200)
        self.assertEqual(self.call("POST", "/api/stakeholder/done", dict(booking=booking["id"]), SH)[0], 400)
        status, _ = self.call("POST", "/api/stakeholder/decline", dict(team=1, ticks=3), SH)
        self.assertEqual(status, 200)
        status, data = self.call("POST", "/api/stakeholder/decline", dict(team=1, ticks=3), SH)
        self.assertEqual(status, 400)
        _, mine = self.call("GET", "/api/team/%s/bookings" % self.codes[1])
        self.assertTrue(next(r for r in mine["roles"] if r["role"] == "cto")["mine"]["done"])

    def test_unknown_paths_and_bodies_with_a_valid_password(self):
        self.assertEqual(self.call("GET", "/api/stakeholder/nothing", None, SH)[0], 404)
        self.assertEqual(self.call("POST", "/api/stakeholder/nothing", {}, SH)[0], 404)
        self.assertEqual(self.call("POST", "/api/stakeholder/done", {}, SH)[0], 400)
        self.assertEqual(self.call("POST", "/api/stakeholder/done", b"[1]", SH)[0], 400)
        self.assertEqual(self.call("POST", "/api/stakeholder/decline", dict(team=[1], ticks=3), SH)[0], 400)

    def test_a_bad_booking_body_is_a_400(self):
        status, _ = self.call("POST", "/api/team/%s/bookings" % self.codes[1], dict(role=3))
        self.assertEqual(status, 400)
        status, _ = self.call("GET", "/api/team/NOPE00/bookings")
        self.assertEqual(status, 404)

    def test_no_stakeholder_or_booking_response_carries_a_hidden_field_or_debt_number(self):
        hidden = set(self.g.cfg["HIDDEN_FIELD_NAMES"])
        self.g.states[1]["uod"] = 23.456
        self.team_book(1, "cto")
        for q in (0, 91 + 3, 2 * 91 + 3, 3 * 91 + 3):
            set_day(self.g, q)
            _, board = self.call("GET", "/api/stakeholder/board", None, SH)
            _, mine = self.call("GET", "/api/team/%s/bookings" % self.codes[1])
            for body in (board, mine):
                self.assertFalse(helpers.all_keys(body) & hidden, q)
                self.assertNotIn("23.456", str(body))
                self.assertNotIn("uod", str(body).lower())
            self.assertEqual(board["teams"][0]["band"], "amber")
            for t in board["teams"]:
                self.assertEqual(set(t), {"team", "name", "band", "cto_line", "whale", "declined"})
                self.assertEqual(set(t["whale"]), {"facts", "lines"})
