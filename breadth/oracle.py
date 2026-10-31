"""Oracle (v3 Groups → Oracle, Oct 30, 2026; Adam: "3 charts, 180D, 60D, 15D aligned next to each other; pills = Cohorts 180D / 60D /
15 day / 5 day = the strongest stocks in those periods; when the 5-day cohort is selected its stocks show across all 3 charts").

Cohort = the top theme stocks by return over N sessions (180 / 60 / 15 / 5), liquid only ($5+, $10M+ a day). For every stock in any
cohort the payload carries its last 181 closes, so the page can draw each cohort over the 180-, 60- and 15-session windows (each line
rebased to 0% at the window start) next to SPY. Descriptive only; never touches picks.
"""
import re

import numpy as np
import pandas as pd

from . import config

COHORTS = {"d180": 180, "d60": 60, "d15": 15, "d5": 5}
WINDOWS = [180, 60, 15]
TOP = 15         # Adam, Oct 30: top 7 first, then "lets try top 15"
SUB_MIN = 3      # sub-themes need 3+ members with data
MIN_PRICE, MIN_DV = 5.0, 10e6


def _r(x, n=4):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(x) else round(x, n)


def build(adjusted, theme_data=None):
    T = theme_data or {}
    # every theme / sub-theme stock incl. ADRs (is_stock is False for ADRs too); ETFs dropped by name
    stocks = [s for s in T.get("stocks") or [] if s.get("name") and not re.search(r"\bETF\b|\bFund\b|\bTrust\b", s["name"])]
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
    weak = {}    # Adam, Oct 30: "a toggle between strongest and weakest" → bottom TOP by the same return, worst first
    for key, k in COHORTS.items():
        ret = (last[liquid] / C[liquid].iloc[-(k + 1)] - 1).dropna().sort_values(ascending=False)
        weak[key] = list(ret.index[::-1][:TOP])
        need.update(weak[key])
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
    overlap = {a: {b: len(set(cohorts[a]) & set(cohorts[b])) for b in COHORTS} for a in COHORTS}
    # ---- sub-themes: equal-weight index of members with data (daily returns averaged, so late listings don't jump it) ----
    subs, scoh = {}, {}
    strength = {g["theme"]: g.get("strength") for g in T.get("subthemes") or []}
    ret_d = C.pct_change(fill_method=None).clip(-0.5, 1.0)
    for g in T.get("subthemes") or []:
        mem = [t for t in (g.get("members") or []) if t in C.columns and t in meta and C[t].iloc[-(n + 1):].notna().sum() >= 150]
        if len(mem) < SUB_MIN:
            continue
        idx = (1 + ret_d[mem].iloc[-n:].mean(axis=1).fillna(0)).cumprod()
        series = [100.0] + (100 * idx).tolist()
        full = (1 + ret_d[mem].mean(axis=1).fillna(0)).cumprod()
        r = [_r(full.iloc[-1] / full.iloc[-(k + 1)] - 1) for k in (180, 60, 15, 5)]
        subs[g["theme"]] = {"n": len(mem), "group": g.get("group"), "strength": _r(strength.get(g["theme"]), 1), "r": r,
                            "c": [_r(v, 2) for v in series],
                            "members": sorted(mem, key=lambda t: -(rets[180].get(t) if pd.notna(rets[180].get(t)) else -9))}
    wscoh = {}
    for key, k in COHORTS.items():
        j = list(COHORTS).index(key)
        scoh[key] = [g for g, _ in sorted(subs.items(), key=lambda kv: -(kv[1]["r"][j] if kv[1]["r"][j] is not None else -9))[:TOP]]
        wscoh[key] = [g for g, _ in sorted(subs.items(), key=lambda kv: (kv[1]["r"][j] if kv[1]["r"][j] is not None else 9))[:TOP]]
    # Adam, Oct 31: "run through all the sub-themes 15 at a time" → every sub-theme kept, full ranking per cohort (best first)
    sall = {}
    for key in COHORTS:
        j = list(COHORTS).index(key)
        sall[key] = [g for g, _ in sorted(subs.items(), key=lambda kv: -(kv[1]["r"][j] if kv[1]["r"][j] is not None else -9))]
    # Adam, Oct 30: "select a sub-theme and have its stocks show below" → every member of a listed sub-theme gets its closes too
    for g in subs.values():
        for t in g["members"]:
            if t not in rows:
                s = meta[t]
                rows[t] = {"name": s.get("name"), "sub": s.get("sub") or ((s.get("themes") or [""])[0]), "rsr": s.get("rsr"),
                           "r": [_r(rets[k].get(t)) for k in (180, 60, 15, 5)], "c": [_r(v, 2) for v in win[t].tolist()]}
    return {"date": C.index[-1].strftime("%Y-%m-%d"), "dates": [d.strftime("%Y-%m-%d") for d in win.index],
            "windows": WINDOWS, "cohorts": cohorts, "scohorts": scoh, "wcohorts": weak, "wscohorts": wscoh, "sall": sall, "subs": subs, "rows": rows, "spy": spy, "overlap": overlap,
            "spy_r": [_r(rets[k].get(config.BENCHMARK)) for k in (180, 60, 15, 5)], "universe": len(liquid),
            "rules": {"top": TOP, "min_price": MIN_PRICE, "min_dv": MIN_DV}}
