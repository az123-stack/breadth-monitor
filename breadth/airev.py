"""AI Revenue Setups (Nov 5, 2026; Adam: "all these software companies are reporting great things with AI ... APPN, EPAM, APP, ACN's AI
backlog ... I want a separate tab for AI Revenue Setups where we look for all these stocks coming back into EMAs"). v3 Stocks → AI Revenue.

Names (each row says why it's on the list):
  verified  = the AI Monetizers pool (data/aimon.json: a documented AI revenue line), with the market's verdict (in / out) from aimon
  theme     = members of the "AI & ROBOTICS - Enterprise AI SaaS" / "AI Monetizers" themes
  report    = a REWARDED earnings-style reaction (earnings.frames: gap ≥ max(3%, 1 ADR) on 2.5x vol, closed up) in the last 20 sessions in a
              software / IT services sub-theme — the AI angle is NOT verified (check the report; add real ones to the aimon pool)
Per stock: the Lined-up buys fields (close, high, low, daily 9 / 21 EMAs, ADR, touched the 9/21 ribbon in the last 3 sessions) so the page
runs the same `lineupState` test live: in the EMAs → buy over yesterday's high, stop the dip low (max 1 ADR). Plus uptrend, RS, its
sub-theme's lifecycle stage (BUY groups are the proven filter: +0.85R a trade vs +0.11R elsewhere), Pop watch flag, last report.
The "AI revenue" filter itself is untested as an edge.
"""
import json

import numpy as np
import pandas as pd

from . import config, earnings, store

THEMES = ("AI & ROBOTICS - Enterprise AI SaaS", "AI & ROBOTICS - AI Monetizers")
SOFT = ("Software", "SaaS", "IT Services", "Cyber", "Identity", "Data & Observability", "AI Applications", "Cloud", "Analytics",
        "Defense IT", "Design & Engineering Software", "Business Services & Data", "Vertical", "Fintech Software", "HR", "Ad Tech")
CFG = dict(report_win=20, min_price=5.0, min_dvol=10e6, touch=0.25, hold21=0.5, max9=1.0, fresh=3)


def _r(x, k=4):
    return None if x is None or not np.isfinite(x) else round(float(x), k)


