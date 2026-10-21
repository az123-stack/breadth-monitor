"""Strength on Weakness (Adam, Oct 21 2026): weekly position trades out of a stage-1 base.

Adam's write-up (charts: NRIX, APPN, AMPL, MTCH):
  1. Base: 6-24+ months sideways, 50-week EMA flat or curling up, price trading around it.
  2. Pre-thrust test: 2-3 "pumps" that clear the 50 WEMA.
  3. Re-anchor ("black box"): after the first thrust the stock does NOT sell off hard; it rests
     sideways right on the rising 9 / 21-week EMA ribbon.
  4. Trigger: a weekly close above the 8-12 week high on expanding volume, stack price > 9 > 21 > 50.
  5. Entry (his actual buy): once it rides the 9/21 up, buy when it nuzzles back into them and
     take the next pop.

Code rules (weekly bars built from our split-adjusted daily bars; week = Mon-Fri, labelled by its
last session; the current week counts as it stands, volume paced to a full week):
  liquid    close >= $5 and >= $10M a day (20-day average)
  stack     EMA9 > EMA21 > EMA50 and EMA9 above where it was 4 weeks ago (curling up)
  flat50    EMA50 >= 99% of its value 13 weeks ago (flat or rising)
  base      2+ closes crossing up through the 50 WEMA in the last 52 weeks (the pumps) AND 20%+ of
            those 52 weekly closes under the 50 WEMA (it really was basing, not a year-long uptrend)
  anchor    over the last 10 weeks a low came within 3% of the 21 WEMA and no close fell 5%+ under it
  tight     the last 10 weeks' range (before this week) <= 3 weekly ATRs
  breakout  close above the prior 10-week high on 1.2x+ the 20-week average volume
  nuzzle    weekly low within 2% of the 9 WEMA (or below it) while the close holds 98% of the 21 WEMA
  pop       the week after a nuzzle closes above the nuzzle week's high

States today: breakout (this or last week) > pop (this or last week) > nuzzle (buy zone: buy above
this week's high) > riding (stacked, between the EMAs and 1.5 ATR above the 9) > extended (wait).
Riding / extended / nuzzle / pop need a 10-week-high close in the last 26 weeks (the first thrust).

Evidence (`evidence`): every breakout and pop since the 50 WEMA had a year of data, bought at the
NEXT session's open, held 13 and 26 weeks, vs the average liquid stock bought the same day
(and vs SPY). Per-date averages so busy weeks don't dominate; halves split by date.
Our bars reach ~2 years (Massive free plan), so only ~1 year of signals is testable.
"""
import numpy as np
import pandas as pd

CFG = {"min_price": 5.0, "min_dvol": 10e6, "e_fast": 9, "e_mid": 21, "e_slow": 50, "curl": 4, "flat_wk": 13, "flat": 0.99,
       "pump_wk": 78, "pumps": 2, "below_wk": 10, "min_rs": 70, "anchor_wk": 10, "anchor_touch": 0.03, "anchor_hold": 0.95,
       "box_wk": 10, "tight_atr": 3.0, "atr_wk": 10, "vol_wk": 20, "vol_x": 1.2, "nuzzle": 0.02, "hold21": 0.98,
       "thrust_wk": 26, "ext_atr": 1.5, "warm": 52, "holds": (13, 26), "spark": 78, "spark_rows": 25}
STATES = [("breakout", "Breakout", "Closed above the black box (prior 10-week high) on 1.2× normal volume, stacked 9 > 21 > 50."),
          ("pop", "Pop", "Nuzzled into the 9/21 WEMA last week and popped back over that week's high: Adam's entry."),
          ("nuzzle", "Nuzzling (buy zone)", "Pulled into the 9 WEMA this week, holding the 21. Buy a pop over this week's high; stop under this week's low."),
          ("riding", "Riding the 9/21", "Stacked and rising, close to the EMAs. Wait for it to nuzzle in."),
          ("extended", "Extended", "More than 1.5 weekly ATRs above the 9 WEMA. Don't chase; wait for the nuzzle.")]


def _r(x, n=2):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def weekly(w, cols):
    """Weekly OHLCV frames (index = the week's last session) from the daily wide frames."""
    c = w["c"][cols]
    wk = c.index.to_period("W-FRI")
    agg = {"o": w["o"][cols].groupby(wk).first(), "h": w["h"][cols].groupby(wk).max(), "l": w["l"][cols].groupby(wk).min(),
           "c": c.groupby(wk).last(), "v": w["v"][cols].groupby(wk).sum(min_count=1)}
    last = pd.Series(c.index, index=c.index).groupby(wk).max()
    n = pd.Series(1, index=c.index).groupby(wk).sum()
    idx = pd.DatetimeIndex(last.values)
    for k in agg:
        agg[k].index = idx
    return agg, pd.Series(n.values, index=idx)


