"""Version-2 measures: RS Rating, Theme Strength, tightness and setup lists.

All computed from stored daily OHLCV for the whole US common-stock universe,
so RS Rating ranks a stock against the market rather than against itself.

RS Rating (1-99): percentile of a weighted 3/6/9/12-month return
  (40/20/20/20, the IBD-style weighting) among liquid US stocks.
  Missing longer horizons are dropped and the weights renormalised.
RS line new high: close / SPY at its highest level of the last year.

Theme Strength (0-100): cross-sectional percentile composite across groups of
  - relative performance: median member return minus SPY over 5/15/30/60/90 days
  - participation: share of members above their 21- and 50-day EMAs
  - leadership: median member RS Rating
  "Today" is deliberately left out so one session can't reshuffle the ranks.

Tightness (per stock): ADR% (20-day average daily range), 5-day range as a
  multiple of ADR, narrow-range-7 and inside days, volume dry-up (5d/50d),
  distance from the 52-week high.
"""
import numpy as np
import pandas as pd

from . import config

RS_W = [(63, 0.4), (126, 0.2), (189, 0.2), (252, 0.2)]
STR_HORIZONS = [(5, 0.15), (15, 0.20), (30, 0.25), (60, 0.20), (90, 0.20)]
STR_WEIGHTS = {"rel": 0.5, "part": 0.25, "lead": 0.25}


def wide_all(adjusted):
    p = lambda col: adjusted.pivot(index="date", columns="ticker", values=col).sort_index().astype("float64")
    c = p("c")
    return {"o": p("o").reindex_like(c), "h": p("h").reindex_like(c), "l": p("l").reindex_like(c),
            "c": c, "v": p("v").reindex_like(c)}


# ---------------------------------------------------------------------------
# RS Rating
# ---------------------------------------------------------------------------
def rs_raw(close):
    num = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    den = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for n, w in RS_W:
        r = close / close.shift(n) - 1
        num += (w * r).fillna(0)
        den += w * r.notna()
    raw = num / den.replace(0, np.nan)
    return raw.where((close / close.shift(RS_W[0][0])).notna())


def breakpoints(raw_row, liquid_row):
    v = raw_row[liquid_row & raw_row.notna()].to_numpy()
    if len(v) < 50:
        return None
    return np.percentile(v, np.arange(1, 100))   # 99 cut points


def rate(raw_values, bp):
    """Map raw scores to 1-99 using a day's breakpoints."""
    if bp is None:
        return np.full(len(raw_values), np.nan)
    out = np.searchsorted(bp, raw_values, side="right").astype(float)
    out = np.clip(out, 1, 99)
    out[np.isnan(raw_values)] = np.nan
    return out


def rs_ratings(close, liquid, days):
    """RS Rating for every ticker on each row index in `days`. Returns
    (DataFrame of ratings indexed by those dates, dict of breakpoints by row)."""
    raw = rs_raw(close)
    out, bps = {}, {}
    for i in days:
        bp = breakpoints(raw.iloc[i], liquid.iloc[i])
        bps[i] = bp
        out[close.index[i]] = pd.Series(rate(raw.iloc[i].to_numpy(), bp), index=close.columns)
    return pd.DataFrame(out).T, bps, raw


def rs_line_flags(close, spy):
    """RS line (close/SPY) at a 1-year high today (star), and 'RS leads price' (flag):
    the RS line made a new 1-year high within the last LEAD_DAYS sessions while
    price is still 3%+ below its own 52-week high - relative strength out in
    front of price, the classic early tell."""
    if spy is None:
        return None, None
    rsl = close.div(spy, axis=0)
    nh = rsl >= rsl.rolling(252, min_periods=120).max() * 0.999
    recent = nh.astype(float).rolling(LEAD_DAYS, min_periods=1).max() > 0
    price_hi = close >= close.rolling(252, min_periods=120).max() * 0.97
    return nh, recent & ~price_hi


LEAD_DAYS = 5


