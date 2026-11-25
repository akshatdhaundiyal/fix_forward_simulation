"""Pure daily simulation of one team's product.

State is a JSON-serializable dict. step() and apply() change it in place; the
guarantee of determinism is that replay(config, seed, team, log) always gives
the same state. Nothing here reads a clock or draws a random number. Display
noise is hashed from (seed, team, series, day) and never feeds back into state.
"""
import hashlib
import json

# --- calendar -------------------------------------------------------------
def week_of(cfg, day):
    return day // cfg["DAYS_PER_WEEK"] + 1


def quarter_of_week(cfg, week):
    return (week - 1) // cfg["WEEKS_PER_QUARTER"] + 1


def quarter_of_day(cfg, day):
    return quarter_of_week(cfg, week_of(cfg, day))


# --- state ----------------------------------------------------------------
def variant_for(cfg, team_no):
    order = cfg["VARIANT_ORDER"]
    return order[team_no % len(order)]


def _inc(state, n):
    for inc in state["incidents"]:
        if inc["n"] == n:
            return inc
    return None


def new_state(cfg, team_no, seed):
    seg = {}
    for s in cfg["SEGMENT_ORDER"]:
        b = cfg["SEGMENTS"][s]
        seg[s] = dict(accounts=float(b["accounts"]),
                      arr_pa=float(b["arr_per_account"]),
                      trust=float(cfg["TRUST_START"]))
    variant = variant_for(cfg, team_no)
    incidents = [dict(n=n, status="pending", variant=variant, segs=[], slice={},
                      cause=None, caused_by=None, patched=False, opened_day=None,
                      slows=False) for n in sorted(cfg["INCIDENTS"])]
    return dict(
        team=team_no, seed=seed, day=0, seg=seg, uod=0.0, penalty=0.0,
        bespoke_arr=0.0, bespoke_n=0, quality=cfg["QUALITY_DEFAULT"],
        queue=[], next_item=1, shipped={}, rolled_back=[], rollbacks=[],
        p_used=[], defects=[], incidents=incidents, reports=[], releases=[],
        b1_applied=False, b1_awarded=False, rework_owed=0.0, history=[],
        events=[],
    )


def _clamp_trust(cfg, v):
    return max(cfg["TRUST_MIN"], min(cfg["TRUST_MAX"], v))


def _add_trust(cfg, state, seg, delta):
    sd = state["seg"][seg]
    sd["trust"] = _clamp_trust(cfg, sd["trust"] + delta)


def _event(state, kind, **info):
    info.update(day=state["day"], kind=kind)
    state["events"].append(info)


# --- funnel maths ---------------------------------------------------------
def _lift_mult(state, seg, stage):
    m = 1.0
    for e in state["shipped"].values():
        if e["seg"] == seg and e["stage"] == stage:
            m *= max(0.0, 1.0 - e["lift"]) if stage == "retention" else (1.0 + e["lift"])
    return m


def _defect_mult(cfg, state, seg, stage, restrict):
    m = 1.0
    for d in state["defects"]:
        if d["stage"] != stage or seg not in d["segs"]:
            continue
        frac = 1.0
        for dim, val in d["slice"].items():
            if restrict and dim in restrict:
                frac *= 1.0 if restrict[dim] == val else 0.0
            else:
                frac *= cfg["SLICES"][dim][val]
        effective = 1.0 - d["factor"] * (1.0 - d["mult"])
        m *= 1.0 - frac * (1.0 - effective)
    return m


