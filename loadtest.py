"""Load test: a room of polling consoles against the real server for a full game.

    python loadtest.py                       16 teams, 20 consoles, one game day per second
    python loadtest.py --full-length         the event's pace, 13 seconds per game day

The server runs as a child process. Each of the 16 scripted teams plays through
the same HTTP routes a browser uses, and 20 consoles poll the clock and their
team view every 3 seconds with the ETag, as the console does. Half of them also
fetch the funnel and operations windows on every fifth poll, which are the
heaviest views. An accelerated clock changes the view more often than the
event's pace does, so it is the harder case. When the game ends the server is
killed and its log is replayed, which checks every tick's digest.
It exits non-zero if any bar below is missed.
"""
import argparse
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import time

import bots
import config
import game as gamemod
import httpgame
from drill import ServerProc

# Pass bars. These are properties of the test, not game numbers.
P99_BAR_SECONDS = 1.0            # slowest 1% of requests
TICK_P95_OVER = 0.25             # clock ticks may run this much late at the 95th percentile
LATENESS_MIN_SECONDS_PER_DAY = 0.5   # below this the 20 ms clock sampling is too coarse to judge
OK_STATUSES = (200, 304)
SAMPLE_SECONDS = 0.02
WINDOW_EVERY = 5                 # a console with a window tab open refetches it every 5th poll
FUNNEL_DAYS = 91
OPERATIONS_DAYS = 182


def percentile(values, q):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


class Recorder:
    def __init__(self):
        self.rows = []     # (kind, seconds, status), appended from many threads

    def timed(self, kind, call):
        start = time.perf_counter()
        try:
            status = call()
        except (OSError, http.client.HTTPException, ValueError):
            status = 0
        self.rows.append((kind, time.perf_counter() - start, status))
        return status


class KeepAlive:
    """One persistent connection, as a browser holds. Reconnects once if it was dropped."""

    def __init__(self, port, timeout=10):
        self.port, self.timeout, self.conn = port, timeout, None

    def raw(self, method, path, body=None, etag=None):
        headers = {"Content-Type": "application/json"}
        if etag:
            headers["If-None-Match"] = etag
        data = None if body is None else json.dumps(body).encode()
        for attempt in (0, 1):
            try:
                if self.conn is None:
                    self.conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=self.timeout)
                self.conn.request(method, path, body=data, headers=headers)
                resp = self.conn.getresponse()
                payload = resp.read()
                return resp.status, resp.getheader("ETag"), payload
            except (OSError, http.client.HTTPException):
                self.close()
                if attempt:
                    raise

    def request(self, method, path, body=None, headers=None):
        """Same shape as httpgame.Client.request: (status, parsed json or None)."""
        status, _, payload = self.raw(method, path, body)
        return status, (json.loads(payload) if payload else None)

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None


def console(port, code, index, poll, detail, recorder, stop):
    """One browser: clock and view with the ETag, plus window views if it has a tab open."""
    link = KeepAlive(port)
    etags = {}
    count = 0
    stop.wait(poll * (index % 20) / 20.0)           # spread the first polls like real page loads
    while not stop.is_set():
        count += 1
        recorder.timed("clock", lambda: link.raw("GET", "/api/clock")[0])
        paths = [("view", "/api/team/%s/view" % code)]
        if detail and count % WINDOW_EVERY == 0:
            paths += [("funnel", "/api/team/%s/view?days=%d&slices=1" % (code, FUNNEL_DAYS)),
                      ("operations", "/api/team/%s/view?days=%d" % (code, OPERATIONS_DAYS))]
        for kind, path in paths:
            def call(path=path):
                status, etag, _ = link.raw("GET", path, etag=etags.get(path))
                if etag:
                    etags[path] = etag
                return status
            recorder.timed(kind, call)
        stop.wait(poll)
    link.close()


