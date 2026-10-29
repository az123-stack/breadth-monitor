"""Biotech value chain (Adam, Oct 29 2026: "biotech is the only thing moving; track it in detail so we can invest in the exact
right places"). Information only: never touches the picks.

Stages from data/valuechain.json (target design → instruments → reagents → CROs → CDMO → clinical software → distribution →
data / drug owners). For every stage, from daily bars (split-adjusted):
  - price strength vs SPY (1d / 5d / 1m / 3m, equal-weight), % above the 50 EMA, median distance from the 1-year high, median RS;
  - dollar flow: volume vs normal (5d / 20d vs the 50 sessions before), net flow (each day's $ volume signed by the close's
    direction, ÷ normal $ volume; a rough proxy, not order flow), share of the whole chain's $ volume now vs before;
  - a composite rank (price + flow), and a 60-session line of the stage vs SPY for the sparkline.
For every stock: the same numbers plus where it sits for an entry ("spot", Adam's rules: buy zone = uptrend and within 1.25 ADRs
of the rising 21 EMA; pullback = into or just under the 9/21 ribbon; extended = 2+ ADRs over the 21 EMA; broken = under the 50 EMA).
The page adds today's live move per stage from the Google sheet (where the sheet has the ticker).
"""
import json

import numpy as np
import pandas as pd

from . import config

PATH = config.ROOT / "data" / "valuechain.json"


def load():
    try:
        return json.loads(PATH.read_text())
    except Exception:
        return {"stages": [], "demand": []}


def tickers():
    V = load()
    return {t for s in V.get("stages") or [] for t in s.get("tickers") or []} | set(V.get("demand") or [])


def _r(x, n=4):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(x) else round(x, n)


def spot(p, e9, e21, e50, e21_prev, adr):
    """Where a stock sits for an entry, in ADRs vs its EMAs (daily close)."""
    if not adr or not np.isfinite(adr) or adr <= 0:
        return "na"
    if p < e50:
        return "broken"
    d21 = (p / e21 - 1) / adr
    up = e21 > e50 and e21 >= e21_prev
    if d21 >= 2:
        return "extended"
    if up and -0.5 <= d21 <= 0.3:
        return "pullback"            # in or just under the 9/21 ribbon
    if up and d21 <= 1.25:
        return "buy"                 # riding the rising 21 within ~1 ADR
    if not up:
        return "basing"
    return "stretched"               # 1.25-2 ADRs over the 21


