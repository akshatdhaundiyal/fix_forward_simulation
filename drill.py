"""Failure drill: kill the real server and time how long the game takes to come back.

    python drill.py            run every scenario and print a table
    python drill.py kill       hard kills at three points, then a full-length log
    python drill.py spare      the primary dies while a spare follows it
    python drill.py snapshot   the log is gone and the game restarts from a snapshot

Each scenario starts real server processes, plays scripted teams over HTTP,
injects the failure, restarts, and checks that every acknowledged action is
still in the log, that no game day was lost, and that the game carries on. It
exits non-zero on any failed check or any recovery over the five-minute bar.
Router pull is a network event with no server-side effect; check it by hand
with the runbook in README.md.
"""
import argparse
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

import bots
import config
import engine
import game as gamemod
import httpgame
import replicate
import store

ROOT = os.path.dirname(os.path.abspath(__file__))
ADMIN = "drill-admin"
RECOVERY_BAR_SECONDS = 300      # spec section 13: recovery in under 5 minutes
REBUILD_TARGET_SECONDS = 60     # spec section 10.3: rebuild in under a minute
START_TIMEOUT = 120
SECONDS_PER_DAY = 0.05
FOLLOW_INTERVAL = 0.5

BURST_ACTIONS = [dict(type="queue_add", card="A2"), dict(type="queue_add", card="A3"),
                 dict(type="queue_add", report="W"), dict(type="set_quality", mode="low"),
                 dict(type="set_quality", mode="high"), dict(type="queue_add", card="P1")]


class Failed(Exception):
    pass


class ServerProc:
    """The real server in a child process, with its console output parsed."""

    def __init__(self, state_dir, teams, extra=(), new_game=False, seconds_per_day=SECONDS_PER_DAY,
                 checkpoint_pause=1):
        env = dict(os.environ, FF_ADMIN_PASSWORD=ADMIN, FF_STAKEHOLDER_PASSWORD="drill",
                   PYTHONUNBUFFERED="1")
        cmd = [sys.executable, os.path.join(ROOT, "server.py"), "--host", "127.0.0.1", "--port", "0",
               "--state-dir", state_dir, "--teams", str(teams),
               "--seconds-per-day", str(seconds_per_day),
               "--checkpoint-pause-seconds", str(checkpoint_pause)]
        cmd += list(extra)
        if new_game:
            cmd.append("--new-game")
        self.spawned = time.time()
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                  cwd=ROOT, text=True)
        self.codes, self.notes = {}, []
        while True:
            line = self._line()
            if "server on port" in line:
                self.port = int(line.split("port ")[1].split(",")[0])
                break
            self.notes.append(line)
        self.printed_after = time.time() - self.spawned
        while len(self.codes) < teams:
            parts = self._line().split()
            if len(parts) >= 3 and parts[0].isdigit():
                self.codes[int(parts[0])] = parts[-1]
        self.client = httpgame.Client("127.0.0.1", self.port, timeout=10)
        self.ready_after = None

    def _line(self):
        deadline = time.time() + START_TIMEOUT
        while time.time() < deadline:
            line = self.p.stdout.readline()
            if line:
                return line.strip()
            if self.p.poll() is not None:
                raise Failed("the server exited early with code %s" % self.p.returncode)
        raise Failed("the server did not start within %d seconds" % START_TIMEOUT)

    def wait_ready(self):
        """Seconds from spawn to the first good answer from /api/clock."""
        while True:
            try:
                status, _ = self.client.request("GET", "/api/clock")
                if status == 200:
                    self.ready_after = time.time() - self.spawned
                    return self.ready_after
            except (OSError, http.client.HTTPException):
                pass
            if time.time() - self.spawned > START_TIMEOUT:
                raise Failed("the server never answered /api/clock")
            time.sleep(0.05)

    def clock(self):
        return self.client.request("GET", "/api/clock")[1]

    def admin(self, method, path, body=None):
        return self.client.admin(method, path, ADMIN, body)

    def kill(self):
        self.p.kill()
        self.p.wait(timeout=10)
        self.p.stdout.close()

    def stop(self):
        if self.p.poll() is None:
            self.kill()


