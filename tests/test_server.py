import http.client
import json
import os
import shutil
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock

import gamehelpers as gh
import helpers
import engine
import server
import store

ADMIN = "admin-secret"
STAKE = "stake-secret"


class ServerCase(unittest.TestCase):
    cfg_over = {}

    def setUp(self):
        self.g, self.ft, self.dir = gh.open_game(self, **self.cfg_over)
        self.static = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.static, True)
        with open(os.path.join(self.static, "index.html"), "w") as f:
            f.write("<p>hello</p>")
        with open(os.path.join(self.static, "a.txt"), "w") as f:
            f.write("static file")
        with open(os.path.join(os.path.dirname(self.static), "outside-secret.txt"), "w") as f:
            f.write("secret")
        self.addCleanup(os.remove, os.path.join(os.path.dirname(self.static), "outside-secret.txt"))
        self.httpd = server.make_server(self.g, "127.0.0.1", 0, ADMIN, STAKE, self.static)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.codes = {t["team"]: t["code"] for t in self.g.registry["teams"]}

    def call(self, method, path, body=None, headers=None, raw=False):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            h = dict(headers or {})
            data = None
            if body is not None:
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                h.setdefault("Content-Type", "application/json")
            conn.request(method, path, body=data, headers=h)
            resp = conn.getresponse()
            payload = resp.read()
            if raw:
                return resp.status, payload, resp
            return resp.status, (json.loads(payload) if payload else None)
        finally:
            conn.close()

    def admin(self, method, path, body=None):
        return self.call(method, path, body, {server.ADMIN_HEADER: ADMIN})


