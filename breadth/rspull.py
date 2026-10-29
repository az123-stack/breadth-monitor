"""RS leaders pulling back (Oct 29, 2026; Adam: a trader he follows "finds tickers making new RS highs and waits for weakness on them
for the entry" — HNGE weekly chart with blue RS-new-high dots).

RS line = close ÷ SPY. An RS high = the RS line at its highest level of the past year (252 sessions). The idea: big money keeps
buying the stock relative to everything else; instead of chasing that strength, wait for the first dip into the daily 9 / 21 EMA
ribbon and buy the break of the dip day's high.

Code measures (no agent, info only, never touches the picks):
- `frames`: per day / ticker, liquid uptrend ($5+, $20M+/day, 21 EMA > 50 EMA, 50 EMA rising 10 sessions), RS high, sessions since
  the last RS high, ribbon touch (same rule as lifecycle / lined-up buys: low within 0.25 ADR of the 9/21 ribbon, close ≥ 21 EMA −
  0.5 ADR and ≤ 9 EMA + 1 ADR), first touch = no touch in the prior 5 sessions.
- `study`: every FIRST touch, traded like the live card: buy the break of the touch-day high within 3 sessions (fill = max(open,
  trigger)), stop = max(touch-day low, entry − 1 ADR), risk floored at 0.3 ADR, exit the close 10 / 20 sessions after entry (or the
  stop). Groups: RS high within 25 sessions ("rs") vs strong stocks (63-day return in the top 20%) with NO RS high in 60 sessions
  ("strong_no") vs every uptrend touch ("all"); recency buckets; RS-ahead (RS high while price was 3%+ below its 52-week high);
  market state (SPY over its 50-day, post-thrust window). Edge = same-day difference vs "strong_no" (t over days), and halves.
- `live`: today's names with an RS high within 30 sessions, their state (dipping / near / waiting) and the numbers the page needs to
  redo the state on live prices (same fields as lifecycle.live, so the page reuses `lineupState`).
"""
import numpy as np
import pandas as pd

from . import config

CFG = dict(min_price=5.0, min_dvol=20e6, look=252, recent=25, live_recent=30, no_recent=60, strong=0.8, touch=0.25, hold21=0.5,
           max9=1.0, fresh=3, trig_days=3, hold=20, hold_short=10, floor=0.3, warm=260, ahead=0.03, n_live=60, recent_trades=40)


def _r(x, n=3):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, n) if np.isfinite(x) else None


def frames(adjusted, bench=None):
    bench = bench or config.BENCHMARK
    piv = lambda k: adjusted.pivot_table(index="date", columns="ticker", values=k).sort_index()
    c = piv("c").astype("float64")
    o, h, l, v = (piv(k).reindex_like(c).astype("float64") for k in ("o", "h", "l", "v"))
    if bench not in c.columns:
        return None
    spy = c[bench]
    adr = ((h / l) - 1).rolling(20, min_periods=15).mean()
    dvol = (c * v).rolling(20, min_periods=15).mean()
    e9, e10, e21, e50 = (c.ewm(span=n, adjust=False, min_periods=n).mean() for n in (9, 10, 21, 50))
    rl = c.div(spy, axis=0)
    rs_hi = rl >= rl.rolling(CFG["look"], min_periods=200).max()
    hi52 = h.rolling(CFG["look"], min_periods=200).max()
    off = c / hi52 - 1
    # sessions since the last RS high (large when none)
    n = len(c)
    idx = np.arange(n)[:, None] * np.ones((1, c.shape[1]))
    last = np.where(rs_hi.to_numpy(), idx, np.nan)
    last = pd.DataFrame(last, index=c.index, columns=c.columns).ffill()
    since = pd.DataFrame(np.arange(n)[:, None] - last.to_numpy(), index=c.index, columns=c.columns)
    # RS high while price was still 3%+ under its 52-week high (RS leads price), remembered with the high
    ahead_day = rs_hi & (off <= -CFG["ahead"])
    ahead_last = pd.DataFrame(np.where(rs_hi.to_numpy(), ahead_day.to_numpy().astype(float), np.nan), index=c.index,
                              columns=c.columns).ffill().fillna(0).astype(bool)
    r63 = (c / c.shift(63) - 1).rank(axis=1, pct=True)
    up = (e21 > e50) & (e50 > e50.shift(10))
    liq = (c >= CFG["min_price"]) & (dvol >= CFG["min_dvol"])
    base = liq & up
    rib = np.maximum(e9, e21)
    touch = base & (l <= rib + CFG["touch"] * adr * c) & (c >= e21 - CFG["hold21"] * adr * c) & (c <= e9 + CFG["max9"] * adr * c)
    first = touch & ~touch.shift(1, fill_value=False).rolling(5, min_periods=1).max().astype(bool)
    return dict(c=c, o=o, h=h, l=l, adr=adr, dvol=dvol, e9=e9, e10=e10, e21=e21, e50=e50, rl=rl, rs_hi=rs_hi, since=since, off=off,
                ahead=ahead_last, r63=r63, base=base, touch=touch, first=first, spy=spy)