def stage_rates(cfg, state, seg, restrict=None):
    """Effective weekly rates for a segment, or for one slice if restrict is set."""
    b = cfg["SEGMENTS"][seg]
    sd = state["seg"][seg]
    uod = state["uod"]

    def dm(stage):
        return _defect_mult(cfg, state, seg, stage, restrict)

    uod_act = max(0.0, 1.0 - cfg["UOD_ACTIVATION_PER_POINT"] * uod)
    trust_f = max(0.0, 1.0 + cfg["TRUST_CHURN_COEF"] * (cfg["TRUST_NEUTRAL"] - sd["trust"]))
    return dict(
        leads=b["leads"] * _lift_mult(state, seg, "leads") * dm("leads"),
        signup=min(1.0, b["signup"] * _lift_mult(state, seg, "signup") * dm("signup")),
        activation=min(1.0, b["activation"] * _lift_mult(state, seg, "activation")
                       * dm("activation") * uod_act),
        paid=min(1.0, b["paid"] * _lift_mult(state, seg, "paid") * dm("paid")),
        churn=b["churn"] * trust_f * _lift_mult(state, seg, "retention")
        * dm("retention") * (1.0 + cfg["UOD_CHURN_PER_POINT"] * uod),
        arr_pa=sd["arr_pa"] * _lift_mult(state, seg, "arr_per_account"),
    )


def seg_arr(cfg, state, seg):
    return state["seg"][seg]["accounts"] * stage_rates(cfg, state, seg)["arr_pa"]


def _record_day(cfg, state, per_seg):
    if not cfg["RECORD_HISTORY"]:
        return
    open_segs = sorted({s for i in state["incidents"] if i["status"] == "open"
                        for s in i["segs"]})
    rec = dict(
        day=state["day"], uod=state["uod"],
        slow=any(i["status"] == "open" and i["slows"] for i in state["incidents"]),
        inc_segs=open_segs,
        trust={s: state["seg"][s]["trust"] for s in cfg["SEGMENT_ORDER"]},
        seg=per_seg,
    )
    state["history"].append(rec)


def _funnel(cfg, state):
    per_seg = {}
    dpw = cfg["DAYS_PER_WEEK"]
    for s in cfg["SEGMENT_ORDER"]:
        sd = state["seg"][s]
        r = stage_rates(cfg, state, s)
        new_w = r["leads"] * r["signup"] * r["activation"] * r["paid"]
        lost_w = sd["accounts"] * r["churn"]
        entry = None
        if cfg["RECORD_HISTORY"]:
            entry = dict(rates={k: r[k] for k in ("leads", "signup", "activation", "paid", "churn")},
                         new=new_w / dpw, lost=lost_w / dpw)
            if cfg["RECORD_SLICES"]:
                slices = {}
                for dim, shares in cfg["SLICES"].items():
                    for val in shares:
                        sr = stage_rates(cfg, state, s, {dim: val})
                        slices["%s:%s" % (dim, val)] = {
                            k: sr[k] for k in ("leads", "signup", "activation", "paid", "churn")}
                entry["slices"] = slices
        sd["accounts"] = max(0.0, sd["accounts"] + (new_w - lost_w) / dpw)
        if entry is not None:
            entry["accounts"] = sd["accounts"]
            entry["arr"] = sd["accounts"] * r["arr_pa"]
            per_seg[s] = entry
    _record_day(cfg, state, per_seg)


# --- incidents ------------------------------------------------------------
def _latest_release(state):
    for rel in reversed(state["releases"]):
        if rel["card"] in state["shipped"] and rel["seg"] and not rel["bespoke"]:
            return rel
    return None


def _open_incident(cfg, state, n, caused_by_card=None):
    inc = _inc(state, n)
    spec = cfg["INCIDENTS"][n]
    v = spec["variants"][inc["variant"]]
    segs = v["segs"]
    caused_by = None
    if segs == "release":
        card_id = caused_by_card
        if card_id is None:
            rel = _latest_release(state)
            if rel is None:
                inc["status"] = "skipped"
                return False
            card_id = rel["card"]
        card = cfg["CARD_BY_ID"][card_id]
        segs, caused_by = [card["seg"]], card["id"]
    inc.update(status="open", segs=list(segs), slice=dict(v["slice"]), cause=v["cause"],
               caused_by=caused_by, patched=False, opened_day=state["day"],
               slows=bool(v["slows"]))
    state["defects"].append(dict(incident=n, segs=list(segs), stage=spec["stage"],
                                 slice=dict(v["slice"]), mult=spec["mult"], factor=1.0))
    _event(state, "incident_open", n=n)
    return True


def _close_incident(state, n, status):
    inc = _inc(state, n)
    state["defects"] = [d for d in state["defects"] if d["incident"] != n]
    inc["status"] = status
    _event(state, "incident_" + status, n=n)


