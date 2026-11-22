"""The game clock as a small state machine with injectable time.

Every method takes the current time as an argument, so tests drive it with a
fake clock. After a tick the next one is scheduled a full interval ahead, never
as a catch-up, so a stalled server cannot fast-forward the game.
"""


class Clock:
    def __init__(self, cfg, day=0, speed=1.0):
        self.cfg = cfg
        self.day = day
        self.speed = speed
        self.running = False
        self.reason = "start"
        self.next_tick = None
        self.countdown_end = None
        self.hold = False
        self.finished = day >= cfg["TOTAL_DAYS"]
        if self.finished:
            self.reason = "finished"

    # --- helpers ----------------------------------------------------------
    def interval(self):
        return self.cfg["SECONDS_PER_DAY"] / self.speed

    def _week(self):
        return min(self.cfg["WEEKS"], self.day // self.cfg["DAYS_PER_WEEK"] + 1)

    def _next_checkpoint_week(self):
        for w in self.cfg["CHECKPOINT_WEEKS"]:
            if w * self.cfg["DAYS_PER_WEEK"] > self.day:
                return w
        return None

    # --- what is due ------------------------------------------------------
    def due(self, now):
        """'tick', 'auto_resume' or None."""
        if self.finished:
            return None
        if self.running:
            return "tick" if now >= self.next_tick else None
        if self.countdown_end is not None and not self.hold and now >= self.countdown_end:
            return "auto_resume"
        return None

    def ticked(self, now):
        """Record a completed day. Returns 'checkpoint', 'finished' or None."""
        self.day += 1
        if self.day >= self.cfg["TOTAL_DAYS"]:
            self.running, self.finished, self.reason = False, True, "finished"
            self.next_tick = self.countdown_end = None
            return "finished"
        dpw = self.cfg["DAYS_PER_WEEK"]
        if self.day % dpw == 0 and self.day // dpw in self.cfg["CHECKPOINT_WEEKS"]:
            self.running, self.reason, self.hold = False, "checkpoint", False
            self.next_tick = None
            self.countdown_end = now + self.cfg["CHECKPOINT_PAUSE_SECONDS"]
            return "checkpoint"
        self.next_tick = now + self.interval()
        return None

    # --- operator operations ---------------------------------------------
    def resume(self, now):
        if self.finished:
            return False
        self.running, self.reason = True, None
        self.countdown_end, self.hold = None, False
        self.next_tick = now + self.interval()
        return True

    def pause(self, now, reason="operator"):
        if self.finished or not self.running:
            return False
        self.running, self.reason = False, reason
        self.next_tick = None
        return True

    def extend(self, now, seconds):
        if self.finished or self.running or seconds <= 0:
            return False
        base = self.countdown_end if self.countdown_end is not None else now
        self.countdown_end, self.hold = base + seconds, False
        return True

    def set_countdown(self, now, seconds):
        if self.finished or self.running or seconds < 0:
            return False
        self.countdown_end, self.hold = now + seconds, False
        return True

    def hold_pause(self, now):
        if self.finished or self.running:
            return False
        self.hold, self.countdown_end = True, None
        return True

    def set_speed(self, now, speed):
        if speed not in self.cfg["SPEED_CHOICES"]:
            return False
        self.speed = speed
        if self.running:
            self.next_tick = min(self.next_tick, now + self.interval())
        return True

    def restored(self, day, speed):
        """Come back after a restart: paused, with the speed the log last recorded."""
        self.day, self.speed = day, speed
        self.running, self.next_tick = False, None
        self.countdown_end, self.hold = None, False
        self.finished = day >= self.cfg["TOTAL_DAYS"]
        self.reason = "finished" if self.finished else ("start" if day == 0 else "restart")

    # --- report -----------------------------------------------------------
    def status(self, now):
        remaining = None
        if self.countdown_end is not None:
            remaining = max(0.0, self.countdown_end - now)
        warn = (remaining is not None and 0 < remaining <= self.cfg["CHECKPOINT_WARNING_SECONDS"]
                and not self.running)
        return dict(
            day=self.day, week=self._week(), running=self.running, paused=not self.running,
            reason=self.reason, speed=self.speed, seconds_per_day=self.interval(),
            seconds_to_next_tick=(max(0.0, self.next_tick - now) if self.running else None),
            countdown_remaining=remaining, warning=warn, hold=self.hold,
            finished=self.finished, next_checkpoint_week=self._next_checkpoint_week(),
            poll_seconds=self.cfg["TEAM_POLL_SECONDS"],
            projector_poll_seconds=self.cfg["PROJECTOR_POLL_SECONDS"])
