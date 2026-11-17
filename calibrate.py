"""Solve hidden feature lifts to the spec's target gains, tune telemetry noise,
and write the balance report.

    python calibrate.py            solve lifts and noise, write calibration/lifts.json
    python calibrate.py --report   also write docs/balance/stage2-report.md

A card's gain is ARR at week 52 with only that card queued at its unlock week
in Medium quality, minus the same run with no card, with scripted events off.
"""
import copy
import json
import math
import os
import statistics
import sys

import bots
import config
import engine

ROOT = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(ROOT, "docs", "balance", "stage2-report.md")
NOISE_LEVELS = [round(0.05 * i, 2) for i in range(1, 11)]   # 5% to 50%; more would swamp the reading
NOISE_MAX_RATIO_ONE_QUARTER = 2.0
NOISE_MIN_RATIO_TWO_QUARTERS = 3.0
RETARGET_SHARE_OF_MAX = 0.8   # what-if: unreachable targets set to this share of the reachable maximum
PHANTOM_CARDS = ["A1", "B4", "C3"]


# --- lift solving ---------------------------------------------------------
def _solve_cfg(overrides, lifts):
    ov = dict(overrides or {})
    ov.update(EVENTS_ENABLED={k: False for k in config.EVENTS_ENABLED},
              RECORD_HISTORY=False, LIFTS=lifts)
    return config.load(ov, calibrated=False)


def unlock_day(cfg, card):
    quarter = max(1, card["unlock_q"])
    return (quarter - 1) * cfg["WEEKS_PER_QUARTER"] * cfg["DAYS_PER_WEEK"]


def _final_arr(cfg, card_id):
    state = engine.new_state(cfg, 1, 1)
    day0 = unlock_day(cfg, cfg["CARD_BY_ID"][card_id]) if card_id else None
    ship_day = None
    for day in range(cfg["TOTAL_DAYS"]):
        if day == day0:
            engine.apply(cfg, state, dict(type="queue_add", card=card_id))
        engine.step(cfg, state)
        if card_id and ship_day is None and card_id in state["shipped"]:
            ship_day = day
    return engine.score(cfg, state)["arr"], ship_day


def card_gain(overrides, card_id, lift):
    """(gain in Cr, ship day) for one card at one lift."""
    lifts = dict(config.LIFTS)
    lifts[card_id] = lift
    cfg = _solve_cfg(overrides, lifts)
    base, _ = _final_arr(cfg, None)
    arr, ship_day = _final_arr(cfg, card_id)
    return arr - base, ship_day


def solve_card(overrides, card):
    cfg = _solve_cfg(overrides, dict(config.LIFTS))
    cap = cfg["LIFT_CAPS"].get(card["stage"], cfg["LIFT_CAPS"]["default"])
    tol = cfg["CALIBRATION_TOLERANCE"]
    target = card["gain"]
    g0, ship_day = card_gain(overrides, card["id"], 0.0)
    g_mid, _ = card_gain(overrides, card["id"], cap / 2)
    g_cap, _ = card_gain(overrides, card["id"], cap)
    if not g0 <= g_mid <= g_cap:
        raise RuntimeError("gain is not monotonic in lift for %s" % card["id"])
    if g_cap < target:
        lift, achieved, status = cap, g_cap, "unreachable"
    elif g0 >= target:
        lift, achieved, status = 0.0, g0, "met at zero lift"
    else:
        lo, hi = 0.0, cap
        for _ in range(60):
            mid = (lo + hi) / 2
            if card_gain(overrides, card["id"], mid)[0] < target:
                lo = mid
            else:
                hi = mid
            if hi - lo < 1e-7:
                break
        lift = round(hi, 6)
        achieved = card_gain(overrides, card["id"], lift)[0]
        status = "solved" if abs(achieved - target) <= tol else "off target"
    return dict(id=card["id"], name=card["name"], unlock_q=card["unlock_q"], cost=card["cost"],
                stage=card["stage"], target=target, lift=lift, achieved=round(achieved, 4),
                max_gain=round(g_cap, 4), ship_day=ship_day, status=status,
                gain_per_bu=round(achieved / card["cost"], 4))


