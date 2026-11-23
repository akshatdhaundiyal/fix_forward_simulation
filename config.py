"""Every game number for Fix Forward lives here.

All values are untested starting values taken from the build spec and the
project defaults. Money is in rupees crore (Cr). ARR per account is therefore
50 L = 0.5 Cr. Nothing in engine.py or bots.py may hard-code a game number.
"""
import copy
import json
import os

# --- time -----------------------------------------------------------------
DAYS_PER_WEEK = 7
WEEKS = 52
WEEKS_PER_QUARTER = 13
TOTAL_DAYS = DAYS_PER_WEEK * WEEKS  # 364

# --- product --------------------------------------------------------------
SEGMENT_ORDER = ["W", "M", "S"]
SEGMENTS = {
    "W": dict(name="Whales", accounts=20, arr_per_account=0.5, leads=2,
              signup=0.50, activation=0.50, paid=0.10, churn=0.0025),
    "M": dict(name="Mid-Market", accounts=150, arr_per_account=0.06, leads=60,
              signup=0.30, activation=0.50, paid=0.10, churn=0.006),
    "S": dict(name="Self-Serve", accounts=2000, arr_per_account=0.003, leads=4000,
              signup=0.10, activation=0.50, paid=0.10, churn=0.010),
}

# Fixed shares of every segment. The new-cohort share is a build default.
SLICES = {
    "platform": {"web": 0.60, "mobile": 0.40},
    "plan": {"monthly": 0.70, "annual": 0.30},
    "cohort": {"new": 0.15, "existing": 0.85},
}

# Funnel stages a feature or a defect can act on.
STAGES = ["leads", "signup", "activation", "paid", "retention", "arr_per_account"]

# --- trust and hidden debt ------------------------------------------------
TRUST_START = 60.0
TRUST_NEUTRAL = 60.0
TRUST_CHURN_COEF = 0.02
TRUST_MIN = 0.0
TRUST_MAX = 100.0
UOD_ACTIVATION_PER_POINT = 0.002
UOD_CHURN_PER_POINT = 0.002   # build default: churn x (1 + 0.002 x UOD)

# --- capacity and quality -------------------------------------------------
CAPACITY_BU_PER_WEEK = 8.0
BESPOKE_CAPACITY_TAX = 0.8
QUALITY_MODES = {
    "low": dict(keep=1.00, debt_mult=1.6),
    "medium": dict(keep=0.90, debt_mult=1.0),
    "high": dict(keep=0.80, debt_mult=0.35),
}
QUALITY_DEFAULT = "medium"

# --- cards ----------------------------------------------------------------
# unlock_q 0 means always available. gain is the hidden target ARR gain.
def _card(id, unlock_q, name, cost, seg, stage, pitch, gain, risk, trust=None, **flags):
    c = dict(id=id, unlock_q=unlock_q, name=name, cost=cost, seg=seg, stage=stage,
             pitch=pitch, gain=gain, risk=risk, trust=trust or {})
    c.update(flags)
    return c