def _incident_trust_loss(cfg, state):
    per_day = cfg["INCIDENT_TRUST_LOSS_PER_WEEK"] / cfg["DAYS_PER_WEEK"]
    for inc in state["incidents"]:
        if inc["status"] == "open" and not inc["patched"]:
            for s in inc["segs"]:
                _add_trust(cfg, state, s, -per_day)


# --- shipping -------------------------------------------------------------
def _ship_card(cfg, state, item):
    card = cfg["CARD_BY_ID"][item["card"]]
    day = state["day"]
    debt = 0.0
    if card["risk"]:
        debt = card["risk"] * item["mq"] / item["cost"]
        state["uod"] += debt
    delta = card.get("uod_delta", 0.0)
    if delta:
        state["uod"] = max(0.0, state["uod"] + delta)
    for s, d in card["trust"].items():
        _add_trust(cfg, state, s, d)
    if card.get("once_per_quarter"):
        state["p_used"].append([card["id"], quarter_of_day(cfg, day)])
        _event(state, "ship", card=card["id"])
        return
    state["shipped"][card["id"]] = dict(
        card=card["id"], day=day, seg=card["seg"], stage=card["stage"],
        lift=cfg["LIFTS"].get(card["id"], 0.0), debt=debt, trust=dict(card["trust"]),
        bespoke=bool(card.get("bespoke")))
    if card["id"] in state["rolled_back"]:
        state["rolled_back"].remove(card["id"])
    if card.get("bespoke"):
        state["bespoke_arr"] += card["signed"]
        state["bespoke_n"] += 1
    state["releases"].append(dict(card=card["id"], day=day, seg=card["seg"],
                                  bespoke=bool(card.get("bespoke"))))
    _event(state, "ship", card=card["id"])
    if cfg["EVENTS_ENABLED"]["incidents"] and card["seg"] and not card.get("bespoke"):
        wk = week_of(cfg, day)
        for n, spec in sorted(cfg["INCIDENTS"].items()):
            trig = spec["trigger"]
            if (trig["type"] == "ship_in_window" and _inc(state, n)["status"] == "pending"
                    and trig["first_week"] <= wk <= trig["last_week"]):
                _open_incident(cfg, state, n, caused_by_card=card["id"])


def _alerts_for_segment(cfg, state, seg):
    return [a["text"] for a in cfg["ALERTS"].values()
            if a["seg"] == seg and a["needs_card"] not in state["shipped"]]


def _complete_item(cfg, state, item):
    kind = item["kind"]
    if kind == "card":
        _ship_card(cfg, state, item)
    elif kind == "report":
        seg = item["seg"]
        util = {cid: int(round(cfg["UTILITY_SCALE"]
                               * cfg["CALIBRATED_GAIN"].get(cid, cfg["CARD_BY_ID"][cid]["gain"])
                               / cfg["CARD_BY_ID"][cid]["pitch"]))
                for cid in item["avail"]}
        state["reports"].append(dict(seg=seg, day=state["day"], utility=util,
                                     alerts=_alerts_for_segment(cfg, state, seg)))
        _event(state, "report", seg=seg)
    elif kind == "fix":
        inc = _inc(state, item["incident"])
        if inc["status"] == "open" and item["picked"] == inc["cause"]:
            _close_incident(state, inc["n"], "resolved")
            state["uod"] = max(0.0, state["uod"] + cfg["FIX_UOD_DELTA"])
        else:
            _event(state, "fix_wasted", n=item["incident"])
    elif kind == "patch":
        inc = _inc(state, item["incident"])
        if inc["status"] == "open":
            inc["patched"] = True
            for d in state["defects"]:
                if d["incident"] == inc["n"]:
                    d["factor"] = cfg["PATCH_DAMAGE_FACTOR"]
            state["uod"] += cfg["PATCH_UOD_DELTA"]
            _event(state, "patched", n=inc["n"])


def _weekly_capacity(cfg, state):
    return max(0.0, cfg["CAPACITY_BU_PER_WEEK"] - cfg["BESPOKE_CAPACITY_TAX"] * state["bespoke_n"])


