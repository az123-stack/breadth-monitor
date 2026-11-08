"""Heavy lifters (Nov 8, 2026; Adam: "the most powerful stocks moving the market up while the hyperscalers go down ... a tab that shows me
these stocks, both these and the next tier, and which ones are pulling back into their EMAs for good setups. I think it's these stocks I
want to be concentrating on right now").

v3 Stocks → Heavy lifters (`renderHeavy` in v3_tabs.js). Universe = every stock with a Google market cap (S&P 500 + Nasdaq-100 rows of
data/close_snapshot.csv). Python ships per stock: the last WIN+1 closes, today's high / low, EMA 9 / 21 / 50 at the last close (+ the 21
five sessions ago, for "rising"), ADR, market cap, RS, sub-theme. The page picks the window (3 / 6 weeks), ranks by market-cap dollars
added (cap now × (1 − 1 / (1 + return)), ≈ index points = $ / total S&P cap), and tags where price sits vs its EMAs, live with Google
prices. Descriptive only: nothing is backtested and nothing moves the picks.
"""
import logging
import re

import numpy as np
import pandas as pd

from . import config, strength

WIN = 30
log = logging.getLogger("breadth")


def _g(x, sig=5):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return float(f"{x:.{sig}g}") if np.isfinite(x) else None


def build(adjusted, theme_data):
    mc = strength.mega_caps()
    if not mc:
        return None
    try:
        im = pd.read_csv(config.DATA_DIR / "index_members.csv")
        spx = set(im.loc[im["index"] == "SPX", "ticker"])
        sector = im.drop_duplicates("ticker").set_index("ticker")["sector"].to_dict()
    except Exception:
        spx, sector = set(), {}
    S = {s["t"]: s for s in (theme_data or {}).get("stocks") or []}
    tick = set(mc) | {config.BENCHMARK}
    sub = adjusted[adjusted["ticker"].isin(tick)]
    c = sub.pivot_table(index="date", columns="ticker", values="c").sort_index()
    h = sub.pivot_table(index="date", columns="ticker", values="h").reindex_like(c)
    l = sub.pivot_table(index="date", columns="ticker", values="l").reindex_like(c)
    if len(c) < 60:
        return None
    e = {k: c.ewm(span=k, adjust=False, min_periods=k).mean() for k in (9, 21, 50)}
    adr = (h / l - 1).rolling(20, min_periods=15).mean()
    rows = {}
    for t, cap in mc.items():
        if t not in c.columns or t == config.BENCHMARK:
            continue
        cc = c[t].iloc[-(WIN + 1):].to_numpy()
        try:
            cap = float(cap)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(cc).all() or not np.isfinite(cap) or cap <= 0:
            continue
        s = S.get(t) or {}
        rows[t] = {"c": [_g(x) for x in cc], "h": _g(h[t].iat[-1]), "l": _g(l[t].iat[-1]),
                   "e": [_g(e[k][t].iat[-1]) for k in (9, 21, 50)], "e21p": _g(e[21][t].iat[-6]), "adr": _g(adr[t].iat[-1], 3),
                   "cap": _g(cap / 1e9, 4), "spx": t in spx, "rs": s.get("rsr"), "sub": s.get("sub") or "",
                   "sec": sector.get(t, ""), "nm": (s.get("name") or "")[:36]}
    spxcap = sum(r["cap"] for r in rows.values() if r["spx"])
    b = c[config.BENCHMARK].iloc[-(WIN + 1):] if config.BENCHMARK in c.columns else None
    return {"date": c.index[-1].strftime("%Y-%m-%d"), "win": WIN, "spx_cap": _g(spxcap, 4),
            "bench": [_g(x) for x in b] if b is not None else None, "rows": rows}
