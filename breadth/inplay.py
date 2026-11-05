"""In Play (Nov 5, 2026; Adam, after a Lance Breitstein transcript: "should we add something to filter for in play stocks?" →
"Let's have In Play under the stocks tab"). v3 Stocks → In Play.

A stock is IN PLAY when something is happening to it, for one of the transcript's three reasons, measured on our bars:
  1. NEWS: a gap of at least max(3%, 1 ADR) on 2.5x+ the 50-day volume (the earnings-reaction rule in earnings.frames); tagged
     "earnings" when the catalyst agent has an earnings date that day.
  2. TECHNICAL: a fresh close above the 52-week high (no such close in the prior 20 sessions) or above a 60-session high out of a
     tight base (prior 40 sessions within 6 ADRs), on 1.5x+ volume; breakdowns mirrored.
  3. VOLATILITY: a day's range of 2+ ADRs on 2x+ volume, or a recent IPO (under 120 sessions of history).
Window = the last 5 sessions; liquid = $5+, $10M+/day (20-day), US common stocks (universe). The page adds TODAY live from the Google
sheet (move ≥ 2 ADRs, or gap ≥ max(3%, 1 ADR) with paced volume ≥ 2x) and pre-market gaps from Yahoo.
Descriptive only: our studies say "more action" is not a swing edge by itself (record-volume up days lagged SPY ~5% over 10 sessions,
EPs without a catalyst check lost); a test of "same setup, in play vs not" is queued (ROADMAP).
"""
import json

import numpy as np
import pandas as pd

from . import config, store, strength

CFG = dict(win=5, px=5.0, dvol=10e6, gap_min=0.03, gap_adr=1.0, rv_news=2.5, rv_brk=1.5, base_n=40, base_adr=6.0, hi_n=60,
           range_adr=2.0, rv_range=2.0, ipo_n=120, live_move_adr=2.0, live_rv=2.0, max_rows=800)
PTS = {"earnings": 3, "news": 3, "breakout": 2, "base": 2, "breakdown": 2, "range": 1, "ipo": 1}


def _catalysts():
    try:
        return (json.loads((config.DOCS_DIR / "agent" / "catalysts.json").read_text()) or {}).get("stocks") or {}
    except Exception:
        return {}


def frames(W):
    """Per stock per day flags, all from data known at that day's close."""
    o, h, l, c, v = (W[k] for k in ("o", "h", "l", "c", "v"))
    pc = c.shift()
    adr = ((h / l) - 1).rolling(20, min_periods=15).mean().shift()
    v50 = v.rolling(50, min_periods=30).mean().shift()
    rv = v / v50
    gap, move, rng = o / pc - 1, c / pc - 1, h / l - 1
    news = (gap.abs() >= np.maximum(CFG["gap_min"], CFG["gap_adr"] * adr)) & (rv >= CFG["rv_news"])
    hi52 = h.shift().rolling(252, min_periods=120).max()
    lo52 = l.shift().rolling(252, min_periods=120).min()
    up52 = c > hi52
    dn52 = c < lo52
    fresh_up = up52 & ~up52.shift().rolling(20, min_periods=1).max().fillna(0).astype(bool)
    fresh_dn = dn52 & ~dn52.shift().rolling(20, min_periods=1).max().fillna(0).astype(bool)
    hiN = h.shift().rolling(CFG["hi_n"], min_periods=40).max()
    loN = l.shift().rolling(CFG["hi_n"], min_periods=40).min()
    span = (h.shift().rolling(CFG["base_n"]).max() / l.shift().rolling(CFG["base_n"]).min() - 1) / adr
    tight = span <= CFG["base_adr"]
    base_up = (c > hiN) & tight & ~fresh_up
    base_dn = (c < loN) & tight & ~fresh_dn
    vol_ok = rv >= CFG["rv_brk"]
    big_range = (rng >= CFG["range_adr"] * adr) & (rv >= CFG["rv_range"])
    return dict(adr=adr, v50=v50, rv=rv, gap=gap, move=move, news=news, brk=fresh_up & vol_ok, base=base_up & vol_ok,
                bdn=(fresh_dn | base_dn) & vol_ok, rng=big_range, c=c, h=h, l=l, v=v)


