"""Launch list (Adam, Oct 25 2026; card R-2026-10-25-what-made-them-go, layer `launch`, info only).

Stocks sitting where CDNA / DINO / NTRA sat before they went: out of a long base through the 50-week EMA, the 9 WEMA
over a rising 21, not yet extended. Each is scored 0-4 on the tells that separated the ones that went in the study:
  1. group  - its sub-theme is in the top third of sub-themes on 13-week return (the strongest tell, both halves)
  2. rs     - RS Rating 70+
  3. rsline - RS line (price / SPY) up 15%+ over 13 weeks
  4. gap    - a 6%+ gap-up day in the last 13 weeks (earnings / news)
Volume was tested and added nothing, so it is not scored. The group point is the gatekeeper: with it, 13-week returns beat
SPY at every score; without it even 3 other points lagged SPY (those names only "went" more because they swing harder).
Grades: A = group + 2-3 others, B = group + 0-1 others, C = no group point (or no sub-theme). Size A names smaller: they swing more.

Names = the tested setup ("fresh": 2-8 weekly closes over the 50 WEMA after 20+ of 40 weeks under it) plus every
Strength on Weakness row (Adam's watchlist), all scored the same way. The evidence is recomputed every build on the
fresh setup: entry next session's open, best high within 26 weeks, 13-week return vs SPY, lost the 50 WEMA within 13 weeks.
Never touches the picks."""
import numpy as np
import pandas as pd

CFG = {"min_price": 5.0, "min_dvol": 10e6, "run_lo": 2, "run_hi": 8, "base_wk": 40, "base_below": 20, "ext_atr": 3.0,
       "grp_top": 2 / 3, "grp_wk": 13, "grp_min": 3, "rs_min": 70, "rsl_wk": 13, "rsl_min": 0.15, "gap_days": 65, "gap_min": 0.06,
       "warm": 40, "hold": 26, "mid": 13, "went": 0.5, "gap_every": 26}
POINTS = [("group", "Group leading", "Its sub-theme is in the top third of sub-themes on 13-week return. The strongest tell in the study."),
          ("rs", "RS 70+", "RS Rating 70 or higher."),
          ("rsline", "RS line rising", "RS line (price ÷ SPY) up 15%+ over 13 weeks."),
          ("gap", "Gap day", "A 6%+ gap-up day in the last 13 weeks (earnings or news put it in play).")]


def _r(x, n=2):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def frames(w, cols, subthemes, bench="SPY"):
    """Weekly frames for every rule and point. All values known at each week's close."""
    from . import sow, strength
    dC, dO, dH, dL, dV = (w[k][cols] for k in ("c", "o", "h", "l", "v"))
    days = dC.index
    dvol = (dC * dV).rolling(20, min_periods=15).mean()
    raw = strength.rs_raw(dC)
    liqd = (dC >= CFG["min_price"]) & (dvol >= CFG["min_dvol"])
    rsd = (raw.where(liqd).rank(axis=1, pct=True) * 99).clip(1, 99)
    gapd = (dO / dC.shift() - 1).rolling(CFG["gap_days"], min_periods=20).max()
    W, nday = sow.weekly(w, cols)
    c, h, l = W["c"], W["h"], W["l"]
    wd = c.index
    ema = lambda x, n: x.ewm(span=n, adjust=False, min_periods=1).mean()
    e9, e21, e50 = ema(c, 9), ema(c, 21), ema(c, 50)
    pc = c.shift()
    tr = np.maximum(h - l, np.maximum((h - pc).abs(), (l - pc).abs()))
    atr = (tr / c).rolling(10, min_periods=6).mean()
    ab = (c > e50).astype(int)
    cs = ab.cumsum()
    run = cs - cs.where(ab == 0).ffill().fillna(0)
    below = (c < e50).astype(float).rolling(CFG["base_wk"], min_periods=30).sum()
    liq = (c >= CFG["min_price"]) & (dvol.reindex(wd)[cols] >= CFG["min_dvol"])
    zone = liq & (below >= CFG["base_below"]) & (e9 > e21) & (e21 > e21.shift(4)) & (c <= e50 * (1 + CFG["ext_atr"] * atr))
    fresh = zone & (run >= CFG["run_lo"]) & (run <= CFG["run_hi"])
    spy = w["c"][bench].groupby(days.to_period("W-FRI")).last()
    spy.index = wd
    rsl = c.div(spy, axis=0)
    rsl13 = rsl / rsl.shift(CFG["rsl_wk"]) - 1
    sub_of = dict(zip(subthemes["ticker"], subthemes["subtheme"])) if subthemes is not None and len(subthemes) else {}
    members = {}
    for t in cols:
        if t in sub_of:
            members.setdefault(sub_of[t], []).append(t)
    g = {k: (c[m] / c[m].shift(CFG["grp_wk"]) - 1).clip(-0.9, 3).mean(axis=1) for k, m in members.items() if len(m) >= CFG["grp_min"]}
    grank = pd.DataFrame(g).rank(axis=1, pct=True) if g else pd.DataFrame(index=wd)
    gr = pd.DataFrame({t: grank[sub_of[t]] for t in cols if sub_of.get(t) in grank.columns}, index=wd).reindex(columns=cols)
    rs_w = rsd.reindex(wd)
    gap_w = gapd.reindex(wd)
    pts = {"group": gr >= CFG["grp_top"], "rs": rs_w >= CFG["rs_min"], "rsline": rsl13 >= CFG["rsl_min"], "gap": gap_w >= CFG["gap_min"]}
    score = sum(p.astype(int) for p in pts.values())
    return {"W": W, "nday": nday, "wd": wd, "days": days, "e9": e9, "e21": e21, "e50": e50, "atr": atr, "run": run, "below": below,
            "zone": zone, "fresh": fresh, "rs": rs_w, "rsl13": rsl13, "grank": gr, "gap": gap_w, "pts": pts, "score": score,
            "sub_of": sub_of, "dO": dO, "dH": dH, "dC": dC, "dvol": dvol, "rsd": rsd}