CARDS = [
    _card("A1", 1, "AI Copilot", 35, "M", "paid", 6.0, 0.9, 8),
    _card("A2", 1, "Self-serve onboarding revamp", 20, "S", "activation", 2.0, 1.6, 3, {"S": 5}),
    _card("A3", 1, "Bulk import & integrations", 25, "M", "activation", 2.5, 1.9, 5),
    _card("A4", 1, "Enterprise SSO & audit logs", 30, "W", "paid", 3.0, 2.1, 6, {"W": 5}),
    _card("A5", 1, "Mobile app refresh", 20, "S", "signup", 2.5, 0.9, 4),
    _card("A6", 1, "Usage-based pricing tier", 15, "S", "arr_per_account", 1.5, 0.9, 4),
    _card("B1", 2, "Bespoke compliance dashboard, Whale Alpha", 30, "W", "contract", 5.0, 5.0, 9,
          {"W": 10}, bespoke=True, signed=5.0, slots=5),
    _card("B2", 2, "Enterprise data isolation", 30, "W", "retention", 2.0, 1.2, 5),
    _card("B3", 2, "Mid-market reporting suite", 25, "M", "retention", 3.0, 2.4, 5),
    _card("B4", 2, "Partner marketplace API", 35, "M", "leads", 5.0, 1.5, 10),
    _card("B5", 2, "SMB referral loops", 15, "S", "leads", 1.5, 1.05, 3),
    _card("B6", 2, "Workflow automation", 25, "S", "retention", 3.0, 1.65, 6),
    _card("C1", 3, "Bespoke integration, Whale Beta", 25, "W", "contract", 4.0, 4.0, 8,
          {"W": 5}, bespoke=True, signed=4.0),
    _card("C2", 3, "Advanced analytics add-on", 30, "W", "arr_per_account", 4.0, 3.0, 6),
    _card("C3", 3, "AI meeting summaries", 25, "M", "paid", 4.0, 1.0, 7),
    _card("C4", 3, "Annual-plan pricing", 15, "S", "retention", 2.0, 1.7, 2),
    _card("C5", 3, "Localization pack", 25, "M", "leads", 3.0, 1.95, 5),
    _card("D1", 4, "Enterprise expansion pack", 30, "W", "arr_per_account", 4.0, 2.8, 7),
    _card("D2", 4, "Quick-win promo campaign", 20, "S", "signup", 3.0, 1.2, 6),
    _card("D3", 4, "Mid-market upsell bundle", 25, "M", "arr_per_account", 3.0, 2.25, 5),
    _card("D4", 4, "Audit readiness sprint", 20, None, None, 0.0, 0.0, 0, uod_delta=-20),
    _card("D5", 4, "Executive customer summit", 20, None, None, 0.0, 0.0, 0,
          {"W": 5, "M": 5, "S": 5}),
    _card("P1", 0, "Platform hardening", 15, None, None, 0.0, 0.0, 0, uod_delta=-12,
          once_per_quarter=True),
    _card("P2", 0, "Customer success program", 15, None, None, 0.0, 0.0, 0,
          {"W": 3, "M": 3, "S": 3}, once_per_quarter=True),
]

# Hidden true lift per card. Placeholder until calibration solves each one.
# Meaning by stage: leads, signup, activation, paid and arr_per_account lift
# the rate by (1 + lift); retention lowers churn by (1 - lift).
PLACEHOLDER_LIFT = 0.05
LIFTS = {c["id"]: PLACEHOLDER_LIFT for c in CARDS
         if c["stage"] not in (None, "contract")}

# ARR gain each card actually reaches with the solved lifts. Filled from the
# calibration file; a card with no entry uses its target gain. Segment reports
# show utility from this table, so cards that cannot reach their target are not
# overstated.
CALIBRATED_GAIN = {}

# Largest lift the calibrator may assign, by stage. Retention stays below 1 so
# churn cannot reach zero or go negative.
LIFT_CAPS = {"retention": 0.95, "default": 3.0}
CALIBRATION_FILE = "calibration/lifts.json"
CALIBRATION_TOLERANCE = 0.002   # Cr

# --- reports --------------------------------------------------------------
REPORT_COST = 4
UTILITY_SCALE = 100        # utility = round(scale x calibrated gain / pitch ARR); target gain if none (CALIBRATED_GAIN)

# --- bespoke contracts ----------------------------------------------------
B1_CARD = "B1"
B1_APPLY_FIRST_WEEK = 14
B1_APPLY_LAST_WEEK = 17
B1_SLOTS = 5
B1_RANK_SEG = "W"          # applicants are ranked by this segment's trust
DECLINE_SEG = "W"
DECLINE_TRUST = {3: 5.0, 2: 0.0, 1: -5.0, 0: -5.0}

# --- rollback -------------------------------------------------------------
ROLLBACK_DELAY_DAYS = 7
ROLLBACK_TRUST_LOSS = 3.0
RESHIP_COST_SHARE = 0.5

