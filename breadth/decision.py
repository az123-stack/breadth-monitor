"""Decision Cards: every layer behind each trade idea in one place, and a daily log of all of them.

See DECISIONS.md. Layers 1-3 (market, group, setup) are the dashboard's existing, backtested measures. Layer 4 (macro
fit) is computed here from `macrofit`. Layers 5-7 (calendar, catalyst, macro brief) come from the agent files in
docs/agent/ (written by Claude scheduled tasks through .github/workflows/agent.yml); missing or stale files simply show
"not checked". Nothing here changes the ranking of the Top 2 picks: the cards only add information, and every layer's
value goes to data/decision_log.csv so the weekly Reviewer can test, from real forward results, which layers help.
"""
import json
import logging
from datetime import date as _date, datetime, timezone

import numpy as np
import pandas as pd

from . import config, nyse

log = logging.getLogger(__name__)
MAX_CARDS = 25
HOLD = 5                         # sessions, same as the pick scoreboard
EXIT_SESSIONS = HOLD + 1         # an idea carded on day D is held from the open of D+1 to the close of D+1+HOLD
STALE_DAYS = 4                   # agent file older than this vs the card date -> treated as missing

SETUP_NAMES = {"ath": "ATH Magnet", "pullback": "Leader Pullback", "rotation": "Rotation Rookie", "kq": "Qullamaggie Flag",
               "vcp": "Minervini VCP", "round": "Round Number Magnet", "box": "Box Retest", "spring": "Box Spring"}
LOG_COLS = ["date", "t", "role", "setup", "state", "regime", "setup_verdict", "setup_avg_r", "rsr", "sub", "grp_str",
            "flow_tier", "ignited", "tail5", "tail20", "macro_words", "earn_date", "earn_days", "event_risk",
            "catalyst", "cat_depth", "cat_dir", "cat_quality", "red_flags", "brief_risk", "support", "warn",
            "entry", "exit", "fwd5", "spy5", "status"]


# ----------------------------------------------------------------- helpers
def _f(v):
    try:
        v = float(v)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    return [x for x in v if isinstance(x, (str, dict))] if isinstance(v, list) else []


def _clean_agent(name, js):
    """Coerce an agent file to the shapes the cards expect; anything unusable becomes empty."""
    if not isinstance(js, dict):
        return {}
    if name == "catalysts":
        st = js.get("stocks")
        st = {str(t).upper(): c for t, c in st.items() if isinstance(c, dict)} if isinstance(st, dict) else {}
        for c in st.values():
            c["red_flags"] = [str(x) for x in _as_list(c.get("red_flags")) if isinstance(x, str)]
            c["sources"] = [str(x) for x in _as_list(c.get("sources")) if isinstance(x, str)]
            if not (isinstance(c.get("earnings_date"), str) and _valid_date(c["earnings_date"])):
                c["earnings_date"] = None
        js["stocks"] = st
    if name == "catalysts":
        for c in js["stocks"].values():
            for k in ("why", "direction", "quality", "depth"):
                c[k] = _txt(c.get(k))
    if name == "macro_brief":
        js["events"] = [{k: _txt(e.get(k)) for k in ("date", "time", "name", "impact")}
                        for e in _as_list(js.get("events")) if isinstance(e, dict) and _valid_date(e.get("date"))]
        js["sources"] = [str(x) for x in _as_list(js.get("sources")) if isinstance(x, str)]
        for k in ("headline", "risk", "rates", "fed", "oil", "geo"):
            js[k] = _txt(js.get(k))
        if (js.get("risk") or "").lower() not in ("low", "medium", "high"):
            return {}                                   # no usable risk level = no brief
    if name == "plan":
        js["summary"] = _txt(js.get("summary"))
        if not js["summary"]:
            return {}
        js["items"] = [{k: (_txt(v) if k not in ("cards", "priority") else v) for k, v in it.items()}
                       for it in _as_list(js.get("items")) if isinstance(it, dict)]
        for k in ("new_agents", "retire", "registry_updates", "card_updates"):
            js[k] = [{kk: _txt(vv) for kk, vv in a.items()} for a in _as_list(js.get(k)) if isinstance(a, dict)]
        for it in js["items"]:
            it["cards"] = [c for c in _as_list(it.get("cards")) if isinstance(c, str)]
            it["priority"] = it.get("priority") if isinstance(it.get("priority"), int) else None
    if name == "review":
        for k in ("findings", "proposals"):
            js[k] = [str(x) for x in _as_list(js.get(k)) if isinstance(x, str)]
        js["summary"] = _txt(js.get("summary"))
        if not js["summary"]:
            return {}
    return js


def _txt(v):
    """Text the page can safely call string methods on: strings stay, anything else becomes None."""
    return v if isinstance(v, str) else None


