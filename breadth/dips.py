"""Dip buys: Box + Strength-on-Weakness names under, or wicking under and back over, their 9 / 21-day EMAs
(Adam, Oct 24, 2026: "I'd like to get in when the price is wicking under the 9 or the 21 and then coming back up").

Names: Box trades longs (retest_long any tag, trap_long "failed" = spring) + every Strength on Weakness row.
Daily EMAs (span 9 / 21, same as stairs.py). Per name at the last close:
- under9 / under21   close below the 9 / 21 EMA
- wick9 / wick21     low below the EMA, close back at or above it (same day)
- reclaim            closed under the 9 or 21 in one of the 3 prior sessions, now closes above it again
Weekly switch (Oct 24): the same tests on weekly bars and 9 / 21-WEEK EMAs (Strength on Weakness settings; the current week counts
as it stands, low = the week's low so far); live = last week's EMA + alpha x (price - last week's EMA), low = min(week so far, today).
The page re-runs the same tests live from the Google Sheet (price + today's low, column L "low"): today's EMA =
last EMA + alpha x (price - last EMA), alpha = 2/(n+1), so the live numbers move exactly like the close will.
Information only (card R-2026-10-24-dip-buys).
"""
import numpy as np
import pandas as pd

CFG = {"reclaim_days": 3, "strip": 10, "box_types": ("retest_long",), "spring_tag": "failed"}


def sources(theme_data):
    """{ticker: {"box": [...], "sow": {...}}} from today's Box + SoW payloads."""
    out = {}
    bx = (theme_data or {}).get("boxes") or {}
    for r in bx.get("live") or []:
        if r.get("side") != "long":
            continue
        if not (r.get("type") in CFG["box_types"] or (r.get("type") == "trap_long" and r.get("tag") == CFG["spring_tag"])):
            continue
        out.setdefault(r["t"], {}).setdefault("rsr", r.get("rsr"))
        out[r["t"]].setdefault("sub", r.get("sub")); out[r["t"]].setdefault("theme", r.get("theme"))
        out[r["t"]].setdefault("box", []).append(
            {"type": r.get("type"), "tag": r.get("tag"), "grade": r.get("grade"), "lvl": r.get("lvl"),
             "stop": r.get("stop"), "target": r.get("target"), "exp": r.get("exp")})
    sw = (theme_data or {}).get("sow") or {}
    for r in sw.get("rows") or []:
        out.setdefault(r["t"], {}).setdefault("rsr", r.get("rsr"))
        out[r["t"]].setdefault("sub", r.get("sub")); out[r["t"]].setdefault("theme", r.get("theme"))
        out[r["t"]]["sow"] = {"state": r.get("state"), "prime": bool(r.get("prime")),
                                             "trig": r.get("trig"), "stop": r.get("stop")}
    return out