# --- incidents ------------------------------------------------------------
INCIDENT_TRUST_LOSS_PER_WEEK = 2.0
FIX_COST = 15
FIX_UOD_DELTA = -10.0
PATCH_COST = 6
PATCH_UOD_DELTA = 15.0
PATCH_DAMAGE_FACTOR = 0.5

CAUSES_STANDARD = ["external_load", "organic_growth", "own_release", "vendor"]
CAUSES_INCIDENT_3 = ["external_load", "pricing_change", "own_release", "vendor"]

# Variant letter for a team is VARIANT_ORDER[team number % len(VARIANT_ORDER)].
VARIANT_ORDER = ["A", "B", "C"]

ALL_SEGS = ["W", "M", "S"]
# Each incident is data. trigger types:
#   week_start     opens at the first day of start_week
#   ship_in_window opens on the day the first qualifying card ships inside the window
# A variant's segs is a list of segments, or "release" meaning the segment of
# the release that caused it (the shipping card, or else the latest release).
# stage "retention" multiplies churn; every other stage multiplies its rate.
INCIDENTS = {
    1: dict(
        trigger=dict(type="week_start", week=6), stage="retention", mult=2.0,
        causes=CAUSES_STANDARD, symptom="Retention is falling.",
        variants={
            "A": dict(segs=["W"], slice={}, cause="external_load", slows=True),
            "B": dict(segs=["S"], slice={}, cause="organic_growth", slows=True),
            "C": dict(segs=ALL_SEGS, slice={"plan": "annual"}, cause="vendor", slows=False),
        }),
    2: dict(
        trigger=dict(type="ship_in_window", first_week=15, last_week=24),
        stage="activation", mult=0.6, causes=CAUSES_STANDARD,
        symptom="Activation has dropped sharply.",
        variants={
            "A": dict(segs="release", slice={"platform": "mobile"}, cause="own_release", slows=False),
            "B": dict(segs="release", slice={"cohort": "new"}, cause="own_release", slows=False),
            "C": dict(segs="release", slice={"plan": "annual"}, cause="own_release", slows=False),
        }),
    3: dict(
        trigger=dict(type="week_start", week=33), stage="paid", mult=0.5,
        causes=CAUSES_INCIDENT_3, symptom="Paid conversion has fallen.",
        variants={
            "A": dict(segs=ALL_SEGS, slice={"plan": "annual"}, cause="vendor", slows=False),
            "B": dict(segs="release", slice={}, cause="own_release", slows=False),
            "C": dict(segs=ALL_SEGS, slice={"platform": "web", "cohort": "new"},
                      cause="pricing_change", slows=False),
        }),
}

# --- peak season ----------------------------------------------------------
PEAK_START_WEEK = 28
PEAK_END_WEEK = 30
PEAK_UOD_THRESHOLD = 40.0
PEAK_REWORK_FLOOR = 30.0
PEAK_REWORK_CAP = 50.0
PEAK_PENALTY = 3.0
PEAK_OUTAGE_TRUST = {"W": -35.0}
PEAK_SAFE_TRUST = {"W": 5.0, "M": 5.0, "S": 5.0}

# --- churn alerts (end of week 39) ----------------------------------------
ALERTS = {
    "alpha": dict(week=39, seg="W", needs_card="B2", arr_loss=3.0, trust=-10.0,
                  text="A whale account (about 3 Cr ARR) is at risk of leaving in Q3."),
    "competitor": dict(week=39, seg="M", needs_card="B3", arr_loss=0.0, trust=-15.0,
                       text="Mid-market accounts are evaluating a competitor over reporting."),
}

# --- scoring --------------------------------------------------------------
TRUST_MULTIPLE_BASE = 2.0
TRUST_MULTIPLE_SLOPE = 0.03
BESPOKE_VALUE_MULT = 2.0
UOD_VALUATION_COST = 0.25   # Cr per UOD point at the end

