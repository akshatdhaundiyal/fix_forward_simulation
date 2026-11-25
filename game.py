"""The game controller: every team's state, one lock, one log.

Anything that changes state is validated, applied, appended to the event log
and only then acknowledged. Recovery replays the log alone and checks the
digest on every tick. See store.py for the log format and clock.py for time.
"""
import hashlib
import hmac
import json
import math
import os
import secrets
import threading
import time

import engine
import store
from clock import Clock
from config import booking_quarter


class GameError(Exception):
    pass


class Degraded(GameError):
    """The log could not be written. The game is paused until the operator reloads."""


class StartupRefused(GameError):
    """The saved game cannot be continued safely."""


# --- helpers --------------------------------------------------------------
def _read_baseline(event, fresh_states):
    """Team states, speed, revealed and board carried by a baseline log line.

    A baseline starts a game from a snapshot when the log it came from is gone.
    History is not in a snapshot and is derived, so it starts empty.
    """
    teams = {int(n): dict(st, history=[]) for n, st in event["teams"].items()}
    if sorted(teams) != sorted(fresh_states):
        raise StartupRefused("the baseline's team list does not match the game")
    if _all_digest(teams) != event["digest"]:
        raise StartupRefused("the baseline does not match its own digest")
    board = event.get("board") or {}
    declined = {int(n): t for n, t in (board.get("declined") or {}).items()}
    return (teams, event["speed"], event["revealed"],
            dict(bookings=list(board.get("bookings") or []), declined=declined))

def config_digest(cfg):
    """Digest of every setting that is part of the game rather than the server."""
    skip = set(cfg["SERVER_ONLY_KEYS"]) | {"CARD_BY_ID"}
    body = {k: v for k, v in cfg.items() if k not in skip}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def _is_number(v, cfg):
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v) and abs(v) <= cfg["MAX_NUMBER"])


def _kind_ok(kind, v, cfg):
    if kind == "str":
        return isinstance(v, str) and 0 < len(v) <= cfg["MAX_STRING_LENGTH"]
    if kind == "text":
        return isinstance(v, str) and 0 < len(v.strip()) and len(v) <= cfg["MAX_TEXT_LENGTH"]
    if kind == "int":
        return isinstance(v, int) and not isinstance(v, bool) and abs(v) <= cfg["MAX_NUMBER"]
    if kind == "number":
        return _is_number(v, cfg)
    if kind == "scalar":
        return _is_number(v, cfg) or _kind_ok("str", v, cfg)
    return False


def validate_action(cfg, caller, action):
    """Return (clean_action, None) or (None, reason). Nothing outside the table passes."""
    if not isinstance(action, dict) or not isinstance(action.get("type"), str):
        return None, "action must be an object with a type"
    kind = action["type"]
    if kind not in cfg["CALLER_ACTIONS"].get(caller, []):
        return None, "action not allowed"
    spec = cfg["ACTION_SPECS"][kind]
    fields = spec["fields"]
    extra = set(action) - set(fields) - {"type"}
    if extra:
        return None, "unknown field"
    for name in spec.get("required", []):
        if name not in action:
            return None, "missing field: %s" % name
    one_of = spec.get("one_of")
    if one_of and sum(1 for n in one_of if n in action) != 1:
        return None, "exactly one of %s is required" % "/".join(one_of)
    for name, value in action.items():
        if name != "type" and not _kind_ok(fields[name], value, cfg):
            return None, "bad value for %s" % name
    return dict(action), None


def _all_digest(states):
    h = hashlib.sha256()
    for n in sorted(states):
        h.update(engine.state_digest(states[n]).encode())
    return h.hexdigest()