def _valid_date(s):
    try:
        _date.fromisoformat(str(s))
        return True
    except (TypeError, ValueError):
        return False


def load_agent(name, card_date=None, max_age=None):
    """docs/agent/<name>.json, or {} when missing, unreadable, malformed or stale (written for another card date).
    Catalysts are ticker-specific, so they must be for this exact card date; the macro brief may be a few days old.
    A missing or impossible for_date counts as stale."""
    p = config.DOCS_DIR / "agent" / f"{name}.json"
    if not p.exists():
        return {}
    try:
        js = json.loads(p.read_text())
    except Exception:
        return {}
    if not isinstance(js, dict) or not _valid_date(js.get("for_date")):
        return {}
    if card_date:
        age = (pd.Timestamp(card_date) - pd.Timestamp(js["for_date"])).days
        weekly = name in ("review", "plan")             # written on weekends, after the last card date: fine
        if age > (STALE_DAYS if max_age is None else max_age) or (age < 0 and not weekly):
            return {}
    return _clean_agent(name, js)


def load_evidence():
    """data/layer_evidence.json with only well-formed sections kept (a bad file never costs the cards)."""
    try:
        ev = json.loads((config.DATA_DIR / "layer_evidence.json").read_text())
    except Exception:
        return {}
    if not isinstance(ev, dict):
        return {}
    out = {}
    m = ev.get("macro_fit")
    if isinstance(m, dict) and isinstance(m.get("tail5"), dict) and isinstance(m.get("signals"), int):
        out["macro_fit"] = m
    if isinstance(ev.get("log"), dict):
        out["log"] = ev["log"]
    return out


