"""Post-thrust board (Nov 23, 2026; Adam: "what can we build to track the cross between best sub-theme, where money is going and stocks that
are lined up best over the next few sessions" → v3 Stocks → Setups → "Post-thrust board"). Info only, layer `thrust_board`.

One ranked list: the sub-themes leading since the last major breadth thrust (or follow-through), crossed with money flow (rotation.flow
tier), Theme Strength and the lifecycle stage, and inside each of the top groups the RS 80+ liquid stocks that are buyable now.

Group score (0-100) = 40% percentile of the median member return vs SPY since the close BEFORE the thrust day ("lead")
                    + 20% percentile of the thrust-day median return ("tday")
                    + 20% money-flow tier (confirmed / new 1, steady .7, bouncing .5, fading .3, outflow / none 0)
                    + 20% Theme Strength / 100.
No thrust in the last 25 sessions → anchor = 10 sessions ago and the board says so (it is a post-thrust tool).

Stock states (last close; the page re-checks against live Google prices):
  zone     = low touched the 9 EMA (or within 0.5 ADR above the 21 EMA) and closed above the 21 EMA → buy over today's high, stop under
             today's low (capped at 1 ADR below the trigger)
  tight    = 3-session range ≤ 1.5 ADR, within 1 ADR of the 9 EMA → buy over the 3-day high, stop under the 3-day low (cap 1 ADR)
  extended = close more than 1.5 ADR above the 9 EMA → wait; level to watch = the 9 EMA
  watch    = anything else above the 21 EMA
Thresholds are rules of thumb from the Lined-up buys / Dip buys / KQ screens, NOT a backtested ranking yet (card R-2026-11-23-thrust-board).
Follow-through check: SPY and RSP still above the thrust-day close, and 4% up-movers ≥ down-movers on average since the thrust.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config, metrics

log = logging.getLogger(__name__)
TOP_GROUPS = 8
PER_GROUP = 5
MIN_RS, MIN_PRICE, MIN_DVOL = 80, 10.0, 20e6
FLOW_PTS = {"confirmed": 1.0, "new": 1.0, "steady": 0.7, "bouncing": 0.5, "fading": 0.3, "outflow": 0.0}
WINDOW = metrics.THRUST_WINDOW


def _f(x, n=4):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(x) else round(x, n)


def last_thrust(history, dates):
    """(index into dates of the thrust day, event) for the latest major thrust / follow-through within WINDOW sessions, else (None, None)."""
    try:
        ev = metrics.events(history)
    except Exception:
        return None, None
    idx = {pd.Timestamp(d): i for i, d in enumerate(dates)}
    best = (None, None)
    for e in ev:
        if e.get("kind") in ("thrust", "followthrough") and e.get("tier") == "major":
            i = idx.get(pd.Timestamp(e["date"]))
            if i is not None and len(dates) - 1 - i < WINDOW and (best[0] is None or i > best[0]):
                best = (i, e)
    return best


def stock_state(c, h, l, e9, e21, adr_pct):
    """State + plan for one stock from its last 3 sessions (arrays, oldest first). adr_pct is in % (e.g. 4.5)."""
    px, adr = c[-1], c[-1] * adr_pct / 100.0
    if not (np.isfinite(px) and adr > 0 and np.isfinite(e9) and np.isfinite(e21)):
        return None
    if px < e21:
        return None
    cap = lambda trig, stop: max(stop, trig - adr)
    if px > e9 + 1.5 * adr:
        return {"st": "extended", "trigger": None, "stop": None, "level": _f(e9, 2),
                "plan": f"Extended {((px - e9) / adr):.1f} ADR over the 9 EMA: wait for a pullback toward {e9:.2f}"}
    if l[-1] <= e9 * 1.003 or px <= e21 + 0.5 * adr:
        trig = h[-1] + 0.01
        return {"st": "zone", "trigger": _f(trig, 2), "stop": _f(cap(trig, l[-1] - 0.01), 2), "level": _f(e21, 2),
                "plan": "In the 9/21 EMAs: buy over today's high, stop under today's low (max 1 ADR)"}
    rng = max(h[-3:]) - min(l[-3:])
    if rng <= 1.5 * adr and px - e9 <= adr:
        trig = max(h[-3:]) + 0.01
        return {"st": "tight", "trigger": _f(trig, 2), "stop": _f(cap(trig, min(l[-3:]) - 0.01), 2), "level": _f(e9, 2),
                "plan": f"Tight 3-day range ({rng / adr:.1f} ADR): buy over the 3-day high, stop under the 3-day low (max 1 ADR)"}
    return {"st": "watch", "trigger": None, "stop": None, "level": _f(e9, 2), "plan": "Above the 21 EMA but not set up yet"}


def build(adjusted, theme_data, history):
    T = theme_data or {}
    stocks = {s["t"]: s for s in T.get("stocks") or []}
    subs = {g["theme"]: [t for t in g.get("members") or [] if t in stocks and stocks[t].get("is_stock", True) is not False]
            for g in T.get("subthemes") or []}
    flow = {r["g"]: r for r in ((T.get("rotation") or {}).get("flow") or {}).get("rows") or []}
    life = {r["g"]: r for r in (T.get("lifecycle") or {}).get("rows") or []}
    tick = sorted({t for m in subs.values() for t in m})
    bench = [config.BENCHMARK, "RSP", "QQQ", "IWM"]
    sub = adjusted[adjusted["ticker"].isin(set(tick) | set(bench))]
    piv = lambda k: sub.pivot_table(index="date", columns="ticker", values=k).sort_index()
    c = piv("c")
    if len(c) < 60 or config.BENCHMARK not in c.columns:
        return None
    h, l, v = piv("h").reindex_like(c), piv("l").reindex_like(c), piv("v").reindex_like(c)
    dates = list(c.index)
    n = len(dates)
    ti, ev = last_thrust(history, dates)
    thrust = ti is not None
    tday = ti if thrust else n - 10
    a = max(tday - 1, 0)                                  # anchor = close before the thrust day
    since = c.iloc[-1] / c.iloc[a] - 1
    spy_since = since.get(config.BENCHMARK, np.nan)
    tret = c.iloc[tday] / c.iloc[tday - 1] - 1 if tday >= 1 else since * np.nan
    dv50 = (c * v).rolling(50, min_periods=30).mean().iloc[-1]
    e9 = c.ewm(span=9, adjust=False, min_periods=9).mean().iloc[-1]
    e21 = c.ewm(span=21, adjust=False, min_periods=21).mean().iloc[-1]

    groups = []
    for g, mem in subs.items():
        m = [t for t in mem if t in c.columns and np.isfinite(since.get(t, np.nan)) and (dv50.get(t, 0) or 0) >= 5e6]
        if len(m) < 3:
            continue
        rs = since[m]
        fr, lr = flow.get(g) or {}, life.get(g) or {}
        tier = fr.get("tier") or lr.get("tier")
        groups.append({"g": g, "sector": fr.get("sector") or lr.get("sector"), "n": len(m),
                       "lead": _f(rs.median() - spy_since), "tday": _f(tret[m].median()), "up": _f((rs > 0).mean(), 3),
                       "tier": tier, "flow": FLOW_PTS.get(tier or "", 0.0), "strength": _f(fr.get("strength") or lr.get("strength"), 1),
                       "stage": lr.get("stage"), "buy": bool(lr.get("buy")), "members": m})
    if not groups:
        return None
    G = pd.DataFrame(groups)
    pr = lambda s: s.rank(pct=True).fillna(0)
    G["score"] = (100 * (0.4 * pr(G["lead"]) + 0.2 * pr(G["tday"]) + 0.2 * G["flow"] + 0.2 * G["strength"].fillna(50) / 100)).round(1)
    G = G.sort_values("score", ascending=False).reset_index(drop=True)
    G["rank"] = G.index + 1

    order = {"zone": 0, "tight": 1, "extended": 2, "watch": 3}
    out = []
    for _, r in G.head(TOP_GROUPS).iterrows():
        rows = []
        for t in r["members"]:
            s = stocks[t]
            if (s.get("rsr") or 0) < MIN_RS or (s.get("price") or 0) < MIN_PRICE or (dv50.get(t, 0) or 0) < MIN_DVOL:
                continue
            st = stock_state(c[t].to_numpy()[-3:], h[t].to_numpy()[-3:], l[t].to_numpy()[-3:], e9.get(t), e21.get(t), s.get("adr") or 0)
            if not st:
                continue
            rows.append({"t": t, "rs": s.get("rsr"), "price": _f(c[t].iloc[-1], 2), "adr": s.get("adr"), "since": _f(since[t]),
                         "tday": _f(tret.get(t)), "off_hi": s.get("off_hi"), "dvol": _f(dv50[t] / 1e6, 1), **st})
        rows.sort(key=lambda x: (order[x["st"]], -(x["rs"] or 0)))
        d = {k: r[k] for k in ("rank", "g", "sector", "n", "lead", "tday", "up", "tier", "strength", "stage", "buy", "score")}
        d["strength"] = _f(d["strength"], 1)
        d["stage"] = d["stage"] if isinstance(d["stage"], str) else None
        d["sector"] = d["sector"] if isinstance(d["sector"], str) else None
        d["tier"] = d["tier"] if isinstance(d["tier"], str) else None
        d["rank"], d["n"], d["buy"] = int(d["rank"]), int(d["n"]), bool(d["buy"])
        d["stocks"] = rows[:PER_GROUP]
        d["more"] = max(0, len(rows) - PER_GROUP)
        out.append(d)

    ft = None
    if thrust:
        hist = history.set_index(pd.to_datetime(history["date"])) if "date" in history.columns else history
        hs = hist[pd.to_datetime(hist.index) >= dates[tday]]
        rsp_ok = "RSP" in c.columns and c["RSP"].iloc[-1] >= c["RSP"].iloc[tday]
        spy_ok = c[config.BENCHMARK].iloc[-1] >= c[config.BENCHMARK].iloc[tday]
        net = float((hs["up4"] - hs["dn4"]).mean()) if len(hs) and "up4" in hs else 0.0
        ok = sum([bool(spy_ok), bool(rsp_ok), net >= 0])
        ft = {"spy_ok": bool(spy_ok), "rsp_ok": bool(rsp_ok), "net4": round(net, 1),
              "verdict": "holding" if ok == 3 else ("wobbling" if ok == 2 else "fading")}
    return {"date": str(dates[-1].date()), "thrust": thrust,
            "thrust_date": str(dates[tday].date()), "anchor": str(dates[a].date()), "day": n - tday,
            "label": (ev or {}).get("label"), "detail": (ev or {}).get("detail"), "window": WINDOW,
            "spy_since": _f(spy_since), "rsp_since": _f(since.get("RSP")), "ft": ft,
            "groups": out, "n_groups": int(len(G))}