def _spend_capacity(cfg, state):
    cap = _weekly_capacity(cfg, state) / cfg["DAYS_PER_WEEK"]
    if state["rework_owed"] > cfg["FLOAT_EPS"]:
        pay = min(state["rework_owed"], cap)
        state["rework_owed"] -= pay
        state["uod"] = max(0.0, state["uod"] - pay)
        cap -= pay
    mode = cfg["QUALITY_MODES"][state["quality"]]
    avail = cap * mode["keep"]
    queue = state["queue"]
    while avail > cfg["FLOAT_EPS"] and queue:
        item = queue[0]
        take = min(avail, item["cost"] - item["progress"])
        item["progress"] += take
        item["mq"] += take * mode["debt_mult"]
        avail -= take
        if item["cost"] - item["progress"] <= cfg["FLOAT_EPS"]:
            queue.pop(0)
            _complete_item(cfg, state, item)
        else:
            break


def _process_rollbacks(cfg, state):
    due = [r for r in state["rollbacks"] if r["day"] <= state["day"]]
    if not due:
        return
    state["rollbacks"] = [r for r in state["rollbacks"] if r["day"] > state["day"]]
    for r in due:
        entry = state["shipped"].pop(r["card"], None)
        if entry is None:
            continue
        state["uod"] = max(0.0, state["uod"] - entry["debt"])
        for s, d in entry["trust"].items():
            _add_trust(cfg, state, s, -d)
        if entry["seg"]:
            _add_trust(cfg, state, entry["seg"], -cfg["ROLLBACK_TRUST_LOSS"])
        state["rolled_back"].append(r["card"])
        for inc in state["incidents"]:
            if inc["status"] == "open" and inc["caused_by"] == r["card"]:
                _close_incident(state, inc["n"], "resolved")
        _event(state, "rollback", card=r["card"])


def _week_start(cfg, state, week):
    if week == cfg["PEAK_START_WEEK"] and cfg["EVENTS_ENABLED"]["peak_season"]:
        if state["uod"] > cfg["PEAK_UOD_THRESHOLD"]:
            owed = min(cfg["PEAK_REWORK_CAP"], state["uod"] - cfg["PEAK_REWORK_FLOOR"])
            state["rework_owed"] += owed
            state["penalty"] += cfg["PEAK_PENALTY"]
            for s, delta in cfg["PEAK_OUTAGE_TRUST"].items():
                _add_trust(cfg, state, s, delta)
            _event(state, "outage", owed=owed)
        else:
            for s, delta in cfg["PEAK_SAFE_TRUST"].items():
                _add_trust(cfg, state, s, delta)
            _event(state, "peak_held")
    if cfg["EVENTS_ENABLED"]["incidents"]:
        for n, spec in sorted(cfg["INCIDENTS"].items()):
            trig = spec["trigger"]
            if (trig["type"] == "week_start" and week == trig["week"]
                    and _inc(state, n)["status"] == "pending"):
                _open_incident(cfg, state, n)


def _end_of_week_alerts(cfg, state, week):
    for key, a in cfg["ALERTS"].items():
        if a["week"] != week or a["needs_card"] in state["shipped"]:
            continue
        seg = state["seg"][a["seg"]]
        if a["arr_loss"]:
            pa = stage_rates(cfg, state, a["seg"])["arr_pa"]
            seg["accounts"] = max(0.0, seg["accounts"] - a["arr_loss"] / pa)
        _add_trust(cfg, state, a["seg"], a["trust"])
        _event(state, "alert", alert=key)


def step(cfg, state):
    """Advance one simulated day."""
    day = state["day"]
    week = week_of(cfg, day)
    if day % cfg["DAYS_PER_WEEK"] == 0:
        _week_start(cfg, state, week)
    _process_rollbacks(cfg, state)
    _incident_trust_loss(cfg, state)
    _spend_capacity(cfg, state)
    _funnel(cfg, state)
    if (day + 1) % cfg["DAYS_PER_WEEK"] == 0 and cfg["EVENTS_ENABLED"]["churn_alerts"]:
        _end_of_week_alerts(cfg, state, week)
    state["day"] = day + 1