def sessions_until(day_from, day_to):
    """Trading sessions after day_from up to and including day_to (0 = same day; negative = already past).
    Uses config.MARKET_HOLIDAYS (NYSE closures)."""
    a = pd.Timestamp(day_from).normalize().date()
    b = pd.Timestamp(day_to).normalize().date()
    one = pd.Timedelta(days=1)
    hol = config.MARKET_HOLIDAYS
    if b >= a:                                   # sessions in (a, b]
        return int(np.busday_count(a + one, b + one, holidays=hol))
    return -int(np.busday_count(b + one, a + one, holidays=hol))


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
    passed = bool(ev.get("passed"))
    proven = passed and "macro_fit" in getattr(config, "APPROVED_LAYERS", ())
    if m:
        tw = m.get("tail5")
        mtxt = ("; ".join(m["words"]) if m["words"] else "no clear link to rates, oil or the dollar")
        if tw:
            mtxt += f" · last 5 days of macro moves {'help' if tw > 0 else 'hurt'} it by about {abs(tw):.1f}%"
        if passed and not proven:
            mtxt += " · backtest passed, waiting for your approval"
        add("macro", "Macro fit", ("good" if (tw or 0) > 0.25 else "bad" if (tw or 0) < -0.25 else "neutral") if proven else "info",
            mtxt, proven=proven)
    else:
        add("macro", "Macro fit", "info", "macro data unavailable or not enough history", proven=proven)
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
        if 1 <= dd <= EXIT_SESSIONS and str(e.get("impact", "")).lower() == "high":
            ev_risk = f"{e.get('name')} {e.get('date')}"
            break
    if not cat and not brief:
        add("calendar", "Calendar", "unknown", "not checked yet (agents run ~7 AM ET)", proven=False)
    else:
        parts = []
        if ed and edays is not None:
            parts.append(f"earnings {ed} ({'in ' + str(edays) + ' sessions' if edays >= 0 else 'reported'})")
        elif cat:
            parts.append("next earnings date not confirmed" if c else "earnings not checked")
        if ev_risk:
            parts.append(f"market event inside the hold: {ev_risk}")
        bad = edays is not None and 0 <= edays <= EXIT_SESSIONS   # through the exit day
        clear = edays is not None and not bad            # a confirmed earnings date outside the hold
        add("calendar", "Calendar", "bad" if bad else "neutral" if ev_risk else "good" if clear else "unknown",
            " · ".join(parts) or "no events", proven=False)
    # 6 catalyst: positive real/strong news supports; negative news warns; red flags show and soften a "support"
    if c:
        q = c.get("quality") or "unknown"
        txt = f"{c.get('why') or 'no clear catalyst found'}"
        if c.get("red_flags"):
            txt += " · ⚠ " + "; ".join(c["red_flags"][:2])
        if c.get("direction") == "negative":
            cstate = "bad"
        elif c.get("direction") == "positive" and q in ("strong", "real"):
            cstate = "neutral" if c.get("red_flags") else "good"
        else:
            cstate = "neutral"
        add("catalyst", "Catalyst", cstate, txt, proven=False)
        layers[-1]["links"] = (c.get("sources") or [])[:3]
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
                     "cat_depth": (c.get("depth") or ("earnings_only" if str(c.get("why") or "").lower().startswith("earnings date check only") else "full")) if c else None,
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
        cards = []
        for t, role in candidates(theme_data):
            try:                 # one bad input never costs the other cards
                cards.append(card(t, role, theme_data, history, mfit or {}, cat, brief, regime_label, day))
            except Exception as e:
                log.warning("decision card %s failed: %s", t, e)
        ev = load_evidence()
        review = load_agent("review", day, max_age=10)
        plan = load_agent("plan", day, max_age=10)
        return {"plan": plan or None,
                "review": {k: review.get(k) for k in ("for_date", "summary", "findings", "proposals")} if review else None,"date": day, "cards": cards, "macro": (mfit or {}).get("ctx"), "evidence": ev,
                "written": {"catalysts": cat.get("written"), "macro_brief": brief.get("written")},
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
    try:
        df = pd.read_csv(p, dtype={"date": str, "t": str})
    except Exception as e:                       # corrupt / empty file: keep a copy, start a fresh log
        log.error("decision log unreadable (%s); moved to %s", e, p.name + ".bad")
        p.replace(p.with_name(p.name + ".bad"))
        return pd.DataFrame(columns=LOG_COLS)
    for c in LOG_COLS:
        if c not in df.columns:
            df[c] = np.nan
    return df[LOG_COLS]


AGENT_COLS = {"catalysts": ["catalyst", "cat_depth", "cat_dir", "cat_quality", "red_flags", "earn_date", "earn_days"],
              "macro_brief": ["brief_risk", "event_risk"]}
AGENT_LAYERS = {"catalysts": ("calendar", "catalyst"), "macro_brief": ("brief",)}


def _utc(s):
    """'2026-10-17T02:17Z' -> aware datetime, or None."""
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def record(dec, now=None):
    """Write today's cards to data/decision_log.csv without letting anything learned after the entry leak in.

    An idea carded on day D is bought at 9:30 AM ET on the next session (the entry cutoff). Rules:
      * before the cutoff, today's rows are (re)written with the current cards;
      * after the cutoff, rows already logged for D are frozen (a later rebuild can't change them);
      * if D is first logged after the cutoff (late update), or an agent file was written after the cutoff, that
        agent's columns are left blank and its layers are not counted in support / warnings.
    """
    if not dec or not dec.get("cards"):
        return
    now = now or datetime.now(timezone.utc)
    day = dec["date"]
    cutoff = nyse.entry_cutoff(day)
    df = load_log()
    if now >= cutoff and (df["date"] == day).any():
        return                                                     # frozen
    late = {k for k in AGENT_COLS
            if now >= cutoff or ((w := _utc((dec.get("written") or {}).get(k))) is not None and w >= cutoff)}
    skip = {lk for k in late for lk in AGENT_LAYERS[k]}
    rows = []
    for cd in dec["cards"]:
        r = dict(cd["_log"])
        for k in late:
            for col in AGENT_COLS[k]:
                r[col] = None
        if skip:
            kept = [l for l in cd["layers"] if l["k"] not in skip]
            r["support"] = sum(l["state"] == "good" for l in kept)
            r["warn"] = sum(l["state"] == "bad" for l in kept)
        r.update({"entry": None, "exit": None, "fwd5": None, "spy5": None, "status": "pending"})
        rows.append(r)
    new = pd.DataFrame(rows, columns=LOG_COLS)
    df = pd.concat([df[df["date"] != day], new], ignore_index=True)
    df.sort_values(["date", "role", "t"]).to_csv(_path(), index=False)


def settle(adjusted, bench="SPY"):
    """Fill outcomes: buy the next session's open, exit at the close HOLD sessions after the entry day (same as the
    pick ledger and the Trade Setups backtest); SPY the same way."""
    df = load_log()
    if df.empty:
        return df
    o = adjusted.pivot_table(index="date", columns="ticker", values="o").sort_index()
    c = adjusted.pivot_table(index="date", columns="ticker", values="c").sort_index()
    dates = c.index
    for i in df.index[df["status"].astype(str) != "closed"]:
        d, t = pd.Timestamp(df.at[i, "date"]), df.at[i, "t"]
        k = dates.searchsorted(d, side="right")           # next session after the card date
        if k + HOLD >= len(dates) or t not in c.columns:
            continue
        e, x = o[t].iloc[k], c[t].iloc[k + HOLD]
        if not (np.isfinite(e) and np.isfinite(x)) or e <= 0:
            df.at[i, "status"] = "no data"
            continue
        se, sx = o[bench].iloc[k], c[bench].iloc[k + HOLD]
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