def complete_weeks(days_per_week, last_date):
    """True for weeks that are finished (the next session falls in a later week)."""
    from . import nyse
    done = np.ones(len(days_per_week), bool)
    try:
        nxt = pd.Timestamp(nyse.next_session(pd.Timestamp(last_date).date()))
        done[-1] = nxt.to_period("W-FRI") != pd.Timestamp(last_date).to_period("W-FRI")
    except Exception:
        done[-1] = days_per_week.iloc[-1] >= 5
    return done


def features(W, dvol, nday=None, rs=None):
    """Every rule as a weeks x stocks boolean / float frame. `nday` = sessions in each week (volume pace)."""
    P = CFG
    c, h, l, v = W["c"], W["h"], W["l"], W["v"]
    ema = lambda n: c.ewm(span=n, adjust=False, min_periods=1).mean()
    e9, e21, e50 = ema(P["e_fast"]), ema(P["e_mid"]), ema(P["e_slow"])
    pc = c.shift()
    tr = np.maximum(h - l, np.maximum((h - pc).abs(), (l - pc).abs()))
    atr = (tr / c).rolling(P["atr_wk"], min_periods=6).mean()
    vpace = v if nday is None else v.mul(5 / nday.clip(lower=1), axis=0)
    v20 = v.shift().rolling(P["vol_wk"], min_periods=10).mean()
    hi10 = h.shift().rolling(P["box_wk"], min_periods=6).max()
    lo10 = l.shift().rolling(P["box_wk"], min_periods=6).min()
    up50 = ((c > e50) & (pc <= e50.shift())).astype(float)
    pumps = up50.rolling(P["pump_wk"], min_periods=26).sum()
    below = (c < e50).astype(float).rolling(P["pump_wk"], min_periods=26).sum()
    liq = (c >= P["min_price"]) & (dvol.reindex(c.index, method="ffill")[c.columns] >= P["min_dvol"])
    stack = (e9 > e21) & (e21 > e50) & (e9 >= e9.shift(P["curl"]) * P["flat"]) & (e21 > e21.shift(P["curl"]))
    flat50 = e50 >= e50.shift(P["flat_wk"]) * P["flat"]
    base = (pumps >= P["pumps"]) & (below >= P["below_wk"])
    anchor = ((l / e21 - 1).rolling(P["anchor_wk"], min_periods=5).min() <= P["anchor_touch"]) & \
             ((c / e21).rolling(P["anchor_wk"], min_periods=5).min() >= P["anchor_hold"])
    tight = (hi10 / lo10 - 1) <= P["tight_atr"] * atr
    brk = c > hi10
    volx = vpace >= P["vol_x"] * v20
    strong = (rs >= P["min_rs"]) if rs is not None else pd.DataFrame(True, index=c.index, columns=c.columns)
    qual = liq & stack & flat50 & base & strong
    nuz = (l <= e9 * (1 + P["nuzzle"])) & (c >= e21 * P["hold21"])
    thrust = brk.astype(float).rolling(P["thrust_wk"], min_periods=1).max() > 0
    sig_brk = qual & anchor & tight & brk & volx
    sig_pop = (qual & thrust & nuz).shift(1, fill_value=False) & (c > h.shift()) & qual
    return {"e9": e9, "e21": e21, "e50": e50, "atr": atr, "v20": v20, "vpace": vpace, "hi10": hi10, "lo10": lo10, "pumps": pumps,
            "below": below, "liq": liq, "strong": strong, "stack": stack, "flat50": flat50, "base": base, "anchor": anchor, "tight": tight, "brk": brk,
            "volx": volx, "qual": qual, "nuz": nuz, "thrust": thrust, "breakout": sig_brk, "pop": sig_pop}


def _state(F, j, wi):
    """Today's state for stock column j at week wi (the latest week), or None."""
    g = lambda k, i=wi: bool(F[k].iat[i, j]) if i >= 0 else False
    for ago in (0, 1):
        if g("breakout", wi - ago):
            return "breakout", ago
    for ago in (0, 1):
        if g("pop", wi - ago):
            return "pop", ago
    if not (g("qual") and g("thrust")):
        return None, None
    if g("nuz"):
        return "nuzzle", 0
    c, e9, atr = F["_c"].iat[wi, j], F["e9"].iat[wi, j], F["atr"].iat[wi, j]
    if np.isfinite(atr) and c > e9 * (1 + CFG["ext_atr"] * atr):
        return "extended", 0
    return "riding", 0