def _trades(F, mask):
    """Trade every True cell of `mask` with the live rule. Returns a DataFrame of trades."""
    c, o, h, l, adr, e10 = (F[k].to_numpy() for k in ("c", "o", "h", "l", "adr", "e10"))
    spy = F["spy"].to_numpy()
    days = F["c"].index
    n = len(days)
    H, H2, D = CFG["hold"], CFG["hold_short"], CFG["trig_days"]
    ii, jj = np.nonzero(mask.to_numpy())
    rows = []
    for i, j in zip(ii, jj):
        if i < CFG["warm"] or i + D + H >= n:
            continue
        a = adr[i, j]
        if not (np.isfinite(a) and a > 0):
            continue
        hi_i, lo_i = h[i, j], l[i, j]
        for k in range(i + 1, i + 1 + D):
            if h[k, j] >= hi_i:
                en = max(o[k, j], hi_i)
                st = max(lo_i, en * (1 - a))
                risk = max(en - st, CFG["floor"] * a * en)
                out = {}
                for lab, hh in (("R", H), ("R10", H2)):
                    lw = l[k:k + hh, j]
                    hit = np.flatnonzero(lw <= st)
                    ex = st if len(hit) else c[k + hh - 1, j]
                    out[lab] = (ex - en) / risk
                    if lab == "R":
                        out["ret"] = ex / en - 1
                        out["xs"] = ex / en - 1 - (spy[k + H - 1] / spy[k - 1] - 1)
                        out["stopped"] = bool(len(hit))
                # Adam's exit: stop as above, else sell on the first close under the 10 EMA (from the day after entry), max 20 sessions
                ex, xr = None, None
                for m in range(k, k + H):
                    if l[m, j] <= st:
                        ex = st; break
                    if m > k and c[m, j] < e10[m, j]:
                        ex = c[m, j]; break
                out["Rk"] = ((ex if ex is not None else c[k + H - 1, j]) - en) / risk
                rows.append((days[i], days[k], int(j), en, *[out[x] for x in ("R", "R10", "Rk", "ret", "xs", "stopped")]))
                break
    X = pd.DataFrame(rows, columns=["date", "edate", "j", "entry", "R", "R10", "Rk", "ret", "xs", "stopped"])
    X["Rc"] = X["R"].clip(upper=10)          # capped: a few tiny-risk trades print 30R+ and swamp the mean
    return X


def _stat(x, split):
    if not len(x):
        return {"n": 0}
    return {"n": int(len(x)), "R": _r(x["Rc"].mean()), "Rraw": _r(x["R"].mean()), "R10": _r(x["R10"].clip(upper=10).mean()),
            "Rk": _r(x["Rk"].clip(upper=10).mean()), "win": _r((x["R"] > 0).mean()), "winK": _r((x["Rk"] > 0).mean()),
            "xs": _r(x["xs"].mean(), 4), "xs_med": _r(x["xs"].median(), 4), "stop": _r(x["stopped"].mean()),
            "h1": _r(x[x["date"] < split]["Rc"].mean()), "h2": _r(x[x["date"] >= split]["Rc"].mean()),
            "k1": _r(x[x["date"] < split]["Rk"].clip(upper=10).mean()), "k2": _r(x[x["date"] >= split]["Rk"].clip(upper=10).mean())}


