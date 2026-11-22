"""HTTP server for Fix Forward. Standard library only.

    python server.py [--port N] [--teams N] [--seconds-per-day S] [--new-game]

Team codes and passwords are printed once at startup. The server always comes
back paused after a restart; the operator resumes it from the admin routes.
"""
import argparse
import hmac
import json
import mimetypes
import os
import secrets
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

import config
import game as gamemod

ROOT = os.path.dirname(os.path.abspath(__file__))
ADMIN_HEADER = "X-Admin-Password"


class App:
    def __init__(self, game, admin_password, stakeholder_password, static_root=None):
        self.game = game
        self.cfg = game.cfg
        self.admin_password = admin_password
        self.stakeholder_password = stakeholder_password
        self.static_root = os.path.realpath(static_root or os.path.join(ROOT, self.cfg["STATIC_DIR"]))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "FixForward"
    app = None   # set by make_server

    # --- plumbing ---------------------------------------------------------
    def log_message(self, fmt, *args):   # keep the operator's console quiet
        pass

    def _send(self, status, body, ctype="application/json", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, obj, extra=None):
        self._send(status, json.dumps(obj, separators=(",", ":")).encode(), extra=extra)

    def _error(self, status, message):
        self._json(status, dict(error=message))

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > self.app.cfg["MAX_REQUEST_BYTES"]:
            self.close_connection = True
            return None
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    def _is_admin(self):
        given = self.headers.get(ADMIN_HEADER, "")
        return hmac.compare_digest(given.encode(), self.app.admin_password.encode())

    # --- routing ----------------------------------------------------------
    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_HEAD(self):
        self._route("GET")

    def _route(self, method):
        try:
            url = urlparse(self.path)
            parts = [p for p in url.path.split("/") if p]
            query = parse_qs(url.query)
            if parts[:1] == ["api"]:
                self._api(method, parts[1:], query)
            elif method == "GET":
                self._static(url.path)
            else:
                self._error(404, "not found")
        except gamemod.Degraded as exc:
            self._error(503, "the game is paused because it cannot write its log")
        except Exception:
            traceback.print_exc(file=sys.stderr)
            self._error(500, "server error")

    def _api(self, method, parts, query):
        app = self.app
        if parts == ["clock"] and method == "GET":
            return self._json(200, app.game.clock_status())
        if parts == ["projector"] and method == "GET":
            return self._json(200, app.game.projector())
        if parts[:1] == ["team"] and len(parts) == 3:
            return self._team(method, parts[1], parts[2], query)
        if parts[:1] == ["admin"] and len(parts) == 2:
            if not self._is_admin():
                return self._error(401, "unauthorized")
            return self._admin(method, parts[1])
        return self._error(404, "not found")

    # --- team routes ------------------------------------------------------
    def _team(self, method, code, what, query):
        game = self.app.game
        team = game.team_by_code(code)
        if team is None:
            return self._error(404, "not found")
        if what == "view" and method == "GET":
            try:
                window = int(query.get("days", [0])[0])
            except ValueError:
                window = 0
            slices = query.get("slices", ["0"])[0] == "1"
            etag, body = game.view_response(team, window, slices)
            if self.headers.get("If-None-Match") == etag:
                return self._send(304, b"", extra={"ETag": etag})
            clock = json.dumps(game.clock_status(), separators=(",", ":")).encode()
            return self._send(200, b'{"clock":' + clock + b',"view":' + body + b"}",
                              extra={"ETag": etag})
        if what == "action" and method == "POST":
            data = self._body()
            if data is None or "action" not in data:
                return self._error(400, "bad request")
            result = game.submit(team, data["action"], "team")
            return self._json(200 if result.get("ok") else 400, result)
        return self._error(404, "not found")

    # --- admin routes -----------------------------------------------------
    def _admin(self, method, what):
        game = self.app.game
        if method == "GET":
            if what == "status":
                return self._json(200, game.status())
            if what == "snapshots":
                return self._json(200, dict(snapshots=game.list_snapshots()))
            return self._error(404, "not found")
        data = self._body()
        if data is None:
            return self._error(400, "bad request")
        if what == "clock":
            result = game.clock_op(data.get("op"), data.get("value"))
        elif what == "incident":
            team = data.get("team")
            if team != "all" and not isinstance(team, int):
                return self._error(400, "bad request")
            result = game.admin_incident(team, data.get("incident"), data.get("op"))
        elif what == "edit":
            result = game.admin_edit(data.get("team"), data.get("path"), data.get("value"),
                                     data.get("reason"))
        elif what == "decline":
            result = game.decline_result(data.get("team"), data.get("ticks"))
        elif what == "restore":
            result = game.restore(data.get("snapshot"))
        elif what == "reveal":
            result = game.reveal()
        elif what == "reload":
            result = game.reload()
        elif what == "snapshot":
            result = dict(ok=True, snapshot=game.snapshot_now())
        else:
            return self._error(404, "not found")
        return self._json(200 if result.get("ok") else 400, result)

    # --- static -----------------------------------------------------------
    def _static(self, raw_path):
        root = self.app.static_root
        rel = unquote(raw_path).lstrip("/\\") or "index.html"
        if "\x00" in rel:
            return self._error(404, "not found")
        full = os.path.realpath(os.path.join(root, rel))
        inside = full == root or full.startswith(root + os.sep)
        if not inside or not os.path.isfile(full):
            return self._error(404, "not found")
        with open(full, "rb") as f:
            body = f.read()
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        self._send(200, body, ctype)


class ThreadedServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_server(game, host, port, admin_password, stakeholder_password, static_root=None):
    app = App(game, admin_password, stakeholder_password, static_root)
    handler = type("BoundHandler", (Handler,), dict(app=app))
    return ThreadedServer((host, port), handler)


# --- background threads ---------------------------------------------------
def runner(game, stop):
    while not stop.is_set():
        try:
            game.pump()
        except gamemod.GameError:
            pass
        except Exception:
            traceback.print_exc(file=sys.stderr)
        stop.wait(game.cfg["CLOCK_POLL_SECONDS"])


def snapshotter(game, stop):
    while not stop.wait(game.cfg["SNAPSHOT_INTERVAL_SECONDS"]):
        try:
            game.snapshot_now()
        except Exception:
            traceback.print_exc(file=sys.stderr)


def start_threads(game):
    stop = threading.Event()
    for target in (runner, snapshotter):
        threading.Thread(target=target, args=(game, stop), daemon=True).start()
    return stop


# --- command line ---------------------------------------------------------
def parse_args(argv):
    p = argparse.ArgumentParser(description="Fix Forward server")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--state-dir", default=None)
    p.add_argument("--teams", type=int, default=None)
    p.add_argument("--seconds-per-day", type=float, default=None)
    p.add_argument("--checkpoint-pause-seconds", type=float, default=None)
    p.add_argument("--new-game", action="store_true",
                   help="move any existing game aside and start clean")
    p.add_argument("--admin-password", default=os.environ.get("FF_ADMIN_PASSWORD"))
    p.add_argument("--stakeholder-password", default=os.environ.get("FF_STAKEHOLDER_PASSWORD"))
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    overrides = {}
    for flag, key in (("host", "BIND_HOST"), ("port", "SERVER_PORT"), ("state_dir", "STATE_DIR"),
                      ("teams", "NUM_TEAMS"), ("seconds_per_day", "SECONDS_PER_DAY"),
                      ("checkpoint_pause_seconds", "CHECKPOINT_PAUSE_SECONDS")):
        if getattr(args, flag) is not None:
            overrides[key] = getattr(args, flag)
    cfg = config.load(overrides)
    admin_pw = args.admin_password or secrets.token_urlsafe(9)
    stake_pw = args.stakeholder_password or secrets.token_urlsafe(9)
    try:
        game = gamemod.Game(cfg, new_game=args.new_game)
    except gamemod.GameError as exc:
        print("Cannot start: %s" % exc, file=sys.stderr)
        return 2
    httpd = make_server(game, cfg["BIND_HOST"], cfg["SERVER_PORT"], admin_pw, stake_pw)
    start_threads(game)
    st = game.status()
    print("Fix Forward server on port %d, day %d, %s" % (
        httpd.server_address[1], st["clock"]["day"], "PAUSED (resume from admin)"), flush=True)
    print("Admin password:       %s" % admin_pw)
    print("Stakeholder password: %s" % stake_pw)
    print("Team codes:")
    for t in st["teams"]:
        print("  %2d  %-10s %s" % (t["team"], t["name"], t["code"]))
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        game.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