def build(adjusted, theme_data, names=None):
    """Payload for DATA.themes.dips."""
    from . import strength
    src = sources(theme_data)
    if not src:
        return None
    names = names or {}
    info = {r["t"]: r for r in (theme_data or {}).get("stocks") or []}
    w = strength.wide_all(adjusted[adjusted["ticker"].isin(list(src))])
    c, h, l = w["c"], w["h"], w["l"]
    if len(c.index) < 30:
        return None
    e9 = c.ewm(span=9, adjust=False, min_periods=9).mean()
    e21 = c.ewm(span=21, adjust=False, min_periods=21).mean()
    adr = (h / l - 1).rolling(20, min_periods=15).mean()
    D = _flags(c, l, e9, e21)
    # weekly (same weekly bars + EMA settings as Strength on Weakness; this week counts as it stands so far)
    from . import sow
    W, nday = sow.weekly(w, list(c.columns))
    wdone = bool(sow.complete_weeks(nday, c.index[-1])[-1])
    we9 = W["c"].ewm(span=9, adjust=False, min_periods=1).mean()
    we21 = W["c"].ewm(span=21, adjust=False, min_periods=1).mean()
    watr = (W["h"] / W["l"] - 1).rolling(10, min_periods=6).mean()
    WK = _flags(W["c"], W["l"], we9, we21)
    d = c.index[-1]
    rows = []
    for t, s in src.items():
        if t not in c.columns or pd.isna(c.at[d, t]) or pd.isna(e21.at[d, t]):
            continue
        ad = float(adr.at[d, t]) if pd.notna(adr.at[d, t]) else None
        st = info.get(t, {})
        row = {"t": t, "name": names.get(t) or st.get("name"), "price": round(float(c.at[d, t]), 2),
               "low": round(float(l.at[d, t]), 2), "e9": round(float(e9.at[d, t]), 2), "e21": round(float(e21.at[d, t]), 2),
               "adr": round(ad * 100, 1) if ad else None, **_row(D, t), "up": bool(e9.at[d, t] > e21.at[d, t]),
               "rsr": st.get("rsr") or s.get("rsr"), "sub": st.get("sub") or s.get("sub"),
               "theme": (st.get("themes") or [None])[0] or s.get("theme")}
        if t in W["c"].columns and pd.notna(W["c"][t].iloc[-1]):
            wa = watr[t].iloc[-1]
            row["w"] = {"low": round(float(W["l"][t].iloc[-1]), 2), "e9": round(float(we9[t].iloc[-1]), 2),
                        "e21": round(float(we21[t].iloc[-1]), 2),
                        "p9": round(float(we9[t].iloc[-2]), 2) if len(we9) > 1 else None,     # last week's EMAs (base for a live week)
                        "p21": round(float(we21[t].iloc[-2]), 2) if len(we21) > 1 else None,
                        "atr": round(float(wa) * 100, 1) if pd.notna(wa) else None, **_row(WK, t),
                        "up": bool(we9[t].iloc[-1] > we21[t].iloc[-1])}
        if "box" in s:
            row["box"] = s["box"]
        if "sow" in s:
            row["sow"] = s["sow"]
        rows.append(row)
    rows.sort(key=lambda r: (not (r["wick9"] or r["wick21"] or r["reclaim9"] or r["reclaim21"]),
                             not (r["under9"] or r["under21"]), -(r["rsr"] or 0)))
    return {"date": str(pd.Timestamp(d).date()), "cfg": CFG, "rows": rows, "week": str(pd.Timestamp(W["c"].index[-1]).date()),
            "week_done": wdone, "week_days": int(nday.iloc[-1]),
            "n_under": sum(r["under9"] or r["under21"] for r in rows),
            "n_wick": sum(r["wick9"] or r["wick21"] or r["reclaim9"] or r["reclaim21"] for r in rows)}


def _flags(c, l, e9, e21):
    u9, u21 = c < e9, c < e21
    return {"u9": u9, "u21": u21, "w9": (l < e9) & ~u9, "w21": (l < e21) & ~u21}


def _row(F, t):
    """Flags for one ticker at the last bar (day or week) + reclaim within CFG reclaim_days bars + a 10-bar strip."""
    k, n = CFG["reclaim_days"], CFG["strip"]
    u9, u21, w9, w21 = (F[x][t] for x in ("u9", "u21", "w9", "w21"))
    prev = slice(-1 - k, -1)
    strip = [3 if u21.iloc[i] else 2 if u9.iloc[i] else 1 if (w21.iloc[i] or w9.iloc[i]) else 0 for i in range(-min(n, len(u9)), 0)]
    return {"under9": bool(u9.iloc[-1]), "under21": bool(u21.iloc[-1]), "wick9": bool(w9.iloc[-1]),
            "wick21": bool(w21.iloc[-1]), "reclaim9": bool(u9.iloc[prev].any()) and not bool(u9.iloc[-1]),
            "reclaim21": bool(u21.iloc[prev].any()) and not bool(u21.iloc[-1]),
            "run9": int(u9.iloc[::-1].cumprod().sum()), "run21": int(u21.iloc[::-1].cumprod().sum()), "strip": strip}


def tickers(payload):
    return [r["t"] for r in (payload or {}).get("rows") or []]
