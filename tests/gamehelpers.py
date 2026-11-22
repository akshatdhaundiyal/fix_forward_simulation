"""Helpers for tests that run a Game against a fake clock in a temporary directory."""
import os
import shutil
import tempfile

import helpers
import engine
import game as gamemod


class FakeTime:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make_game_cfg(teams=3, **over):
    over.setdefault("NUM_TEAMS", teams)
    over.setdefault("LOG_FSYNC", False)
    over.setdefault("SECONDS_PER_DAY", 1.0)
    over.setdefault("CHECKPOINT_PAUSE_SECONDS", 2)
    over.setdefault("RECORD_SLICES", False)
    return helpers.make_cfg(**over)


def open_game(case, cfg=None, directory=None, ft=None, new_game=False, **cfg_over):
    """Open a Game in a temp dir that is removed when the test case ends."""
    cfg = cfg or make_game_cfg(**cfg_over)
    ft = ft or FakeTime()
    if directory is None:
        directory = tempfile.mkdtemp()
        case.addCleanup(shutil.rmtree, directory, True)
    g = gamemod.Game(cfg, os.path.join(directory, "state"), now=ft, new_game=new_game)
    case.addCleanup(g.close)
    return g, ft, directory


def advance_days(game, ft, n, limit=100000):
    """Run the clock until n more days have completed, a second at a time."""
    target = game.clock.day + n
    for _ in range(limit):
        if game.clock.day >= target or game.clock.finished:
            return
        ft.t += 1.0
        game.pump()
    raise AssertionError("clock did not advance")


def digests(game):
    return {n: engine.state_digest(st) for n, st in game.states.items()}
