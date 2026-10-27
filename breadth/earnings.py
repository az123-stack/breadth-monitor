"""Earnings clusters: several companies in one group reporting the same thing in the same week (Adam, planned for the week of
Nov 2 2026, started Oct 27: "earnings results that together point to a theme, captured in the write-ups").

What it measures (bars only, so it runs every night and can be backtested)
  - A REACTION = a stock's earnings-style day: gap of at least max(3%, 1 ADR) on 2.5x+ its 50-day volume. Direction = how
    the day CLOSED vs the prior close (the market's verdict), "mixed" when the close moved less than half an ADR. When the
    catalyst agent saw an earnings date on that day (docs/agent/catalysts.json) the row is marked confirmed; otherwise the
    story writer confirms it with a search ("earnings" vs other news).
  - A CLUSTER = a sub-theme (3+ liquid members) with 2+ reactions in the last 5 sessions and at least 2/3 of them the same
    way. Read-through = how the group's members that did NOT react moved over the same window (vs SPY): the market treating
    the reports as a statement about the whole group.
  - Upcoming: members whose next earnings date (catalyst agent) falls in the next 5 sessions.

Evidence (`evidence`, recomputed each build; no look-ahead: cluster known at the close of its day, measured from the next
close): the group's equal-weight index over the next 20 sessions vs the average group, signed by the cluster's direction,
first cluster per group per 20 sessions, halves. Plus the drift of the members that hadn't reported yet (the read-through
trade). Information only; never touches the picks.
"""
import json

import numpy as np
import pandas as pd

from . import config, store

CFG = dict(gap_min=0.03, gap_adr=1.0, rvol=2.5, mixed_adr=0.5, win=5, min_react=2, agree=2 / 3, min_members=3,
           px=5.0, dvol=10e6, hold=20, cool=20, warm=60, max_rows=25, upcoming=5)


def _members():
    sd = store.load_subthemes()
    return sd.groupby("subtheme")["ticker"].apply(list).to_dict(), sd.groupby("subtheme")["group"].first().to_dict()


def _wide(adjusted, tickers):
    sub = adjusted[adjusted["ticker"].isin(tickers)]
    piv = lambda k: sub.pivot_table(index="date", columns="ticker", values=k).sort_index()
    c = piv("c")
    return {k: (c if k == "c" else piv(k).reindex_like(c)) for k in ("o", "h", "l", "c", "v")}


def frames(W):
    """Per stock per day: reaction flag (+1 / -1 / 0 mixed, NaN none), gap, day move, relative volume, ADR %."""
    o, h, l, c, v = (W[k] for k in ("o", "h", "l", "c", "v"))
    pc = c.shift()
    adr = ((h / l) - 1).rolling(20, min_periods=15).mean().shift()        # ADR known before the day
    v50 = v.rolling(50, min_periods=30).mean().shift()
    gap, move, rvol = o / pc - 1, c / pc - 1, v / v50
    liq = (pc >= CFG["px"]) & ((c * v).rolling(20, min_periods=15).mean().shift() >= CFG["dvol"])
    big = (gap.abs() >= np.maximum(CFG["gap_min"], CFG["gap_adr"] * adr)) & (rvol >= CFG["rvol"]) & liq
    d = np.sign(move).where(move.abs() >= CFG["mixed_adr"] * adr, 0.0)
    return {"react": d.where(big), "gap": gap, "move": move, "rvol": rvol, "adr": adr, "c": c, "liq": liq}


def clusters(F, members, win=CFG["win"]):
    """Every day x group: reactions in the window ending that day -> (n, up, down, direction or 0)."""
    R = F["react"]
    out = {}
    for g, tick in members.items():
        t = [x for x in tick if x in R.columns]
        if len(t) < CFG["min_members"]:
            continue
        r = R[t]
        up = (r > 0).astype(int).rolling(win, min_periods=1).sum().sum(axis=1)
        dn = (r < 0).astype(int).rolling(win, min_periods=1).sum().sum(axis=1)
        n = r.notna().astype(int).rolling(win, min_periods=1).sum().sum(axis=1)
        dirn = pd.Series(0, index=R.index)
        ok = n >= CFG["min_react"]
        dirn[ok & (up >= CFG["agree"] * n) & (up >= CFG["min_react"])] = 1
        dirn[ok & (dn >= CFG["agree"] * n) & (dn >= CFG["min_react"])] = -1
        out[g] = pd.DataFrame({"n": n, "up": up, "dn": dn, "dir": dirn})
    return out


