"""Durable storage: the append-only event log, snapshots and the team registry.

The log is JSON lines. A line is only trusted if it ends in a newline, so a
write cut short by a crash leaves a fragment that recovery drops and truncates
before anything new is appended.
"""
import json
import os
import re
import secrets
import time


class LogWriteError(Exception):
    """A log line could not be written; nothing may be acknowledged."""


class CorruptLog(Exception):
    """A line before the last one is not valid JSON."""


class SnapshotError(Exception):
    """A snapshot could not be swapped into place."""


# --- event log ------------------------------------------------------------
def read_events(path):
    """Return (events, good_bytes). Drops an unterminated or unreadable final line."""
    if not os.path.exists(path):
        return [], 0
    with open(path, "rb") as f:
        data = f.read()
    lines = data.split(b"\n")
    tail = lines.pop()          # empty when the file ends in a newline, else a torn line
    events, good = [], 0
    for number, raw in enumerate(lines, 1):
        try:
            events.append(json.loads(raw))
        except ValueError:
            raise CorruptLog("event log line %d is not valid JSON" % number)
        good += len(raw) + 1
    return events, good


def effective_events(events):
    """Apply rewind markers: a rewind to sequence k drops earlier lines above k."""
    out = []
    for e in events:
        if e.get("kind") == "system" and e.get("op") == "rewind":
            out = [x for x in out if x["seq"] <= e["to_seq"]]
        else:
            out.append(e)
    return out


class EventLog:
    def __init__(self, path, fsync=True):
        self.path = path
        self.fsync = fsync
        self.seq = 0
        self._f = None
        self._good = 0

    @property
    def size(self):
        """Bytes of complete lines written so far."""
        return self._good

    def open(self):
        """Repair a torn tail, then open for append. Returns the events already there."""
        events, good = read_events(self.path)
        if os.path.exists(self.path) and os.path.getsize(self.path) != good:
            with open(self.path, "r+b") as f:
                f.truncate(good)
        self._good = good
        self.seq = events[-1]["seq"] if events else 0
        self._f = open(self.path, "ab")
        return events

    def append(self, event):
        """Write one event, flush and force it to disk. Returns its sequence number."""
        line = dict(event, seq=self.seq + 1)
        raw = (json.dumps(line, separators=(",", ":")) + "\n").encode()
        try:
            self._f.write(raw)
            self._f.flush()
            if self.fsync:
                os.fsync(self._f.fileno())
        except (OSError, ValueError) as exc:
            self._undo_partial()
            raise LogWriteError(str(exc))
        self.seq += 1
        self._good += len(raw)
        return self.seq

    def _undo_partial(self):
        try:
            self._f.close()
            os.truncate(self.path, self._good)
            self._f = open(self.path, "ab")
        except (OSError, ValueError):
            pass

    def close(self):
        if self._f:
            self._f.close()
            self._f = None


# --- snapshots ------------------------------------------------------------
_NAME = re.compile(r"^snap-(\d+)-d(\d+)\.json$")


class SnapshotStore:
    def __init__(self, directory, keep_recent, retries, retry_seconds, days_per_week):
        self.dir = directory
        self.keep_recent = keep_recent
        self.retries = retries
        self.retry_seconds = retry_seconds
        self.days_per_week = days_per_week
        os.makedirs(self.dir, exist_ok=True)

    def _entries(self):
        out = []
        for name in os.listdir(self.dir):
            m = _NAME.match(name)
            if m:
                seq, day = int(m.group(1)), int(m.group(2))
                out.append(dict(id=name[:-5], seq=seq, day=day,
                                week=day // self.days_per_week + 1, file=name))
        return sorted(out, key=lambda x: x["seq"])

    def write(self, seq, day, text):
        """Write a snapshot atomically. Raises SnapshotError if the swap stays blocked."""
        name = "snap-%010d-d%03d.json" % (seq, day)
        final = os.path.join(self.dir, name)
        tmp = final + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        last = None
        for _ in range(self.retries):
            try:
                os.replace(tmp, final)
                self._prune()
                return name[:-5]
            except PermissionError as exc:      # a reader holds the target open (Windows)
                last = exc
                time.sleep(self.retry_seconds)
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise SnapshotError("snapshot swap blocked: %s" % last)

    def _prune(self):
        entries = self._entries()
        keep = {e["id"] for e in entries[-self.keep_recent:]}
        first_of_week = {}
        for e in entries:
            first_of_week.setdefault(e["week"], e["id"])
        keep |= set(first_of_week.values())
        for e in entries:
            if e["id"] not in keep:
                try:
                    os.remove(os.path.join(self.dir, e["file"]))
                except OSError:
                    pass

    def latest(self):
        """(id, text) of the newest snapshot, or None. The text is the file as written."""
        entries = self._entries()
        if not entries:
            return None
        newest = entries[-1]
        try:
            with open(os.path.join(self.dir, newest["file"]), "r", encoding="utf-8") as f:
                return newest["id"], f.read()
        except OSError:
            return None

    def list(self):
        """Snapshots with their digest and clock fields, oldest first."""
        out = []
        for e in self._entries():
            info = self.read(e["id"])
            out.append(dict(e, digest=info.get("digest"), revealed=info.get("revealed")))
        return out

    def read(self, snapshot_id):
        """Whole snapshot as a dict, read and closed immediately."""
        if not re.match(r"^snap-\d+-d\d+$", snapshot_id):
            return None
        path = os.path.join(self.dir, snapshot_id + ".json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


# --- team registry --------------------------------------------------------
def load_or_create_registry(path, count, alphabet, length):
    """Team numbers, names and codes. Saved once, so a restart keeps every code."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    codes, teams = set(), []
    for n in range(1, count + 1):
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(length))
            if code not in codes:
                codes.add(code)
                break
        teams.append(dict(team=n, name="Team %d" % n, code=code))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(teams=teams), f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return dict(teams=teams)