def calibrate(overrides=None):
    """Solve every funnel card. Returns cards, lifts and the Q4 value bar."""
    cfg = _solve_cfg(overrides, dict(config.LIFTS))
    cards = [solve_card(overrides, c) for c in cfg["CARDS"]
             if c["stage"] not in (None, "contract")]
    bar = statistics.median(c["gain_per_bu"] for c in cards if c["unlock_q"] < 4)
    for c in cards:
        c["worth_building"] = (c["gain_per_bu"] >= bar) if c["unlock_q"] == 4 else None
    return dict(cards=cards, lifts={c["id"]: c["lift"] for c in cards}, q4_bar=round(bar, 4))


def calibration_table(result):
    lines = ["%-4s %-30s %2s %4s %-15s %6s %7s %8s %7s %7s %s" % (
        "id", "card", "Q", "BU", "stage", "target", "lift", "achieved", "max", "Cr/BU", "status")]
    for c in result["cards"]:
        note = c["status"]
        if c["worth_building"] is not None:
            note += ", Q4 worth building" if c["worth_building"] else ", Q4 below the Q1-Q3 median"
        lines.append("%-4s %-30s %2d %4d %-15s %6.2f %7.3f %8.3f %7.2f %7.3f %s" % (
            c["id"], c["name"][:30], c["unlock_q"], c["cost"], c["stage"], c["target"],
            c["lift"], c["achieved"], c["max_gain"], c["gain_per_bu"], note))
    return "\n".join(lines)


# --- noise ----------------------------------------------------------------
def _mean_uod_path(cfg, name):
    teams = [t for t in bots.league_teams() if t[1] == name]
    res = bots.run_game(cfg, teams)
    paths = [[rec["uod"] for rec in r["state"]["history"]] for r in res.values()]
    return [statistics.mean(day) for day in zip(*paths)]


def _ratio(series, weeks, level, days_per_week):
    window = series[:weeks * days_per_week]
    first = statistics.mean(window[:days_per_week])
    last = statistics.mean(window[-days_per_week:])
    noise_sd = level * statistics.mean(window) / math.sqrt(3 * days_per_week)
    return abs(last - first) / noise_sd if noise_sd else float("inf")


def pick_noise_level(series, cfg):
    """Smallest level that is ambiguous after one quarter and clear after two, else the closest."""
    dpw, q = cfg["DAYS_PER_WEEK"], cfg["WEEKS_PER_QUARTER"]
    best = None
    for level in NOISE_LEVELS:
        r1, r2 = _ratio(series, q, level, dpw), _ratio(series, 2 * q, level, dpw)
        miss = (max(0.0, r1 - NOISE_MAX_RATIO_ONE_QUARTER)
                + max(0.0, NOISE_MIN_RATIO_TWO_QUARTERS - r2))
        cand = dict(level=level, one_quarter=round(r1, 2), two_quarters=round(r2, 2),
                    rule_met=miss == 0.0)
        if best is None or miss < best[0]:
            best = (miss, cand)
        if miss == 0.0:
            break
    return best[1]


def tune_noise(cfg):
    """Pick error-rate and latency noise from the corner-cutter's debt path.

    That team is the one with a trend to hide, so both windows are measured on
    it. The measured-risk ratios at the chosen level are reported alongside.
    """
    dpw, q = cfg["DAYS_PER_WEEK"], cfg["WEEKS_PER_QUARTER"]
    paths = {n: _mean_uod_path(cfg, n) for n in ("corner-cutter", "measured-risk")}
    series = {
        "error_rate": lambda u: cfg["ERROR_RATE_BASE"] + cfg["ERROR_RATE_PER_UOD"] * u,
        "p99": lambda u: cfg["P99_BASE_MS"] + cfg["P99_PER_UOD_MS"] * u,
    }
    out = {}
    for key, fn in series.items():
        ref = [fn(u) for u in paths["corner-cutter"]]
        best = pick_noise_level(ref, cfg)
        before = config.NOISE[key]
        if not best["rule_met"]:
            # no sane level hides one quarter: keep the current level and say what it would take
            r1 = _ratio(ref, q, before, dpw)
            best = dict(level=before, one_quarter=round(r1, 2),
                        two_quarters=round(_ratio(ref, 2 * q, before, dpw), 2), rule_met=False)
            best["level_needed"] = round(before * r1 / NOISE_MAX_RATIO_ONE_QUARTER, 2)
        other = [fn(u) for u in paths["measured-risk"]]
        best["before"] = before
        best["measured_risk_one_quarter"] = round(_ratio(other, q, best["level"], dpw), 2)
        best["measured_risk_two_quarters"] = round(_ratio(other, 2 * q, best["level"], dpw), 2)
        out[key] = best
    return out