def build(adjusted, theme_data=None):
    V = load()
    stages = V.get("stages") or []
    if not stages:
        return None
    T = theme_data or {}
    RS = {s["t"]: s.get("rsr") for s in T.get("stocks") or []}
    names = {s["t"]: s.get("name") for s in T.get("stocks") or []}
    try:
        from . import store
        names = {**store.load_names(), **{k: v for k, v in names.items() if v}}
    except Exception:
        pass
    want = sorted(tickers() | {config.BENCHMARK})
    sub = adjusted[adjusted["ticker"].isin(want)]
    W = {k: sub.pivot_table(index="date", columns="ticker", values=k).sort_index() for k in ("c", "h", "l", "v")}
    C, H, L, Vv = W["c"], W["h"].reindex_like(W["c"]), W["l"].reindex_like(W["c"]), W["v"].reindex_like(W["c"])
    if config.BENCHMARK not in C.columns or len(C) < 80:
        return None
    spy = C[config.BENCHMARK]
    n = len(C)
    chg = C.pct_change(fill_method=None)
    dv = C * Vv
    sgn = np.sign(chg)
    adr = (H / L - 1).rolling(20, min_periods=15).mean()
    e9, e21, e50 = (C.ewm(span=k, adjust=False).mean() for k in (9, 21, 50))
    # RS for names outside the dashboard's stock list: raw score vs today's breakpoints
    try:
        from . import strength
        bp = T.get("rs_bp")
        raw = strength.rs_raw(C).iloc[-1]
        rs_calc = dict(zip(raw.index, strength.rate(raw.to_numpy(), np.array(bp)) if bp else [np.nan] * len(raw)))
    except Exception:
        rs_calc = {}

    def rs_of(t):
        v = RS.get(t)
        return v if v is not None else _r(rs_calc.get(t), 0)

    def spy_ret(k):
        return spy.iloc[-1] / spy.iloc[-1 - k] - 1

    def ok(t):
        return t in C.columns and C[t].iloc[-70:].notna().sum() >= 65

    stocks, out, tot_now, tot_then = {}, [], 0.0, 0.0
    for s in stages:
        ts = [t for t in s.get("tickers") or [] if ok(t)]
        for t in ts:
            if t in stocks:
                stocks[t]["stages"].append(s["k"])
                continue
            c = C[t]
            a = adr[t].iloc[-1]
            hi = H[t].iloc[-252:].max()
            base = dv[t].iloc[-70:-20].mean()
            stocks[t] = {"t": t, "name": names.get(t) or "", "stages": [s["k"]], "price": _r(c.iloc[-1], 2), "rs": rs_of(t),
                         "d1": _r(c.iloc[-1] / c.iloc[-2] - 1), "d5": _r(c.iloc[-1] / c.iloc[-6] - 1),
                         "d20": _r(c.iloc[-1] / c.iloc[-21] - 1), "d60": _r(c.iloc[-1] / c.iloc[-61] - 1),
                         "adr": _r(a), "x10": _r((c.iloc[-1] / C[t].ewm(span=10, adjust=False).mean().iloc[-1] - 1) / a if a else None, 2),
                         "x21": _r((c.iloc[-1] / e21[t].iloc[-1] - 1) / a if a else None, 2), "v50": _r(c.iloc[-1] / e50[t].iloc[-1] - 1),
                         "e9": _r(e9[t].iloc[-1], 2), "e21": _r(e21[t].iloc[-1], 2), "e50": _r(e50[t].iloc[-1], 2),
                         "off": _r(c.iloc[-1] / hi - 1), "hi": _r(hi, 2),
                         "rv5": _r(dv[t].iloc[-5:].mean() / base if base else None, 2), "rv20": _r(dv[t].iloc[-20:].mean() / base if base else None, 2),
                         "net20": _r((sgn[t] * dv[t]).iloc[-20:].sum() / (base * 20) if base else None, 3),
                         "net20_usd": _r((sgn[t] * dv[t]).iloc[-20:].sum() / 1e6, 0), "dvol": _r(dv[t].iloc[-20:].mean() / 1e6, 1),
                         "spot": spot(c.iloc[-1], e9[t].iloc[-1], e21[t].iloc[-1], e50[t].iloc[-1], e21[t].iloc[-6], a)}
        if not ts:
            continue
        d, sg = dv[ts], sgn[ts] * dv[ts]
        base = d.iloc[-70:-20].sum(axis=1).mean()
        now, then = d.iloc[-20:].sum().sum(), d.iloc[-70:-20].sum().sum()
        tot_now += now
        tot_then += then
        rel = (C[ts] / C[ts].iloc[-61]).mean(axis=1) / (spy / spy.iloc[-61])      # equal-weight stage vs SPY, last 60 sessions
        rsv = [rs_of(t) for t in ts if rs_of(t) is not None]
        out.append({"k": s["k"], "name": s["name"], "desc": s.get("desc", ""), "n": len(ts), "tickers": ts,
                    "missing": [t for t in s.get("tickers") or [] if t not in ts],
                    **{f"r{k}": _r(np.mean([C[t].iloc[-1] / C[t].iloc[-1 - k] - 1 for t in ts]) - spy_ret(k)) for k in (1, 5, 20, 60)},
                    "above50": _r(np.mean([C[t].iloc[-1] > e50[t].iloc[-1] for t in ts]), 3),
                    "off": _r(np.median([C[t].iloc[-1] / H[t].iloc[-252:].max() - 1 for t in ts])),
                    "rs": _r(np.median(rsv), 0) if rsv else None,
                    "rv5": _r(d.iloc[-5:].sum(axis=1).mean() / base if base else None, 2),
                    "rv20": _r(d.iloc[-20:].sum(axis=1).mean() / base if base else None, 2),
                    "net5": _r(sg.iloc[-5:].sum().sum() / (base * 5) if base else None, 3),
                    "net20": _r(sg.iloc[-20:].sum().sum() / (base * 20) if base else None, 3),
                    "up20": _r((d.iloc[-20:] * (chg[ts].iloc[-20:] > 0)).sum().sum() / d.iloc[-20:].sum().sum(), 3),
                    "dvol": _r(d.iloc[-20:].sum(axis=1).mean() / 1e6, 0), "_now": now, "_then": then,
                    "line": [_r(x, 4) for x in rel.iloc[-61:].tolist()],
                    "spots": {k: sum(1 for t in ts if stocks[t]["spot"] == k) for k in ("buy", "pullback", "stretched", "extended", "basing", "broken")}})
    if not out:
        return None
    for o in out:
        o["share"] = _r(o.pop("_now") / tot_now if tot_now else None, 4)
        o["share_chg"] = _r(o["share"] - o.pop("_then") / tot_then if tot_then and o["share"] is not None else None, 4)
    S = pd.DataFrame(out)
    # composite rank: price (1m, 3m, 5d half weight, above-50, near highs) + flow (net 20d, share change, 5d volume)
    pr = (S.r20.rank() + S.r60.rank() + 0.5 * S.r5.rank() + S.above50.rank() + S.off.rank()) / 4.5
    fl = (S.net20.rank() + S.share_chg.rank() + 0.5 * S.rv5.rank()) / 2.5
    S["price_rank"], S["flow_rank"] = pr.rank(ascending=False).astype(int), fl.rank(ascending=False).astype(int)
    S["score"] = (pr + fl) / 2
    S = S.sort_values("score", ascending=False)
    rows = S.to_dict("records")
    for i, r in enumerate(rows):
        r["rank"] = i + 1
        r["score"] = _r(r["score"], 2)
        r["read"] = ("Leading, money confirming" if r["price_rank"] <= 3 and r["flow_rank"] <= 3 else
                     "Leading on price, money lagging" if r["price_rank"] <= 3 else
                     "Money moving in, price catching up" if r["flow_rank"] <= 3 else
                     "Being sold" if (r["net20"] or 0) < 0 and (r["r20"] or 0) < 0 else "Middle of the pack")
    demand = []
    for t in V.get("demand") or []:
        if ok(t):
            c = C[t]
            demand.append({"t": t, **{f"r{k}": _r(c.iloc[-1] / c.iloc[-1 - k] - 1 - spy_ret(k)) for k in (1, 5, 20, 60)},
                           "off": _r(c.iloc[-1] / H[t].iloc[-252:].max() - 1), "v50": _r(c.iloc[-1] / e50[t].iloc[-1] - 1)})
    return {"date": C.index[-1].strftime("%Y-%m-%d"), "stages": rows, "stocks": stocks, "demand": demand,
            "line_dates": [d.strftime("%Y-%m-%d") for d in C.index[-61:]]}