# ---------------------------------------------------------------------------
# Tightness
# ---------------------------------------------------------------------------
def tightness(w):
    o, h, l, c, v = w["o"], w["h"], w["l"], w["c"], w["v"]
    rng = (h / l - 1) * 100
    adr = rng.rolling(20, min_periods=15).mean()
    r5 = (h.rolling(5).max() / l.rolling(5).min() - 1) * 100
    t = {
        "adr": adr,
        "tight5": r5 / adr,                                   # 5-day range in ADRs (lower = tighter)
        "nr7": (h - l) <= (h - l).rolling(7).min() * 1.0001,
        "inside": (h <= h.shift(1)) & (l >= l.shift(1)),
        "vdry": v.rolling(5).mean() / v.rolling(50, min_periods=30).mean(),
        "off_high": c / h.rolling(252, min_periods=60).max() - 1,
        "ema10": c.ewm(span=10, adjust=False, min_periods=10).mean(),
        "ema20": c.ewm(span=20, adjust=False, min_periods=20).mean(),
        "ema50": c.ewm(span=50, adjust=False, min_periods=50).mean(),
        "chg": c / c.shift(1) - 1,
        "range_pos": (c - l) / (h - l).replace(0, np.nan),
        "gap": o / c.shift(1) - 1,
        "vol50": v.rolling(50, min_periods=30).mean(),
        "d60": c / c.shift(60) - 1,
    }
    return t


# ---------------------------------------------------------------------------
# Theme Strength
# ---------------------------------------------------------------------------
def group_inputs(close, ema21, ema50, rating_row, members, i, spy_ret):
    """Raw (un-ranked) strength inputs for every group at row i."""
    rows = {}
    for g, tick in members.items():
        tick = [t for t in tick if t in close.columns]
        if not tick:
            continue
        c = close.iloc[i][tick]
        ok = c.notna()
        if ok.sum() == 0:
            continue
        rel, wsum = 0.0, 0.0
        for n, wt in STR_HORIZONS:
            if i - n < 0:
                continue
            r = (c / close.iloc[i - n][tick] - 1)[ok].dropna()
            if len(r) == 0 or spy_ret.get(n) is None:
                continue
            rel += wt * (float(r.median()) - spy_ret[n])
            wsum += wt
        e21 = ema21.iloc[i][tick][ok]; e50 = ema50.iloc[i][tick][ok]
        part = float(((c[ok] > e21).mean() + (c[ok] > e50).mean()) / 2)
        rr = rating_row.reindex(tick)[ok].dropna() if rating_row is not None else pd.Series(dtype=float)
        rows[g] = {"rel": rel / wsum if wsum else np.nan, "part": part,
                   "lead": float(rr.median()) if len(rr) else np.nan, "n": int(ok.sum())}
    return pd.DataFrame(rows).T


def group_inputs_many(close, ema21, ema50, ratings, members, rows, spy):
    """Same numbers as group_inputs, for many rows at once (numpy, ~50x faster).
    Returns {row index: DataFrame like group_inputs}."""
    cols = {t: k for k, t in enumerate(close.columns)}
    C, E21, E50 = close.to_numpy(float), ema21.to_numpy(float), ema50.to_numpy(float)
    R = ratings.reindex(columns=close.columns) if ratings is not None else None
    Rv = R.to_numpy(float) if R is not None else None
    rpos = {d: k for k, d in enumerate(R.index)} if R is not None else {}
    S = spy.to_numpy(float)
    gidx = {g: np.array([cols[t] for t in tick if t in cols], dtype=int) for g, tick in members.items()}
    gidx = {g: ix for g, ix in gidx.items() if len(ix)}
    out = {}
    with np.errstate(invalid="ignore", divide="ignore"):
        for i in rows:
            ri = rpos.get(close.index[i])
            res = {}
            for g, ix in gidx.items():
                c = C[i, ix]
                ok = ~np.isnan(c)
                if not ok.any():
                    continue
                rel, wsum = 0.0, 0.0
                for n, wt in STR_HORIZONS:
                    if i - n < 0:
                        continue
                    r = c[ok] / C[i - n, ix][ok] - 1
                    r = r[~np.isnan(r)]
                    if len(r) == 0:
                        continue
                    rel += wt * (float(np.median(r)) - float(S[i] / S[i - n] - 1))
                    wsum += wt
                part = float(((c[ok] > E21[i, ix][ok]).mean() + (c[ok] > E50[i, ix][ok]).mean()) / 2)
                lead = np.nan
                if ri is not None:
                    rr = Rv[ri, ix][ok]
                    rr = rr[~np.isnan(rr)]
                    lead = float(np.median(rr)) if len(rr) else np.nan
                res[g] = {"rel": rel / wsum if wsum else np.nan, "part": part, "lead": lead, "n": int(ok.sum())}
            out[i] = pd.DataFrame(res).T
    return out


TIMELINE_DAYS = 90   # strength history kept for the Themes timeline heatmap
PAIR_DAYS = 180      # sessions of equal-weight group index for the pair charts

SHRINK_N = 5   # groups with fewer members are pulled toward the middle