# --- actions --------------------------------------------------------------
def _err(msg):
    return dict(ok=False, error=msg)


def _ok(**kw):
    kw["ok"] = True
    return kw


def _new_item(state, kind, cost, **kw):
    item = dict(id=state["next_item"], kind=kind, cost=float(cost), progress=0.0, mq=0.0)
    item.update(kw)
    state["next_item"] += 1
    return item


def _find_item(state, item_id):
    for i, it in enumerate(state["queue"]):
        if it["id"] == item_id:
            return i
    return None


def _card_cost(cfg, state, card):
    share = cfg["RESHIP_COST_SHARE"] if card["id"] in state["rolled_back"] else 1.0
    return card["cost"] * share


def _queue_card(cfg, state, card_id):
    card = cfg["CARD_BY_ID"].get(card_id)
    if card is None:
        return _err("unknown card")
    quarter = quarter_of_day(cfg, state["day"])
    if card["unlock_q"] > quarter:
        return _err("card locked")
    if card["id"] == cfg["B1_CARD"]:
        return _err("B1 is awarded, not queued")
    queued = [it for it in state["queue"] if it["kind"] == "card" and it["card"] == card_id]
    if card.get("once_per_quarter"):
        if [1 for cid, q in state["p_used"] if cid == card_id and q == quarter] or queued:
            return _err("already used this quarter")
    elif card_id in state["shipped"] or queued:
        return _err("already built or queued")
    item = _new_item(state, "card", _card_cost(cfg, state, card), card=card_id, label=card["name"])
    state["queue"].append(item)
    return _ok(item=item["id"])


def _queue_report(cfg, state, seg):
    if seg not in cfg["SEGMENTS"]:
        return _err("unknown segment")
    quarter = quarter_of_day(cfg, state["day"])
    avail = [c["id"] for c in cfg["CARDS"]
             if c["seg"] == seg and c["pitch"] > 0 and c["unlock_q"] <= quarter]
    item = _new_item(state, "report", cfg["REPORT_COST"], seg=seg, avail=avail,
                     label="Segment report: " + cfg["SEGMENTS"][seg]["name"])
    state["queue"].append(item)
    return _ok(item=item["id"])


def _queue_fix(cfg, state, n, cause, patch):
    if n not in cfg["INCIDENTS"]:
        return _err("unknown incident")
    inc = _inc(state, n)
    if inc["status"] != "open":
        return _err("incident not open")
    kind = "patch" if patch else "fix"
    if any(it["kind"] == kind and it["incident"] == n for it in state["queue"]):
        return _err("already queued")
    if patch:
        if inc["patched"]:
            return _err("already patched")
        item = _new_item(state, "patch", cfg["PATCH_COST"], incident=n, label="Patch")
    else:
        if cause not in cfg["INCIDENTS"][n]["causes"]:
            return _err("unknown cause")
        item = _new_item(state, "fix", cfg["FIX_COST"], incident=n, picked=cause,
                         label="Targeted fix")
    state["queue"].insert(0, item)
    return _ok(item=item["id"])


def _rollback(cfg, state, card_id):
    entry = state["shipped"].get(card_id)
    if entry is None:
        return _err("not shipped")
    if entry["bespoke"] or entry["stage"] is None:
        return _err("cannot roll back")
    if any(r["card"] == card_id for r in state["rollbacks"]):
        return _err("rollback already pending")
    state["rollbacks"].append(dict(card=card_id, day=state["day"] + cfg["ROLLBACK_DELAY_DAYS"]))
    return _ok()


_ADMIN_ROOTS = {"seg", "uod", "penalty", "bespoke_arr", "quality", "rework_owed"}


def _admin_edit(state, path, value, reason):
    if not reason:
        return _err("reason required")
    parts = path.split(".")
    if parts[0] not in _ADMIN_ROOTS:
        return _err("field not editable")
    node = state
    for p in parts[:-1]:
        if not isinstance(node, dict) or p not in node:
            return _err("bad path")
        node = node[p]
    if not isinstance(node, dict) or parts[-1] not in node:
        return _err("bad path")
    node[parts[-1]] = value
    _event(state, "admin_edit", path=path, reason=reason)
    return _ok()


