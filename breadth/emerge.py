"""Since the bottom (Nov 7, 2026; Adam: "a tab dedicated to analyzing the themes that emerge starting from the beginning of the day 11/6 …
using the data we have, money flow, EMAs etc. This date may change, but I want to anchor to a bottom where themes and/or leaders begin to
emerge after the bottom. It's impossible to call a bottom so we'll likely change the date, but we have to start somewhere").

v3 Groups → "Since the bottom" (`renderEmerge` in v3_tabs.js). Python ships compact per-stock arrays; the PAGE does every calculation, so
the start date is a picker (any of the last PICK sessions; default `config.EMERGE_START`, the first session counted; the base is the
close before it) and live Google prices extend it during the session.

Per stock (theme / sub-theme members, ETFs out, $5+, $5M+/day 50-day average dollar volume):
  c    closes, last PICK + PRE sessions (PRE = 20 extra so the page can measure the drop INTO the start: 20-day closing high → base)
  dv   dollar volume ($M), last PICK sessions        b50  50-day average $ volume ($M) ending the session before, last PICK sessions
  e    EMA 9 / 21 / 50 on the close at the first of the last PICK sessions (seeds; the page steps them forward)
  hs   highest close over the 63 sessions before the closes array (seed for "new 3-month closing high")
Descriptive only: nothing here is backtested and nothing moves the picks (DECISIONS.md).
"""
import logging
import re

import numpy as np
import pandas as pd

from . import config

PICK, PRE = 25, 20
MIN_PRICE, MIN_DVOL = 5.0, 5e6
log = logging.getLogger("breadth")
ETF_RE = re.compile(r"\bETF\b|\bFund\b|\bTrust\b")


def _g(x, sig=4):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return float(f"{x:.{sig}g}") if np.isfinite(x) else None


def build(adjusted, theme_data, start=None):
    T = theme_data or {}
    names = {s["t"]: s for s in T.get("stocks") or []}
    ok = lambda t: bool((names.get(t) or {}).get("name")) and not ETF_RE.search(names[t]["name"]) and not names[t].get("deal")
    subs = {g["theme"]: [t for t in g.get("members") or [] if ok(t)] for g in T.get("subthemes") or []}
    thms = {g["theme"]: [t for t in g.get("members") or [] if ok(t)] for g in T.get("themes") or []}
    tick = sorted({t for m in list(subs.values()) + list(thms.values()) for t in m})
    bench = [config.BENCHMARK, "QQQ", "IWM"]
    sub = adjusted[adjusted["ticker"].isin(set(tick) | set(bench))]
    c = sub.pivot_table(index="date", columns="ticker", values="c").sort_index()
    v = sub.pivot_table(index="date", columns="ticker", values="v").reindex_like(c)
    n = len(c)
    if n < PICK + PRE + 63 + 2:
        return None
    dv = c * v / 1e6
    b50 = dv.rolling(50, min_periods=30).mean().shift(1)
    ema = {k: c.ewm(span=k, adjust=False, min_periods=k).mean() for k in (9, 21, 50)}
    k0 = n - PICK                      # first of the pickable sessions
    kc = k0 - PRE                      # first close shipped
    hs = c.iloc[kc - 63:kc].max()
    last = c.iloc[-1]
    liq = (last >= MIN_PRICE) & (b50.iloc[-1] >= MIN_DVOL / 1e6)
    rows = {}
    for t in tick:
        if t not in c.columns or not bool(liq.get(t, False)):
            continue
        cc = c[t].iloc[kc:].to_numpy()
        if not np.isfinite(cc).all():
            continue
        s = names.get(t) or {}
        rows[t] = {"c": [_g(x) for x in cc], "dv": [_g(x, 3) for x in dv[t].iloc[k0:]], "b50": [_g(x, 3) for x in b50[t].iloc[k0:]],
                   "e": [_g(ema[k][t].iat[k0 - 1]) for k in (9, 21, 50)], "hs": _g(hs.get(t)),
                   "rs": s.get("rsr"), "sub": s.get("sub") or "", "nm": (s.get("name") or "")[:40]}
    keep = lambda m: [t for t in m if t in rows]
    days = [d.strftime("%Y-%m-%d") for d in c.index[kc:]]
    st = start or config.EMERGE_START
    if st not in days[PRE:]:           # default start fell out of the window (or isn't a session): use the latest pickable one on/before it
        cand = [d for d in days[PRE + 1:] if d <= st]
        st = cand[-1] if cand else days[-1]
    return {"date": days[-1], "days": days, "pre": PRE, "start": st, "default_start": config.EMERGE_START,
            "bench": {b: [_g(x) for x in c[b].iloc[kc:]] for b in bench if b in c.columns},
            "subs": {g: keep(m) for g, m in subs.items() if len(keep(m)) >= 3},
            "themes": {g: keep(m) for g, m in thms.items() if len(keep(m)) >= 3},
            "parent": {g["theme"]: g.get("group") or "" for g in T.get("subthemes") or []},
            "rows": rows, "rules": {"min_price": MIN_PRICE, "min_dvol": MIN_DVOL}}
