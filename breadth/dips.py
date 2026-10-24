"""Dip buys: Box + Strength-on-Weakness names under, or wicking under and back over, their 9 / 21-day EMAs
(Adam, Oct 24, 2026: "I'd like to get in when the price is wicking under the 9 or the 21 and then coming back up").

Names: Box trades longs (retest_long any tag, trap_long "failed" = spring) + every Strength on Weakness row.
Daily EMAs (span 9 / 21, same as stairs.py). Per name at the last close:
- under9 / under21   close below the 9 / 21 EMA
- wick9 / wick21     low below the EMA, close back at or above it (same day)
- reclaim            closed under the 9 or 21 in one of the 3 prior sessions, now closes above it again
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
    u9, u21 = c < e9, c < e21
    w9, w21 = (l < e9) & ~u9, (l < e21) & ~u21
    d = c.index[-1]
    k, n = CFG["reclaim_days"], CFG["strip"]
    rows = []
    for t, s in src.items():
        if t not in c.columns or pd.isna(c.at[d, t]) or pd.isna(e21.at[d, t]):
            continue
        cc, ll, a9, a21 = float(c.at[d, t]), float(l.at[d, t]), float(e9.at[d, t]), float(e21.at[d, t])
        ad = float(adr.at[d, t]) if pd.notna(adr.at[d, t]) else None
        prev = slice(-1 - k, -1)
        was9 = bool(u9[t].iloc[prev].any()) and not bool(u9.at[d, t])
        was21 = bool(u21[t].iloc[prev].any()) and not bool(u21.at[d, t])
        # closes in a row under the 21 / the 9
        run21 = int((u21[t].iloc[::-1].cumprod()).sum())
        run9 = int((u9[t].iloc[::-1].cumprod()).sum())
        strip = []
        for i in range(-n, 0):
            if u21[t].iloc[i]:
                strip.append(3)
            elif u9[t].iloc[i]:
                strip.append(2)
            elif w21[t].iloc[i] or w9[t].iloc[i]:
                strip.append(1)
            else:
                strip.append(0)
        st = info.get(t, {})
        row = {"t": t, "name": names.get(t) or st.get("name"), "price": round(cc, 2), "low": round(ll, 2),
               "e9": round(a9, 2), "e21": round(a21, 2), "adr": round(ad * 100, 1) if ad else None,
               "up": a9 > a21, "under9": bool(u9.at[d, t]), "under21": bool(u21.at[d, t]),
               "wick9": bool(w9.at[d, t]), "wick21": bool(w21.at[d, t]),
               "reclaim9": was9, "reclaim21": was21, "run9": run9, "run21": run21, "strip": strip,
               "rsr": st.get("rsr") or s.get("rsr"), "sub": st.get("sub") or s.get("sub"),
               "theme": (st.get("themes") or [None])[0] or s.get("theme")}
        if "box" in s:
            row["box"] = s["box"]
        if "sow" in s:
            row["sow"] = s["sow"]
        rows.append(row)
    rows.sort(key=lambda r: (not (r["wick9"] or r["wick21"] or r["reclaim9"] or r["reclaim21"]),
                             not (r["under9"] or r["under21"]), -(r["rsr"] or 0)))
    return {"date": str(pd.Timestamp(d).date()), "cfg": CFG, "rows": rows,
            "n_under": sum(r["under9"] or r["under21"] for r in rows),
            "n_wick": sum(r["wick9"] or r["wick21"] or r["reclaim9"] or r["reclaim21"] for r in rows)}


def tickers(payload):
    return [r["t"] for r in (payload or {}).get("rows") or []]