def team_driver(port, code, strategy, recorder, stop, errors, every):
    """One scripted team: decide once per game day, over the routes a browser uses."""
    client = KeepAlive(port)
    last = -1
    while not stop.is_set():
        try:
            status, clock = client.request("GET", "/api/clock")
            if status == 200 and clock["day"] != last and not clock["finished"]:
                last = clock["day"]
                view = recorder_call(recorder, "team view", lambda: httpgame.team_view(client, code, strategy))
                for action in strategy(view, last):
                    recorder.timed("action", lambda: action_status(client, code, action))
        except (OSError, http.client.HTTPException, RuntimeError, ValueError) as exc:
            errors.append(str(exc))
        stop.wait(every)
    client.close()


def action_status(client, code, action):
    """HTTP status of an action, where a game rule saying no (a full queue, say) is a good answer.

    Only an action the table rejects, or a server fault, counts as a failure.
    """
    status, result = client.request("POST", "/api/team/%s/action" % code, {"action": action})
    if status == 400 and not (result or {}).get("error", "").startswith(httpgame.VALIDATION_PREFIXES):
        return 200
    return status


def recorder_call(recorder, kind, call):
    start = time.perf_counter()
    result = call()
    recorder.rows.append((kind, time.perf_counter() - start, 200))
    return result


def watch_ticks(port, stop, ticks):
    """Wall time at which the server's day was first seen to change."""
    client = KeepAlive(port, timeout=5)
    last = None
    while not stop.is_set():
        try:
            status, clock = client.request("GET", "/api/clock")
            if status == 200:
                if last is not None and clock["day"] != last[0]:
                    ticks.append((clock["day"], time.time(), clock["running"]))
                last = (clock["day"], clock["running"])
                if clock["finished"]:
                    return
        except (OSError, http.client.HTTPException, ValueError):
            pass
        stop.wait(SAMPLE_SECONDS)


def tick_gaps(ticks):
    """Seconds between consecutive ordinary ticks, skipping the gaps around a pause."""
    gaps = []
    pause_days = {w * config.DAYS_PER_WEEK for w in config.CHECKPOINT_WEEKS}
    for (d0, t0, _), (d1, t1, _) in zip(ticks, ticks[1:]):
        if d1 == d0 + 1 and d0 not in pause_days:
            gaps.append(t1 - t0)
    return gaps


def evaluate(rows, ticks, seconds_per_day):
    """The verdict as a list of problems. Empty means every bar was met."""
    problems = []
    bad = [r for r in rows if r[2] not in OK_STATUSES]
    if bad:
        statuses = sorted({r[2] for r in bad})
        problems.append("%d requests failed (statuses %s)" % (len(bad), statuses))
    p99 = percentile([r[1] for r in rows], 0.99)
    if p99 > P99_BAR_SECONDS:
        problems.append("p99 latency %.0f ms is over %.0f ms" % (p99 * 1000, P99_BAR_SECONDS * 1000))
    if seconds_per_day >= LATENESS_MIN_SECONDS_PER_DAY:
        gaps = tick_gaps(ticks)
        if gaps:
            late = percentile(gaps, 0.95) / seconds_per_day - 1
            if late > TICK_P95_OVER:
                problems.append("clock ticks ran %.0f%% late at the 95th percentile" % (late * 100))
    return problems


def table(rows, ticks, seconds_per_day):
    lines = ["%-12s %8s %7s %9s %9s %9s %6s" % ("request", "count", "errors", "p50 (ms)", "p99 (ms)", "max (ms)", "304s")]
    for kind in sorted({r[0] for r in rows}):
        sub = [r for r in rows if r[0] == kind]
        secs = [r[1] for r in sub]
        lines.append("%-12s %8d %7d %9.1f %9.1f %9.1f %5.0f%%" % (
            kind, len(sub), sum(1 for r in sub if r[2] not in OK_STATUSES),
            percentile(secs, 0.5) * 1000, percentile(secs, 0.99) * 1000, max(secs) * 1000,
            100.0 * sum(1 for r in sub if r[2] == 304) / len(sub)))
    gaps = tick_gaps(ticks)
    if gaps and seconds_per_day >= LATENESS_MIN_SECONDS_PER_DAY:
        lines.append("clock: %d ordinary ticks, median gap %.3f s, p95 %.3f s, max %.3f s (target %.3f s)" % (
            len(gaps), percentile(gaps, 0.5), percentile(gaps, 0.95), max(gaps), seconds_per_day))
    return "\n".join(lines)


