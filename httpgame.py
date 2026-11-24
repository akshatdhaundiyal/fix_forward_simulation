"""Play scripted strategies against a running server over HTTP, as browsers do.

The scripted strategies in bots.py decide from the same team view a browser
receives, so this harness fetches the view, asks the strategy for actions and
posts them. It uses only the standard library. The full-game test drives it
with a fake clock, and the stage 7 load test will run many of these at once.

    python httpgame.py --port 8000 --admin-password PW CODE1:measured-risk CODE2:do-nothing
"""
import argparse
import http.client
import json
import sys
import time

import bots

ADMIN_HEADER = "X-Admin-Password"
# A rejection from the action table, as opposed to a game rule saying no.
VALIDATION_PREFIXES = ("action must be", "action not allowed", "unknown field", "missing field",
                       "bad value", "exactly one of")


class Client:
    """A tiny JSON client with one connection per call, like a polling browser."""

    def __init__(self, host, port, timeout=10):
        self.host, self.port, self.timeout = host, port, timeout

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            h = dict(headers or {})
            data = None
            if body is not None:
                data = json.dumps(body).encode()
                h["Content-Type"] = "application/json"
            conn.request(method, path, body=data, headers=h)
            resp = conn.getresponse()
            payload = resp.read()
            return resp.status, (json.loads(payload) if payload else None)
        finally:
            conn.close()

    def admin(self, method, path, password, body=None):
        return self.request(method, path, body, {ADMIN_HEADER: password})


class Report:
    def __init__(self):
        self.days = 0
        self.rejected = []     # (day, team, action, error)
        self.accepted = 0

    def validation_rejections(self):
        return [r for r in self.rejected if r[3].startswith(VALIDATION_PREFIXES)]


def team_view(client, code, strategy):
    """The view a browser would hold for this strategy, with slices when it asks."""
    status, data = client.request("GET", "/api/team/%s/view?days=1" % code)
    if status != 200:
        raise RuntimeError("view for %s answered %s" % (code, status))
    view = data["view"]
    wants = getattr(strategy, "wants_detail", None)
    if wants is not None and wants(view):
        status, data = client.request(
            "GET", "/api/team/%s/view?days=%d&slices=1" % (code, bots.DETAIL_DAYS))
        if status == 200:
            view = data["view"]
    return view


def play(client, teams, advance, report=None):
    """Run the game to its end.

    teams maps a team number to (code, strategy). advance() moves the game one
    day on: a test ticks its fake clock, a live run waits for the server's day to
    change. Every team decides once a day, from the day the server reports.
    """
    report = report or Report()
    while True:
        status, clock = client.request("GET", "/api/clock")
        if status != 200:
            raise RuntimeError("clock answered %s" % status)
        if clock["finished"]:
            return report
        day = clock["day"]
        for team, (code, strategy) in sorted(teams.items()):
            for action in strategy(team_view(client, code, strategy), day):
                status, result = client.request("POST", "/api/team/%s/action" % code,
                                                {"action": action})
                if status == 200 and result.get("ok"):
                    report.accepted += 1
                else:
                    report.rejected.append((day, team, action, (result or {}).get("error", "")))
        report.days += 1
        advance()


def wait_for_next_day(client, poll=0.02, timeout=60):
    """advance() for a live server: block until the server's day changes."""
    def advance():
        start = client.request("GET", "/api/clock")[1]["day"]
        deadline = time.time() + timeout
        while time.time() < deadline:
            clock = client.request("GET", "/api/clock")[1]
            if clock["finished"] or clock["day"] != start:
                return
            time.sleep(poll)
        raise RuntimeError("the server's day did not change in %s seconds" % timeout)
    return advance


def main(argv=None):
    p = argparse.ArgumentParser(description="Play scripted teams against a live server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--admin-password", required=True)
    p.add_argument("--no-resume", action="store_true", help="do not resume the paused server")
    p.add_argument("teams", nargs="+", help="CODE:strategy, for example ABC123:measured-risk")
    args = p.parse_args(argv)
    client = Client(args.host, args.port)
    status, info = client.admin("GET", "/api/admin/status", args.admin_password)
    if status != 200:
        print("admin status answered %s" % status, file=sys.stderr)
        return 2
    by_code = {t["code"]: t["team"] for t in info["teams"]}
    teams = {}
    for spec in args.teams:
        code, _, name = spec.partition(":")
        teams[by_code[code]] = (code, bots.make_strategy(name or "measured-risk"))
    if not args.no_resume:
        client.admin("POST", "/api/admin/clock", args.admin_password, {"op": "resume"})
    report = play(client, teams, wait_for_next_day(client))
    print("played %d days: %d actions accepted, %d rejected" % (
        report.days, report.accepted, len(report.rejected)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
