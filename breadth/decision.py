"""Decision Cards: every layer behind each trade idea in one place, and a daily log of all of them.

See DECISIONS.md. Layers 1-3 (market, group, setup) are the dashboard's existing, backtested measures. Layer 4 (macro
fit) is computed here from `macrofit`. Layers 5-7 (calendar, catalyst, macro brief) come from the agent files in
docs/agent/ (written by Claude scheduled tasks through .github/workflows/agent.yml); missing or stale files simply show
"not checked". Nothing here changes the ranking of the Top 2 picks: the cards only add information, and every layer's
value goes to data/decision_log.csv so the weekly Reviewer can test, from real forward results, which layers help.
"""
import json
import logging
from datetime import date as _date

import numpy as np
import pandas as pd

from . import config

log = logging.getLogger(__name__)
MAX_CARDS = 25
HOLD = 5                         # sessions, same as the pick scoreboard
STALE_DAYS = 4                   # agent file older than this vs the card date -> treated as missing

SETUP_NAMES = {"ath": "ATH Magnet", "pullback": "Leader Pullback", "rotation": "Rotation Rookie", "kq": "Qullamaggie Flag",
               "vcp": "Minervini VCP", "round": "Round Number Magnet"}
LOG_COLS = ["date", "t", "role", "setup", "state", "regime", "setup_verdict", "setup_avg_r", "rsr", "sub", "grp_str",
            "flow_tier", "ignited", "tail5", "tail20", "macro_words", "earn_date", "earn_days", "event_risk",
            "catalyst", "cat_dir", "cat_quality", "red_flags", "brief_risk", "support", "warn",
            "entry", "exit", "fwd5", "spy5", "status"]


# ----------------------------------------------------------------- helpers
def _f(v):
    try:
        v = float(v)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def load_agent(name, card_date=None, max_age=None):
    """docs/agent/<name>.json, or {} when missing, unreadable or stale (written for an older card date).
    Catalysts are ticker-specific, so they must be for this exact card date; the macro brief may be a few days old."""
    p = config.DOCS_DIR / "agent" / f"{name}.json"
    if not p.exists():
        return {}
    try:
        js = json.loads(p.read_text())
    except Exception:
        return {}
    if card_date and js.get("for_date"):
        try:
            age = (pd.Timestamp(card_date) - pd.Timestamp(js["for_date"])).days
        except Exception:
            age = 0
        if age > (STALE_DAYS if max_age is None else max_age) or age < 0:
            return {}
    return js


def load_evidence():
    try:
        return json.loads((config.DATA_DIR / "layer_evidence.json").read_text())
    except Exception:
        return {}


def sessions_until(day_from, day_to):
    """Weekday sessions after day_from up to and including day_to (0 = same day; negative = already past).
    Holidays are ignored, so it can be off by one around them."""
    a = pd.Timestamp(day_from).normalize().date()
    b = pd.Timestamp(day_to).normalize().date()
    one = pd.Timedelta(days=1)
    if b >= a:                                   # sessions in (a, b]
        return int(np.busday_count(a + one, b + one))
    return -int(np.busday_count(b + one, a + one))


# ----------------------------------------------------------------- candidates
def candidates(theme_data):
    """Top 2 picks, then the not-yet-actionable watch names, then today's other candidates (max MAX_CARDS)."""
    pb = theme_data.get("playbook") or {}
    out, seen = [], set()

    def add(t, role):
        if t and t not in seen:
            seen.add(t)
            out.append((t, role))
    for k, p in enumerate(pb.get("picks") or []):
        add(p.get("t"), f"pick{k + 1}")
    for w in pb.get("pick_watch") or []:
        add(w.get("t"), "watch")
    for t in pb.get("pick_cands") or []:
        add(t if isinstance(t, str) else t.get("t"), "cand")
    return out[:MAX_CARDS]


