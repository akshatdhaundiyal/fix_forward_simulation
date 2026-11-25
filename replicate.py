"""Keep a spare laptop's copy of the game current. Standard library only.

    python replicate.py --primary http://192.168.0.10:8000 --admin-password PW --state-dir state

Run on the spare. It copies the primary's event log, the team registry and the
newest snapshot into its own state directory, every few seconds. To take over,
stop this script and start the server on that directory with
`python server.py --state-dir state`; it comes back paused, like any restart.
It never opens the game itself and never writes anything but those files.
"""
import argparse
import hashlib
import http.client
import json
import os
import sys
import time
from urllib.parse import urlparse

import config

ADMIN_HEADER = "X-Admin-Password"
EXIT_DIVERGED = 3          # the copy and the primary are different games


class Diverged(Exception):
    pass


class Follower:
    def __init__(self, primary, password, state_dir, cfg=None):
        self.cfg = cfg or config.load()
        url = urlparse(primary if "//" in primary else "http://" + primary)
        self.host, self.port = url.hostname, url.port or 80
        self.password = password
        self.dir = state_dir
        self.log_path = os.path.join(state_dir, self.cfg["LOG_FILE"])
        self.reg_path = os.path.join(state_dir, self.cfg["REGISTRY_FILE"])
        self.snap_dir = os.path.join(state_dir, self.cfg["SNAPSHOT_DIR"])
        os.makedirs(self.snap_dir, exist_ok=True)
        self.snapshot_id = None
        self._trim_torn_tail()

    # --- the local copy ---------------------------------------------------
    def _trim_torn_tail(self):
        """A crash while writing can leave half a line. Keep only whole lines."""
        if not os.path.exists(self.log_path):
            return
        with open(self.log_path, "rb") as f:
            data = f.read()
        whole = data[:data.rfind(b"\n") + 1]
        if len(whole) != len(data):
            with open(self.log_path, "r+b") as f:
                f.truncate(len(whole))

    def local_size(self):
        return os.path.getsize(self.log_path) if os.path.exists(self.log_path) else 0

    def _check(self, offset):
        if not offset:
            return None
        start = max(0, offset - self.cfg["REPLICATE_CHECK_BYTES"])
        with open(self.log_path, "rb") as f:
            f.seek(start)
            return hashlib.sha256(f.read(offset - start)).hexdigest()

    # --- talking to the primary ------------------------------------------
    def _get(self, path):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=10)
        try:
            conn.request("GET", path, headers={ADMIN_HEADER: self.password})
            resp = conn.getresponse()
            return resp.status, resp.read(), resp
        finally:
            conn.close()

    def pull_registry(self):
        if os.path.exists(self.reg_path):
            return
        status, body, _ = self._get("/api/admin/registry")
        if status == 401:
            raise PermissionError("the primary refused the admin password")
        if status == 200:
            _atomic_write(self.reg_path, body)

    def pull_log(self):
        """Append everything new. Returns the number of bytes added."""
        added = 0
        while True:
            offset = self.local_size()
            query = "offset=%d" % offset
            check = self._check(offset)
            if check:
                query += "&check=" + check
            status, body, resp = self._get("/api/admin/log?" + query)
            if status == 401:
                raise PermissionError("the primary refused the admin password")
            if status == 409:
                raise Diverged(json.loads(body).get("error", "the copy and the primary differ"))
            if status != 200:
                raise OSError("the primary answered %d" % status)
            if body:
                with open(self.log_path, "ab") as f:
                    f.write(body)
                    f.flush()
                    os.fsync(f.fileno())
                added += len(body)
            if offset + len(body) >= int(resp.getheader("X-Log-Total", "0")) or not body:
                return added

    def pull_snapshot(self):
        status, body, resp = self._get("/api/admin/snapshot-latest")
        if status != 200:
            return False
        snapshot_id = resp.getheader("X-Snapshot-Id")
        if not snapshot_id or snapshot_id == self.snapshot_id:
            return False
        _atomic_write(os.path.join(self.snap_dir, snapshot_id + ".json"), body)
        self.snapshot_id = snapshot_id
        names = sorted(n for n in os.listdir(self.snap_dir) if n.endswith(".json"))
        for old in names[:-3]:
            os.remove(os.path.join(self.snap_dir, old))
        return True

    def pull_once(self):
        """One round. Returns (bytes added, new snapshot taken)."""
        self.pull_registry()
        added = self.pull_log()
        return added, self.pull_snapshot()


def _atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def main(argv=None):
    cfg = config.load()
    p = argparse.ArgumentParser(description="Follow the primary's game log on a spare laptop")
    p.add_argument("--primary", required=True, help="address of the running server, e.g. 192.168.0.10:8000")
    p.add_argument("--admin-password", default=os.environ.get("FF_ADMIN_PASSWORD"))
    p.add_argument("--state-dir", default=cfg["STATE_DIR"])
    p.add_argument("--interval", type=float, default=cfg["REPLICATE_INTERVAL_SECONDS"])
    p.add_argument("--once", action="store_true", help="pull once and exit")
    args = p.parse_args(argv)
    if not args.admin_password:
        print("An admin password is needed (--admin-password or FF_ADMIN_PASSWORD).", file=sys.stderr)
        return 2
    follower = Follower(args.primary, args.admin_password, args.state_dir, cfg)
    while True:
        try:
            added, snap = follower.pull_once()
            print("%s copied %d bytes, log now %d bytes%s" % (
                time.strftime("%H:%M:%S"), added, follower.local_size(),
                ", new snapshot" if snap else ""), flush=True)
        except Diverged as exc:
            print("STOPPED: %s. Nothing was changed; use a fresh --state-dir." % exc, file=sys.stderr)
            return EXIT_DIVERGED
        except PermissionError as exc:
            print("STOPPED: %s." % exc, file=sys.stderr)
            return 2
        except (OSError, http.client.HTTPException) as exc:
            print("%s could not reach the primary (%s); will retry" % (time.strftime("%H:%M:%S"), exc),
                  flush=True)
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