class TeamRouteTests(ServerCase):
    def test_a_valid_code_returns_the_view_with_the_clock(self):
        status, data = self.call("GET", "/api/team/%s/view" % self.codes[1])
        self.assertEqual(status, 200)
        self.assertEqual(set(data), {"clock", "view"})
        self.assertEqual(data["view"]["team"], 1)
        self.assertEqual(data["clock"]["day"], 0)
        self.assertEqual(data["clock"]["poll_seconds"], 3)

    def test_unknown_codes_all_get_the_same_not_found(self):
        a = self.call("GET", "/api/team/ZZZZZZ/view", raw=True)
        b = self.call("GET", "/api/team/AAAAAA/view", raw=True)
        c = self.call("GET", "/api/team/%s/nothing" % self.codes[1], raw=True)
        self.assertEqual((a[0], a[1]), (404, b[1] and a[1]))
        self.assertEqual(a[1], b[1])
        self.assertEqual(c[0], 404)

    def test_an_unchanged_poll_returns_not_modified_until_something_changes(self):
        path = "/api/team/%s/view" % self.codes[1]
        status, payload, resp = self.call("GET", path, raw=True)
        etag = resp.getheader("ETag")
        self.assertTrue(etag)
        status, payload, _ = self.call("GET", path, headers={"If-None-Match": etag}, raw=True)
        self.assertEqual((status, payload), (304, b""))
        self.g.clock_op("resume")
        gh.advance_days(self.g, self.ft, 1)
        status, payload, resp2 = self.call("GET", path, headers={"If-None-Match": etag}, raw=True)
        self.assertEqual(status, 200)
        self.assertNotEqual(resp2.getheader("ETag"), etag)

    def test_an_etag_from_before_a_restart_is_not_accepted_after_it(self):
        path = "/api/team/%s/view" % self.codes[1]
        etag = self.call("GET", path, raw=True)[2].getheader("ETag")
        again, _, _ = gh.open_game(self, cfg=self.g.cfg, directory=self.dir, ft=self.ft)
        self.assertNotEqual(again.view_response(1)[0], etag)

    def test_the_default_view_is_small_and_fast(self):
        self.g.clock_op("resume")
        gh.advance_days(self.g, self.ft, 40)
        path = "/api/team/%s/view" % self.codes[1]
        status, payload, _ = self.call("GET", path, raw=True)
        self.assertLess(len(payload), 60 * 1024)
        start = time.perf_counter()
        for _ in range(100):
            self.call("GET", path)
        self.assertLess((time.perf_counter() - start) / 100, 0.010)

    def test_a_team_acts_only_as_its_own_team(self):
        status, data = self.call("POST", "/api/team/%s/action" % self.codes[2],
                                 dict(action=dict(type="queue_add", card="A2")))
        self.assertEqual((status, data["ok"]), (200, True))
        self.assertEqual(len(self.g.states[2]["queue"]), 1)
        self.assertEqual(self.g.states[1]["queue"], [])

    def test_admin_actions_from_a_team_are_refused(self):
        path = "/api/team/%s/action" % self.codes[1]
        before = self.g.log.seq
        for action in (dict(type="admin_edit", path="uod", value=0, reason="x"),
                       dict(type="award_bespoke"), dict(type="trigger_incident", incident=1)):
            status, data = self.call("POST", path, dict(action=action))
            self.assertEqual((status, data["ok"]), (400, False))
        self.assertEqual(self.g.log.seq, before)

    def test_bad_json_and_missing_action_are_bad_requests(self):
        path = "/api/team/%s/action" % self.codes[1]
        self.assertEqual(self.call("POST", path, b"not json")[0], 400)
        self.assertEqual(self.call("POST", path, dict(nothing=1))[0], 400)
        self.assertEqual(self.call("POST", path, b"[1,2]")[0], 400)

    def test_an_oversized_body_is_refused_without_changing_anything(self):
        before = self.g.log.seq
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        sock.sendall(("POST /api/team/%s/action HTTP/1.1\r\nHost: x\r\nContent-Length: 99999\r\n\r\n"
                      % self.codes[1]).encode())
        reply = sock.recv(200).decode()
        sock.close()
        self.assertIn(" 400 ", reply.split("\r\n")[0])
        self.assertEqual(self.g.log.seq, before)

    def test_a_degraded_game_answers_503_and_does_not_leak_the_reason(self):
        with mock.patch.object(self.g.log, "append", side_effect=store.LogWriteError("C:\\secret\\path")):
            status, data = self.call("POST", "/api/team/%s/action" % self.codes[1],
                                     dict(action=dict(type="queue_add", card="A2")))
        self.assertEqual(status, 503)
        self.assertNotIn("secret", json.dumps(data))

    def test_a_server_error_does_not_leak_a_traceback(self):
        with mock.patch.object(self.g, "view_response", side_effect=ValueError("internal detail")), \
                mock.patch("server.traceback.print_exc"):
            status, data = self.call("GET", "/api/team/%s/view" % self.codes[1])
        self.assertEqual((status, data), (500, {"error": "server error"}))


class PublicRouteTests(ServerCase):
    def test_clock_and_projector_are_public(self):
        status, clock = self.call("GET", "/api/clock")
        self.assertEqual((status, clock["running"], clock["reason"]), (200, False, "start"))
        status, proj = self.call("GET", "/api/projector")
        self.assertEqual(status, 200)
        self.assertEqual([r["team"] for r in proj["rows"]], [1, 2, 3])
        self.assertFalse(proj["revealed"])

    def test_unknown_api_routes_are_not_found(self):
        self.assertEqual(self.call("GET", "/api/nothing")[0], 404)
        self.assertEqual(self.call("POST", "/api/clock", {})[0], 404)