# ----------------------------------------------------------------- one card
def card(t, role, theme_data, history, mfit, cat, brief, regime_label, card_date):
    T = theme_data
    pb = T.get("playbook") or {}
    ts_rows = ((T.get("trade_setups") or {}).get("rows") or {})
    srow = ts_rows.get(t) or {}
    stock = next((s for s in T.get("stocks") or [] if s.get("t") == t), {})
    pick = next((p for p in pb.get("picks") or [] if p.get("t") == t), None) or \
        next((p for p in pb.get("pick_watch") or [] if p.get("t") == t), None) or {}
    verdicts = {r["key"]: r for r in pb.get("rows") or []}
    setups = srow.get("setups") or ([pick["setup"]] if pick.get("setup") else [])
    main = pick.get("setup") or (sorted(setups, key=lambda k: -(verdicts.get(k, {}).get("avg_r") or -9))[0] if setups else None)
    vrow = verdicts.get(main, {})
    sub = srow.get("sub") or stock.get("sub") or pick.get("sub")
    flow = (T.get("rotation") or {}).get("flow") or {}
    g = (flow.get("stock_group") or {}).get(t) or sub
    tier = next((r.get("tier") for r in flow.get("rows") or [] if r.get("g") == g), None)
    ign = next((r.get("status") for r in ((T.get("rotation") or {}).get("ignition") or {}).get("rows") or [] if r.get("g") == g), None)
    rsr = _f(srow.get("rsr") or stock.get("rsr") or pick.get("rsr"))
    grp = _f(srow.get("sub_str") or srow.get("grp"))

    layers, support, warn = [], 0, 0

    def add(key, name, state, text, proven=True):
        nonlocal support, warn
        if state == "good":
            support += 1
        elif state == "bad":
            warn += 1
        layers.append({"k": key, "name": name, "state": state, "text": text, "proven": proven})

    # 1 market
    st = pb.get("label") or pb.get("state") or "–"
    add("market", "Market", "good" if vrow.get("verdict") == "Focus" else "bad" if vrow.get("verdict") == "Avoid" else "neutral",
        f"{st} · regime {regime_label or '–'} · {vrow.get('name', main or 'setup')} is {vrow.get('verdict', 'unrated')} here"
        + (f" ({vrow['avg_r']:+.2f}R a trade, n {vrow.get('n')})" if vrow.get("avg_r") is not None else ""))
    # 2 group
    gtxt = f"{sub or 'no sub-theme'}" + (f" · Strength {grp:.0f}" if grp is not None else "")
    if tier:
        gtxt += f" · money flow: {tier}"
    if ign:
        gtxt += f" · {ign}"
    if (grp is not None and grp < 40) or tier == "outflow":
        gstate = "bad"
    elif tier in ("fading", "bouncing"):
        gstate = "neutral"
    elif (grp or 0) >= 80 or tier in ("confirmed", "steady") or ign == "ignition":
        gstate = "good"
    else:
        gstate = "neutral"
    add("group", "Group", gstate, gtxt)
    # 3 setup
    stxt = ", ".join(SETUP_NAMES.get(k, k) for k in setups) if setups else "no setup today"
    stxt += f" · RS {rsr:.0f}" if rsr is not None else ""
    if _f(srow.get("off_hi")) is not None:
        stxt += f" · {srow['off_hi'] * 100:+.1f}% vs 52-wk high"
    if _f(srow.get("adr")) is not None:
        stxt += f" · ADR {srow['adr']:.1f}%"
    add("setup", "Setup", "good" if (rsr or 0) >= 90 and setups else "bad" if (rsr or 0) < 70 else "neutral", stxt)
    # 4 macro fit (information only until proven)
    m = (mfit.get("stocks") or {}).get(t)
    ev = (load_evidence().get("macro_fit") or {})
    proven = bool(ev.get("passed"))
    if m:
        tw = m.get("tail5")
        mtxt = ("; ".join(m["words"]) if m["words"] else "no clear link to rates, oil or the dollar")
        if tw:
            mtxt += f" · last 5 days of macro moves {'help' if tw > 0 else 'hurt'} it by about {abs(tw):.1f}%"
        add("macro", "Macro fit", ("good" if (tw or 0) > 0.25 else "bad" if (tw or 0) < -0.25 else "neutral") if proven else "info",
            mtxt, proven=proven)
    else:
        add("macro", "Macro fit", "info", "not enough history", proven=proven)
    # 5 calendar: earnings (Catalyst agent) + market events (Macro agent)
    c = (cat.get("stocks") or {}).get(t) or {}
    ed, edays = c.get("earnings_date"), None
    if ed:
        try:
            edays = sessions_until(card_date, ed)
        except Exception:
            ed = None
    ev_risk = None
    for e in brief.get("events") or []:
        try:
            dd = sessions_until(card_date, e.get("date"))
        except Exception:
            continue
        if 1 <= dd <= HOLD and str(e.get("impact", "")).lower() == "high":
            ev_risk = f"{e.get('name')} {e.get('date')}"
            break
    if not cat and not brief:
        add("calendar", "Calendar", "unknown", "not checked yet (agents run ~7 AM ET)", proven=False)
    else:
        parts = []
        if ed and edays is not None:
            parts.append(f"earnings {ed} ({'in ' + str(edays) + ' sessions' if edays >= 0 else 'reported'})")
        elif cat:
            parts.append("no earnings found in the next weeks" if c else "earnings not checked")
        if ev_risk:
            parts.append(f"market event inside the hold: {ev_risk}")
        bad = edays is not None and 0 <= edays <= HOLD
        add("calendar", "Calendar", "bad" if bad else "neutral" if ev_risk else "good" if c else "unknown",
            " · ".join(parts) or "no events", proven=False)
    # 6 catalyst
    if c:
        q = c.get("quality") or "unknown"
        txt = f"{c.get('why') or 'no clear catalyst found'}"
        if c.get("red_flags"):
            txt += " · ⚠ " + "; ".join(c["red_flags"][:2])
        add("catalyst", "Catalyst", "bad" if c.get("red_flags") or c.get("direction") == "negative" else
            "good" if q in ("strong", "real") and c.get("direction") == "positive" else "neutral", txt, proven=False)
    else:
        add("catalyst", "Catalyst", "unknown", "not checked yet", proven=False)
    # 7 macro brief (market-wide)
    if brief:
        r = str(brief.get("risk", "")).lower()
        add("brief", "Macro brief", "bad" if r == "high" else "good" if r == "low" else "neutral",
            brief.get("headline") or "–", proven=False)
    else:
        add("brief", "Macro brief", "unknown", "not checked yet", proven=False)

    return {"t": t, "role": role, "name": srow.get("name") or stock.get("name") or pick.get("name"),
            "price": _f(srow.get("price") or stock.get("price") or pick.get("price")),
            "setup": main, "setup_name": vrow.get("name"), "plan": pick.get("plan"), "layers": layers,
            "support": support, "warn": warn,
            "_log": {"date": card_date, "t": t, "role": role, "setup": main, "state": pb.get("state"), "regime": regime_label,
                     "setup_verdict": vrow.get("verdict"), "setup_avg_r": vrow.get("avg_r"), "rsr": rsr, "sub": sub,
                     "grp_str": grp, "flow_tier": tier, "ignited": ign, "tail5": (m or {}).get("tail5"),
                     "tail20": (m or {}).get("tail20"), "macro_words": "; ".join((m or {}).get("words") or []),
                     "earn_date": ed, "earn_days": edays, "event_risk": ev_risk, "catalyst": c.get("why"),
                     "cat_dir": c.get("direction"), "cat_quality": c.get("quality"),
                     "red_flags": "; ".join(c.get("red_flags") or []), "brief_risk": brief.get("risk"),
                     "support": support, "warn": warn}}


