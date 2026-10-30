"""Oracle (v3 Groups → Oracle, Oct 30, 2026; Adam: "3 charts, 180D, 60D, 15D aligned next to each other; pills = Cohorts 180D / 60D /
15 day / 5 day = the strongest stocks in those periods; when the 5-day cohort is selected its stocks show across all 3 charts").

Cohort = the top theme stocks by return over N sessions (180 / 60 / 15 / 5), liquid only ($5+, $10M+ a day). For every stock in any
cohort the payload carries its last 181 closes, so the page can draw each cohort over the 180-, 60- and 15-session windows (each line
rebased to 0% at the window start) next to SPY. Descriptive only; never touches picks.
"""
import numpy as np
import pandas as pd

from . import config

COHORTS = {"d180": 180, "d60": 60, "d15": 15, "d5": 5}
WINDOWS = [180, 60, 15]
TOP = 30
MIN_PRICE, MIN_DV = 5.0, 10e6


def _r(x, n=4):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(x) else round(x, n)


def build(adjusted, theme_data=None):
    T = theme_data or {}
    stocks = [s for s in T.get("stocks") or [] if s.get("is_stock", True)]
    meta = {s["t"]: s for s in stocks}
    want = sorted(set(meta) | {config.BENCHMARK})
    sub = adjusted[adjusted["ticker"].isin(want)]
    C = sub.pivot_table(index="date", columns="ticker", values="c").sort_index()
    V = sub.pivot_table(index="date", columns="ticker", values="v").sort_index().reindex_like(C)
    n = max(WINDOWS)
    if config.BENCHMARK not in C.columns or len(C) < n + 1:
        return None
    C = C.ffill(limit=3)
    last = C.iloc[-1]
    dv = (C * V).iloc[-50:].mean()
    liquid = [t for t in meta if t in C.columns and last.get(t, 0) >= MIN_PRICE and dv.get(t, 0) >= MIN_DV
              and C[t].iloc[-(n + 1):].notna().sum() >= 150]
    cohorts, need = {}, set()
    for key, k in COHORTS.items():
        ret = (last[liquid] / C[liquid].iloc[-(k + 1)] - 1).dropna().sort_values(ascending=False)
        top = list(ret.index[:TOP])
        cohorts[key] = top
        need.update(top)
    win = C.iloc[-(n + 1):]
    rets = {k: last / C.iloc[-(k + 1)] - 1 for k in (180, 60, 15, 5)}
    rows = {}
    for t in sorted(need):
        s = meta[t]
        rows[t] = {"name": s.get("name"), "sub": s.get("sub") or ((s.get("themes") or [""])[0]), "rsr": s.get("rsr"),
                   "r": [_r(rets[k].get(t)) for k in (180, 60, 15, 5)],
                   "c": [_r(v, 2) for v in win[t].tolist()]}
    spy = [_r(v, 2) for v in win[config.BENCHMARK].tolist()]
    overlap = {a: {b: len(set(cohorts[a][:20]) & set(cohorts[b][:20])) for b in COHORTS} for a in COHORTS}
    return {"date": C.index[-1].strftime("%Y-%m-%d"), "dates": [d.strftime("%Y-%m-%d") for d in win.index],
            "windows": WINDOWS, "cohorts": cohorts, "rows": rows, "spy": spy, "overlap": overlap,
            "spy_r": [_r(rets[k].get(config.BENCHMARK)) for k in (180, 60, 15, 5)], "universe": len(liquid),
            "rules": {"top": TOP, "min_price": MIN_PRICE, "min_dv": MIN_DV}}