def strength_scores(inp):
    """Percentile composite across groups -> 0-100. Small groups are shrunk
    toward 50 (a one-stock bucket can't be the strongest theme on its own)."""
    if inp.empty:
        return pd.Series(dtype=float)
    s = 0.0
    for k, w in STR_WEIGHTS.items():
        s = s + w * inp[k].rank(pct=True).fillna(0.5)
    s = s * 100
    k = (inp["n"].astype(float) / SHRINK_N).clip(upper=1.0)
    return (50 + (s - 50) * k).round(1)


# ---------------------------------------------------------------------------
# Everything v2 for the dashboard payload
# ---------------------------------------------------------------------------
def mega_caps():
    """Google market caps (S&P 500 + Nasdaq-100 rows) from the close snapshot; {} if the file is missing."""
    try:
        from . import story
        rows, _ = story.read_csv_rows((config.DATA_DIR / "close_snapshot.csv").read_text())
    except Exception:
        return {}
    return {k: r["marketcap"] for k, r in rows.items() if r.get("marketcap")}


def _r(v, nd=4):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if (np.isnan(v) or np.isinf(v)) else round(v, nd)


def build_v2(adjusted, universe, members, sub_members, names, focus, hist_days=30):
    """Returns a dict with per-ticker v2 fields (for `focus` tickers), group
    strength tables with history, RS breakpoints for the live layer, and the
    universe-wide setup lists for the latest day."""
    from . import setups as SU
    w = wide_all(adjusted)
    c = w["c"]
    dates = c.index
    N = len(dates)
    last = N - 1
    uni = pd.Series(c.columns.isin(list(universe)), index=c.columns)
    liquid = (c >= config.MIN_PRICE) & (w["v"].rolling(20, min_periods=15).mean() >= config.MIN_AVG_VOLUME) & uni
    spy = c[config.BENCHMARK] if config.BENCHMARK in c.columns else None

    days = list(range(RS_W[0][0], N))   # full history: also feeds the setup stats
    ratings, bps, raw = rs_ratings(c, liquid, days)
    nh, lead = rs_line_flags(c, spy)
    t = tightness(w)
    ema21 = c.ewm(span=21, adjust=False, min_periods=21).mean()
    ema50 = t["ema50"]

    # ---- group strength, with history for rank change and trail ----
    tl_days = max(hist_days, TIMELINE_DAYS)

    def strength_hist(mem):
        hist = {}
        if spy is None:
            return hist
        rows = list(range(max(91, last - tl_days + 1), N))
        for i, inp in group_inputs_many(c, ema21, ema50, ratings, mem, rows, spy).items():
            sc = strength_scores(inp)
            hist[i] = (inp, sc, sc.rank(ascending=False, method="first"))
        return hist

    tl_idx = []
    day_ret = (c / c.shift(1) - 1).clip(-0.6, 3.0)
    px_rows = day_ret.iloc[-(PAIR_DAYS - 1):]

    def group_index(tick):
        """Equal-weight index of the group's members (start 100), last PAIR_DAYS sessions."""
        tick = [t for t in tick if t in px_rows.columns]
        if not tick:
            return None
        m = px_rows[tick].mean(axis=1, skipna=True).fillna(0.0)
        lvl = np.concatenate([[100.0], 100.0 * np.cumprod(1 + m.to_numpy())])
        return [round(float(v), 2) for v in lvl]

    def group_out(mem):
        hist = strength_hist(mem)
        if not hist:
            return {}
        inp, sc, rk = hist[last]
        allidx = sorted(hist)
        idx = allidx[-hist_days:]
        tl_idx[:] = allidx
        out = {}
        for g in sc.index:
            prev = hist.get(last - 5)
            p4 = hist.get(last - 4)
            out[g] = {"strength": _r(sc[g], 1), "s_rank": int(rk[g]),
                      "s_mv5": (int(prev[2][g] - rk[g]) if prev is not None and g in prev[2].index else None),
                      "s_r_m4": (int(p4[2][g]) if p4 is not None and g in p4[2].index else None),
                      "s_trail": [(_r(hist[i][1].get(g), 0)) for i in idx],
                      "s_hist": [(_r(hist[i][1].get(g), 0)) for i in allidx],
                      "px": group_index(mem.get(g, [])),
                      "rel": _r(inp.loc[g, "rel"]), "part": _r(inp.loc[g, "part"], 3), "lead": _r(inp.loc[g, "lead"], 1)}
        return out

    g_themes, g_subs = group_out(members), group_out(sub_members)

    # ---- per-ticker fields for the tickers shown on the dashboard ----
    rlast = ratings.loc[dates[last]]
    r5 = ratings.loc[dates[last - 5]] if dates[last - 5] in ratings.index else None
    tick = {}
    for tk in focus:
        if tk not in c.columns or pd.isna(c.iloc[last][tk]):
            continue
        tick[tk] = {
            "rsr": _r(rlast.get(tk), 0), "rsr5": (_r(rlast.get(tk) - r5.get(tk), 0) if r5 is not None else None),
            "rsraw": _r(raw.iloc[last][tk]),
            "rs_nh": bool(nh.iloc[last][tk]) if nh is not None and not pd.isna(nh.iloc[last][tk]) else False,
            "rs_lead": bool(lead.iloc[last][tk]) if lead is not None and not pd.isna(lead.iloc[last][tk]) else False,
            "adr": _r(t["adr"].iloc[last][tk], 2), "tight": _r(t["tight5"].iloc[last][tk], 2),
            "nr7": bool(t["nr7"].iloc[last][tk]), "inside": bool(t["inside"].iloc[last][tk]),
            "vdry": _r(t["vdry"].iloc[last][tk], 2), "off_hi": _r(t["off_high"].iloc[last][tk]),
            "v50": _r(t["vol50"].iloc[last][tk], 0), "v1": _r(w["v"].iloc[last][tk], 0),
        }

    # ---- setup lists (whole market, latest session; EPs over the last 5) ----
    burst, checks, lynch, ep = SU.masks(w, t, liquid)
    rating_full = ratings.reindex(index=c.index, columns=c.columns)
    ant = SU.anticipation_mask(w, t, rating_full, liquid)
    dollar = c * t["vol50"]

    def row(tk, i, extra):
        return {"t": tk, "name": names.get(tk, ""), "price": _r(c.iloc[i][tk], 2), "chg": _r(t["chg"].iloc[i][tk]),
                "rsr": _r(rating_full.iloc[i].get(tk), 0), "adr": _r(t["adr"].iloc[i][tk], 2),
                "tight": _r(t["tight5"].iloc[i][tk], 2), "vdry": _r(t["vdry"].iloc[i][tk], 2),
                "off_hi": _r(t["off_high"].iloc[i][tk]), "dvol": _r(dollar.iloc[i][tk] / 1e6, 1),
                "vx": _r(w["v"].iloc[i][tk] / t["vol50"].iloc[i][tk], 1), **extra}

    bl = []
    for tk in c.columns[burst.iloc[last].fillna(False).values]:
        ck = {k: bool(m.iloc[last][tk]) for k, m in checks.items()}
        bl.append(row(tk, last, {"lynch": int(sum(ck.values())), "checks": ck}))
    bl.sort(key=lambda r: (-r["lynch"], -(r["rsr"] or 0), -(r["vx"] or 0)))

    al = [row(tk, last, {"nr7": bool(t["nr7"].iloc[last][tk]), "inside": bool(t["inside"].iloc[last][tk])})
          for tk in c.columns[ant.iloc[last].fillna(False).values]]
    for r in al:   # tighter, quieter, stronger, closer to highs first
        r["_k"] = (r["tight"] or 9) + 2 * (r["vdry"] or 2) - (r["rsr"] or 0) / 25 - 5 * (r["off_hi"] or -1)
    al.sort(key=lambda r: r["_k"])
    for r in al:
        r.pop("_k")

    el = []
    for i in range(max(0, last - 4), N):
        for tk in c.columns[ep.iloc[i].fillna(False).values]:
            el.append(row(tk, i, {"date": dates[i].strftime("%Y-%m-%d"), "gap": _r(t["gap"].iloc[i][tk]),
                                   "since": _r(c.iloc[last][tk] / c.iloc[i][tk] - 1), "days": int(last - i)}))
    el.sort(key=lambda r: (r["days"], -(r["gap"] or 0)))

    # strongest stocks in the whole market, theme or not: 60% RS Rating + 40% closeness to the high
    from . import leaders as _LD
    sl = []
    rl = rating_full.iloc[last]
    okm = liquid.iloc[last] & (c.iloc[last] >= 10) & (dollar.iloc[last] >= 20e6) & (rl >= 90)
    for tk in c.columns[okm.fillna(False).values]:
        offh = t["off_high"].iloc[last][tk]
        sc = 0.6 * float(rl[tk]) + 0.4 * _LD.high_score(None if pd.isna(offh) else float(offh))
        sl.append(row(tk, last, {"score": round(sc, 1), "d60": _r(t["d60"].iloc[last][tk]),
                                 "d5": _r(c.iloc[last][tk] / c.iloc[last - 5][tk] - 1),
                                 "d20": _r(c.iloc[last][tk] / c.iloc[last - 20][tk] - 1),
                                 "e50": _r(c.iloc[last][tk] / ema50.iloc[last][tk] - 1),
                                 "star": bool(nh.iloc[last][tk]) if nh is not None and not pd.isna(nh.iloc[last][tk]) else False}))
    sl.sort(key=lambda r: (-r["score"], -(r["d60"] or 0)))

    # mega caps ($200B+ Google market cap from the close snapshot), same score, no RS floor
    ml = []
    caps = mega_caps()
    for tk in c.columns:
        cap = caps.get(tk.replace("-", ".")) or caps.get(tk)
        if not cap or cap < config.MEGA_CAP or not bool(liquid.iloc[last].get(tk, False)) or pd.isna(rl.get(tk)):
            continue
        offh = t["off_high"].iloc[last][tk]
        sc = 0.6 * float(rl[tk]) + 0.4 * _LD.high_score(None if pd.isna(offh) else float(offh))
        ml.append(row(tk, last, {"score": round(sc, 1), "cap": round(cap / 1e9), "d60": _r(t["d60"].iloc[last][tk]),
                                 "d5": _r(c.iloc[last][tk] / c.iloc[last - 5][tk] - 1),
                                 "d20": _r(c.iloc[last][tk] / c.iloc[last - 20][tk] - 1),
                                 "e50": _r(c.iloc[last][tk] / ema50.iloc[last][tk] - 1),
                                 "star": bool(nh.iloc[last][tk]) if nh is not None and not pd.isna(nh.iloc[last][tk]) else False}))
    ml.sort(key=lambda r: (-r["score"], -(r["d60"] or 0)))

    # historical results of each list by breadth regime (how these trades did)
    stats = None
    try:
        from . import store as _store
        br = _store.load_breadth()
        if len(br):
            stats = SU.regime_stats(w, t, rating_full, liquid, br)
    except Exception:
        stats = None
    vcp_live = None
    try:
        from . import tradesetups as TS
        vcp_live = TS.vcp_today(w, t, sorted(set(focus) & set(universe)))
    except Exception as e:
        import logging
        logging.getLogger("breadth").exception("vcp screen failed: %s", e)
    trade_bt = None
    try:
        from . import store as _store
        from . import tradesetups as TS
        br = _store.load_breadth()
        if len(br):
            trade_bt = TS.backtest(w, t, ratings, liquid, members, sub_members,
                                   sorted(set(focus) & set(universe)), br)
    except Exception as e:
        import logging
        logging.getLogger("breadth").exception("trade setup backtest failed: %s", e)
    reg = None
    try:
        from . import store as _store
        b_ = _store.load_breadth().iloc[-1]
        reg = "strong" if b_["ratio5"] >= 1.5 and b_["ratio10"] >= 1.5 else "weak" if b_["ratio10"] < 1 else "mixed"
    except Exception:
        pass

    hve_out = None
    try:
        from . import hve as HV, store as _store
        th_of = {}
        for g, tk in members.items():
            for x in tk:
                th_of.setdefault(x, {})["theme"] = th_of.get(x, {}).get("theme") or g
        for g, tk in sub_members.items():
            for x in tk:
                th_of.setdefault(x, {})["sub"] = g
        br = _store.load_breadth()
        hve_reg = None
        if len(br):
            br = br[br["complete"]]
            hve_reg = pd.Series("mixed", index=br.index)
            hve_reg[(br["ratio5"] >= 1.5) & (br["ratio10"] >= 1.5)] = "strong"
            hve_reg[br["ratio10"] < 1] = "weak"
        hve_out = HV.screen(w, rating_full, universe, names, theme_of=th_of, regimes=hve_reg)
    except Exception as e:
        import logging
        logging.getLogger("breadth").exception("record volume screen failed: %s", e)
    tl_dates = [dates[i].strftime("%Y-%m-%d") for i in tl_idx]
    px_dates = [d.strftime("%Y-%m-%d") for d in dates[-PAIR_DAYS:]]
    return {"hve": hve_out, "timeline_dates": tl_dates, "px_dates": px_dates, "tickers": tick, "themes": g_themes, "subthemes": g_subs, "setup_stats": stats, "regime_now": reg, "trade_bt": trade_bt, "vcp": vcp_live,
            "rs_bp": [_r(x, 5) for x in (bps.get(last) if bps.get(last) is not None else [])],
            "lists": {"bursts": bl[:80], "anticipation": al[:60], "eps": el[:60], "strongest": sl[:40], "mega": ml,
                      "counts": {"bursts": len(bl), "anticipation": len(al), "eps": len(el), "strongest": len(sl), "mega": len(ml)}}}