# ----------------------------------------------------------------- build + log
def build(theme_data, history, mfit, regime_label=None):
    """Cards for today's candidates. Never raises (returns None on failure)."""
    try:
        day = theme_data.get("date")
        cat = load_agent("catalysts", day, max_age=0)
        brief = load_agent("macro_brief", day, max_age=STALE_DAYS)
        cards = [card(t, role, theme_data, history, mfit or {}, cat, brief, regime_label, day)
                 for t, role in candidates(theme_data)]
        ev = load_evidence()
        return {"date": day, "cards": cards, "macro": (mfit or {}).get("ctx"), "evidence": ev,
                "agents": {"catalysts": cat.get("for_date"), "macro_brief": brief.get("for_date"),
                           "brief": {k: brief.get(k) for k in ("headline", "risk", "rates", "oil", "fed", "geo", "events", "sources")} if brief else None}}
    except Exception as e:
        log.exception("decision cards failed: %s", e)
        return None


def _path():
    return config.DATA_DIR / "decision_log.csv"


def load_log():
    p = _path()
    if not p.exists():
        return pd.DataFrame(columns=LOG_COLS)
    df = pd.read_csv(p, dtype={"date": str, "t": str})
    for c in LOG_COLS:
        if c not in df.columns:
            df[c] = np.nan
    return df[LOG_COLS]


def record(dec):
    """Replace today's rows in data/decision_log.csv with the current cards (keeps outcome columns of settled rows)."""
    if not dec or not dec.get("cards"):
        return
    df = load_log()
    day = dec["date"]
    rows = []
    for cd in dec["cards"]:
        r = dict(cd["_log"])
        r.update({"entry": None, "exit": None, "fwd5": None, "spy5": None, "status": "pending"})
        rows.append(r)
    new = pd.DataFrame(rows, columns=LOG_COLS)
    df = pd.concat([df[df["date"] != day], new], ignore_index=True)
    df.sort_values(["date", "role", "t"]).to_csv(_path(), index=False)


def settle(adjusted, bench="SPY"):
    """Fill outcomes: buy the next session's open, exit at the close HOLD sessions after entry; SPY the same way."""
    df = load_log()
    if df.empty:
        return df
    o = adjusted.pivot_table(index="date", columns="ticker", values="o").sort_index()
    c = adjusted.pivot_table(index="date", columns="ticker", values="c").sort_index()
    dates = c.index
    for i in df.index[df["status"].astype(str) != "closed"]:
        d, t = pd.Timestamp(df.at[i, "date"]), df.at[i, "t"]
        k = dates.searchsorted(d, side="right")           # next session after the card date
        if k + HOLD - 1 >= len(dates) or t not in c.columns:
            continue
        e, x = o[t].iloc[k], c[t].iloc[k + HOLD - 1]
        if not (np.isfinite(e) and np.isfinite(x)) or e <= 0:
            df.at[i, "status"] = "no data"
            continue
        se, sx = o[bench].iloc[k], c[bench].iloc[k + HOLD - 1]
        df.at[i, "entry"], df.at[i, "exit"] = round(float(e), 4), round(float(x), 4)
        df.at[i, "fwd5"] = round(float(x / e - 1), 5)
        df.at[i, "spy5"] = round(float(sx / se - 1), 5) if se > 0 else np.nan
        df.at[i, "status"] = "closed"
    df.to_csv(_path(), index=False)
    return df


def strip_private(dec):
    """Payload copy without the per-card log dicts."""
    if not dec:
        return dec
    return {**dec, "cards": [{k: v for k, v in c.items() if k != "_log"} for c in dec["cards"]]}