class Play:
    """Scripted teams acting over HTTP, remembering every action the server acknowledged."""

    def __init__(self, proc, strategies):
        self.proc = proc
        self.teams = {n: (proc.codes[n], bots.make_strategy(strategies[(n - 1) % len(strategies)]))
                      for n in sorted(proc.codes)}
        self.acked = []          # (team, action key, wall time of the acknowledgement)

    def round(self):
        day = self.proc.clock()["day"]
        for n, (code, strategy) in self.teams.items():
            view = httpgame.team_view(self.proc.client, code, strategy)
            for action in strategy(view, day):
                self._post(n, code, action)

    def _post(self, n, code, action):
        status, result = self.proc.client.request("POST", "/api/team/%s/action" % code, {"action": action})
        if status == 200 and result.get("ok"):
            self.acked.append((n, key(action), time.time()))

    def until(self, stop):
        """Play rounds, one per game day, until stop(clock) is true."""
        while True:
            clock = self.proc.clock()
            if stop(clock):
                return clock
            if clock["finished"]:
                raise Failed("the game ended before the kill point")
            self.round()
            httpgame.wait_for_next_day(self.proc.client, timeout=60)()

    def burst(self, seconds):
        """Every team posting as fast as it can, from its own thread."""
        stop = time.time() + seconds
        lock = threading.Lock()

        def client(n, code):
            i = 0
            while time.time() < stop:
                action = BURST_ACTIONS[(i * 5 + n) % len(BURST_ACTIONS)]
                i += 1
                try:
                    status, result = self.proc.client.request(
                        "POST", "/api/team/%s/action" % code, {"action": action})
                except (OSError, http.client.HTTPException, ValueError):
                    return
                if status == 200 and result.get("ok"):
                    with lock:
                        self.acked.append((n, key(action), time.time()))

        threads = [threading.Thread(target=client, args=(n, c)) for n, (c, _) in self.teams.items()]
        for t in threads:
            t.start()
        return threads


def key(action):
    return json.dumps(action, sort_keys=True)


def logged_actions(state_dir):
    events, _ = store.read_events(os.path.join(state_dir, config.LOG_FILE))
    return collections.Counter(
        (e["team"], key(e["action"])) for e in events if e["kind"] == "action" and e["source"] == "team")


def tick_count(state_dir):
    events, _ = store.read_events(os.path.join(state_dir, config.LOG_FILE))
    return sum(1 for e in events if e["kind"] == "tick")


def lost_actions(acked, state_dir):
    """Acknowledged actions missing from the log in state_dir, as (team, key, time) tuples."""
    have = logged_actions(state_dir)
    lost = []
    for n, k, when in acked:
        if have[(n, k)] > 0:
            have[(n, k)] -= 1
        else:
            lost.append((n, k, when))
    return lost


def check_carries_on(proc, days=2):
    """Resume a restarted server and see the day move on with every team readable."""
    start = proc.clock()
    if start["running"]:
        raise Failed("a restarted server came back running; it must come back paused")
    status, _ = proc.admin("POST", "/api/admin/clock", {"op": "resume"})
    if status != 200:
        raise Failed("resume answered %s" % status)
    httpgame.wait_for_next_day(proc.client, timeout=30)()
    for _ in range(days - 1):
        httpgame.wait_for_next_day(proc.client, timeout=30)()
    if proc.clock()["day"] <= start["day"]:
        raise Failed("the day did not move after a restart")
    for code in proc.codes.values():
        if proc.client.request("GET", "/api/team/%s/view" % code)[0] != 200:
            raise Failed("a team view failed after a restart")
    return start["day"]


# --- scenarios -------------------------------------------------------------
def row(scenario, case, seconds, rebuild, ok, detail):
    return dict(scenario=scenario, case=case, seconds=seconds, rebuild=rebuild, ok=ok, detail=detail)


def recover(scenario, case, state_dir, teams, acked, killed_at, extra_checks=None):
    """Restart on state_dir, time it, and run the checks every scenario shares."""
    problems = []
    lost = lost_actions(acked, state_dir)
    if lost:
        problems.append("%d acknowledged actions missing from the log" % len(lost))
    proc = ServerProc(state_dir, teams)
    try:
        seconds = proc.wait_ready()
        if proc.clock()["day"] != tick_count(state_dir):
            problems.append("restarted day %s is not the logged tick count %s"
                            % (proc.clock()["day"], tick_count(state_dir)))
        day = check_carries_on(proc)
        if extra_checks:
            problems += extra_checks(proc)
        if seconds > RECOVERY_BAR_SECONDS:
            problems.append("recovery took %.0f s, over the %d s bar" % (seconds, RECOVERY_BAR_SECONDS))
        note = "restarted at day %d (killed at day %d), %d acknowledged actions kept" % (
            day, killed_at, len(acked))
    except Failed as exc:
        problems.append(str(exc))
        seconds, note = proc.ready_after or float("nan"), "failed"
    finally:
        proc.stop()
    return row(scenario, case, seconds, proc.printed_after, not problems, "; ".join(problems) or note)