def apply(cfg, state, action):
    """Apply one action at the current day. Returns {'ok': bool, ...}."""
    t = action.get("type")
    week = week_of(cfg, state["day"])
    if t == "queue_add":
        if "report" in action:
            return _queue_report(cfg, state, action["report"])
        return _queue_card(cfg, state, action.get("card"))
    if t == "queue_remove":
        i = _find_item(state, action.get("item"))
        if i is None:
            return _err("no such item")
        state["queue"].pop(i)
        return _ok()
    if t == "queue_reorder":
        i = _find_item(state, action.get("item"))
        if i is None:
            return _err("no such item")
        it = state["queue"].pop(i)
        pos = max(0, min(len(state["queue"]), int(action.get("position", 0))))
        state["queue"].insert(pos, it)
        return _ok()
    if t == "set_quality":
        if action.get("mode") not in cfg["QUALITY_MODES"]:
            return _err("unknown mode")
        state["quality"] = action["mode"]
        return _ok()
    if t == "rollback":
        return _rollback(cfg, state, action.get("card"))
    if t == "targeted_fix":
        return _queue_fix(cfg, state, action.get("incident"), action.get("cause"), False)
    if t == "patch":
        return _queue_fix(cfg, state, action.get("incident"), None, True)
    if t == "apply_b1":
        if not cfg["B1_APPLY_FIRST_WEEK"] <= week <= cfg["B1_APPLY_LAST_WEEK"]:
            return _err("application window closed")
        state["b1_applied"] = True
        return _ok()
    if t == "award_bespoke":
        card = cfg["CARD_BY_ID"][cfg["B1_CARD"]]
        state["b1_awarded"] = True
        state["queue"].append(_new_item(state, "card", card["cost"], card=card["id"],
                                        label=card["name"]))
        return _ok()
    if t == "decline_result":
        ticks = max(0, min(max(cfg["DECLINE_TRUST"]), int(action.get("ticks", 0))))
        _add_trust(cfg, state, cfg["DECLINE_SEG"], cfg["DECLINE_TRUST"][ticks])
        return _ok()
    if t == "trigger_incident":
        n = action.get("incident")
        if n not in cfg["INCIDENTS"] or _inc(state, n)["status"] != "pending":
            return _err("cannot trigger")
        return _ok(started=_open_incident(cfg, state, n))
    if t == "cancel_incident":
        n = action.get("incident")
        if n not in cfg["INCIDENTS"] or _inc(state, n)["status"] != "open":
            return _err("cannot cancel")
        _close_incident(state, n, "cancelled")
        return _ok()
    if t == "admin_edit":
        return _admin_edit(state, action.get("path", ""), action.get("value"),
                           action.get("reason"))
    return _err("unknown action")


# --- league ---------------------------------------------------------------
def resolve_b1_awards(cfg, states):
    """Team numbers that win the B1 slots: highest Whale trust, ties to lower team number."""
    applicants = [s for s in states if s["b1_applied"] and not s["b1_awarded"]]
    applicants.sort(key=lambda s: (-s["seg"][cfg["B1_RANK_SEG"]]["trust"], s["team"]))
    return [s["team"] for s in applicants[:cfg["B1_SLOTS"]]]


# --- replay ---------------------------------------------------------------
def replay(cfg, seed, team_no, log, until_day=None):
    """Rebuild state from an action log of (day, action) pairs."""
    state = new_state(cfg, team_no, seed)
    end = cfg["TOTAL_DAYS"] if until_day is None else until_day
    by_day = {}
    for day, action in log:
        by_day.setdefault(day, []).append(action)
    for day in range(end):
        for action in by_day.get(day, []):
            apply(cfg, state, action)
        step(cfg, state)
    for action in by_day.get(end, []):
        apply(cfg, state, action)
    return state