def _idx(c, members):
    ret = (c / c.shift() - 1).clip(-0.6, 3.0)
    return pd.DataFrame({g: (1 + ret[[x for x in t if x in c.columns]].mean(axis=1, skipna=True).fillna(0.0)).cumprod()
                         for g, t in members.items() if len([x for x in t if x in c.columns]) >= CFG["min_members"]})


def _t(x):
    x = np.asarray([v for v in x if np.isfinite(v)])
    if len(x) < 3 or x.std(ddof=1) == 0:
        return None
    return round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))), 2)


def _stat(x):
    x = [v for v in x if np.isfinite(v)]
    if not x:
        return {"n": 0}
    h = len(x) // 2
    return {"n": len(x), "mean": round(float(np.mean(x)), 4), "win": round(float(np.mean([v > 0 for v in x])), 2), "t": _t(x),
            "h1": round(float(np.mean(x[:h])), 4) if h else None, "h2": round(float(np.mean(x[h:])), 4) if len(x) - h else None}


def evidence(F, CL, I, members, hold=CFG["hold"]):
    """Cluster day (first in `cool` sessions per group) -> group vs avg group next `hold` sessions from the NEXT close,
    signed by direction; and the members that had not reacted yet (read-through drift)."""
    days = I.index
    avg = I.pct_change().mean(axis=1).fillna(0)
    avgc = (1 + avg).cumprod()
    c, R = F["c"], F["react"]
    grp, rt, rows = [], [], []
    by = {"up": ([], []), "down": ([], [])}
    for g, df in CL.items():
        last = -10 ** 9
        dirs = df["dir"].to_numpy()
        for i in range(CFG["warm"], len(days) - hold - 1):
            if dirs[i] == 0 or i - last < CFG["cool"]:
                continue
            last = i
            D = float(dirs[i])
            a, b = i + 1, i + 1 + hold
            ex = float((I[g].iloc[b] / I[g].iloc[a]) / (avgc.iloc[b] / avgc.iloc[a]) - 1)
            t = [x for x in members[g] if x in c.columns]
            recent = R[t].iloc[max(0, i - CFG["win"] + 1):i + 1].notna().any()
            quiet = [x for x in t if not recent[x] and np.isfinite(c[x].iloc[a]) and np.isfinite(c[x].iloc[b])]
            rq = float(np.mean([c[x].iloc[b] / c[x].iloc[a] - 1 for x in quiet]) - (avgc.iloc[b] / avgc.iloc[a] - 1)) if quiet else np.nan
            grp.append(D * ex)
            rt.append(D * rq)
            k = "up" if D > 0 else "down"
            by[k][0].append(ex)
            by[k][1].append(rq)
            rows.append({"date": str(days[i].date()), "g": g, "dir": k, "ex": round(ex, 4), "quiet": round(rq, 4) if np.isfinite(rq) else None})
    rows.sort(key=lambda r: r["date"])
    return {"from": str(days[CFG["warm"]].date()) if len(days) > CFG["warm"] else None, "to": str(days[-hold - 2].date()) if len(days) > hold + 2 else None,
            "hold": hold, "signed": _stat(grp), "quiet": _stat(rt),
            "up": _stat(by["up"][0]), "down": _stat(by["down"][0]), "up_quiet": _stat(by["up"][1]), "down_quiet": _stat(by["down"][1]),
            "recent": rows[-12:]}


def _catalysts():
    try:
        return (json.loads((config.DOCS_DIR / "agent" / "catalysts.json").read_text()) or {}).get("stocks") or {}
    except Exception:
        return {}