def scenario_kill(teams):
    rows = []
    names = [n for n, _ in bots.STRATEGY_SPECS]
    for case in ("mid-quarter", "checkpoint pause", "action burst"):
        tmp = tempfile.mkdtemp()
        state = os.path.join(tmp, "state")
        proc = ServerProc(state, teams)
        try:
            proc.wait_ready()
            play = Play(proc, names)
            proc.admin("POST", "/api/admin/clock", {"op": "resume"})
            if case == "mid-quarter":
                killed_at = play.until(lambda c: c["day"] >= 25)["day"]
            elif case == "checkpoint pause":
                killed_at = play.until(lambda c: c["reason"] == "checkpoint")["day"]
            else:
                play.until(lambda c: c["day"] >= 20)
                threads = play.burst(2.0)
                time.sleep(1.0)
                killed_at = proc.clock()["day"]
                proc.kill()                          # no warning, mid-burst
                for t in threads:
                    t.join()
            if proc.p.poll() is None:
                proc.kill()
            rows.append(recover("kill", case, state, teams, play.acked, killed_at))
        except Failed as exc:
            rows.append(row("kill", case, float("nan"), float("nan"), False, str(exc)))
        finally:
            proc.stop()
            shutil.rmtree(tmp, True)
    return rows


def build_full_log(state_dir, teams, days):
    """A finished-looking game log built in process, faster than a live clock."""
    cfg = config.load(dict(NUM_TEAMS=teams, LOG_FSYNC=False, SECONDS_PER_DAY=1.0,
                           CHECKPOINT_PAUSE_SECONDS=2))
    clock = [1000.0]
    game = gamemod.Game(cfg, state_dir, now=lambda: clock[0])
    try:
        names = [n for n, _ in bots.STRATEGY_SPECS]
        strategies = {n: bots.make_strategy(names[(n - 1) % len(names)]) for n in game.states}
        game.clock_op("resume")
        while game.clock.day < days and not game.clock.finished:
            for n, strategy in strategies.items():
                view = engine.team_view(cfg, game.states[n], series_days=1)
                for action in strategy(view, game.clock.day):
                    game.submit(n, action)
            before = game.clock.day
            while game.clock.day == before and not game.clock.finished:
                clock[0] += 1.0
                game.pump()
    finally:
        game.close()
    return game.clock.day


def scenario_long_log(teams, days):
    tmp = tempfile.mkdtemp()
    state = os.path.join(tmp, "state")
    try:
        built = time.time()
        reached = build_full_log(state, teams, days)
        size = os.path.getsize(os.path.join(state, config.LOG_FILE))
        proc = ServerProc(state, teams)
        try:
            seconds = proc.wait_ready()
            problems = []
            if seconds > RECOVERY_BAR_SECONDS:
                problems.append("recovery took %.0f s, over the %d s bar" % (seconds, RECOVERY_BAR_SECONDS))
            if proc.printed_after > REBUILD_TARGET_SECONDS:
                problems.append("rebuild took %.0f s, over the spec's %d s" % (
                    proc.printed_after, REBUILD_TARGET_SECONDS))
            note = "%d teams, day %d, log %.1f MB, built in %.0f s" % (
                teams, reached, size / 1e6, time.time() - built)
            return row("kill", "full-length log", seconds, proc.printed_after, not problems,
                       "; ".join(problems) or note)
        finally:
            proc.stop()
    except Failed as exc:
        return row("kill", "full-length log", float("nan"), float("nan"), False, str(exc))
    finally:
        shutil.rmtree(tmp, True)


