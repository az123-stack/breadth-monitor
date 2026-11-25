"""Fresh RS fire -> 21 EMA (Nov 24, 2026; Adam: "when the x-timeframe RS fires one or a couple times and then pulls back to the EMAs,
buy the touch or the undercut and rally" → "add this to the setups"). v3 Stocks → Setups → "Fresh RS → 21 EMA". Info only, layer `rs_fire`.

Evidence: card R-2026-11-24-rs-fire-pullback (tools/rs_fire_pullback/study.py, Feb 2025 - Nov 2026). Only in leading groups:
  touch the 21 EMA after 1-3 fires  +0.24R / 5 sessions (t 3.3, n 452, both halves +0.20)
  undercut 0.3 ADR + reclaim, 1-3 fires  +0.47R (n 85, t 1.7: promising, not proven); after 4+ fires -0.07R, no fire -0.08R
By market state (state at the prior close, same rule as Today's playbook) - see STATS.

Rules (production version):
  universe  $10+, $20M+/day (50-day), not an ETF; sub-theme in the top 30% by 60-day median member return ("leading group")
  fire      RS line (close / SPY) at a new 20- or 63-session high; 1-3 fire days in the last 20 sessions, none in the last 2;
            close above the 50 EMA on the last fire day
  zone      no low at/under the 21 EMA since the last fire, close within 1.5 ADR above the 21 EMA
            → buy limit at the 21 EMA, stop 1 ADR under it, exit after 5 sessions (or trail the 10 EMA)
  undercut  first contact since the fire went 0.3+ ADR under the 21 EMA within the last 3 sessions, no reclaim yet
            → buy-stop over max(today's high, 21 EMA), stop under the undercut low (max 2 ADR)
  reclaimed today closed over the 21 EMA and over the prior high after such an undercut → buy next open, stop under the undercut low
  touched   today's low touched the 21 EMA and held (the touch entry happened today) - shown for reference
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config

log = logging.getLogger(__name__)
MIN_PRICE, MIN_DVOL, LOOK = 10.0, 20e6, 20
# 5-session R by market state, leading groups only (study results, Nov 24 2026). n = trades.
STATS = {
    "touch": {"thrust": (0.22, 0.49, 170), "strong": (0.61, 0.57, 49), "mixed": (0.50, 0.59, 114), "weak": (-0.15, 0.39, 119)},
    "undercut": {"thrust": (0.42, 0.58, 26), "strong": (1.20, 1.00, 12), "mixed": (-0.15, 0.32, 22), "weak": (0.72, 0.56, 25)},
}
FIT = {"strong": "Focus", "mixed": "Focus", "thrust": "Selective", "weak": "Avoid"}   # touch version (the proven one)


def _f(x, n=2):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(x) else round(x, n)


def build(adjusted, theme_data, state=None):
    T = theme_data or {}
    stocks = {s["t"]: s for s in T.get("stocks") or [] if s.get("is_stock", True) is not False}
    sub = {}
    for g in T.get("subthemes") or []:
        for t in g.get("members") or []:
            sub.setdefault(t, g["theme"])
    tick = [t for t in stocks if t in sub]
    a = adjusted[adjusted["date"] >= adjusted["date"].max() - pd.Timedelta(days=200)]
    a = a[a["ticker"].isin(set(tick) | {config.BENCHMARK})].drop_duplicates(["date", "ticker"], keep="last").set_index(["date", "ticker"])
    piv = lambda k: a[k].unstack().sort_index()
    c = piv("c")
    if len(c) < 80 or config.BENCHMARK not in c.columns:
        return None
    h, l, v = piv("h").reindex_like(c), piv("l").reindex_like(c), piv("v").reindex_like(c)
    spy = c[config.BENCHMARK]
    cols = [t for t in tick if t in c.columns]
    c, h, l, v = c[cols], h[cols], l[cols], v[cols]
    dv = (c * v).rolling(50, min_periods=30).mean().iloc[-1]
    r60 = c.iloc[-1] / c.iloc[-61] - 1
    liq_all = [t for t in cols if (dv.get(t) or 0) >= 5e6]
    g = r60[liq_all].groupby(pd.Series({t: sub[t] for t in liq_all})).median().dropna()
    lead = set(g[g >= g.quantile(0.7)].index)
    rs = c.div(spy, axis=0)
    fire = (rs >= rs.rolling(20, min_periods=20).max()) | (rs >= rs.rolling(63, min_periods=63).max())
    e21 = c.ewm(span=21, adjust=False, min_periods=21).mean()
    e50 = c.ewm(span=50, adjust=False, min_periods=50).mean()
    adr = ((h - l) / c).rolling(20, min_periods=10).mean() * c
    n = len(c)
    rows = []
    for t in cols:
        if sub[t] not in lead or (dv.get(t) or 0) < MIN_DVOL or c[t].iloc[-1] < MIN_PRICE:
            continue
        f = fire[t].to_numpy()[-LOOK:]
        k = int(f.sum())
        if not (1 <= k <= 3) or f[-2:].any():
            continue
        lf = n - LOOK + int(np.where(f)[0][-1])
        C, H, L, E, A = c[t].to_numpy(), h[t].to_numpy(), l[t].to_numpy(), e21[t].to_numpy(), adr[t].to_numpy()
        if not (C[lf] > e50[t].iloc[lf]) or not np.isfinite(E[-1]) or not np.isfinite(A[-1]) or A[-1] <= 0:
            continue
        contact = [j for j in range(lf + 1, n) if L[j] <= E[j - 1]]
        st, trig, stop, plan = None, None, None, ""
        if not contact:
            if C[-1] <= E[-1] + 1.5 * A[-1]:
                st, trig, stop = "zone", E[-1], E[-1] - A[-1]
                plan = f"Buy limit at the 21 EMA (~${E[-1]:.2f}), stop 1 ADR under (${E[-1] - A[-1]:.2f}), sell after 5 sessions or trail the 10 EMA"
            else:
                continue
        else:
            j0 = contact[0]
            if n - 1 - j0 > 3:
                continue
            deep = L[j0] <= E[j0 - 1] - 0.3 * A[j0]
            low = float(np.nanmin(L[j0:]))
            if deep:
                rec = [j for j in range(j0, n) if C[j] > E[j] and C[j] > H[j - 1]]
                if rec and rec[0] == n - 1:
                    st, trig, stop = "reclaimed", None, max(low, C[-1] - 2 * A[-1])
                    plan = f"Undercut and reclaimed today: buy tomorrow's open, stop under the undercut low (${stop:.2f})"
                elif not rec:
                    trig = max(H[-1], E[-1]) + 0.01
                    st, stop = "undercut", max(low, trig - 2 * A[-1])
                    plan = f"Undercut the 21 EMA: buy-stop over ${trig:.2f} (today's high / the 21 EMA), stop under the undercut low (${stop:.2f})"
                else:
                    continue
            elif j0 == n - 1 and C[-1] >= E[-2]:
                st, trig, stop = "touched", E[-2], E[-2] - A[-1]
                plan = f"Touched the 21 EMA today and held (the touch entry was ~${E[-2]:.2f}); stop ${E[-2] - A[-1]:.2f} if you took it"
            else:
                continue
        s = stocks[t]
        rows.append({"t": t, "g": sub[t], "st": st, "fires": k, "fire_date": str(c.index[lf].date()), "rs": s.get("rsr"),
                     "price": _f(C[-1]), "ema21": _f(E[-1]), "adr": _f(100 * A[-1] / C[-1], 1), "trigger": _f(trig), "stop": _f(stop),
                     "dist": _f((C[-1] - E[-1]) / A[-1], 2), "plan": plan, "g_r60": _f(g.get(sub[t]), 4)})
    order = {"reclaimed": 0, "undercut": 1, "zone": 2, "touched": 3}
    rows.sort(key=lambda r: (order[r["st"]], r["dist"] if r["dist"] is not None else 9, -(r["rs"] or 0)))
    return {"date": str(c.index[-1].date()), "state": state, "fit": FIT.get(state or "", "Selective"), "stats": STATS,
            "n_lead": len(lead), "rows": rows[:40]}