def build(adjusted, theme_data=None):
    uni = store.load_universe()
    tick = sorted(set(adjusted["ticker"].unique()) & uni)
    sub = adjusted[adjusted["ticker"].isin(tick)]
    piv = lambda k: sub.pivot_table(index="date", columns="ticker", values=k).sort_index()
    c = piv("c")
    W = {k: (c if k == "c" else piv(k).reindex_like(c)) for k in ("o", "h", "l", "v")}
    W["c"] = c
    F = frames(W)
    days = c.index
    d = len(days) - 1
    win = range(d - CFG["win"] + 1, d + 1)
    dv20 = (c * W["v"]).rolling(20, min_periods=10).mean()
    nbars = c.notna().cumsum()
    liq = (c.iloc[d] >= CFG["px"]) & (dv20.iloc[d] >= CFG["dvol"])
    # RS Rating for the last session over the whole universe (theme stocks keep the dashboard's own numbers)
    lq = (c >= config.MIN_PRICE) & (W["v"].rolling(20, min_periods=15).mean() >= config.MIN_AVG_VOLUME)
    raw = strength.rs_raw(c)
    bp = strength.breakpoints(raw.iloc[d], lq.iloc[d])
    rs_last = pd.Series(strength.rate(raw.iloc[d].to_numpy(), bp), index=c.columns)
    stocks = {s["t"]: s for s in ((theme_data or {}).get("stocks") or [])}
    names = store.load_names()
    sd = store.load_subthemes()
    sub_of = dict(zip(sd["ticker"], sd["subtheme"]))
    cat = _catalysts()
    deals = {s["t"] for s in stocks.values() if s.get("deal")}
    hi52 = W["h"].rolling(252, min_periods=60).max().iloc[d]
    rows, pool = [], {}
    for t in tick:
        if not bool(liq.get(t, False)) or t in deals:
            continue
        a = F["adr"][t].iloc[d]
        v50 = F["v50"][t].iloc[d]
        s = stocks.get(t) or {}
        if np.isfinite(a) and np.isfinite(v50):
            pool[t] = [round(float(a), 4), int(v50), sub_of.get(t, "")]
        why = []
        for j in win:
            day = str(days[j].date())
            ago = d - j
            g, mv, rv = F["gap"][t].iloc[j], F["move"][t].iloc[j], F["rv"][t].iloc[j]
            if bool(F["news"][t].iloc[j]):
                earn = (cat.get(t) or {}).get("earnings_date") == day
                why.append({"k": "earnings" if earn else "news", "date": day, "ago": ago,
                            "txt": f"{'earnings' if earn else 'news'} gap {g * 100:+.1f}%, closed {mv * 100:+.1f}% on {rv:.1f}x vol"})
            if bool(F["brk"][t].iloc[j]):
                why.append({"k": "breakout", "date": day, "ago": ago, "txt": f"52-wk high breakout {mv * 100:+.1f}% on {rv:.1f}x vol"})
            elif bool(F["base"][t].iloc[j]):
                why.append({"k": "base", "date": day, "ago": ago, "txt": f"base breakout {mv * 100:+.1f}% on {rv:.1f}x vol"})
            if bool(F["bdn"][t].iloc[j]):
                why.append({"k": "breakdown", "date": day, "ago": ago, "txt": f"breakdown {mv * 100:+.1f}% on {rv:.1f}x vol"})
            if bool(F["rng"][t].iloc[j]) and not bool(F["news"][t].iloc[j]):
                rr = (F["h"][t].iloc[j] / F["l"][t].iloc[j] - 1) / F["adr"][t].iloc[j]
                why.append({"k": "range", "date": day, "ago": ago, "txt": f"range {rr:.1f} ADRs, closed {mv * 100:+.1f}% on {rv:.1f}x vol"})
        nb = int(nbars[t].iloc[d])
        if nb < CFG["ipo_n"]:
            why.append({"k": "ipo", "date": str(days[d - nb + 1].date()), "ago": nb - 1, "txt": f"IPO {nb} sessions ago"})
        if not why:
            continue
        kinds = sorted({w["k"] for w in why}, key=lambda k: -PTS[k])
        rvw = F["rv"][t].iloc[list(win)].to_numpy(dtype=float)
        rvmax = float(np.nanmax(rvw)) if np.isfinite(rvw).any() else np.nan
        score = sum(PTS[k] for k in kinds) + (min(rvmax, 10) / 5 if np.isfinite(rvmax) else 0) + (1 if min(w["ago"] for w in why) == 0 else 0)
        c0 = c[t]
        dirn = float(c0.iloc[d] / c0.iloc[d - CFG["win"]] - 1) if nb > CFG["win"] else float(c0.iloc[d] / c0.dropna().iloc[0] - 1)
        e = (cat.get(t) or {}).get("earnings_date")
        rows.append({
            "t": t, "name": s.get("name") or names.get(t, ""), "sub": s.get("sub") or sub_of.get(t, ""),
            "rs": int(round(s["rsr"])) if s.get("rsr") is not None else int(rs_last.get(t)) if np.isfinite(rs_last.get(t, np.nan)) else None,
            "adr": round(float(a) * 100, 2) if np.isfinite(a) else None, "c": round(float(c0.iloc[d]), 2),
            "d1": round(float(F["move"][t].iloc[d]), 4) if np.isfinite(F["move"][t].iloc[d]) else None,
            "d5": round(dirn, 4), "rv1": round(float(F["rv"][t].iloc[d]), 2) if np.isfinite(F["rv"][t].iloc[d]) else None,
            "rvmax": round(rvmax, 2) if np.isfinite(rvmax) else None,
            "off_hi": round(float(c0.iloc[d] / hi52[t] - 1), 4) if np.isfinite(hi52.get(t, np.nan)) else None,
            "dvol": round(float(dv20[t].iloc[d]) / 1e6, 1), "kinds": kinds, "why": sorted(why, key=lambda w: w["ago"]),
            "ago": min(w["ago"] for w in why), "score": round(score, 2),
            "earn_next": e if e and e > str(days[d].date()) else None,
            "dir": "up" if dirn > 0 else "down",
        })
    rows.sort(key=lambda r: (r["ago"], -r["score"]))
    try:
        from . import unseen
        on = unseen.on_lists(theme_data or {}, {r["t"] for r in rows})
        for r in rows:
            r["on"] = on.get(r["t"], [])
    except Exception:
        pass
    counts = {k: sum(1 for r in rows if k in r["kinds"]) for k in PTS}
    return {"date": str(days[d].date()), "days": [str(days[j].date()) for j in win], "cfg": CFG, "rows": rows[:CFG["max_rows"]],
            "n": len(rows), "counts": counts, "pool": pool}


if __name__ == "__main__":   # python -m breadth.inplay → today's in-play list
    b = store.apply_splits(store.load_bars(), store.load_splits())
    X = build(b, json.load(open(config.DOCS_DIR / "data.json"))["themes"])
    print(X["date"], X["n"], X["counts"])
    for r in X["rows"][:30]:
        print(f"{r['t']:6} {r['score']:5.1f} ago {r['ago']} RS {r['rs']} · " + " | ".join(w["txt"] for w in r["why"][:3]))