def _edge(a, b, col="Rc"):
    d = (a.groupby("date")[col].mean() - b.groupby("date")[col].mean()).dropna()
    if len(d) < 3 or d.std(ddof=1) == 0:
        return {"edge": _r(d.mean()) if len(d) else None, "t": None, "days": int(len(d))}
    return {"edge": _r(d.mean()), "t": _r(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))), 2), "days": int(len(d))}


def study(F, history=None):
    first, since, r63 = F["first"], F["since"], F["r63"]
    all_ = _trades(F, first)
    if not len(all_):
        return None
    cols = F["c"].columns
    days = F["c"].index
    di = {d: i for i, d in enumerate(days)}
    I = all_["date"].map(di).to_numpy()
    J = all_["j"].to_numpy()
    s = since.to_numpy()[I, J]
    all_["since"] = s
    all_["strong"] = r63.to_numpy()[I, J] >= CFG["strong"]
    all_["ahead"] = F["ahead"].to_numpy()[I, J]
    spy = F["spy"]
    all_["spy50"] = (spy > spy.ewm(span=50, adjust=False).mean()).to_numpy()[I]
    if history is not None:
        try:
            from . import metrics
            tw = metrics.thrust_window(history, list(days))
            all_["thrust"] = tw[I]
        except Exception:
            all_["thrust"] = False
    else:
        all_["thrust"] = False
    all_["t"] = [cols[j] for j in J]
    split = all_["date"].sort_values().iloc[len(all_) // 2]
    rs = all_[all_["since"] <= CFG["recent"]]
    strong_no = all_[all_["strong"] & (all_["since"] > CFG["recent"])]
    out = {"from": str(all_["date"].min().date()), "to": str(all_["date"].max().date()), "split": str(split.date()),
           "rule": "first dip into the daily 9/21 EMA ribbon; buy the break of the dip-day high within 3 sessions; stop the dip-day "
                   "low (max 1 ADR); exit the close 20 sessions later or at the stop",
           "groups": {"rs": _stat(rs, split), "strong_no": _stat(strong_no, split), "all": _stat(all_, split),
                      "rs_ahead": _stat(rs[rs["ahead"]], split), "rs_atprice": _stat(rs[~rs["ahead"]], split)},
           "buckets": [], "market": {}}
    for lo, hi, lab in ((0, 5, "RS high 0–5 sessions before the dip"), (6, 10, "6–10 sessions"), (11, 25, "11–25 sessions"),
                        (26, 60, "26–60 sessions"), (61, 10 ** 9, "no RS high in 60 sessions")):
        x = all_[(all_["since"] >= lo) & (all_["since"] <= hi)]
        out["buckets"].append({"label": lab, **_stat(x, split)})
    e = _edge(rs, strong_no)
    e1 = _edge(rs[rs["date"] < split], strong_no[strong_no["date"] < split])
    e2 = _edge(rs[rs["date"] >= split], strong_no[strong_no["date"] >= split])
    out["edge"] = {**e, "h1": e1["edge"], "h2": e2["edge"]}
    ek = _edge(rs, strong_no, "Rk")
    out["edge_k"] = {**ek, "h1": _edge(rs[rs["date"] < split], strong_no[strong_no["date"] < split], "Rk")["edge"],
                     "h2": _edge(rs[rs["date"] >= split], strong_no[strong_no["date"] >= split], "Rk")["edge"]}
    ex = _edge(rs, strong_no, "xs")
    out["edge_xs"] = ex
    out["edge_all"] = _edge(rs, all_)
    for lab, m in (("SPY over its 50-day", "spy50"), ("SPY under its 50-day", None), ("Post-thrust window", "thrust")):
        if m is None:
            a, b = rs[~rs["spy50"]], strong_no[~strong_no["spy50"]]
        else:
            a, b = rs[rs[m]], strong_no[strong_no[m]]
        out["market"][lab] = {"rs": _stat(a, split), "strong_no": _stat(b, split)}
    g = out["groups"]["rs"]
    ok = (out["edge"]["t"] is not None and out["edge"]["t"] >= 2 and (out["edge"]["h1"] or 0) > 0 and (out["edge"]["h2"] or 0) > 0
          and g["n"] >= 30 and (g.get("R") or 0) > 0 and (out["edge_k"]["edge"] or 0) > 0)   # must also make money on its own and with Adam's exit
    out["verdict"] = "proven" if ok else ("helps" if (out["edge"]["edge"] or 0) > 0 else "no_edge")
    rec = rs.sort_values("edate", ascending=False).head(CFG["recent_trades"])
    out["recent"] = [{"t": r.t, "date": str(r.date.date()), "entry_date": str(r.edate.date()), "entry": _r(r.entry, 2), "R": _r(r.R, 2),
                      "since": int(r.since)} for r in rec.itertuples()]
    out["curve"] = [_r(v, 2) for v in rs.sort_values("edate")["R"].cumsum().to_numpy()[::5]]
    return out


def live(F, theme_data=None):
    T = theme_data or {}
    stocks = {s["t"]: s for s in (T.get("stocks") or [])}
    names = {}
    try:
        from . import store
        names = store.load_names()
    except Exception:
        pass
    i = len(F["c"]) - 1
    base, since = F["base"].iloc[i], F["since"].iloc[i]
    rows = []
    for t in F["c"].columns:
        if t == config.BENCHMARK or not bool(base.get(t, False)):
            continue
        sn = since.get(t)
        if sn is None or not np.isfinite(sn) or sn > CFG["live_recent"]:
            continue
        c, a = F["c"][t].iat[i], F["adr"][t].iat[i]
        e9, e21 = F["e9"][t].iat[i], F["e21"][t].iat[i]
        if not all(np.isfinite(x) for x in (c, a, e9, e21)) or a <= 0:
            continue
        t3 = bool(F["touch"][t].iloc[i - CFG["fresh"] + 1:i + 1].any())
        d9 = (c - e9) / (a * c)
        rib = max(e9, e21)
        state = "dip" if t3 else "near" if c <= rib * (1 + a) else "wait"
        s = stocks.get(t) or {}
        rows.append({"t": t, "name": (s.get("name") or names.get(t) or "")[:40], "sub": s.get("sub") or "", "rsr": s.get("rsr"),
                     "since": int(sn), "today": bool(sn == 0), "ahead": bool(F["ahead"][t].iat[i]), "state": state,
                     "c": _r(c, 2), "hi": _r(F["h"][t].iat[i], 2), "lo": _r(F["l"][t].iat[i], 2), "e9": _r(e9, 3), "e21": _r(e21, 3),
                     "adr": _r(a, 4), "t3": t3, "d9": _r(d9, 2), "off": _r(F["off"][t].iat[i], 4),
                     "dvol": _r(F["dvol"][t].iat[i] / 1e6, 1), "r63": _r(F["r63"][t].iat[i], 3)})
    order = {"dip": 0, "near": 1, "wait": 2}
    rows.sort(key=lambda r: (order[r["state"]], -(r["rsr"] or r["r63"] * 99 or 0)))
    return rows[:CFG["n_live"] * 3]


def build(adjusted, theme_data=None, history=None, evidence_on=True):
    F = frames(adjusted)
    if F is None:
        return None
    out = {"date": str(F["c"].index[-1].date()), "cfg": {k: CFG[k] for k in ("recent", "live_recent", "no_recent", "hold", "min_price",
                                                                            "min_dvol")},
           "rows": live(F, theme_data)}
    if evidence_on:
        out["evidence"] = study(F, history)
    return out


if __name__ == "__main__":   # python -m breadth.rspull : print the backtest
    import json
    from . import store
    b = store.load_bars()
    a = store.apply_splits(b, store.load_splits())
    try:
        hist = store.load_breadth()
    except Exception:
        hist = None
    X = build(a, None, hist)
    E = X["evidence"]
    print(json.dumps({k: E[k] for k in ("from", "to", "groups", "buckets", "edge", "edge_k", "edge_xs", "edge_all", "market", "verdict")}))
    print("live rows:", len(X["rows"]), [r["t"] for r in X["rows"][:15]])