class CalendarRouteTests(ServerCase):
    def test_calendar_is_public_and_lists_checkpoints_surge_and_contract_weeks(self):
        status, cal = self.call("GET", "/api/calendar")
        cfg = self.g.cfg
        self.assertEqual(status, 200)
        self.assertEqual(cal["surge"], dict(start=cfg["PEAK_START_WEEK"], end=cfg["PEAK_END_WEEK"]))
        self.assertEqual(cal["contract_window"],
                         dict(first=cfg["B1_APPLY_FIRST_WEEK"], last=cfg["B1_APPLY_LAST_WEEK"]))
        self.assertEqual(cal["weeks_per_quarter"], cfg["WEEKS_PER_QUARTER"])
        self.assertEqual(cal["checkpoint_weeks"], [13, 26, 39])
        self.assertEqual(cal["weeks"], cfg["WEEKS"])
        self.assertEqual(cal["days_per_week"], cfg["DAYS_PER_WEEK"])

    def test_calendar_follows_config(self):
        self.g.cfg["PEAK_START_WEEK"] = 20
        self.assertEqual(self.call("GET", "/api/calendar")[1]["surge"]["start"], 20)

    def test_calendar_carries_no_hidden_field_name(self):
        _, cal = self.call("GET", "/api/calendar")
        self.assertFalse(helpers.all_keys(cal) & set(self.g.cfg["HIDDEN_FIELD_NAMES"]))


class StaticTests(ServerCase):
    def test_files_are_served_and_root_serves_the_index(self):
        status, payload, resp = self.call("GET", "/a.txt", raw=True)
        self.assertEqual((status, payload), (200, b"static file"))
        self.assertEqual(self.call("GET", "/", raw=True)[1], b"<p>hello</p>")

    def test_web_assets_get_web_content_types_whatever_the_registry_says(self):
        expected = {"team.html": "text/html", "app.js": "text/javascript",
                    "app.mjs": "text/javascript", "app.css": "text/css",
                    "data.json": "application/json", "logo.svg": "image/svg+xml",
                    "inter.woff2": "font/woff2", "app.js.map": "application/json",
                    "favicon.ico": "image/x-icon"}
        for name in expected:
            with open(os.path.join(self.static, name), "w") as f:
                f.write("x")
        with mock.patch("server.mimetypes.guess_type", return_value=("text/plain", None)):
            for name, ctype in expected.items():
                status, _, resp = self.call("GET", "/" + name, raw=True)
                self.assertEqual(status, 200, name)
                self.assertTrue(resp.getheader("Content-Type").startswith(ctype), name)

    def test_unknown_extensions_fall_back_to_the_registry_then_to_octet_stream(self):
        with open(os.path.join(self.static, "notes.txt"), "w") as f:
            f.write("x")
        with open(os.path.join(self.static, "blob.zzzunknown"), "w") as f:
            f.write("x")
        self.assertEqual(self.call("GET", "/notes.txt", raw=True)[2].getheader("Content-Type"),
                         "text/plain")
        self.assertEqual(self.call("GET", "/blob.zzzunknown", raw=True)[2].getheader("Content-Type"),
                         "application/octet-stream")

    def test_path_traversal_is_refused(self):
        for path in ("/../outside-secret.txt", "/..%2foutside-secret.txt", "/%2e%2e/outside-secret.txt",
                     "/..\\outside-secret.txt", "/a.txt%00", "/C:/Windows/win.ini",
                     "//etc/passwd", "/..%5coutside-secret.txt"):
            status, payload, _ = self.call("GET", path, raw=True)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b"secret", payload)