def build(adjusted, theme_data=None, research=True):
    mem, sector = _members()
    tick = sorted({t for v in mem.values() for t in v} | {"SPY"})
    W = _wide(adjusted, tick)
    if "SPY" not in W["c"].columns or len(W["c"]) < CFG["warm"] + 10:
        return None
    F = frames(W)
    CL = clusters(F, mem)
    I = _idx(W["c"], mem)
    days = W["c"].index
    d = len(days) - 1
    a = d - CFG["win"]              # window start (close before the first session of the window)
    spy = W["c"]["SPY"]
    spy_w = float(spy.iloc[d] / spy.iloc[a] - 1)
    cat = _catalysts()
    stocks = {s["t"]: s for s in ((theme_data or {}).get("stocks") or [])}
    R = F["react"]
    rows = []
    for g, df in CL.items():
        n = int(df["n"].iloc[d])
        if n < 1:
            continue
        t = [x for x in mem[g] if x in R.columns]
        win = R[t].iloc[a + 1:d + 1]
        rep = []
        for x in t:
            hit = win[x].dropna()
            if hit.empty:
                continue
            day = hit.index[-1]
            j = days.get_loc(day)
            c0 = cat.get(x) or {}
            rep.append({"t": x, "date": str(day.date()), "dir": int(hit.iloc[-1]), "gap": round(float(F["gap"][x].iloc[j]), 4),
                        "move": round(float(F["move"][x].iloc[j]), 4), "rvol": round(float(F["rvol"][x].iloc[j]), 1),
                        "since": round(float(W["c"][x].iloc[d] / W["c"][x].iloc[j - 1] - 1), 4),
                        "conf": c0.get("earnings_date") == str(day.date()), "rs": (stocks.get(x) or {}).get("rsr")})
        quiet = [x for x in t if x not in {r["t"] for r in rep} and np.isfinite(W["c"][x].iloc[d]) and np.isfinite(W["c"][x].iloc[a])
                 and bool(F["liq"][x].iloc[d])]
        q = float(np.mean([W["c"][x].iloc[d] / W["c"][x].iloc[a] - 1 for x in quiet])) if quiet else None
        dirn = int(df["dir"].iloc[d])
        if dirn == 0 and len(rep) < CFG["min_react"]:
            continue                       # a single report isn't a theme
        up_next = sorted([{"t": x, "date": (cat.get(x) or {}).get("earnings_date")} for x in t
                          if (cat.get(x) or {}).get("earnings_date") and (cat[x]["earnings_date"] > str(days[d].date()))],
                         key=lambda r: r["date"])[:6]
        rows.append({"g": g, "sector": sector.get(g), "dir": {1: "up", -1: "down"}.get(dirn, "mixed"), "n": len(rep),
                     "members": len(t), "reports": sorted(rep, key=lambda r: r["date"]),
                     "grp": round(float(I[g].iloc[d] / I[g].iloc[a] - 1), 4) if g in I.columns else None,
                     "quiet": round(q, 4) if q is not None else None, "quiet_n": len(quiet), "quiet_names": quiet[:8],
                     "next": up_next})
    rows.sort(key=lambda r: (r["dir"] == "mixed", -r["n"], -abs(r["grp"] or 0)))
    out = {"date": str(days[d].date()), "window": [str(days[a + 1].date()), str(days[d].date())], "spy": round(spy_w, 4),
           "cfg": {k: CFG[k] for k in ("gap_min", "gap_adr", "rvol", "win", "min_react", "hold")},
           "rows": rows[:CFG["max_rows"]], "n_clusters": sum(1 for r in rows if r["dir"] != "mixed")}
    if research:
        out["evidence"] = evidence(F, CL, I, mem)
    return out


if __name__ == "__main__":     # python -m breadth.earnings  -> today's clusters + evidence (research)
    b = store.apply_splits(store.load_bars(), store.load_splits())
    r = build(b)
    print(json.dumps({k: r[k] for k in ("date", "window", "spy", "n_clusters")}, indent=1))
    for x in r["rows"][:12]:
        print(f"{x['g']:36s} {x['dir']:6s} {x['n']}/{x['members']} grp {x['grp']:+.1%} quiet {x['quiet'] if x['quiet'] is None else format(x['quiet'], '+.1%')} ",
              ", ".join(f"{y['t']} {y['move']:+.0%}" for y in x["reports"]))
    print(json.dumps(r["evidence"], indent=1))