def grade(group, score):
    return "A" if group and score >= 3 else "B" if group else "C"


def _sum(x):
    if not len(x):
        return {"n": 0}
    return {"n": int(len(x)), "went": _r(float(np.mean(x["maxg"] >= CFG["went"])), 3), "best": _r(float(np.median(x["maxg"])), 3),
            "x13": _r(float(np.nanmedian(x["x13"])), 3) if np.isfinite(x["x13"]).any() else None,
            "lost": _r(float(np.mean(x["lost"])), 3), "atr": _r(float(np.median(x["atr"])), 3)}


def evidence(F, w, bench="SPY"):
    """Every fresh setup (first per stock per 26 weeks) with 26 weeks of future: outcomes by score."""
    days, wd = F["days"], F["wd"]
    M = F["fresh"].to_numpy().copy()
    M[:CFG["warm"]] = False
    O, H, C = F["dO"].to_numpy(), F["dH"].to_numpy(), F["dC"].to_numpy()
    WC, E50 = F["W"]["c"].to_numpy(), F["e50"].to_numpy()
    S, A = F["score"].to_numpy(), F["atr"].to_numpy()
    G = F["grank"].to_numpy()
    PG = F["pts"]["group"].to_numpy()
    spy = w["c"][bench].to_numpy()
    ent_i = days.searchsorted(wd, side="right")
    hd, md = CFG["hold"] * 5, CFG["mid"] * 5
    last = {}
    rows = []
    for i in range(len(wd)):
        a = ent_i[i]
        if a + hd > len(days):
            break
        for j in np.flatnonzero(M[i]):
            if j in last and i - last[j] < CFG["gap_every"]:
                continue
            last[j] = i
            e = O[a, j]
            if not np.isfinite(e) or e <= 0:
                continue
            mx = np.nanmax(H[a:a + hd, j]) / e - 1
            r13 = C[a + md, j] / e - 1 if a + md < len(days) else np.nan
            s13 = spy[a + md] / spy[a] - 1 if a + md < len(days) else np.nan
            lost = bool(np.any(WC[i + 1:i + 1 + CFG["mid"], j] < E50[i + 1:i + 1 + CFG["mid"], j]))
            rows.append((wd[i], S[i, j], np.isfinite(G[i, j]), mx, r13 - s13, lost, A[i, j], grade(bool(PG[i, j]), int(S[i, j]))))
    if not rows:
        return None
    X = pd.DataFrame(rows, columns=["date", "score", "grp", "maxg", "x13", "lost", "atr", "grade"])
    split = X["date"].sort_values().iloc[len(X) // 2]
    out = {"from": str(X["date"].min().date()), "to": str(X["date"].max().date()), "n": int(len(X)), "all": _sum(X),
           "by_score": {str(k): _sum(X[X["score"] == k]) for k in range(5)}, "grp_share": _r(float(X["grp"].mean()), 3),
           "by_grade": {k: _sum(X[X["grade"] == k]) for k in "ABC"},
           "halves": {h: {k: _sum(g[g["grade"] == k]) for k in "ABC"}
                      for h, g in (("h1", X[X["date"] < split]), ("h2", X[X["date"] >= split]))}}
    return out


def build(adjusted, universe, stocks=None, names=None, sow_payload=None, subthemes=None, evidence_on=True):
    from . import strength, config, store
    names = names or {}
    info = {r["t"]: r for r in (stocks or [])}
    w = strength.wide_all(adjusted)
    uni = set(universe)
    cols = [t for t in w["c"].columns if t in uni]
    if len(w["c"].index) < 250 or not cols or config.BENCHMARK not in w["c"]:
        return None
    if subthemes is None:
        subthemes = store.load_subthemes()
    F = frames(w, cols, subthemes, config.BENCHMARK)
    wi = len(F["wd"]) - 1
    di = len(F["days"]) - 1
    sow_rows = {r["t"]: r for r in ((sow_payload or {}).get("rows") or [])}
    W = F["W"]
    adr = ((w["h"][cols] / w["l"][cols]) - 1).rolling(20, min_periods=15).mean().iloc[-1] * 100
    gap_day = (F["dO"] / F["dC"].shift() - 1).iloc[-CFG["gap_days"]:]
    rows = []
    for j, t in enumerate(cols):
        fresh = bool(F["fresh"].iat[wi, j])
        s = sow_rows.get(t)
        if not fresh and not s:
            continue
        pts = {k: bool(F["pts"][k].iat[wi, j]) for k, _, _ in POINTS}
        gser = gap_day[t]
        gmax = gser.max()
        gdate = str(gser.idxmax().date()) if np.isfinite(gmax) else None
        c = W["c"].iat[wi, j]
        e50, e9, e21, atr = F["e50"].iat[wi, j], F["e9"].iat[wi, j], F["e21"].iat[wi, j], F["atr"].iat[wi, j]
        ir = info.get(t, {})
        sc = int(sum(pts.values()))
        rows.append({"t": t, "grade": grade(pts["group"], sc), "early": bool(F["run"].iat[wi, j] <= CFG["run_hi"]), "name": names.get(t, ir.get("name", "")), "sub": F["sub_of"].get(t), "theme": (ir.get("themes") or [None])[0],
                     "score": sc, "pts": pts, "fresh": fresh, "sow": s.get("state") if s else None,
                     "prime": bool(s.get("prime")) if s else False, "grank": _r(F["grank"].iat[wi, j], 3), "rs": _r(F["rs"].iat[wi, j], 0),
                     "rsl13": _r(F["rsl13"].iat[wi, j], 3), "gap": _r(gmax, 3), "gap_date": gdate if (gmax or 0) >= CFG["gap_min"] else None,
                     "run": int(F["run"].iat[wi, j]), "ext": _r((c / e50 - 1) / atr if atr else np.nan, 2), "atr": _r(atr * 100, 1),
                     "adr": _r(adr.get(t, np.nan), 1), "price": _r(c, 2), "e9": _r(e9, 2), "e21": _r(e21, 2), "e50": _r(e50, 2),
                     "vs50": _r(c / e50 - 1, 3), "dvol": _r(F["dvol"][t].iat[di] / 1e6, 0)})
    rows.sort(key=lambda r: (r["grade"], -r["score"], not r["early"], -(r["grank"] or 0), -(r["rs"] or 0)))
    from . import sow
    done = bool(sow.complete_weeks(F["nday"], F["days"][-1])[-1])
    out = {"date": str(F["days"][-1].date()), "week": str(F["wd"][-1].date()), "week_done": done, "week_days": int(F["nday"].iloc[-1]),
           "cfg": CFG, "points": [{"key": k, "name": n, "desc": d} for k, n, d in POINTS], "rows": rows,
           "counts": {k: sum(1 for r in rows if r["grade"] == k) for k in "ABC"}}
    if evidence_on:
        out["evidence"] = evidence(F, w, config.BENCHMARK)
    return out