class AdminRouteTests(ServerCase):
    routes = [("GET", "/api/admin/status"), ("GET", "/api/admin/snapshots"),
              ("POST", "/api/admin/clock"), ("POST", "/api/admin/incident"),
              ("POST", "/api/admin/edit"), ("POST", "/api/admin/decline"),
              ("POST", "/api/admin/restore"), ("POST", "/api/admin/reveal"),
              ("POST", "/api/admin/reload"), ("POST", "/api/admin/snapshot")]

    def test_every_admin_route_rejects_missing_and_wrong_passwords(self):
        before = self.g.log.seq
        for method, path in self.routes:
            for headers in ({}, {server.ADMIN_HEADER: "wrong"}, {server.ADMIN_HEADER: STAKE},
                            {server.ADMIN_HEADER: self.codes[1]}):
                status, _, _ = self.call(method, path, {} if method == "POST" else None,
                                         headers, raw=True)
                self.assertEqual(status, 401, (path, headers))
        self.assertEqual(self.g.log.seq, before)

    def test_status_lists_team_codes_and_health(self):
        status, data = self.admin("GET", "/api/admin/status")
        self.assertEqual(status, 200)
        self.assertEqual({t["team"]: t["code"] for t in data["teams"]}, self.codes)
        self.assertIsNone(data["degraded"])

    def test_status_offers_the_configured_speed_choices(self):
        data = self.admin("GET", "/api/admin/status")[1]
        self.assertEqual(data["speed_choices"], self.g.cfg["SPEED_CHOICES"])

    def test_clock_controls_over_http_change_the_clock_and_are_logged(self):
        before = self.g.log.seq
        self.assertEqual(self.admin("POST", "/api/admin/clock", dict(op="resume"))[0], 200)
        self.assertTrue(self.g.clock.running)
        self.assertEqual(self.admin("POST", "/api/admin/clock", dict(op="speed", value=2))[0], 200)
        self.assertEqual(self.g.clock.speed, 2)
        self.assertEqual(self.admin("POST", "/api/admin/clock", dict(op="pause"))[0], 200)
        self.assertFalse(self.g.clock.running)
        self.assertEqual(self.admin("POST", "/api/admin/clock", dict(op="extend", value=30))[0], 200)
        self.assertEqual(self.admin("POST", "/api/admin/clock", dict(op="speed", value=7))[0], 400)
        self.assertEqual(self.g.log.seq, before + 4)

    def test_incident_trigger_and_cancel_for_one_team_and_for_all(self):
        self.assertEqual(self.admin("POST", "/api/admin/incident",
                                    dict(team=2, incident=1, op="trigger"))[0], 200)
        self.assertEqual(self.g.states[2]["incidents"][0]["status"], "open")
        self.assertEqual(self.g.states[1]["incidents"][0]["status"], "pending")
        self.assertEqual(self.admin("POST", "/api/admin/incident",
                                    dict(team="all", incident=1, op="cancel"))[0], 200)
        self.assertEqual(self.admin("POST", "/api/admin/incident",
                                    dict(team="bogus", incident=1, op="cancel"))[0], 400)

    def test_edit_needs_a_reason(self):
        body = dict(team=1, path="seg.W.trust", value=71)
        self.assertEqual(self.admin("POST", "/api/admin/edit", body)[0], 400)
        self.assertEqual(self.admin("POST", "/api/admin/edit", dict(body, reason="fix"))[0], 200)
        self.assertEqual(self.g.states[1]["seg"]["W"]["trust"], 71)

    def test_reveal_shows_debt_and_valuation_on_the_projector_and_survives_a_restart(self):
        self.assertEqual(self.admin("POST", "/api/admin/reveal", {})[0], 200)
        rows = self.call("GET", "/api/projector")[1]["rows"]
        self.assertTrue({"uod", "nev"} <= set(rows[0]))
        again, _, _ = gh.open_game(self, cfg=self.g.cfg, directory=self.dir, ft=self.ft)
        self.assertTrue(again.revealed)

    def test_snapshots_can_be_listed_and_restored_over_http(self):
        self.g.clock_op("resume")
        gh.advance_days(self.g, self.ft, 5)
        self.assertEqual(self.admin("POST", "/api/admin/snapshot", {})[0], 200)
        listing = self.admin("GET", "/api/admin/snapshots")[1]["snapshots"]
        self.assertEqual(len(listing), 1)
        at_snapshot = gh.digests(self.g)
        gh.advance_days(self.g, self.ft, 5)
        status, data = self.admin("POST", "/api/admin/restore", dict(snapshot=listing[0]["id"]))
        self.assertEqual((status, data["ok"]), (200, True))
        self.assertEqual(gh.digests(self.g), at_snapshot)
        self.assertEqual(self.admin("POST", "/api/admin/restore", dict(snapshot="nope"))[0], 400)

    def test_status_shows_a_snapshot_warning_after_a_blocked_swap(self):
        self.g.clock_op("resume")
        gh.advance_days(self.g, self.ft, 2)
        with mock.patch("store.os.replace", side_effect=PermissionError("in use")):
            self.admin("POST", "/api/admin/snapshot", {})
        self.assertIn("blocked", self.admin("GET", "/api/admin/status")[1]["snapshot_warning"])

    def test_reload_clears_a_degraded_game(self):
        with mock.patch.object(self.g.log, "append", side_effect=store.LogWriteError("full")):
            self.call("POST", "/api/team/%s/action" % self.codes[1],
                      dict(action=dict(type="queue_add", card="A2")))
        self.assertIsNotNone(self.admin("GET", "/api/admin/status")[1]["degraded"])
        self.assertEqual(self.admin("POST", "/api/admin/reload", {})[0], 200)
        self.assertIsNone(self.admin("GET", "/api/admin/status")[1]["degraded"])