def build(adjusted, theme_data):
    T = theme_data or {}
    stocks = {s["t"]: s for s in (T.get("stocks") or [])}
    sd = store.load_subthemes()
    sub_of = dict(zip(sd["ticker"], sd["subtheme"]))
    th = store.load_themes()
    try:
        pool = json.loads((config.DATA_DIR / "aimon.json").read_text()).get("pool") or {}
    except Exception:
        pool = {}
    A = T.get("aimon") or {}
    status = A.get("status") or {}
    score = {r["t"]: r for r in (A.get("score") or [])}
    names = {}
    for t, note in pool.items():
        names.setdefault(t, {})["verified"] = note if isinstance(note, str) else (note or {}).get("note", "")
    for t in th[th["theme"].isin(THEMES)]["ticker"]:
        names.setdefault(t, {})["theme"] = True
    # rewarded reports in software / IT sub-themes, last 20 sessions
    soft_subs = {g for g in set(sd["subtheme"]) if any(k in g for k in SOFT)}
    soft_t = [t for t, g in sub_of.items() if g in soft_subs]
    tick = sorted(set(soft_t) | set(names))
    W = earnings._wide(adjusted, tick)
    c = W["c"]
    days = c.index
    i = len(days) - 1
    F = earnings.frames(W)
    R = F["react"]
    win = R.iloc[i - CFG["report_win"] + 1:i + 1]
    for t in soft_t:
        if t not in win.columns:
            continue
        hit = win[t].dropna()
        hit = hit[hit > 0]
        if len(hit):
            day = hit.index[-1]
            j = days.get_loc(day)
            names.setdefault(t, {})["report"] = {"date": str(day.date()), "gap": _r(F["gap"][t].iat[j]), "move": _r(F["move"][t].iat[j]),
                                                 "rvol": _r(F["rvol"][t].iat[j], 1), "since": _r(c[t].iat[i] / c[t].iat[j - 1] - 1)}
    # latest report of any direction for verified / theme names too (context)
    for t in names:
        if "report" in names[t] or t not in R.columns:
            continue
        hit = R[t].iloc[i - 60:i + 1].dropna()
        if len(hit):
            day = hit.index[-1]
            j = days.get_loc(day)
            names[t]["last_react"] = {"date": str(day.date()), "move": _r(F["move"][t].iat[j]), "since": _r(c[t].iat[i] / c[t].iat[j - 1] - 1)}
    o, h, l, v = W["o"], W["h"], W["l"], W["v"]
    adr = ((h / l) - 1).rolling(20, min_periods=15).mean()
    dvol = (c * v).rolling(20, min_periods=15).mean()
    e9, e21, e50 = (c.ewm(span=n, adjust=False, min_periods=n).mean() for n in (9, 21, 50))
    rib = np.maximum(e9, e21)
    touch = (l <= rib + CFG["touch"] * adr * c) & (c >= e21 - CFG["hold21"] * adr * c) & (c <= e9 + CFG["max9"] * adr * c)
    up = (e21 > e50) & (e50 > e50.shift(10))
    hi252 = h.rolling(252, min_periods=60).max()
    LC = (T.get("lifecycle") or {}).get("all") or {}
    pops = {r["g"]: r for r in ((T.get("popwatch") or {}).get("rows") or [])}
    cat = earnings._catalysts()
    rows = []
    for t, why in names.items():
        if t not in c.columns or not np.isfinite(c[t].iat[i]):
            continue
        s = stocks.get(t) or {}
        if s.get("deal") or s.get("is_stock") is False:
            continue
        g = s.get("sub") or sub_of.get(t, "")
        lc = LC.get(g)
        pw = pops.get(g)
        st = status.get(t) or {}
        e = (cat.get(t) or {}).get("earnings_date")
        rows.append({
            "t": t, "name": s.get("name", ""), "g": g, "rs": _r(s.get("rsr"), 0) if s.get("rsr") is not None else None,
            "c": _r(c[t].iat[i]), "hi": _r(h[t].iat[i]), "lo": _r(l[t].iat[i]), "e9": _r(e9[t].iat[i]), "e21": _r(e21[t].iat[i]),
            "e50": _r(e50[t].iat[i]), "adr": _r(adr[t].iat[i]),
            "t3": bool(touch[t].iloc[i - CFG["fresh"] + 1:i + 1].any()), "t0": bool(touch[t].iat[i]),
            "up": bool(up[t].iat[i]), "liq": bool(c[t].iat[i] >= CFG["min_price"] and dvol[t].iat[i] >= CFG["min_dvol"]),
            "d5": _r(c[t].iat[i] / c[t].iat[i - 5] - 1), "d20": _r(c[t].iat[i] / c[t].iat[i - 20] - 1),
            "off_hi": _r(c[t].iat[i] / hi252[t].iat[i] - 1),
            "src": [k for k in ("verified", "theme", "report") if k in why],
            "ai_note": why.get("verified") or "", "ai_in": st.get("in"), "ai_why": st.get("why", ""),
            "ai_score": _r((score.get(t) or {}).get("score"), 0),
            "report": why.get("report") or why.get("last_react"),
            "stage": lc[0] if lc else None, "signal": lc[5] if lc else None,
            "pop": {"date": pw["pop"], "ago": pw["ago"], "state": pw["state"]} if pw else None,
            "earn": e if e and e >= str(days[i].date()) else None,
        })
    rows.sort(key=lambda r: (not r["t3"], -(r["rs"] or 0)))
    return {"date": str(days[i].date()), "cfg": CFG, "rows": rows, "themes": list(THEMES),
            "counts": {k: sum(1 for r in rows if k in r["src"]) for k in ("verified", "theme", "report")}}


if __name__ == "__main__":
    b = store.apply_splits(store.load_bars(), store.load_splits())
    X = build(b, json.load(open(config.DOCS_DIR / "data.json"))["themes"])
    print(X["date"], len(X["rows"]), X["counts"])
    for r in X["rows"][:40]:
        print(f"{r['t']:6} {str(r['rs']):5} t3={r['t3']} up={r['up']} {r['src']} {r['g'][:28]:28} {r['stage']} {r['signal']} rep={r['report']}")
