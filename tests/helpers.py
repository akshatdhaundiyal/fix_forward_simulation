import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import engine  # noqa: E402

ALL_OFF = {"incidents": False, "peak_season": False, "churn_alerts": False}


def make_cfg(events=None, **overrides):
    """Config with scripted events off unless named, and slice recording off."""
    ev = dict(ALL_OFF)
    ev.update(events or {})
    overrides.setdefault("RECORD_SLICES", False)
    overrides.setdefault("LIFTS", dict(config.LIFTS))  # placeholders, never the calibration file
    overrides["EVENTS_ENABLED"] = ev
    return config.load(overrides)


def run_days(cfg, state, n):
    for _ in range(n):
        engine.step(cfg, state)


def ship(cfg, state, card_id, limit=400):
    """Queue a card and step until it ships. Returns days stepped."""
    assert engine.apply(cfg, state, dict(type="queue_add", card=card_id))["ok"]
    for i in range(limit):
        engine.step(cfg, state)
        if card_id in state["shipped"]:
            return i + 1
    raise AssertionError("card never shipped")


def all_keys(node, out=None):
    out = set() if out is None else out
    if isinstance(node, dict):
        for k, v in node.items():
            out.add(str(k).lower())
            all_keys(v, out)
    elif isinstance(node, list):
        for v in node:
            all_keys(v, out)
    return out


def dump(state):
    return json.dumps(state, sort_keys=True)