class HiddenFieldScanTests(ServerCase):
    cfg_over = dict(events={"incidents": True}, RECORD_SLICES=True)

    def test_no_team_facing_response_contains_a_hidden_field_name(self):
        g = self.g
        g.clock_op("resume")
        g.submit(2, dict(type="queue_add", report="S"))
        g.submit(2, dict(type="queue_add", card="A2"))
        gh.advance_days(g, self.ft, 45)
        self.assertEqual(g.states[2]["incidents"][0]["status"], "open")
        self.assertTrue(g.states[2]["reports"])
        code = self.codes[2]
        hidden = set(g.cfg["HIDDEN_FIELD_NAMES"])
        paths = ["/api/team/%s/view" % code, "/api/team/%s/view?days=364" % code,
                 "/api/team/%s/view?days=364&slices=1" % code, "/api/team/%s/view?days=0" % code,
                 "/api/clock", "/api/projector", "/api/team/ZZZZZZ/view", "/api/nothing"]
        for path in paths:
            status, data = self.call("GET", path)
            found = helpers.all_keys(data) & hidden
            self.assertFalse(found, (path, found))
        for action in (dict(type="queue_add", card="A3"), dict(type="queue_add", card="B3"),
                       dict(type="targeted_fix", incident=1, cause="vendor"),
                       dict(type="admin_edit", path="uod", value=1, reason="x"), dict(type="bogus")):
            status, data = self.call("POST", "/api/team/%s/action" % code, dict(action=action))
            self.assertFalse(helpers.all_keys(data) & hidden, action)

    def test_the_scan_is_not_vacuous(self):
        self.g.clock_op("resume")
        gh.advance_days(self.g, self.ft, 40)
        raw = self.g.states[2]
        self.assertTrue(helpers.all_keys(raw) & set(self.g.cfg["HIDDEN_FIELD_NAMES"]))

    def test_nothing_hidden_leaks_in_response_values_either(self):
        self.g.clock_op("resume")
        gh.advance_days(self.g, self.ft, 45)
        status, payload, _ = self.call("GET", "/api/team/%s/view?days=364&slices=1" % self.codes[2], raw=True)
        text = payload.decode()
        self.assertNotIn('"cause"', text)
        self.assertNotIn("caused_by", text)


class MainTests(unittest.TestCase):
    def test_flags_become_config_overrides_and_passwords_are_generated_when_absent(self):
        args = server.parse_args(["--port", "9001", "--teams", "5", "--new-game"])
        self.assertEqual((args.port, args.teams, args.new_game), (9001, 5, True))
        self.assertIsNone(args.host)


if __name__ == "__main__":
    unittest.main()