# --- digest ---------------------------------------------------------------
def state_digest(state):
    """Hash of a team's state without its per-day history (history is derived)."""
    body = {k: v for k, v in state.items() if k != "history"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# --- scoring --------------------------------------------------------------
def score(cfg, state):
    arr_nb = sum(seg_arr(cfg, state, s) for s in cfg["SEGMENT_ORDER"])
    trust_avg = sum(state["seg"][s]["trust"] for s in cfg["SEGMENT_ORDER"]) / len(cfg["SEGMENT_ORDER"])
    multiple = cfg["TRUST_MULTIPLE_BASE"] + cfg["TRUST_MULTIPLE_SLOPE"] * trust_avg
    nev = (arr_nb * multiple + state["bespoke_arr"] * cfg["BESPOKE_VALUE_MULT"]
           - cfg["UOD_VALUATION_COST"] * state["uod"] - state["penalty"])
    return dict(arr=arr_nb + state["bespoke_arr"], arr_nonbespoke=arr_nb,
                bespoke_arr=state["bespoke_arr"], trust_avg=trust_avg,
                uod=state["uod"], penalty=state["penalty"], nev=nev)


def cto_band(cfg, uod):
    """The CTO's traffic light for a hidden-debt level: green, amber or red."""
    green, amber = cfg["CTO_BAND_LIMITS"]
    return "green" if uod <= green else "amber" if uod <= amber else "red"


def weekly_records(cfg, state):
    """The last daily record of each week, as {week: record}. Empty weeks are absent."""
    out = {}
    for rec in state["history"]:
        out[week_of(cfg, rec["day"])] = rec
    return out


def record_arr(rec):
    return sum(e["arr"] for e in rec["seg"].values())


# --- display noise and the team view --------------------------------------
def noise(seed, team_no, series, day):
    """Deterministic value in [-1, 1] for one (seed, team, series, day)."""
    h = hashlib.sha256(("%s:%s:%s:%s" % (seed, team_no, series, day)).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2.0 ** 64 * 2.0 - 1.0


def _telemetry_point(cfg, seed, team_no, rec):
    day = rec["day"]
    wk = week_of(cfg, day)
    nz = cfg["NOISE"]
    err = (cfg["ERROR_RATE_BASE"] + cfg["ERROR_RATE_PER_UOD"] * rec["uod"]) \
        * (1 + nz["error_rate"] * noise(seed, team_no, "error", day))
    p99 = cfg["P99_BASE_MS"] + cfg["P99_PER_UOD_MS"] * rec["uod"]
    if rec["slow"]:
        p99 += cfg["P99_INCIDENT_MS"]
    if cfg["PEAK_START_WEEK"] <= wk <= cfg["PEAK_END_WEEK"]:
        p99 *= cfg["P99_PEAK_MULT"]
    p99 *= 1 + nz["p99"] * noise(seed, team_no, "p99", day)
    tickets = {}
    for s in cfg["SEGMENT_ORDER"]:
        t = cfg["TICKETS_BASELINE_PER_WEEK"][s] / cfg["DAYS_PER_WEEK"] \
            * (1 + cfg["TICKETS_TRUST_COEF"] * (cfg["TRUST_NEUTRAL"] - rec["trust"][s]))
        if s in rec["inc_segs"]:
            t *= 1 + cfg["TICKETS_INCIDENT_BUMP"]
        tickets[s] = t * (1 + nz["tickets"] * noise(seed, team_no, "tickets" + s, day))
    return dict(day=day, error_rate=err, p99_ms=p99, tickets=tickets)


def debrief_series(cfg, state):
    """One point a week for the debrief: hidden debt, the error rate the team saw, the CTO band, ARR.

    Only for use after the final reveal. The error rate is the same noisy figure the
    team's own dashboard showed.
    """
    series = []
    for week, rec in sorted(weekly_records(cfg, state).items()):
        point = _telemetry_point(cfg, state["seed"], state["team"], rec)
        series.append(dict(week=week, debt=rec["uod"], error_rate=point["error_rate"],
                           band=cto_band(cfg, rec["uod"]), arr=record_arr(rec)))
    return series


def team_view(cfg, state, series_days=None, include_slices=False):
    """Everything a team's browser may see, built field by field."""
    seed, team_no, day = state["seed"], state["team"], state["day"]
    week = week_of(cfg, day)
    quarter = quarter_of_week(cfg, week)
    recent = state["history"][-(series_days or cfg["TELEMETRY_WINDOW_DAYS"]):]
    nz = cfg["NOISE"]["funnel"]
    funnel = {}
    for s in cfg["SEGMENT_ORDER"]:
        series = []
        for rec in recent:
            e = rec["seg"][s]
            d = rec["day"]
            point = dict(day=d, arr=e["arr"], accounts=e["accounts"],
                         new=e["new"] * (1 + nz * noise(seed, team_no, "new" + s, d)),
                         lost=e["lost"] * (1 + nz * noise(seed, team_no, "lost" + s, d)),
                         rates={k: v * (1 + nz * noise(seed, team_no, k + s, d))
                                for k, v in e["rates"].items()})
            if include_slices and "slices" in e:
                point["slices"] = {
                    key: {k: v * (1 + nz * noise(seed, team_no, key + k + s, d))
                          for k, v in rates.items()}
                    for key, rates in e["slices"].items()}
            series.append(point)
        funnel[s] = series
    cards = []
    for c in cfg["CARDS"]:
        if c["unlock_q"] > quarter:
            continue
        queued = any(it["kind"] == "card" and it["card"] == c["id"] for it in state["queue"])
        if c.get("once_per_quarter"):
            used = any(cid == c["id"] and q == quarter for cid, q in state["p_used"])
            status = "queued" if queued else ("done_this_quarter" if used else "available")
        elif c["id"] in state["shipped"]:
            status = "shipped"
        elif queued:
            status = "queued"
        elif c["id"] == cfg["B1_CARD"]:
            status = "awarded" if state["b1_awarded"] else "apply"
        else:
            status = "available"
        cards.append(dict(id=c["id"], name=c["name"], cost=_card_cost(cfg, state, c),
                          seg=c["seg"], stage=c["stage"], pitch_arr=c["pitch"],
                          trust_effect=dict(c["trust"]), status=status,
                          bespoke=bool(c.get("bespoke"))))
    incidents = [dict(id=i["n"], symptom=cfg["INCIDENTS"][i["n"]]["symptom"],
                      metric=cfg["INCIDENTS"][i["n"]]["stage"],
                      options=list(cfg["INCIDENTS"][i["n"]]["causes"]),
                      since_day=i["opened_day"], patched=i["patched"])
                 for i in state["incidents"] if i["status"] == "open"]
    queue = [dict(id=it["id"], kind=it["kind"], label=it["label"], cost=it["cost"],
                  progress=it["progress"], seg=it.get("seg"), picked=it.get("picked"),
                  incident=it.get("incident"))
             for it in state["queue"]]
    return dict(
        team=team_no, day=day, week=week, quarter=quarter,
        tiles=dict(arr=score(cfg, state)["arr"],
                   trust={s: state["seg"][s]["trust"] for s in cfg["SEGMENT_ORDER"]},
                   capacity_bu_week=_weekly_capacity(cfg, state),
                   open_incidents=len(incidents)),
        quality=state["quality"], queue=queue, cards=cards, incidents=incidents,
        # True while a peak-season outage has seized build capacity. The amount
        # owed would reveal hidden debt, so only the fact is shown.
        outage=state["rework_owed"] > cfg["FLOAT_EPS"],
        reports=[dict(seg=r["seg"], day=r["day"], utility=dict(r["utility"]),
                      alerts=list(r["alerts"])) for r in state["reports"]],
        b1=dict(window_open=cfg["B1_APPLY_FIRST_WEEK"] <= week <= cfg["B1_APPLY_LAST_WEEK"],
                applied=state["b1_applied"], awarded=state["b1_awarded"]),
        releases=[dict(card=r["card"], day=r["day"],
                       name=cfg["CARD_BY_ID"][r["card"]]["name"])
                  for r in state["releases"]],
        funnel=funnel,
        telemetry=[_telemetry_point(cfg, seed, team_no, rec) for rec in recent],
    )