# --- calibration file -----------------------------------------------------
def write_calibration(result, noise, path=None):
    path = path or os.path.join(ROOT, config.CALIBRATION_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = dict(
        inputs=dict(capacity_bu_per_week=config.CAPACITY_BU_PER_WEEK,
                    quality_modes=config.QUALITY_MODES, lift_caps=config.LIFT_CAPS,
                    segments=config.SEGMENTS, tolerance=config.CALIBRATION_TOLERANCE),
        lifts=result["lifts"],
        noise={k: v["level"] for k, v in noise.items()},
        noise_check=noise, cards=result["cards"], q4_bar=result["q4_bar"])
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write("\n")
    return path


# --- what-if --------------------------------------------------------------
def _cards_with_gains(changes):
    cards = copy.deepcopy(config.CARDS)
    for c in cards:
        if c["id"] in changes:
            c["gain"] = changes[c["id"]]
    return cards


def what_if_rows(result):
    """(label, config overrides, whether lifts must be re-solved)."""
    retarget = {c["id"]: round(RETARGET_SHARE_OF_MAX * c["max_gain"], 2)
                for c in result["cards"] if c["status"] == "unreachable"}
    gains = {c["id"]: c["gain"] for c in config.CARDS}
    phantom = {cid: gains[cid] / 2 for cid in PHANTOM_CARDS}
    return [
        ("report cost 4 -> 2", dict(REPORT_COST=2), False),
        ("valuation rate 0.25 -> 0.40 Cr per UOD", dict(UOD_VALUATION_COST=0.40), False),
        ("valuation rate 0.25 -> 0.60 Cr per UOD", dict(UOD_VALUATION_COST=0.60), False),
        ("unreachable targets lowered to %s" % ", ".join(
            "%s %.2f" % kv for kv in sorted(retarget.items())),
         dict(CARDS=_cards_with_gains(retarget)), True),
        ("phantom targets halved (%s)" % ", ".join(PHANTOM_CARDS),
         dict(CARDS=_cards_with_gains(phantom)), True),
        ("report cost 2 and valuation rate 0.60",
         dict(REPORT_COST=2, UOD_VALUATION_COST=0.60), False),
    ]


def run_what_if(label, overrides, lifts, noise_levels):
    ov = dict(overrides, LIFTS=lifts, NOISE={**config.NOISE, **noise_levels})
    rows = bots.run_league(config.load(ov, calibrated=False))
    return dict(label=label, winner=rows[0]["name"], rows=rows, criteria=bots.criteria(rows))


def what_if(result, noise):
    """League criteria under named number changes. Nothing is committed."""
    levels = {k: v["level"] for k, v in noise.items()}
    out = []
    for label, overrides, resolve in what_if_rows(result):
        lifts = calibrate(overrides)["lifts"] if resolve else result["lifts"]
        out.append(run_what_if(label, overrides, lifts, levels))
    return out


# --- report ---------------------------------------------------------------
def _md_league(rows):
    lines = ["| Strategy | ARR wk26 | ARR wk52 | Trust | UOD | Penalty | NEV | NEV min | NEV max |",
             "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in rows:
        lines.append("| %s | %.2f | %.2f | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f |" % (
            r["name"], r["arr26"], r["arr52"], r["trust"], r["uod"], r["penalty"],
            r["nev"], r["nev_min"], r["nev_max"]))
    return "\n".join(lines)


def _md_criteria(crit):
    return "\n".join("- **%s** %s. %s." % ("PASS" if ok else "FAIL", label,
                                          detail[0].upper() + detail[1:])
                     for label, ok, detail in crit)


def write_report(result, noise, before_rows, after_rows, whatifs, path=None):
    path = path or REPORT_PATH
    crit = bots.criteria(after_rows)
    out = ["# Stage 2 balance report", "",
           "Generated by `python calibrate.py --report`. All runs are deterministic. "
           "The league is 24 teams: 8 strategies in 3 copies, one per incident variant.", "",
           "## Pass criteria after calibration", "", _md_criteria(crit), "",
           "## Calibration", "",
           "Gain is ARR at week 52 from one card queued at its unlock week in Medium quality, "
           "minus the no-card run, with scripted events off. Lifts are capped at %.2f for "
           "retention and %.1f for other stages." % (config.LIFT_CAPS["retention"],
                                                     config.LIFT_CAPS["default"]), "",
           "| Card | Q | BU | Stage | Target Cr | Lift | Achieved Cr | Max reachable Cr | Cr per BU | Status |",
           "| :--- | ---: | ---: | :--- | ---: | ---: | ---: | ---: | ---: | :--- |"]
    for c in result["cards"]:
        out.append("| %s %s | %d | %d | %s | %.2f | %.3f | %.3f | %.2f | %.3f | %s |" % (
            c["id"], c["name"], c["unlock_q"], c["cost"], c["stage"], c["target"], c["lift"],
            c["achieved"], c["max_gain"], c["gain_per_bu"], c["status"]))
    out += ["", "## Are the Q4 cards worth building?", "",
            "A Q4 card counts as worth building when its gain per BU is at least the median of "
            "the Q1 to Q3 cards (%.3f Cr per BU)." % result["q4_bar"], ""]
    for c in result["cards"]:
        if c["unlock_q"] == 4:
            out.append("- %s %s: %.3f Cr per BU, %s." % (
                c["id"], c["name"], c["gain_per_bu"],
                "worth building" if c["worth_building"] else "below the bar"))
    out += ["", "## League before calibration (placeholder lifts of %.2f)" % config.PLACEHOLDER_LIFT,
            "", _md_league(before_rows), "", "## League after calibration", "",
            _md_league(after_rows), "", "## Telemetry noise", "",
            "Rule: the signal-to-noise ratio on weekly means of the corner-cutter's series is at "
            "most %.0f over weeks 1 to 13 and at least %.0f over weeks 1 to 26."
            % (NOISE_MAX_RATIO_ONE_QUARTER, NOISE_MIN_RATIO_TWO_QUARTERS), "",
            "| Series | Before | After | Ratio, one quarter | Ratio, two quarters | Rule met | Measured-risk ratios |",
            "| :--- | ---: | ---: | ---: | ---: | :--- | :--- |"]
    for key, n in noise.items():
        met = "yes" if n["rule_met"] else "no, would need %.2f" % n["level_needed"]
        out.append("| %s | %.2f | %.2f | %.2f | %.2f | %s | %.2f and %.2f |" % (
            key, n["before"], n["level"], n["one_quarter"], n["two_quarters"], met,
            n["measured_risk_one_quarter"], n["measured_risk_two_quarters"]))
    labels = [c[0] for c in crit]
    out += ["", "## What-if table", "",
            "Each row changes only the numbers named, re-solves lifts where targets change, and "
            "re-runs the league. None of these changes is committed.", "",
            "| Change | Winner | measured-risk NEV | " + " | ".join(
                "C%d" % (i + 1) for i in range(len(labels))) + " |",
            "| :--- | :--- | ---: | " + " | ".join(":---:" for _ in labels) + " |"]
    base_m = {r["name"]: r for r in after_rows}["measured-risk"]["nev"]
    out.append("| none (calibrated baseline) | %s | %.1f | %s |" % (
        after_rows[0]["name"], base_m, " | ".join("pass" if c[1] else "fail" for c in crit)))
    for w in whatifs:
        m = {r["name"]: r for r in w["rows"]}["measured-risk"]["nev"]
        out.append("| %s | %s | %.1f | %s |" % (
            w["label"], w["winner"], m,
            " | ".join("pass" if c[1] else "fail" for c in w["criteria"])))
    out.append("")
    out += ["C%d: %s." % (i + 1, label) for i, label in enumerate(labels)]
    out.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    return path


def main(argv):
    result = calibrate()
    print(calibration_table(result))
    noise = tune_noise(config.load(dict(LIFTS=result["lifts"]), calibrated=False))
    for key, n in noise.items():
        print("noise %-10s %.2f -> %.2f  one quarter %.2f, two quarters %.2f, rule met: %s" % (
            key, n["before"], n["level"], n["one_quarter"], n["two_quarters"], n["rule_met"]))
    print("wrote", write_calibration(result, noise))
    if "--report" in argv:
        before = bots.run_league(config.load(calibrated=False))
        after = bots.run_league(config.load())
        print(bots.results_table(after))
        print(bots.criteria_lines(after))
        print("wrote", write_report(result, noise, before, after, what_if(result, noise)))


if __name__ == "__main__":
    main(sys.argv[1:])