def scenario_spare(teams):
    tmp = tempfile.mkdtemp()
    primary, spare = os.path.join(tmp, "primary"), os.path.join(tmp, "spare")
    names = [n for n, _ in bots.STRATEGY_SPECS]
    proc = ServerProc(primary, teams)
    stop = threading.Event()
    last_round = [0.0]
    try:
        proc.wait_ready()
        follower = replicate.Follower("127.0.0.1:%d" % proc.port, ADMIN, spare)

        def follow():
            while not stop.is_set():
                started = time.time()
                try:
                    follower.pull_once()
                    last_round[0] = started
                except (OSError, replicate.Diverged):
                    pass
                stop.wait(FOLLOW_INTERVAL)

        thread = threading.Thread(target=follow, daemon=True)
        thread.start()
        play = Play(proc, names)
        proc.admin("POST", "/api/admin/clock", {"op": "resume"})
        killed_at = play.until(lambda c: c["day"] >= 30)["day"]
        proc.admin("POST", "/api/admin/snapshot")
        time.sleep(FOLLOW_INTERVAL * 2)
        proc.kill()
        stop.set()
        thread.join(timeout=5)
        late = [a for a in play.acked if a[2] >= last_round[0]]
        lost = lost_actions(play.acked, spare)
        unexpected = [a for a in lost if a not in late]
        recovered = recover("spare", "primary killed", spare, teams, [a for a in play.acked if a not in lost],
                            killed_at)
        if unexpected:
            recovered["ok"] = False
            recovered["detail"] += "; %d actions older than the last pull were lost" % len(unexpected)
        else:
            recovered["detail"] += "; %d acknowledged after the last pull were not on the spare" % len(lost)
        return [recovered]
    except Failed as exc:
        return [row("spare", "primary killed", float("nan"), float("nan"), False, str(exc))]
    finally:
        stop.set()
        proc.stop()
        shutil.rmtree(tmp, True)


def scenario_snapshot(teams):
    tmp = tempfile.mkdtemp()
    state = os.path.join(tmp, "state")
    names = [n for n, _ in bots.STRATEGY_SPECS]
    proc = ServerProc(state, teams)
    try:
        proc.wait_ready()
        play = Play(proc, names)
        proc.admin("POST", "/api/admin/clock", {"op": "resume"})
        play.until(lambda c: c["day"] >= 30)
        proc.admin("POST", "/api/admin/snapshot")
        snap_day = proc.clock()["day"]
        proc.kill()
        snaps = os.path.join(state, config.SNAPSHOT_DIR)
        newest = sorted(n for n in os.listdir(snaps) if n.endswith(".json"))[-1]
        keep = os.path.join(tmp, "only-this-snapshot")
        os.makedirs(keep)
        shutil.copy(os.path.join(snaps, newest), os.path.join(keep, newest))
        shutil.copy(os.path.join(state, config.REGISTRY_FILE), os.path.join(keep, config.REGISTRY_FILE))
        shutil.rmtree(state)                                  # the log is gone
        again = ServerProc(state, teams, extra=["--from-snapshot", os.path.join(keep, newest),
                                                "--registry", os.path.join(keep, config.REGISTRY_FILE)])
        try:
            seconds = again.wait_ready()
            problems = []
            day = again.clock()["day"]
            if not 0 < day <= snap_day:
                problems.append("started at day %s, snapshot taken near day %s" % (day, snap_day))
            check_carries_on(again, days=28)
            note = "started from a bare snapshot at day %d, carried on to day %d" % (day, again.clock()["day"])
            return [row("snapshot", "log deleted", seconds, again.printed_after, not problems,
                        "; ".join(problems) or note)]
        finally:
            again.stop()
    except Failed as exc:
        return [row("snapshot", "log deleted", float("nan"), float("nan"), False, str(exc))]
    finally:
        proc.stop()
        shutil.rmtree(tmp, True)


# --- report ------------------------------------------------------------------
def table(rows):
    lines = ["%-9s %-17s %9s %9s  %-4s %s" % ("scenario", "case", "ready (s)", "build (s)", "ok", "detail")]
    for r in rows:
        lines.append("%-9s %-17s %9.1f %9.1f  %-4s %s" % (
            r["scenario"], r["case"], r["seconds"], r["rebuild"], "yes" if r["ok"] else "NO", r["detail"]))
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="Kill the real server and time the recovery")
    p.add_argument("scenario", nargs="?", default="all", choices=["all", "kill", "spare", "snapshot"])
    p.add_argument("--teams", type=int, default=6, help="teams for the scripted games")
    p.add_argument("--long-teams", type=int, default=16, help="teams in the full-length log case")
    p.add_argument("--long-days", type=int, default=360, help="days in that log; 0 skips the case")
    args = p.parse_args(argv)
    rows = []
    if args.scenario in ("all", "kill"):
        rows += scenario_kill(args.teams)
        if args.long_days:
            rows.append(scenario_long_log(args.long_teams, args.long_days))
    if args.scenario in ("all", "spare"):
        rows += scenario_spare(args.teams)
    if args.scenario in ("all", "snapshot"):
        rows += scenario_snapshot(args.teams)
    print(table(rows))
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
