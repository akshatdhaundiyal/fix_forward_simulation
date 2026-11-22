"""The stage's done-when: kill the real server process mid-game and restart it."""
import collections
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import helpers
import config
import engine
import game as gamemod
import store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN = "kill-test-admin"
TEAMS = 4
START_TIMEOUT = 20


class Proc:
    """The real server in a child process, with its console output parsed."""

    def __init__(self, state_dir, new_game=False):
        env = dict(os.environ, FF_ADMIN_PASSWORD=ADMIN, FF_STAKEHOLDER_PASSWORD="x", PYTHONUNBUFFERED="1")
        cmd = [sys.executable, os.path.join(ROOT, "server.py"), "--host", "127.0.0.1", "--port", "0",
               "--state-dir", state_dir, "--teams", str(TEAMS), "--seconds-per-day", "0.05",
               "--checkpoint-pause-seconds", "1"]
        if new_game:
            cmd.append("--new-game")
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                  cwd=ROOT, text=True)
        self.codes = {}
        first = self._line()
        self.port = int(first.split("port ")[1].split(",")[0])
        self.start_line = first
        while len(self.codes) < TEAMS:
            parts = self._line().split()
            if len(parts) >= 3 and parts[0].isdigit():
                self.codes[int(parts[0])] = parts[-1]

    def _line(self):
        deadline = time.time() + START_TIMEOUT
        while time.time() < deadline:
            line = self.p.stdout.readline()
            if line:
                return line.strip()
            if self.p.poll() is not None:
                raise AssertionError("server exited early with %s" % self.p.returncode)
        raise AssertionError("server did not start")

    def call(self, method, path, body=None, admin=False):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            headers = {"Content-Type": "application/json"}
            if admin:
                headers["X-Admin-Password"] = ADMIN
            conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
            r = conn.getresponse()
            data = r.read()
            return r.status, json.loads(data) if data else None
        finally:
            conn.close()

    def kill(self):
        self.p.kill()
        self.p.wait(timeout=10)
        self.p.stdout.close()

    def stop(self):
        if self.p.poll() is None:
            self.kill()


ACTIONS = [dict(type="queue_add", card="A2"), dict(type="queue_add", card="A3"),
           dict(type="queue_add", card="A4"), dict(type="queue_add", card="A5"),
           dict(type="queue_add", report="W"), dict(type="queue_add", report="M"),
           dict(type="set_quality", mode="low"), dict(type="set_quality", mode="high"),
           dict(type="set_quality", mode="medium"), dict(type="queue_add", card="P1"),
           dict(type="queue_reorder", item=1, position=0), dict(type="queue_remove", item=2)]


class KillRestartTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.state = os.path.join(self.dir, "state")
        self.cfg = config.load(dict(NUM_TEAMS=TEAMS))

    def _burst(self, proc, seconds, acked):
        stop = time.time() + seconds

        def client(team):
            i = 0
            while time.time() < stop:
                action = ACTIONS[(i * 7 + team) % len(ACTIONS)]
                i += 1
                try:
                    status, data = proc.call("POST", "/api/team/%s/action" % proc.codes[team],
                                             dict(action=action))
                except (OSError, http.client.HTTPException, ValueError):
                    return
                if status == 200 and data.get("ok"):
                    acked.append((team, json.dumps(action, sort_keys=True)))

        threads = [threading.Thread(target=client, args=(t,)) for t in proc.codes]
        for th in threads:
            th.start()
        return threads

    def test_kill_during_a_burst_of_actions_loses_nothing_acknowledged_and_no_day(self):
        proc = Proc(self.state)
        self.addCleanup(proc.stop)
        self.assertIn("PAUSED", proc.start_line)
        self.assertEqual(proc.call("POST", "/api/admin/clock", dict(op="resume"), admin=True)[0], 200)
        acked = []
        threads = self._burst(proc, 4.0, acked)
        time.sleep(2.5)
        proc.kill()                                    # no warning, mid-burst
        for th in threads:
            th.join(timeout=10)
        self.assertGreater(len(acked), 20)

        events, _ = store.read_events(os.path.join(self.state, self.cfg["LOG_FILE"]))
        logged = collections.Counter(
            (e["team"], json.dumps(e["action"], sort_keys=True)) for e in events
            if e["kind"] == "action" and e["source"] == "team")
        for key, n in collections.Counter(acked).items():
            self.assertGreaterEqual(logged[key], n, "acknowledged action missing from the log: %s" % (key,))
        ticks = [e["day"] for e in events if e["kind"] == "tick"]
        self.assertGreater(len(ticks), 10)
        self.assertEqual(ticks, list(range(len(ticks))))

        # the restarted process recovers to exactly what the log implies, paused
        again = Proc(self.state)
        self.addCleanup(again.stop)
        self.assertIn("PAUSED", again.start_line)
        self.assertEqual(again.codes, proc.codes)
        status, clock = again.call("GET", "/api/clock")
        self.assertEqual((clock["day"], clock["running"], clock["reason"]), (len(ticks), False, "restart"))
        again.stop()
        check = gamemod.Game(self.cfg, self.state, now=time.monotonic)
        self.addCleanup(check.close)
        self.assertEqual(check.clock.day, len(ticks))
        replayed = engine.replay(check.cfg, check.cfg["GAME_SEED"], 1, [
            (e["day"], e["action"]) for e in events
            if e["kind"] == "action" and e["team"] == 1], until_day=len(ticks))
        self.assertEqual(engine.state_digest(replayed), engine.state_digest(check.states[1]))

    def test_resuming_after_the_restart_continues_without_skipping_or_repeating_a_day(self):
        proc = Proc(self.state)
        self.addCleanup(proc.stop)
        proc.call("POST", "/api/admin/clock", dict(op="resume"), admin=True)
        time.sleep(1.2)
        proc.kill()
        again = Proc(self.state)
        self.addCleanup(again.stop)
        before = again.call("GET", "/api/clock")[1]["day"]
        self.assertEqual(again.call("POST", "/api/admin/clock", dict(op="resume"), admin=True)[0], 200)
        deadline = time.time() + 10
        while time.time() < deadline and again.call("GET", "/api/clock")[1]["day"] < before + 5:
            time.sleep(0.1)
        again.stop()
        events, _ = store.read_events(os.path.join(self.state, self.cfg["LOG_FILE"]))
        ticks = [e["day"] for e in events if e["kind"] == "tick"]
        self.assertEqual(ticks, list(range(len(ticks))))
        self.assertGreaterEqual(len(ticks), before + 5)

    def test_a_kill_after_the_first_checkpoint_recovers_through_the_pause(self):
        proc = Proc(self.state)
        self.addCleanup(proc.stop)
        proc.call("POST", "/api/admin/clock", dict(op="speed", value=10), admin=True)
        proc.call("POST", "/api/admin/clock", dict(op="resume"), admin=True)
        deadline = time.time() + 20
        day = 0
        while time.time() < deadline and day < 95:
            time.sleep(0.2)
            day = proc.call("GET", "/api/clock")[1]["day"]
        self.assertGreaterEqual(day, 91)
        proc.kill()
        again = Proc(self.state)
        self.addCleanup(again.stop)
        clock = again.call("GET", "/api/clock")[1]
        self.assertGreaterEqual(clock["day"], 91)
        self.assertEqual((clock["running"], clock["reason"], clock["speed"]), (False, "restart", 10))


if __name__ == "__main__":
    unittest.main()