# --- telemetry (display only) ---------------------------------------------
ERROR_RATE_BASE = 0.005
ERROR_RATE_PER_UOD = 0.0004
P99_BASE_MS = 300.0
P99_PER_UOD_MS = 6.0
P99_INCIDENT_MS = 200.0
P99_PEAK_MULT = 1.5
TICKETS_BASELINE_PER_WEEK = {"W": 5.0, "M": 40.0, "S": 400.0}
TICKETS_TRUST_COEF = 0.03
TICKETS_INCIDENT_BUMP = 0.5   # +50% while an incident touches the segment
# Relative noise half-widths. Tuned in calibration, then in the live trial.
NOISE = {"error_rate": 0.15, "p99": 0.08, "tickets": 0.12, "funnel": 0.03}

# --- scripted events ------------------------------------------------------
# The spec's incidents, peak-season trust bonus and week-39 alerts all move a
# team that does nothing, so the "holds at 25 Cr" check runs with them off.
EVENTS_ENABLED = {"incidents": True, "peak_season": True, "churn_alerts": True}

# --- numerics -------------------------------------------------------------
FLOAT_EPS = 1e-9

# --- server ---------------------------------------------------------------
BIND_HOST = "0.0.0.0"
SERVER_PORT = 8000
STATE_DIR = "state"
LOG_FILE = "events.jsonl"
SNAPSHOT_DIR = "snapshots"
REGISTRY_FILE = "teams.json"
STATIC_DIR = "static"
NUM_TEAMS = 16
TEAM_CODE_LENGTH = 6
TEAM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0, O, 1, I
GAME_SEED = 20261204
LOG_FSYNC = True                       # force every logged line to disk
RECOVERY_BUDGET_SECONDS = 60

# --- clock ----------------------------------------------------------------
SECONDS_PER_DAY = 13.0
SPEED_CHOICES = [0.5, 1, 2, 4, 10]
CHECKPOINT_WEEKS = [13, 26, 39]
CHECKPOINT_PAUSE_SECONDS = 420
CHECKPOINT_WARNING_SECONDS = 30
CLOCK_POLL_SECONDS = 0.05              # how often the runner asks the clock what is due

# --- snapshots ------------------------------------------------------------
SNAPSHOT_INTERVAL_SECONDS = 5
SNAPSHOT_KEEP_RECENT = 12
SNAPSHOT_SWAP_RETRIES = 5
SNAPSHOT_SWAP_RETRY_SECONDS = 0.02

# --- http -----------------------------------------------------------------
VIEW_DEFAULT_SERIES_DAYS = 28
VIEW_MAX_SERIES_DAYS = 364
MAX_REQUEST_BYTES = 8192
MAX_STRING_LENGTH = 64
MAX_TEXT_LENGTH = 500
MAX_NUMBER = 1e9
TEAM_POLL_SECONDS = 3                  # hints sent to browsers, which never hard-code them
PROJECTOR_POLL_SECONDS = 2

# --- who may submit which actions ----------------------------------------
# Field kinds: str (short), text (long), int, number (int or float), scalar (number or str).
ACTION_SPECS = {
    "queue_add": dict(fields=dict(card="str", report="str"), one_of=["card", "report"]),
    "queue_remove": dict(fields=dict(item="int"), required=["item"]),
    "queue_reorder": dict(fields=dict(item="int", position="int"), required=["item", "position"]),
    "set_quality": dict(fields=dict(mode="str"), required=["mode"]),
    "rollback": dict(fields=dict(card="str"), required=["card"]),
    "targeted_fix": dict(fields=dict(incident="int", cause="str"), required=["incident", "cause"]),
    "patch": dict(fields=dict(incident="int"), required=["incident"]),
    "apply_b1": dict(fields={}),
    "trigger_incident": dict(fields=dict(incident="int"), required=["incident"]),
    "cancel_incident": dict(fields=dict(incident="int"), required=["incident"]),
    "admin_edit": dict(fields=dict(path="str", value="scalar", reason="text"),
                       required=["path", "value", "reason"]),
    "decline_result": dict(fields=dict(ticks="int"), required=["ticks"]),
    "award_bespoke": dict(fields={}),
}
CALLER_ACTIONS = {
    "team": ["queue_add", "queue_remove", "queue_reorder", "set_quality", "rollback",
             "targeted_fix", "patch", "apply_b1"],
    "admin": ["trigger_incident", "cancel_incident", "admin_edit", "decline_result"],
    "system": ["award_bespoke"],
}