class Game:
    def __init__(self, cfg, state_dir=None, now=time.monotonic, new_game=False):
        self.cfg = cfg
        self.now = now
        self.lock = threading.RLock()
        self.boot = secrets.token_hex(4)
        state_dir = state_dir or cfg["STATE_DIR"]
        if new_game and os.path.isdir(state_dir) and os.listdir(state_dir):
            os.rename(state_dir, "%s.%s" % (state_dir.rstrip("/\\"), time.strftime("%Y%m%d-%H%M%S")))
        os.makedirs(state_dir, exist_ok=True)
        self.dir = state_dir
        self.registry = store.load_or_create_registry(
            os.path.join(state_dir, cfg["REGISTRY_FILE"]), cfg["NUM_TEAMS"],
            cfg["TEAM_CODE_ALPHABET"], cfg["TEAM_CODE_LENGTH"])
        self.log_path = os.path.join(state_dir, cfg["LOG_FILE"])
        self.snapshots = store.SnapshotStore(
            os.path.join(state_dir, cfg["SNAPSHOT_DIR"]), cfg["SNAPSHOT_KEEP_RECENT"],
            cfg["SNAPSHOT_SWAP_RETRIES"], cfg["SNAPSHOT_SWAP_RETRY_SECONDS"], cfg["DAYS_PER_WEEK"])
        self.degraded = None
        self.snapshot_warning = None
        self.last_snapshot_seq = 0
        self.last_snapshot_wall = None
        self.revealed = False
        self.board = dict(bookings=[], declined={})
        self.clock = Clock(cfg)
        self.states, self.versions, self._cache = {}, {}, {}
        self.log = store.EventLog(self.log_path, cfg["LOG_FSYNC"])
        try:
            self._start()
        except Exception:
            self.log.close()
            raise

    # --- start and recovery ----------------------------------------------
    def _team_numbers(self):
        return sorted(t["team"] for t in self.registry["teams"])

    def _start(self):
        events = self.log.open()
        if events:
            self._adopt(self._replay(store.effective_events(events)))
        else:
            seed = self.cfg["GAME_SEED"]
            self.states = {n: engine.new_state(self.cfg, n, seed) for n in self._team_numbers()}
            self._log(dict(kind="init", seed=seed, teams=self._team_numbers(),
                           config_digest=config_digest(self.cfg)))
        self.versions = {n: 0 for n in self.states}

    def _replay(self, effective):
        """Rebuild team states from effective log lines, checking every tick's digest."""
        cfg = self.cfg
        if not effective or effective[0].get("kind") != "init":
            raise StartupRefused("the event log does not begin with an init line")
        init = effective[0]
        if init["config_digest"] != config_digest(cfg):
            raise StartupRefused(
                "the game settings differ from the ones this game started with; "
                "restore the old settings or start over with --new-game")
        if sorted(init["teams"]) != self._team_numbers():
            raise StartupRefused("the saved team list does not match the event log")
        states = {n: engine.new_state(cfg, n, init["seed"]) for n in init["teams"]}
        speed, revealed = 1.0, False
        board = dict(bookings=[], declined={})
        for position, e in enumerate(effective[1:], 1):
            kind = e["kind"]
            if kind == "baseline":
                if position != 1:
                    raise StartupRefused("a baseline at line %d is not the second line" % e["seq"])
                states, speed, revealed, board = _read_baseline(e, states)
            elif kind == "action":
                st = states[e["team"]]
                if st["day"] != e["day"]:
                    raise StartupRefused("action at line %d is out of order" % e["seq"])
                engine.apply(cfg, st, e["action"])
                if e["action"].get("type") == "decline_result":
                    board["declined"][e["team"]] = e["action"].get("ticks")
            elif kind == "booking":
                board["bookings"].append(dict(
                    id=e["seq"], team=e["team"], role=e["role"], quarter=e["quarter"],
                    day=e["day"], done=False))
            elif kind == "booking_done":
                for b in board["bookings"]:
                    if b["id"] == e["booking"]:
                        b["done"] = True
            elif kind == "tick":
                for st in states.values():
                    engine.step(cfg, st)
                bad = [n for n, d in e["digests"].items()
                       if engine.state_digest(states[int(n)])[:16] != d]
                if bad:
                    raise StartupRefused("replay differs from the log at day %d for teams %s"
                                         % (e["day"], ", ".join(sorted(bad))))
            elif kind == "clock" and e.get("op") == "speed":
                speed = e["value"]
            elif kind == "system" and e.get("op") == "reveal":
                revealed = True
        return dict(states=states, speed=speed, revealed=revealed, board=board)

    def _adopt(self, result):
        self.states = result["states"]
        self.revealed = result["revealed"]
        self.board = result["board"]
        day = next(iter(self.states.values()))["day"]
        self.clock.restored(day, result["speed"])
        for n in self.states:
            self.versions[n] = self.versions.get(n, 0) + 1
        self._cache.clear()

    def reload(self):
        """Rebuild from the log after a write failure. Comes back paused."""
        with self.lock:
            self.log.close()
            self.log = store.EventLog(self.log_path, self.cfg["LOG_FSYNC"])
            events = self.log.open()
            self._adopt(self._replay(store.effective_events(events)))
            self.degraded = None
            return dict(ok=True)

    # --- logging ----------------------------------------------------------
    def _log(self, event):
        try:
            return self.log.append(event)
        except store.LogWriteError as exc:
            self._degrade("event log write failed: %s" % exc)
            raise Degraded(self.degraded)

    def _degrade(self, message):
        self.degraded = message
        self.clock.pause(self.now(), "degraded")
        self.clock.reason = "degraded"

    def _check_open(self):
        if self.degraded:
            raise Degraded(self.degraded)

    # --- actions ----------------------------------------------------------
    def submit(self, team, action, caller="team"):
        """Validate, apply, log and acknowledge one action. Returns the engine's result."""
        with self.lock:
            self._check_open()
            if team not in self.states:
                return dict(ok=False, error="no such team")
            clean, err = validate_action(self.cfg, caller, action)
            if err:
                return dict(ok=False, error=err)
            state = self.states[team]
            try:
                result = engine.apply(self.cfg, state, clean)
            except Exception:
                self._degrade("engine error while applying an action")
                raise Degraded(self.degraded)
            if result.get("ok"):
                self._log(dict(kind="action", day=state["day"], team=team, source=caller,
                               action=clean))
                self.versions[team] += 1
            return result

    def admin_incident(self, team, incident, op):
        kind = {"trigger": "trigger_incident", "cancel": "cancel_incident"}.get(op)
        if kind is None:
            return dict(ok=False, error="unknown incident operation")
        with self.lock:
            targets = sorted(self.states) if team == "all" else [team]
            return dict(ok=True, results={
                str(n): self.submit(n, dict(type=kind, incident=incident), "admin") for n in targets})

    def admin_edit(self, team, path, value, reason):
        return self.submit(team, dict(type="admin_edit", path=path, value=value, reason=reason),
                           "admin")

    def decline_result(self, team, ticks):
        """Operator entry of a decline result. Same once-per-team rule as the stakeholder
        screen; a mistake is corrected with an admin edit of Whale trust and a reason."""
        with self.lock:
            if team in self.board["declined"]:
                return dict(ok=False, error="a result is already entered for this team; "
                                            "correct Whale trust with an admin edit")
            result = self.submit(team, dict(type="decline_result", ticks=ticks), "admin")
            if result.get("ok"):
                self.board["declined"][team] = ticks
            return result

    # --- stakeholders -----------------------------------------------------
    def _role(self, role):
        return next((r for r in self.cfg["STAKEHOLDER_ROLES"] if r["id"] == role), None)

    def book(self, team, role):
        """A team books a stakeholder for the current quarter, first come first served."""
        cfg = self.cfg
        with self.lock:
            self._check_open()
            if team not in self.states or self._role(role) is None:
                return dict(ok=False, error="unknown stakeholder")
            day = self.clock.day
            quarter = booking_quarter(cfg, day)
            taken = [b for b in self.board["bookings"]
                     if b["role"] == role and b["quarter"] == quarter]
            if any(b["team"] == team for b in taken):
                return dict(ok=False, error="your team has already booked this stakeholder this quarter")
            if len(taken) >= cfg["BOOKINGS_PER_ROLE_PER_QUARTER"]:
                return dict(ok=False, error="all places with this stakeholder are taken this quarter")
            seq = self._log(dict(kind="booking", team=team, role=role, quarter=quarter, day=day))
            self.board["bookings"].append(dict(id=seq, team=team, role=role, quarter=quarter,
                                               day=day, done=False))
            return dict(ok=True, booking=seq)

    def mark_done(self, booking_id):
        with self.lock:
            self._check_open()
            found = None
            if isinstance(booking_id, int) and not isinstance(booking_id, bool):
                found = next((b for b in self.board["bookings"] if b["id"] == booking_id), None)
            if found is None:
                return dict(ok=False, error="no such booking")
            if found["done"]:
                return dict(ok=False, error="that meeting is already marked done")
            self._log(dict(kind="booking_done", booking=booking_id))
            found["done"] = True
            return dict(ok=True)

    def stakeholder_decline(self, team, ticks):
        """Enter a team's decline-conversation result once; Whale trust moves once."""
        cfg = self.cfg
        with self.lock:
            self._check_open()
            if isinstance(team, bool) or not isinstance(team, int) or team not in self.states:
                return dict(ok=False, error="no such team")
            top = max(cfg["DECLINE_TRUST"])
            if isinstance(ticks, bool) or not isinstance(ticks, int) or not 0 <= ticks <= top:
                return dict(ok=False, error="ticks must be 0 to %d" % top)
            if team in self.board["declined"]:
                return dict(ok=False, error="a result is already entered for this team")
            result = self.submit(team, dict(type="decline_result", ticks=ticks), "stakeholder")
            if result.get("ok"):
                self.board["declined"][team] = ticks
            return result

    def team_bookings(self, team):
        """What a team may see about stakeholder places: its own bookings and the counts."""
        cfg = self.cfg
        with self.lock:
            quarter = booking_quarter(cfg, self.clock.day)
            roles = []
            for r in cfg["STAKEHOLDER_ROLES"]:
                taken = [b for b in self.board["bookings"]
                         if b["role"] == r["id"] and b["quarter"] == quarter]
                waiting = [b for b in self.board["bookings"]
                           if b["role"] == r["id"] and not b["done"]]
                own = next((b for b in taken if b["team"] == team), None)
                mine = None
                if own:
                    pos = None if own["done"] else 1 + sum(1 for b in waiting if b["id"] < own["id"])
                    mine = dict(id=own["id"], position=pos, done=own["done"])
                roles.append(dict(
                    role=r["id"], title=r["title"], mine=mine,
                    places_left=max(0, cfg["BOOKINGS_PER_ROLE_PER_QUARTER"] - len(taken))))
            return dict(quarter=quarter, per_quarter=cfg["BOOKINGS_PER_ROLE_PER_QUARTER"],
                        roles=roles)

    def _cto_band(self, uod):
        green, amber = self.cfg["CTO_BAND_LIMITS"]
        return "green" if uod <= green else "amber" if uod <= amber else "red"

    def stakeholder_board(self):
        """Everything the stakeholder screen shows. Built field by field: a band, three
        yes-or-no facts and booking order, never a debt number."""
        cfg = self.cfg
        with self.lock:
            quarter = booking_quarter(cfg, self.clock.day)
            cards = cfg["SCRIPT_CARDS"][quarter]
            bands = cards["cto"].get("bands")
            teams = []
            for n in sorted(self.states):
                st = self.states[n]
                facts = dict(
                    data_isolation_shipped=cfg["WHALE_LEAD_CARD"] in st["shipped"],
                    outage_hit=any(ev["kind"] == "outage" for ev in st["events"]),
                    applied=bool(st["b1_applied"]))
                band = self._cto_band(st["uod"])
                lines = [c["text"] for c in cards["whale_lead"].get("conditional", [])
                         if facts[c["when"]] == c["is_true"]]
                teams.append(dict(
                    team=n, name=self._name(n), band=band,
                    cto_line=bands[band] if bands else None,
                    whale=dict(facts=facts, lines=lines),
                    declined=n in self.board["declined"]))
            roles = []
            for r in cfg["STAKEHOLDER_ROLES"]:
                card = cards[r["id"]]
                roles.append(dict(
                    role=r["id"], title=r["title"], unprompted=card.get("unprompted"),
                    asked=[dict(question=q, answer=a) for q, a in card["asked"]],
                    after=card.get("after")))
            bookings = [dict(id=b["id"], team=b["team"], name=self._name(b["team"]),
                             role=b["role"], quarter=b["quarter"], done=b["done"])
                        for b in self.board["bookings"]]
            return dict(clock=self.clock.status(self.now()), quarter=quarter, roles=roles,
                        teams=teams, bookings=bookings)

    # --- time -------------------------------------------------------------
    def pump(self, now=None):
        """Do whatever the clock says is due. Called by the runner thread."""
        now = self.now() if now is None else now
        with self.lock:
            if self.degraded:
                return None
            due = self.clock.due(now)
            if due == "tick":
                self._tick(now)
            elif due == "auto_resume":
                self.clock.resume(now)
                self._log(dict(kind="clock", op="auto_resume", day=self.clock.day))
            return due

    def _tick(self, now):
        cfg = self.cfg
        day = self.clock.day
        if day == cfg["B1_APPLY_LAST_WEEK"] * cfg["DAYS_PER_WEEK"]:
            for n in engine.resolve_b1_awards(cfg, list(self.states.values())):
                action = dict(type="award_bespoke")
                engine.apply(cfg, self.states[n], action)
                self._log(dict(kind="action", day=day, team=n, source="system", action=action))
                self.versions[n] += 1
        for st in self.states.values():
            engine.step(cfg, st)
        digests = {str(n): engine.state_digest(st)[:16] for n, st in self.states.items()}
        self._log(dict(kind="tick", day=day, digests=digests))
        for n in self.versions:
            self.versions[n] += 1
        outcome = self.clock.ticked(now)
        if outcome == "checkpoint":
            self._log(dict(kind="clock", op="checkpoint_pause", day=self.clock.day,
                           value=cfg["CHECKPOINT_PAUSE_SECONDS"]))
        elif outcome == "finished":
            self._log(dict(kind="clock", op="finished", day=self.clock.day))

    def clock_op(self, op, value=None):
        with self.lock:
            self._check_open()
            now = self.now()
            needs_number = op in ("extend", "countdown", "speed")
            if needs_number and not _is_number(value, self.cfg):
                return dict(ok=False, error="a number is required")
            done = {
                "pause": lambda: self.clock.pause(now),
                "resume": lambda: self.clock.resume(now),
                "extend": lambda: self.clock.extend(now, value),
                "hold": lambda: self.clock.hold_pause(now),
                "countdown": lambda: self.clock.set_countdown(now, value),
                "speed": lambda: self.clock.set_speed(now, value),
            }.get(op)
            if done is None:
                return dict(ok=False, error="unknown clock operation")
            if not done():
                return dict(ok=False, error="not possible in the current clock state")
            self._log(dict(kind="clock", op=op, value=value, day=self.clock.day))
            return dict(ok=True, clock=self.clock.status(now))

    def clock_status(self):
        with self.lock:
            return self.clock.status(self.now())

    def reveal(self):
        with self.lock:
            self._check_open()
            self._log(dict(kind="system", op="reveal"))
            self.revealed = True
            return dict(ok=True)

    # --- reads ------------------------------------------------------------
    def team_by_code(self, code):
        """Team number for a code, or None. Compares every code in constant time."""
        found = None
        for t in self.registry["teams"]:
            if hmac.compare_digest(str(code).encode(), t["code"].encode()):
                found = t["team"]
        return found

    def view_response(self, team, window=None, slices=False):
        """(etag, body bytes) for a team's engine view, cached by team version."""
        cfg = self.cfg
        window = cfg["VIEW_DEFAULT_SERIES_DAYS"] if not window or window < 1 else min(
            window, cfg["VIEW_MAX_SERIES_DAYS"])
        with self.lock:
            key = (team, window, bool(slices))
            version = self.versions[team]
            hit = self._cache.get(key)
            if hit and hit[0] == version:
                return hit[1], hit[2]
            view = engine.team_view(cfg, self.states[team], series_days=window,
                                    include_slices=bool(slices))
            body = json.dumps(view, separators=(",", ":")).encode()
            etag = '"%s-%d-%d-%d-%d"' % (self.boot, team, version, window, 1 if slices else 0)
            self._cache[key] = (version, etag, body)
            return etag, body

    def calendar(self):
        """The game's fixed calendar, from config. Holds nothing hidden."""
        cfg = self.cfg
        return dict(
            weeks=cfg["WEEKS"], weeks_per_quarter=cfg["WEEKS_PER_QUARTER"],
            days_per_week=cfg["DAYS_PER_WEEK"],
            checkpoint_weeks=list(cfg["CHECKPOINT_WEEKS"]),
            surge=dict(start=cfg["PEAK_START_WEEK"], end=cfg["PEAK_END_WEEK"]),
            contract_window=dict(first=cfg["B1_APPLY_FIRST_WEEK"], last=cfg["B1_APPLY_LAST_WEEK"]))

    def projector(self):
        with self.lock:
            rows = []
            for n in sorted(self.states):
                sc = engine.score(self.cfg, self.states[n])
                row = dict(team=n, name=self._name(n), arr=sc["arr"], trust_avg=sc["trust_avg"])
                if self.revealed:
                    row.update(uod=sc["uod"], nev=sc["nev"], penalty=sc["penalty"],
                               bespoke_arr=sc["bespoke_arr"])
                rows.append(row)
            rows.sort(key=lambda r: -(r["nev"] if self.revealed else r["arr"]))
            for i, r in enumerate(rows, 1):
                r["rank"] = i
            return dict(clock=self.clock.status(self.now()), revealed=self.revealed, rows=rows)

    def _name(self, n):
        for t in self.registry["teams"]:
            if t["team"] == n:
                return t["name"]
        return "Team %d" % n

    def status(self):
        with self.lock:
            return dict(
                clock=self.clock.status(self.now()), log_seq=self.log.seq,
                degraded=self.degraded, snapshot_warning=self.snapshot_warning,
                last_snapshot_seq=self.last_snapshot_seq,
                last_snapshot_age=(None if self.last_snapshot_wall is None
                                   else time.time() - self.last_snapshot_wall),
                revealed=self.revealed, boot=self.boot,
                speed_choices=list(self.cfg["SPEED_CHOICES"]),
                teams=[dict(team=t["team"], name=t["name"], code=t["code"])
                       for t in self.registry["teams"]])

    # --- spare laptop -----------------------------------------------------
    def log_chunk(self, offset, check):
        """Complete log lines from a byte offset, for a follower. Returns (chunk, error).

        `check` is the sha256 of the last bytes the follower already holds before
        `offset`. A mismatch means its copy is not a prefix of this log (the
        primary was restarted from a snapshot or began a new game), and nothing
        is returned, so the follower can never extend a copy of a different game.
        """
        cfg = self.cfg
        with self.lock:
            total = self.log.size
            if offset < 0 or offset > total:
                return None, "the follower's copy is longer than the log"
            with open(self.log_path, "rb") as f:
                if offset:
                    start = max(0, offset - cfg["REPLICATE_CHECK_BYTES"])
                    f.seek(start)
                    held = f.read(offset - start)
                    if check != hashlib.sha256(held).hexdigest():
                        return None, "the follower's copy does not match this log"
                f.seek(offset)
                data = f.read(min(total - offset, cfg["REPLICATE_CHUNK_BYTES"]))
            if offset + len(data) < total:
                data = data[:data.rfind(b"\n") + 1]
            return dict(data=data, total=total, boot=self.boot), None

    def registry_text(self):
        return json.dumps(self.registry, indent=1)

    def latest_snapshot(self):
        return self.snapshots.latest()

    # --- snapshots --------------------------------------------------------
    def snapshot_now(self):
        """Write a snapshot of every team without history. Never raises."""
        with self.lock:
            if self.degraded or self.log.seq == self.last_snapshot_seq:
                return None
            seq, day = self.log.seq, self.clock.day
            payload = dict(
                seq=seq, day=day, digest=_all_digest(self.states), speed=self.clock.speed,
                revealed=self.revealed,
                board=json.loads(json.dumps(self.board)),
                teams={str(n): {k: v for k, v in st.items() if k != "history"}
                       for n, st in self.states.items()})
            text = json.dumps(payload, separators=(",", ":"))
        try:
            snapshot_id = self.snapshots.write(seq, day, text)
        except (store.SnapshotError, OSError) as exc:
            with self.lock:
                self.snapshot_warning = str(exc)
            return None
        with self.lock:
            self.last_snapshot_seq = seq
            self.last_snapshot_wall = time.time()
            self.snapshot_warning = None
        return snapshot_id

    def list_snapshots(self):
        return self.snapshots.list()

    def restore(self, snapshot_id):
        """Rewind to a snapshot: replay the log up to it, verify, then append a rewind line."""
        with self.lock:
            self._check_open()
            snap = self.snapshots.read(snapshot_id) if isinstance(snapshot_id, str) else None
            if snap is None:
                return dict(ok=False, error="unknown snapshot")
            events, _ = store.read_events(self.log_path)
            marker = dict(kind="system", op="rewind", to_seq=snap["seq"])
            prospective = store.effective_events(events + [dict(marker, seq=self.log.seq + 1)])
            try:
                result = self._replay(prospective)
            except StartupRefused as exc:
                return dict(ok=False, error=str(exc))
            if _all_digest(result["states"]) != snap["digest"]:
                return dict(ok=False, error="replay does not match the snapshot; nothing changed")
            self._log(marker)
            self._adopt(result)
            self.clock.reason = "restore"
            return dict(ok=True, day=self.clock.day)

    def close(self):
        with self.lock:
            self.log.close()


