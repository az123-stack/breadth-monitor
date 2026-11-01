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

COHORTS = {"d180": 180, "d60": 60, "d30": 30, "d15": 15, "d5": 5}   # d30 added Oct 31 (Adam)
RETS = (180, 60, 30, 15, 5)
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


# ---- Accelerating vs SPY (Oct 31, 2026; Adam: "catch runners like Cloud Communications early — accelerating on the 60 and 15 session
# charts, like Defense IT / IT Services"; study tools/oracle_study/accel.py, card R-2026-10-31-accelerating-groups) ----
# rel = price / SPY; pace N = (rel now / rel N sessions ago − 1) / N. ACCELERATING = 15-session pace > 60-session pace > 180-session pace,
# 15-session rel > 0 and 60-session rel ≥ +10% (STRONG = that last part alone). Stage early = 180-session rel < +25%, else running.
ACC = {"s60": 0.10, "early180": 0.25, "gap": 30}


def accel(rel):
    """rel = price ÷ SPY (a pandas Series by date). Returns per-date flags (acc, strong) and the three rel returns."""
    s15, s60, s180 = rel / rel.shift(15) - 1, rel / rel.shift(60) - 1, rel / rel.shift(180) - 1
    strong = s60 >= ACC["s60"]
    acc = strong & (s15 > 0) & (s15 / 15 > s60 / 60) & (s60 / 60 > s180 / 180)
    return acc, strong, s15, s60, s180


def acc_tag(rel):
    """Today's acceleration tag: {a: 1/0 accelerating, st: 1/0 strong 60D, stage, start (first fire of this episode), on20 (days on
    in the last 20 sessions), v: [180, 60, 15] rel returns}."""
    rel = rel.dropna()
    if len(rel) < 181:
        return None
    acc, strong, s15, s60, s180 = accel(rel)
    on = acc[acc.fillna(False)].index
    start = None
    if bool(acc.iloc[-1]):
        start = on[-1]
        for d in reversed(on[:-1]):
            if (start - d).days > ACC["gap"]:
                break
            start = d
    v = [_r(s180.iloc[-1]), _r(s60.iloc[-1]), _r(s15.iloc[-1])]
    return {"a": int(bool(acc.iloc[-1])), "st": int(bool(strong.iloc[-1])), "stage": "early" if (v[0] or 0) < ACC["early180"] else "running",
            "start": start.strftime("%Y-%m-%d") if start is not None else None, "on20": int(acc.iloc[-20:].fillna(False).sum()), "v": v}


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
    cohorts, need, rank_all = {}, set(), {}
    weak = {}    # Adam, Oct 30: "a toggle between strongest and weakest" → bottom TOP by the same return, worst first
    for key, k in COHORTS.items():
        ret = (last[liquid] / C[liquid].iloc[-(k + 1)] - 1).dropna().sort_values(ascending=False)
        weak[key] = list(ret.index[::-1][:TOP])
        rank_all[key] = list(ret.index)
        need.update(weak[key])
        top = list(ret.index[:TOP])
        cohorts[key] = top
        need.update(top)
    win = C.iloc[-(n + 1):]
    rets = {k: last / C.iloc[-(k + 1)] - 1 for k in RETS}
    spyC = C[config.BENCHMARK]
    liq = set(liquid)
    def row(t):
        s = meta[t]
        return {"name": s.get("name"), "sub": s.get("sub") or ((s.get("themes") or [""])[0]), "rsr": s.get("rsr"),
                "r": [_r(rets[k].get(t)) for k in RETS], "c": [_r(v, 2) for v in win[t].tolist()],
                "lq": int(t in liq), "ac": acc_tag(C[t] / spyC), "adr": s.get("adr")}
    rows = {}
    for t in sorted(need):
        rows[t] = row(t)
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
        r = [_r(full.iloc[-1] / full.iloc[-(k + 1)] - 1) for k in RETS]
        subs[g["theme"]] = {"n": len(mem), "group": g.get("group"), "strength": _r(strength.get(g["theme"]), 1), "r": r,
                            "c": [_r(v, 2) for v in series], "ac": acc_tag(full / spyC.reindex(full.index)),
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
                rows[t] = row(t)
    for t in liquid:            # every liquid stock gets a row, so the stock filter can page through all of them
        if t not in rows:
            rows[t] = row(t)
    return {"date": C.index[-1].strftime("%Y-%m-%d"), "dates": [d.strftime("%Y-%m-%d") for d in win.index],
            "windows": WINDOWS, "cohorts": cohorts, "scohorts": scoh, "wcohorts": weak, "wscohorts": wscoh, "sall": sall, "rall": rank_all, "subs": subs, "rows": rows, "spy": spy, "overlap": overlap,
            "spy_r": [_r(rets[k].get(config.BENCHMARK)) for k in RETS], "universe": len(liquid),
            "rules": {"top": TOP, "min_price": MIN_PRICE, "min_dv": MIN_DV, "acc": ACC}}