# Settings that may differ between runs of the same game. Everything else is
# part of the game and is recorded as a digest when a game starts.
SERVER_ONLY_KEYS = [
    "BIND_HOST", "SERVER_PORT", "STATE_DIR", "LOG_FILE", "SNAPSHOT_DIR", "REGISTRY_FILE",
    "STATIC_DIR", "NUM_TEAMS", "TEAM_CODE_LENGTH", "TEAM_CODE_ALPHABET", "LOG_FSYNC",
    "RECOVERY_BUDGET_SECONDS", "SECONDS_PER_DAY", "SPEED_CHOICES", "CHECKPOINT_PAUSE_SECONDS",
    "CHECKPOINT_WARNING_SECONDS", "CLOCK_POLL_SECONDS", "SNAPSHOT_INTERVAL_SECONDS",
    "SNAPSHOT_KEEP_RECENT", "SNAPSHOT_SWAP_RETRIES", "SNAPSHOT_SWAP_RETRY_SECONDS",
    "VIEW_DEFAULT_SERIES_DAYS", "VIEW_MAX_SERIES_DAYS", "MAX_REQUEST_BYTES",
    "MAX_STRING_LENGTH", "MAX_TEXT_LENGTH", "MAX_NUMBER", "TEAM_POLL_SECONDS", "PROJECTOR_POLL_SECONDS",
    "ACTION_SPECS", "CALLER_ACTIONS", "CALIBRATION_FILE", "RECORD_HISTORY", "RECORD_SLICES",
    "TELEMETRY_WINDOW_DAYS", "CALIBRATION_TOLERANCE",
]

# --- recording ------------------------------------------------------------
RECORD_HISTORY = True
RECORD_SLICES = True
TELEMETRY_WINDOW_DAYS = 364

# --- visibility -----------------------------------------------------------
# Key names that must never appear anywhere in a team view.
HIDDEN_FIELD_NAMES = [
    "lift", "lifts", "gain", "target_gain", "risk", "risk_points", "uod", "nev",
    "debt", "debt_mult", "cause", "true_cause", "variant", "caused_by", "defect",
    "defects", "mult", "hidden", "quality_debt", "mq", "other_teams",
]


def _read_calibration(cfg):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), cfg["CALIBRATION_FILE"])
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(overrides=None, calibrated=True):
    """Return an independent configuration dict. Overrides use module names.

    Solved lifts and tuned noise from the calibration file replace the
    placeholders unless calibrated is False or an override names that key.
    """
    overrides = overrides or {}
    cfg = {k: copy.deepcopy(v) for k, v in globals().items()
           if k.isupper() and not k.startswith("_")}
    for key, value in overrides.items():
        if key not in cfg:
            raise KeyError("unknown config key: %s" % key)
        cfg[key] = copy.deepcopy(value)
    data = _read_calibration(cfg) if calibrated else None
    if data:
        if "LIFTS" not in overrides:
            for cid, lift in data.get("lifts", {}).items():
                if cid not in cfg["LIFTS"]:
                    raise ValueError("calibration file names unknown card: %s" % cid)
                cfg["LIFTS"][cid] = lift
        if "LIFTS" not in overrides and "CALIBRATED_GAIN" not in overrides:
            for entry in data.get("cards", []):
                if entry["id"] in cfg["LIFTS"] and "achieved" in entry:
                    cfg["CALIBRATED_GAIN"][entry["id"]] = entry["achieved"]
        if "NOISE" not in overrides:
            cfg["NOISE"].update(data.get("noise", {}))
    cfg["CARD_BY_ID"] = {c["id"]: c for c in cfg["CARDS"]}
    return cfg