def start_from_snapshot(cfg, snapshot_path, state_dir, registry_path=None):
    """Create a state directory whose log is `init` plus a `baseline` from one snapshot.

    For when the log is gone. The team registry (codes and names) is not in a
    snapshot, so it is copied from beside the snapshot or from registry_path.
    Nothing is written until every check has passed. Returns the day started at.
    """
    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snap = json.load(f)
    except (OSError, ValueError) as exc:
        raise StartupRefused("cannot read the snapshot: %s" % exc)
    registry_path = registry_path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(snapshot_path))), cfg["REGISTRY_FILE"])
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        raise StartupRefused("the team registry %s is needed and cannot be read: %s"
                             % (registry_path, exc))
    teams = sorted(t["team"] for t in registry["teams"])
    fresh = {n: engine.new_state(cfg, n, cfg["GAME_SEED"]) for n in teams}
    event = dict(kind="baseline", day=snap["day"], speed=snap["speed"], revealed=snap["revealed"],
                 digest=snap["digest"], board=snap.get("board") or {}, teams=snap["teams"])
    _read_baseline(event, fresh)                       # raises StartupRefused on any mismatch
    log_path = os.path.join(state_dir, cfg["LOG_FILE"])
    if os.path.exists(log_path) and os.path.getsize(log_path):
        raise StartupRefused("%s already holds a game log" % state_dir)
    os.makedirs(state_dir, exist_ok=True)
    reg_out = os.path.join(state_dir, cfg["REGISTRY_FILE"])
    with open(reg_out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(registry, f, indent=1)
    log = store.EventLog(log_path, cfg["LOG_FSYNC"])
    log.open()
    try:
        log.append(dict(kind="init", seed=cfg["GAME_SEED"], teams=teams,
                        config_digest=config_digest(cfg)))
        log.append(event)
    finally:
        log.close()
    return snap["day"]