def build(adjusted, universe, stocks=None, names=None, evidence=True):
    """Payload for DATA.themes.sow: today's rows + backtest evidence."""
    from . import config, strength
    names = names or {}
    info = {r["t"]: r for r in (stocks or [])}
    w = strength.wide_all(adjusted)
    uni = set(universe)
    cols = [t for t in w["c"].columns if t in uni]
    if len(w["c"].index) < 120 or not cols:
        return None
    dvol = (w["c"][cols] * w["v"][cols]).rolling(20, min_periods=15).mean()
    W, nday = weekly(w, cols)
    done = complete_weeks(nday, w["c"].index[-1])
    raw = strength.rs_raw(w["c"][cols])
    liqd = (w["c"][cols] >= 5) & (dvol >= 20e6)
    rsd = (raw.where(liqd).rank(axis=1, pct=True) * 99).clip(1, 99)
    rs_w = rsd.reindex(W["c"].index)                      # RS Rating at each week's last session
    rs = rsd.iloc[-1]
    F = features(W, dvol, nday, rs_w)
    F["_c"] = W["c"]
    wi = len(W["c"].index) - 1
    rows = []
    for j, t in enumerate(cols):
        if not bool(F["liq"].iat[wi, j]):
            continue
        st, ago = _state(F, j, wi)
        if not st:
            continue
        k = wi - (ago or 0)
        c, h, l = (W[x].iat[wi, j] for x in ("c", "h", "l"))
        e9, e21, e50, atr = (F[x].iat[wi, j] for x in ("e9", "e21", "e50", "atr"))
        hi10, lo10 = F["hi10"].iat[k, j], F["lo10"].iat[k, j]
        if st == "breakout":
            trig, stop = None, lo10
        elif st == "pop":
            trig, stop = None, W["l"].iat[k - 1, j]
        elif st == "nuzzle":
            trig, stop = h, l
        else:
            trig, stop = None, e21 * CFG["hold21"]
        s = info.get(t, {})
        n0 = max(0, wi - CFG["spark"] + 1)
        lo52 = np.nanmin(W["l"].iloc[max(0, wi - 52):wi + 1, j].to_numpy())
        hi52 = np.nanmax(W["h"].iloc[max(0, wi - 52):wi + 1, j].to_numpy())
        rows.append({
            "t": t, "name": s.get("name") or names.get(t, ""), "state": st, "ago": ago, "price": _r(c),
            "e9": _r(e9), "e21": _r(e21), "e50": _r(e50), "vs9": _r(c / e9 - 1, 4), "vs21": _r(c / e21 - 1, 4), "vs50": _r(c / e50 - 1, 4),
            "atr": _r(atr * 100, 1), "pumps": int(F["pumps"].iat[wi, j]) if np.isfinite(F["pumps"].iat[wi, j]) else None,
            "below": int(F["below"].iat[wi, j]) if np.isfinite(F["below"].iat[wi, j]) else None, "box_hi": _r(hi10), "box_lo": _r(lo10),
            "box_atr": _r((hi10 / lo10 - 1) / atr, 1) if np.isfinite(atr) and atr > 0 else None,
            "volx": _r(F["vpace"].iat[k, j] / F["v20"].iat[k, j], 2) if F["v20"].iat[k, j] else None,
            "trig": _r(trig), "stop": _r(stop), "risk": _r(1 - stop / (trig or c), 4) if stop and np.isfinite(stop) else None,
            "lo52": _r(lo52), "hi52": _r(hi52), "off_hi52": _r(c / hi52 - 1, 4),
            "rsr": s.get("rsr") if s.get("rsr") is not None else _r(rs.get(t), 0),
            "dvol": _r(dvol[t].iloc[-1] / 1e6, 0), "theme": (s.get("themes") or [None])[0], "sub": s.get("sub"),
            "wk": [_r(x) for x in W["c"].iloc[n0:, j]], "w9": [_r(x) for x in F["e9"].iloc[n0:, j]],
            "w21": [_r(x) for x in F["e21"].iloc[n0:, j]], "w50": [_r(x) for x in F["e50"].iloc[n0:, j]],
        })
    order = {k: i for i, (k, _, _) in enumerate(STATES)}
    rows.sort(key=lambda r: (order[r["state"]], r["ago"] or 0, -(r["rsr"] or 0)))
    seen = {}
    for r in rows:                                        # weekly mini chart only for the first rows of each state (page size)
        seen[r["state"]] = seen.get(r["state"], 0) + 1
        if seen[r["state"]] > CFG["spark_rows"]:
            for k in ("wk", "w9", "w21", "w50"):
                r.pop(k)
    out = {"date": w["c"].index[-1].strftime("%Y-%m-%d"), "week": W["c"].index[-1].strftime("%Y-%m-%d"),
           "week_done": bool(done[-1]), "week_days": int(nday.iloc[-1]), "rows": rows,
           "states": [{"key": k, "name": n, "desc": d, "n": sum(r["state"] == k for r in rows)} for k, n, d in STATES], "cfg": CFG}
    if evidence:
        try:
            ev = backtest(W, F, w, cols, done, config.BENCHMARK)
            ev["any_rs"] = {k: v for k, v in backtest(W, features(W, dvol, nday), w, cols, done, config.BENCHMARK).items()
                            if k in ("breakout", "pop")}  # same rules without the RS 70 floor
            out["evidence"] = ev
        except Exception as e:   # evidence is optional
            import logging
            logging.getLogger(__name__).exception("sow backtest failed: %s", e)
            out["evidence"] = None
    return out