def run(teams=16, clients=20, seconds_per_day=1.0, poll=3.0, checkpoint_pause=5, verify=True):
    """Play a full game with polling consoles. Returns (rows, ticks, problems, summary)."""
    tmp = tempfile.mkdtemp()
    state = os.path.join(tmp, "state")
    proc = ServerProc(state, teams, seconds_per_day=seconds_per_day, checkpoint_pause=checkpoint_pause)
    recorder, ticks, errors = Recorder(), [], []
    stop = threading.Event()
    threads = []
    try:
        proc.wait_ready()
        names = [n for n, _ in bots.STRATEGY_SPECS]
        for n, code in sorted(proc.codes.items()):
            strategy = bots.make_strategy(names[(n - 1) % len(names)])
            threads.append(threading.Thread(target=team_driver, args=(
                proc.port, code, strategy, recorder, stop, errors, max(0.1, seconds_per_day / 4)),
                daemon=True))
        codes = sorted(proc.codes.values())
        for i in range(clients):
            threads.append(threading.Thread(target=console, args=(
                proc.port, codes[i % len(codes)], i, poll, i % 2 == 0, recorder, stop), daemon=True))
        threads.append(threading.Thread(target=watch_ticks, args=(proc.port, stop, ticks), daemon=True))
        for t in threads:
            t.start()
        proc.admin("POST", "/api/admin/clock", {"op": "resume"})
        limit = time.time() + 2 * (config.TOTAL_DAYS * seconds_per_day + 3 * checkpoint_pause) + 120
        while not proc.clock()["finished"]:
            if time.time() > limit:
                raise RuntimeError("the game did not finish in time")
            time.sleep(0.2)
        stop.set()
        for t in threads:
            t.join(timeout=15)
        problems = evaluate(recorder.rows, ticks, seconds_per_day)
        if errors:
            problems.append("%d scripted-team errors, first: %s" % (len(errors), errors[0]))
        summary = "%d teams, %d consoles, %d requests" % (teams, clients, len(recorder.rows))
        proc.kill()
        if verify:
            try:
                again = gamemod.Game(config.load(dict(NUM_TEAMS=teams)), state, now=time.time)
                again.close()
            except gamemod.GameError as exc:
                problems.append("replaying the log failed: %s" % exc)
        return recorder.rows, ticks, problems, summary
    finally:
        stop.set()
        proc.stop()
        shutil.rmtree(tmp, True)


def main(argv=None):
    p = argparse.ArgumentParser(description="Load test with polling consoles")
    p.add_argument("--teams", type=int, default=16)
    p.add_argument("--clients", type=int, default=20)
    p.add_argument("--seconds-per-day", type=float, default=1.0)
    p.add_argument("--poll", type=float, default=float(config.TEAM_POLL_SECONDS))
    p.add_argument("--checkpoint-pause", type=float, default=5)
    p.add_argument("--full-length", action="store_true",
                   help="the event's pace of 13 seconds per game day with 60-second breaks (about 90 minutes)")
    args = p.parse_args(argv)
    if args.full_length:
        args.seconds_per_day, args.checkpoint_pause = float(config.SECONDS_PER_DAY), 60
    rows, ticks, problems, summary = run(args.teams, args.clients, args.seconds_per_day, args.poll,
                                         args.checkpoint_pause)
    print(summary)
    print(table(rows, ticks, args.seconds_per_day))
    print("PASS" if not problems else "FAIL: " + "; ".join(problems))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
