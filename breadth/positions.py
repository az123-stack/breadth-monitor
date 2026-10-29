"""My positions (Oct 28, 2026; Adam: a card for his own real trades that flags his exit rules live, synced across phone and computer).

Adam's trades live in the "Positions" tab of his Google Sheet "Breadth Monitor – Live Prices" (published with the rest of the sheet,
config.POSITIONS_CSV_URL), so he can add or edit them from the Google Sheets app on any device and the page picks them up. The tab has
ticker | bought | entry | shares | stop | sold | setup | notes, plus GOOGLEFINANCE price / closeyest / low / high columns.
Nothing about the positions is stored in this (public) repo: the page reads the tab directly.

This module only ships the end-of-day references the page needs to judge his exit rules for ANY liquid ticker:
last close, 10 / 20-day EMAs, 20-day ADR % and the last session's high / low, plus the recent session dates (to count days held).
Rules (from Adam's style: Qullamaggie flags, stop at the low of day, sell part after 3–5 days, trail the 10 / 20 EMA) live in the
page (`posState` in v2_template.html).
"""
import numpy as np
import pandas as pd

CFG = dict(min_price=3.0, min_dv=2e6, min_bars=25, dates=40)


def refs(adjusted):
    c = adjusted.pivot(index="date", columns="ticker", values="c").sort_index().astype("float64")
    h = adjusted.pivot(index="date", columns="ticker", values="h").sort_index().astype("float64").reindex_like(c)
    lo = adjusted.pivot(index="date", columns="ticker", values="l").sort_index().astype("float64").reindex_like(c)
    v = adjusted.pivot(index="date", columns="ticker", values="v").sort_index().astype("float64").reindex_like(c)
    tail = c.iloc[-120:]
    e10 = tail.ewm(span=10, adjust=False, min_periods=10).mean().iloc[-1]
    e20 = tail.ewm(span=20, adjust=False, min_periods=20).mean().iloc[-1]
    adr = ((h / lo - 1) * 100).iloc[-20:].mean()
    dv = (c * v).iloc[-50:].mean()
    last = c.iloc[-1]
    n = c.iloc[-120:].notna().sum()
    ok = (last >= CFG["min_price"]) & (dv >= CFG["min_dv"]) & (n >= CFG["min_bars"]) & c.iloc[-1].notna()
    rows = {}
    for t in ok[ok].index:
        vals = [last[t], e10[t], e20[t], adr[t], h.iloc[-1][t], lo.iloc[-1][t]]
        if any(x is None or not np.isfinite(x) for x in vals):
            continue
        r = lambda x: float(f"{x:.4g}") if x < 1000 else round(float(x), 2)
        rows[str(t)] = [r(vals[0]), r(vals[1]), r(vals[2]), round(float(vals[3]), 2), r(vals[4]), r(vals[5])]
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in c.index[-CFG["dates"]:]]
    return {"date": dates[-1], "dates": dates, "cols": ["c", "e10", "e20", "adr", "h", "l"], "rows": rows}