def _stats(ex, dates, raw=None, spy=None):
    """ex: excess return per trade; summarised per signal week (dates) so busy weeks don't dominate."""
    if len(ex) < 5:
        return {"n": int(len(ex))}
    s = pd.Series(ex, index=pd.DatetimeIndex(dates))
    g = s.groupby(level=0).mean()
    nd = len(g)
    t = g.mean() / (g.std(ddof=1) / np.sqrt(nd)) if nd > 2 and g.std(ddof=1) > 0 else None
    mid = g.index[nd // 2]
    return {"n": int(len(ex)), "dates": int(nd), "ex": _r(g.mean(), 4), "ex_trade": _r(s.mean(), 4), "med": _r(float(np.median(ex)), 4),
            "win": _r(float(np.mean(np.asarray(ex) > 0)), 3), "t": _r(t, 2), "h1": _r(g[g.index < mid].mean(), 4),
            "h2": _r(g[g.index >= mid].mean(), 4), "ret": _r(float(np.mean(raw)), 4) if raw is not None else None,
            "vs_spy": _r(float(np.mean(spy)), 4) if spy is not None else None,
            "from": g.index[0].strftime("%Y-%m-%d"), "to": g.index[-1].strftime("%Y-%m-%d")}


def backtest(W, F, w, cols, done, bench="SPY"):
    """Signals (complete weeks after the warm-up) -> next session's open -> close 13 / 26 weeks later."""
    P = CFG
    wd = W["c"].index
    days = w["c"].index
    DO = w["o"][cols].to_numpy()
    WC = W["c"].to_numpy()
    spy_o = spy_wc = None
    if bench in w["c"]:
        spy_o = w["o"][bench].to_numpy()
        spy_wc = w["c"][bench].groupby(days.to_period("W-FRI")).last().to_numpy()   # same week order as W
    liq = F["liq"].to_numpy()
    strong = (F["liq"] & F["strong"]).to_numpy()
    nW = len(wd)
    ent_i = days.searchsorted(wd, side="right")          # next session after each week's close
    out = {"holds": list(P["holds"]), "warm": P["warm"]}
    for key in ("breakout", "pop"):
        S = F[key].to_numpy().copy()
        S[:P["warm"]] = False
        S[~done] = False
        res = {}
        for n in P["holds"]:
            ex, dt, raw, sp, exs = [], [], [], [], []
            for i in range(nW - n):
                if ent_i[i] >= len(days):
                    continue
                js = np.flatnonzero(S[i])
                if not len(js):
                    continue
                ent = DO[ent_i[i]]
                fwd = WC[i + n] / ent - 1
                m = liq[i] & np.isfinite(fwd)
                if m.sum() < 50:
                    continue
                base = float(np.mean(np.clip(fwd[m], -0.95, 5)))
                ms = strong[i] & np.isfinite(fwd)
                base_s = float(np.mean(np.clip(fwd[ms], -0.95, 5))) if ms.sum() >= 20 else np.nan
                s_ret = (spy_wc[i + n] / spy_o[ent_i[i]] - 1) if spy_o is not None and spy_wc is not None else np.nan
                for j in js:
                    if np.isfinite(fwd[j]):
                        r = float(np.clip(fwd[j], -0.95, 5))
                        ex.append(r - base); dt.append(wd[i]); raw.append(r); sp.append(r - s_ret); exs.append(r - base_s)
            res[f"w{n}"] = _stats(ex, dt, raw, sp)
            ok = np.isfinite(exs)
            res[f"w{n}"]["vs_strong"] = _stats(list(np.asarray(exs)[ok]), list(np.asarray(dt, dtype=object)[ok]))
        out[key] = res
    return out
